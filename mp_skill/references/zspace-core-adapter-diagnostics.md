# MoviePilot ZSpace/极影视 core adapter diagnostics

Use this note when MoviePilot's built-in `app/modules/zspace/zspace.py` fails against a ZSpace/极影视 media server with errors like `Users/AuthenticateByName 未获取到返回数据`, `System/Info 未获取到返回数据`, or `Library/SelectableMediaFolders 未获取到返回数据`.

## Safe diagnostic workflow

1. Read the configured media servers through MoviePilot instead of printing secrets:
   - API: `GET /api/v1/system/setting/MediaServers`
   - Redact `config.password`, API keys, cookies, and tokens before displaying.
2. Confirm the server list via `GET /api/v1/mediaserver/clients`.
3. Reproduce auth from inside the MoviePilot container using the stored config, but only print booleans/lengths:
   - Login path may be `/emby/Users/AuthenticateByName` rather than `/Users/AuthenticateByName`.
   - Header should include an Emby-style `X-Emby-Authorization` value plus JSON body `{"Username": ..., "Pw": ...}`.
4. Probe follow-up endpoints using the returned token in headers, not just query params:
   - `X-Emby-Token: <token>`
   - `X-MediaBrowser-Token: <token>`
5. Check endpoint quirks before patching:
   - Some ZSpace deployments return `401` for `?api_key=<token>` even after successful login.
   - Some return `400` for `/emby/Users/Me`, while `/emby/Users/{user_id}` works.
   - Some return `404` for `/emby/Library/SelectableMediaFolders` and `/emby/Library/VirtualFolders/Query`; do not assume a token fix will make library-folder sync work.

## Patch/verification cautions

- Do not patch `zspace.py` in-place without a backup under `/config/` and `python -m py_compile` verification.
- Avoid restart loops: if a code patch causes MoviePilot API requests to hang or nginx to return 502, restore the backup before continuing.
- MoviePilot startup can be blocked by plugin dependency reinitialization after failed dependency install. If logs show `安装依赖项时发生错误` followed by `正在重新初始化插件` and plugin stop hangs, investigate that separately instead of blaming the ZSpace patch.
- Treat `Library/SelectableMediaFolders` 404 as a server capability/endpoint mismatch, not necessarily an auth failure.

## Minimal secret-safe probe pattern

```python
# Run inside the MoviePilot container with /opt/venv/bin/python.
from app.db.systemconfig_oper import SystemConfigOper
from app.schemas.types import SystemConfigKey
import json, urllib.request

item = [c for c in SystemConfigOper().get(SystemConfigKey.MediaServers) if c.get('type') == 'zspace'][0]
cfg = item['config']
base = cfg['host'].rstrip('/') + '/emby'
body = json.dumps({'Username': cfg['username'], 'Pw': cfg['password']}).encode()
req = urllib.request.Request(
    base + '/Users/AuthenticateByName',
    data=body,
    headers={
        'Content-Type': 'application/json',
        'X-Emby-Authorization': 'MediaBrowser Client="MoviePilot", Device="requests", DeviceId="1", Version="1.0.0"',
    },
    method='POST',
)
with urllib.request.urlopen(req, timeout=15) as r:
    obj = json.load(r)
print({'auth_ok': bool(obj.get('AccessToken')), 'user_id_len': len(obj.get('User', {}).get('Id', ''))})

token = obj['AccessToken']
uid = obj['User']['Id']
headers = {'X-Emby-Token': token, 'X-MediaBrowser-Token': token}
for endpoint in ['/System/Info', f'/Users/{uid}', '/Users/Me', '/Library/SelectableMediaFolders']:
    try:
        with urllib.request.urlopen(urllib.request.Request(base + endpoint, headers=headers), timeout=15) as r:
            print(endpoint, r.status)
    except Exception as e:
        print(endpoint, type(e).__name__, str(e).splitlines()[0][:120])
```
