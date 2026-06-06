# MoviePilot Plugin Runtime Diagnostics

Use this note when a MoviePilot plugin is installed and the user asks why it is failing at runtime (logs, schedules, API calls, sync jobs), especially when the failure may involve third-party credentials.

## Workflow

1. Verify MoviePilot connectivity with the token-safe helper:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/user/current --compact
   ```
2. Identify plugin ID and container name:
   ```bash
   docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -i -E 'movie|pilot'
   python3 scripts/mp_request.py GET /api/v1/plugin/installed --compact --raw-out /tmp/mp_installed_plugins.json
   ```
3. Inspect plugin-specific logs first; they may contain clearer context than `docker logs`:
   ```bash
   docker exec -i MoviePilot sh -lc 'ls -lah /config/logs/plugins || true'
   docker exec -i MoviePilot python - <<'PY'
   from pathlib import Path
   p=Path('/config/logs/plugins/<plugin_id_lower>.log')
   print('exists', p.exists(), 'size', p.stat().st_size if p.exists() else None)
   if p.exists():
       for i,l in enumerate(p.read_text(encoding='utf-8',errors='ignore').splitlines()[-200:], 1):
           print(f'{i}: {l[:800]}')
   PY
   ```
4. If the plugin config is needed, read it from `/config/user.db` but never print secrets. Most plugin configs are stored in `systemconfig.key = 'plugin.<PluginId>'`:
   ```bash
   docker exec -i MoviePilot python - <<'PY'
   import sqlite3,json,re
   con=sqlite3.connect('/config/user.db'); con.row_factory=sqlite3.Row
   row=con.execute("select value from systemconfig where key='plugin.<PluginId>'").fetchone()
   cfg=json.loads(row['value']) if row else {}
   red={k: ('***' if any(s in k.lower() for s in ['cookie','token','password','key','secret','authorization']) else v) for k,v in cfg.items()}
   print(json.dumps(red, ensure_ascii=False, indent=2))
   PY
   ```
5. For third-party sync failures, reproduce the exact failing HTTP operation with sanitized output: status code, content type, redirect target, and a redacted response snippet. Do not paste cookies/tokens or raw request headers.
6. Interpret repeated scheduled failures by correlating the cron time, plugin log context, and API response. If a third-party endpoint returns auth/permission errors, label it as credential/auth failure rather than a media/resource failure.

## ZvideoHelper / 极影视助手 + Douban “标记在看失败”

For `ZvideoHelper` logs like:

```text
title: <name>, douban_id: <id>，标记在看失败
```

Observed root-cause pattern: the plugin may successfully map titles to Douban IDs but fail when POSTing to Douban's interest endpoint because the configured Douban cookie is no longer logged in or is forbidden.

Verification recipe:

1. Confirm `plugin.ZvideoHelper` has `sync_douban_status: true`; redact the `cookie` field.
2. Inspect `/config/logs/plugins/zvideohelper.log` around the failure. Look for repeated daily cron failures around `0 0 * * *` and matched `douban_id` lines.
3. Test login state without printing cookies:
   - `GET https://www.douban.com/mine/` with the configured cookie.
   - If it returns `302` to `/accounts/login`, the cookie is not accepted as a logged-in session.
4. Test the mark-watching endpoint with redacted output only:
   - `POST https://movie.douban.com/j/subject/<douban_id>/interest`
   - form fields include `ck`, `interest=do`, `rating=`, `foldcollect=U`, `tags=`, `comment=`, optionally `private=on`.
   - `403 {"r": 1, "code": 403}` means Douban refused the operation (usually stale/invalid cookie or permission/login-state issue).
