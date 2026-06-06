# MCP Server SSE Priming Event Regression

Use this note when fixing or verifying MoviePilot `MCPServer` Streamable HTTP / SSE initialization issues, especially logs like:

```text
mcp.server.streamable_http - ERROR - Error in SSE writer
AttributeError: 'NoneType' object has no attribute 'root'
```

## Root cause

Newer MCP Python SDKs can create a resumability priming event during Streamable HTTP initialization:

```python
await event_store.store_event(str(request_id), None)
```

The priming event intentionally has no JSON-RPC payload. MoviePilot-Plugins `plugins.v2/mcpserver/event_store.py` previously assumed every stored message was a `JSONRPCMessage` and called:

```python
message.root.model_dump()
```

When `message is None`, LobeChat / MCP client connection tests can time out while MoviePilot logs the `NoneType.root` exception.

## Correct fix pattern

Patch both event stores, not only SQLite:

- Accept `JSONRPCMessage | None` in `EventEntry.message` and `store_event` signatures.
- In `SQLiteEventStore._serialize_message`, serialize `None` as `json.dumps(None)`.
- In `_deserialize_message`, return `None` when the stored JSON is `null`.
- During replay, skip `None` messages; priming events are SSE id anchors and should not be emitted as application JSON-RPC messages.
- In `InMemoryEventStore.replay_events_after`, skip entries whose `event.message is None`.

Minimal SQLite logic:

```python
def _serialize_message(self, message: JSONRPCMessage | None) -> str:
    if message is None:
        return json.dumps(None)
    message_dict = message.root.model_dump()
    return json.dumps(message_dict)

def _deserialize_message(self, message_str: str) -> JSONRPCMessage | None:
    message_dict = json.loads(message_str)
    if message_dict is None:
        return None
    return JSONRPCMessage.model_validate(message_dict)
```

## Versioning

`MCPServer` is a v2 plugin under `plugins.v2/mcpserver`, so bump both:

- `plugins.v2/mcpserver/__init__.py`: `plugin_version`
- `package.v2.json`: `MCPServer.version` and matching `history` entry

## Local verification recipe

1. Static checks:

```bash
python3 -m py_compile $(find plugins.v2/mcpserver -name '*.py' -not -path '*/venv/*')
python3 -m json.tool package.v2.json >/tmp/package.v2.validated.json
```

2. Regression test without installing MCP by stubbing the few imported MCP symbols and loading `event_store.py` via `importlib.util.spec_from_file_location`. Verify:

- `await SQLiteEventStore(...).store_event('stream', None)` does not raise.
- SQLite stores the message as `null`.
- `_deserialize_message('null') is None`.
- replay after a priming event skips the `None` payload and still sends later real events.
- repeat the replay-skip check for `InMemoryEventStore`.

3. Deploy pre-commit patch to live MoviePilot only after backing up actual plugin files:

```bash
TS=$(date +%Y%m%d%H%M%S)
docker exec MoviePilot sh -lc "cp /app/app/plugins/mcpserver/event_store.py /config/temp/mcpserver_event_store.py.$TS.bak && cp /app/app/plugins/mcpserver/__init__.py /config/temp/mcpserver___init__.py.$TS.bak"
docker cp plugins.v2/mcpserver/event_store.py MoviePilot:/app/app/plugins/mcpserver/event_store.py
docker cp plugins.v2/mcpserver/__init__.py MoviePilot:/app/app/plugins/mcpserver/__init__.py
docker exec MoviePilot sh -lc 'python -m py_compile /app/app/plugins/mcpserver/event_store.py /app/app/plugins/mcpserver/__init__.py'
```

4. Reload/start the plugin through MoviePilot APIs. If the plugin's venv exists but dependencies are missing, `_ensure_venv()` may not reinstall dependencies because it only installs on venv creation; running the venv pip install can be needed before start:

```bash
docker exec MoviePilot sh -lc '/app/app/plugins/mcpserver/venv/bin/python -m pip install --upgrade -i https://mirrors.aliyun.com/pypi/simple/ "mcp[cli]"'
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py POST /api/v1/plugin/MCPServer/start --compact --raw-out /tmp/mcp_start.json
```

Do not print token-bearing config/status responses; if parsed, redact/drop `auth_token`, `access_token`, and similar keys before summarizing.

5. End-to-end Streamable HTTP proof (when auth is disabled by current config or a safe token can be read without printing):

```bash
python3 - <<'PY'
import json, urllib.request
payload=json.dumps({
  "jsonrpc":"2.0","id":1,"method":"initialize",
  "params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"hermes-regression","version":"0.1"}}
}).encode()
req=urllib.request.Request(
  "http://172.17.0.1:3111/mcp/", data=payload,
  headers={"Content-Type":"application/json", "Accept":"application/json, text/event-stream", "MCP-Protocol-Version":"2025-11-25"},
  method="POST")
with urllib.request.urlopen(req, timeout=10) as r:
  body=r.read(4096).decode('utf-8','replace')
  print(r.status, r.headers.get('content-type'))
  print(body[:300])
PY
```

Expected: HTTP 200, `text/event-stream`, an initial empty `data:` priming event, and an initialize result. Then inspect sanitized MoviePilot logs and confirm no `Error in SSE writer` / `NoneType.root` traceback appears.

## Issue follow-up

For fixed GitHub issues, comment with commit link and verification summary, remove stale labels, add `resolved`, and close with `state_reason: completed`.