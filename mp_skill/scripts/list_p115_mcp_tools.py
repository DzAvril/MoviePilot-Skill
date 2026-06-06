#!/usr/bin/env python3
"""List tools exposed by P115StrmHelper's MCP SSE endpoint.

Reads MoviePilot host/API key from ~/.config/mp_skill/config or env:
MP_HOST/MOVIEPILOT_URL and MP_API_KEY. Never prints credentials.
"""
import json
import os
import queue
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def load_config():
    cfg = Path.home() / ".config" / "mp_skill" / "config"
    host = os.environ.get("MP_HOST") or os.environ.get("MOVIEPILOT_URL")
    key = os.environ.get("MP_API_KEY")
    if cfg.exists():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k in ("MP_HOST", "MOVIEPILOT_URL") and not host:
                host = v
            elif k == "MP_API_KEY" and not key:
                key = v
    if not host or not key:
        raise SystemExit("Missing MP_HOST/MOVIEPILOT_URL or MP_API_KEY")
    return host.rstrip("/"), key


def http_post_json(url, key, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode("utf-8", "replace")[:1000]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:1000]


def main():
    host, key = load_config()
    sse_url = f"{host}/api/v1/plugin/P115StrmHelper/mcp/sse"
    q = queue.Queue()
    stop = threading.Event()

    def reader():
        try:
            req = urllib.request.Request(
                sse_url, headers={"X-API-KEY": key, "Accept": "text/event-stream"}
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                q.put(("status", r.status, r.headers.get("content-type")))
                event = "message"
                data = []
                while not stop.is_set():
                    raw = r.readline()
                    if not raw:
                        break
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    if line == "":
                        if data:
                            q.put(("event", event, "\n".join(data)))
                        event = "message"
                        data = []
                    elif line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data.append(line[5:].strip())
        except urllib.error.HTTPError as e:
            q.put(("http_error", e.code, e.read().decode("utf-8", "replace")[:1000]))
        except Exception as e:  # noqa: BLE001 - diagnostic script
            q.put(("exception", repr(e)))

    th = threading.Thread(target=reader, daemon=True)
    th.start()
    endpoint = None
    status = None
    start = time.time()
    while time.time() - start < 15:
        try:
            item = q.get(timeout=1)
        except queue.Empty:
            continue
        if item[0] == "status":
            status = item
        elif item[0] == "event" and item[1] == "endpoint":
            endpoint = item[2]
            break
        elif item[0] in ("http_error", "exception"):
            print(json.dumps({"status": status, "error": item}, ensure_ascii=False))
            return 1
    if not endpoint:
        print(json.dumps({"status": status, "error": "no endpoint event"}, ensure_ascii=False))
        return 1

    msg_url = urllib.parse.urljoin(host, endpoint)

    def post(method, params=None, id_=1, wait=True):
        payload = {"jsonrpc": "2.0", "method": method}
        if id_ is not None:
            payload["id"] = id_
        if params is not None:
            payload["params"] = params
        code, body = http_post_json(msg_url, key, payload)
        got = []
        if not wait:
            return code, body, got
        t = time.time()
        while time.time() - t < 20:
            try:
                item = q.get(timeout=1)
            except queue.Empty:
                continue
            if item[0] == "event" and item[1] == "message":
                try:
                    obj = json.loads(item[2])
                except Exception:
                    obj = {"raw": item[2]}
                got.append(obj)
                if obj.get("id") == id_:
                    return code, body, got
        return code, body, got

    init_params = {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "moviepilot-skill-probe", "version": "0.1"},
    }
    post("initialize", init_params, 1)
    # Some plugin servers may return Method not found for this notification; tools/list still works.
    post("notifications/initialized", None, None, wait=False)
    _, _, tools_msgs = post("tools/list", {}, 2)
    stop.set()

    for msg in tools_msgs:
        if "result" in msg:
            print(json.dumps(msg["result"].get("tools", []), ensure_ascii=False, indent=2))
            return 0
    print(json.dumps({"error": "tools/list did not return a result", "messages": tools_msgs}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