5. If CookieCloud is involved, verify both sides before changing MoviePilot config:
   - Find the container with `docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' | grep -i -E 'cookie|cookiecloud|cloud'`; on this user's host the known service has appeared as `easychen_cookiecloud`, image `easychen/cookiecloud:latest`, with host port `3333` mapped to container port `8088`.
   - Read the MoviePilot-side CookieCloud/plugin URLs from `/config/user.db` with secrets redacted. `plugin.ZvideoHelper.cookie` may be direct Douban cookie; core/other plugin settings may include `COOKIECLOUD_HOST`.
   - Important precedence: `ZvideoHelper` uses the configured `plugin.ZvideoHelper.cookie` whenever it is non-empty; it only falls back to CookieCloud when that field is empty. If the user says they “synced Douban cookie” but failures continue, first test the actual `plugin.ZvideoHelper.cookie` field, not just CookieCloud.
   - Safe CookieCloud probe from inside MoviePilot:
     ```bash
     docker exec -i MoviePilot python - <<'PY'
     from app.helper.cookiecloud import CookieCloudHelper
     cookie_dict, msg = CookieCloudHelper().download()
     print('cookiecloud_msg', msg)
     print('cookiecloud_ok', cookie_dict is not None, 'domains_count', len(cookie_dict or {}))
     dc=(cookie_dict or {}).get('douban.com') or (cookie_dict or {}).get('.douban.com') or ''
     print('douban_cookie_present_in_cookiecloud', bool(dc), 'len', len(dc) if isinstance(dc,str) else 'nonstr')
     PY
     ```
     `domains_count=0`, missing local CookieCloud files, or no `douban.com` domain means syncing did not reach MoviePilot, even if the browser extension appears updated.
   - Before replacing a hostname, DNS/HTTP-probe the exact new domain (do not guess from Chinese speech such as “骑士 dod.top”); avoid writing an unresolvable URL into MoviePilot. The old host observed in this session was `http://qizhidaodao.xyz:3333`.
   - If a new CookieCloud host is valid, update only the relevant `systemconfig` JSON field(s), preserve secrets, and verify by reading back the redacted config plus rerunning the plugin or a safe CookieCloud fetch.
6. To manually trigger `ZvideoHelper` after changing config, use the core plugin config API rather than editing SQLite directly when possible:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/plugin/ZvideoHelper --compact --raw-out /tmp/zvideo_current.json
   python3 - <<'PY'
   import json
   cfg=json.load(open('/tmp/zvideo_current.json'))
   cfg['cookie']=''          # only if the user intends CookieCloud fallback
   cfg['onlyonce']=True      # same as the UI “立即运行一次” switch
   open('/tmp/zvideo_trigger.json','w').write(json.dumps(cfg, ensure_ascii=False))
   PY
   python3 scripts/mp_request.py PUT /api/v1/plugin/ZvideoHelper --json @/tmp/zvideo_trigger.json --compact --raw-out /tmp/zvideo_put.json
   python3 scripts/mp_request.py GET /api/v1/plugin/reload/ZvideoHelper --compact --raw-out /tmp/zvideo_reload.json
   ```
   Verify `/tmp/zvideo_put.json` and `/tmp/zvideo_reload.json` both have `success: true`, then tail `/config/logs/plugins/zvideohelper.log`. A successful trigger should log `极影视助手服务启动，立即运行一次`; after execution, `onlyonce` usually resets to `false`.
7. If the field was cleared but logs show `本地CookieCloud文件不存在：/config/cookies/<id>.json` and CookieCloud returns `domains_count=0`, the manual trigger worked but no usable CookieCloud cookie reached MoviePilot. Report that distinction clearly: the execution path is fixed, the credential source is still empty.
8. User-facing conclusion: this is Douban status-sync/auth failure, not resource download failure. Ask the user to refresh the Douban Cookie in 极影视助手's own `豆瓣cookie` field, or clear that field so the plugin can use CookieCloud after confirming CookieCloud has a valid `douban.com` cookie; then rerun the plugin / wait for the next cron.

## Security

- Redact cookies (`bid`, `dbcl2`, `ck`, `frodotk_db`, etc.), tokens, API keys, passwords, torrent URLs/passkeys, and authorization headers.
- Keep raw plugin responses in `/tmp` or inside the container; summarize only safe fields.
- Third-party cookie reproduction commands should print booleans, status codes, redirect locations, and redacted snippets only.
- ZvideoHelper debug logs can print full Douban cookies in lines from `DoubanHelper.py` containing `ck:`/`cookie:` or raw `ll=...; bid=...`; filter or replace those lines before displaying logs.
