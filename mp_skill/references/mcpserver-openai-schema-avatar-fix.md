# MCPServer OpenAI schema + base64 avatar response fix

Use this reference when fixing or verifying MoviePilot `plugins.v2/mcpserver` issues where OpenAI-compatible MCP clients fail because tool schemas or tool responses are too large/strict.

## Context

GitHub issue: `DzAvril/MoviePilot-Plugins#17`.

The MCPServer plugin exposes built-in tools to MCP/OpenAI-compatible clients. Two classes of problems can break downstream clients:

1. Tool schemas that are valid-ish JSON Schema for generic MCP clients but rejected by OpenAI function-schema validators.
2. Tool responses that include huge inline payloads, especially user avatars encoded as `data:image/...;base64,...`, which can exceed model/client token or payload limits.

## Fix pattern

- Keep MCP tool input schemas conservative for OpenAI compatibility: avoid unsupported composition/ambiguous constructs where possible and regression-test every built-in tool schema.
- In user-info style tools, do not return custom avatar `data:image/...;base64,...` values verbatim.
  - Preserve normal `http://` or `https://` avatar URLs.
  - Replace/trim inline base64 avatar fields with a compact marker or omit the payload while retaining useful metadata.
- Bump both:
  - `plugins.v2/mcpserver/__init__.py` `plugin_version`
  - `package.v2.json` MCPServer package metadata/history

## Regression recipe

From the plugin repository root:

```bash
python3 tests/mcpserver_openai_schema_user_info_regression.py
python3 -m py_compile \
  plugins.v2/mcpserver/tools/user/info.py \
  plugins.v2/mcpserver/tools/database/pt_stats.py \
  plugins.v2/mcpserver/__init__.py \
  tests/mcpserver_openai_schema_user_info_regression.py
python3 -m json.tool package.v2.json >/dev/null
git diff --check
```

The regression script should be standalone enough to run without a full MoviePilot runtime by using import stubs/fixtures. It should cover:

- all MCPServer built-in tool schemas that the plugin registers;
- OpenAI-compatible schema conversion/validation behavior;
- user info formatting with a large base64 avatar, asserting the output does not contain the large base64 payload;
- normal URL avatars, asserting `http(s)` URLs remain available.

## Live MoviePilot verification

After commit/push or manual copy into the running container, verify the live service rather than trusting GitHub metadata alone:

1. Back up existing container files before overwriting live plugin files.
2. Copy changed plugin files into the active MoviePilot plugin path, usually `/app/app/plugins/mcpserver/...` for built-in/online plugin code on this instance.
3. Run container-side compile checks:

```bash
docker exec MoviePilot python -m py_compile \
  /app/app/plugins/mcpserver/__init__.py \
  /app/app/plugins/mcpserver/tools/user/info.py \
  /app/app/plugins/mcpserver/tools/database/pt_stats.py
```

4. Reload via MoviePilot API:

```bash
python3 scripts/mp_request.py POST /api/v1/plugin/PluginManagerVue/reload --json '{"plugin_id":"MCPServer"}'
```

5. Read back plugin state with `PluginManagerVue/last_reload` and/or `PluginManagerVue/plugins`; confirm `status=running`, expected `version`, and `has_update=false` when applicable.

## Pitfalls

- Do not close the issue based only on a GitHub push. Verify runtime plugin state through MoviePilot API if the user expects end-to-end plugin bug fixing.
- Do not print API keys, GitHub tokens, MoviePilot API keys, torrent URLs, or other secrets from config/API responses.
- `gh` may fail or be unauthenticated in this environment; GitHub REST with an out-of-band token is a valid fallback, but never echo the token.
- If only one of `plugin_version` or `package.v2.json` is bumped, MoviePilot may not detect/display the update correctly.
