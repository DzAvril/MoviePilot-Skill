# P115StrmHelper API Playbook

Session-derived notes for using the MoviePilot plugin `P115StrmHelper` / “P115 Stream Helper” through `/api/v1/plugin/P115StrmHelper/*`.

## Safe discovery workflow

1. Verify plugin state first:
   ```bash
   cd /opt/data/skills/productivity/moviepilot-api-control
   python3 scripts/mp_request.py GET /api/v1/plugin/P115StrmHelper/get_status --output /tmp/p115_status.json
   ```
   Expected shape: `code/msg/data`, with `data.enabled`, `data.has_client`, `data.running`.

2. Read config shape, but never print secrets:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/plugin/P115StrmHelper --output /tmp/p115_plugin_config.json
   ```
   Redact fields containing `cookie`, `token`, `password`, `key`, `authorization`.

3. Check 115 account/storage status:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/plugin/P115StrmHelper/user_storage_status --output /tmp/p115_storage.json
   ```
   Safe summary fields include VIP status/expiry and storage totals. Avatar URL is usually safe but can be omitted.

4. Use OpenAPI to enumerate current endpoints:
   ```bash
   python3 - <<'PY'
   import json
   s=json.load(open('references/openapi.json'))
   for path, methods in s.get('paths',{}).items():
       if '/P115StrmHelper/' in path:
           for method, spec in methods.items():
               if method.lower() in ['get','post','put','delete']:
                   print(method.upper(), path, spec.get('summary') or '')
   PY
   ```

## Useful read-only / low-risk endpoints

- `GET /get_status` — plugin enabled/client/running status.
- `GET /user_storage_status` — 115 user/VIP/storage status.
- `GET /browse_dir?path=/...` — browse 115 directories; `is_local=true` browses local filesystem paths.
- `POST /offline_tasks` with `{"page":1,"limit":10}` — list 115 offline tasks.
- `GET /fuse_status` — FUSE enabled/mounted state.
- `GET /get_authorization_status`, `/get_machine_id`, `/check_feature` — authorization/enhancement status. Redact machine IDs.
- `GET /get_strm_sync_history`, `/get_sync_del_history` — STRM/sync-delete history.
- `GET /strm_cleanup_pending`, `/share_strm_cleanup_pending`, `/share_strm_cleanup_last_summary`, `/share_strm_missing_media_list` — cleanup/consistency state.
- `GET /generate_emby2alist_config` — generate Emby 302 redirect mapping. Redact MoviePilot URL/API key in summaries.

## Higher-impact endpoints — confirm intent before calling

- `POST /add_offline_task` — add 115 offline download links. Body: `{"links":[...],"path":"/..."}`.
- `GET /add_transfer_share?share_url=...` — parse 115 share URL, transfer it to configured pan-transfer path, recognize media, and notify.
- `POST /manual_transfer` — trigger pan/media organization for a path. Body requires `path`.
- `POST /full_sync` or `/full_sync_db` — start full STRM sync.
- `POST /share_sync` — start share STRM sync.
- `POST /api_strm_sync_creata`, `/api_strm_sync_create_by_path`, `/api_strm_sync_remove` — generate/remove STRM by API payload.
- `POST /fuse_mount`, `/fuse_unmount` — mount/unmount FUSE; depends on container privileges and may affect filesystem state.
- `POST /strm_cleanup_execute`, `/share_strm_cleanup_execute`, history-delete endpoints, and missing-media clear endpoints — destructive or cleanup actions; require explicit user approval and read-back verification.
- `POST /clear_302_cache`, `/clear_id_path_cache`, `/clear_increment_skip_cache` — cache invalidation; low data risk but can affect performance/behavior.

## P115StrmHelper MCP tools

The plugin exposes its own MCP SSE endpoint in addition to normal REST plugin APIs:

- `GET /api/v1/plugin/P115StrmHelper/mcp/sse`
- `POST /api/v1/plugin/P115StrmHelper/mcp/messages?session_id=...`

Use the bundled probe to list live tools without printing MoviePilot credentials:

```bash
cd /opt/data/skills/productivity/moviepilot-api-control
python3 scripts/list_p115_mcp_tools.py > /tmp/p115_mcp_tools.json
python3 - <<'PY'
import json
tools=json.load(open('/tmp/p115_mcp_tools.json'))
for t in tools:
    schema=t.get('inputSchema') or {}
    props=schema.get('properties') or {}
    req=set(schema.get('required') or [])
    fields=', '.join(f"{k}{'*' if k in req else ''}:{v.get('type','?')}" for k,v in props.items())
    print(f"- {t.get('name')}: {t.get('description','')} ({fields})")
PY
```

Live-tested tool set on this instance included 19 tools:

- Read-only/diagnostic: `get_plugin_status`, `get_storage_status`, `browse_directory(path,is_local)`, `get_offline_tasks(page,limit)`, `get_sync_delete_history(page,limit)`, `get_fuse_status`, `check_life_event_status`.
- Sync/STRM operations: `trigger_full_sync`, `trigger_share_sync`, `trigger_full_sync_db`, `manual_pan_transfer(path)`.
- 115 share/offline operations: `add_share_transfer(share_url)`, `add_offline_task(links,path)`.
- Cache maintenance: `clear_id_path_cache`, `clear_increment_skip_cache`.
- FUSE: `fuse_mount(mountpoint,readdir_ttl)`, `fuse_unmount`.
- Destructive cleanup: `clear_recyclebin`, `clear_receive_path`.

MCP handshake notes: the SSE stream first emits an `endpoint` event; POST JSON-RPC `initialize`, then `tools/list` to the message endpoint. This plugin may return `Method not found` for `notifications/initialized`; that is benign if `tools/list` returns tools.

## 302 redirect behavior

`GET|POST|HEAD /redirect_url` supports:

- Own-file redirect via `pickcode` and optional `file_name` / `app`.
- Share-file redirect via `share_code`, optional `receive_code`, and either `id` or `file_name`.

The endpoint returns a 302 with `Location` pointing to a short-lived 115 download URL. Never print the final URL; it may be tokenized. For Emby integration, prefer `generate_emby2alist_config` and redact the generated URL/API key.

### Diagnosing STRM playback domain / stale MoviePilot address

When playback works or fails depending on domain, do not rely only on `p115strmhelper.log`: on this instance the plugin log records the UA, pickcode cache, and final 115 CDN URL, but not the inbound `Host` used by the player.

Use a three-way check instead:

1. **Plugin config source of generated STRM URLs** — inspect `plugin.P115StrmHelper` in `/config/user.db` and read `moviepilot_address` without printing cookies/tokens:
   ```bash
   docker exec -i MoviePilot python - <<'PY'
   import json, sqlite3
   con=sqlite3.connect('/config/user.db')
   row=con.execute("select value from systemconfig where key='plugin.P115StrmHelper'").fetchone()
   cfg=json.loads(row[0]) if row else {}
   print('moviepilot_address=', cfg.get('moviepilot_address'))
   print('strm_url_format=', cfg.get('strm_url_format'))
   PY
   ```
2. **Plugin redirect activity** — search `/config/logs/plugins/p115strmhelper.log*` for `【302跳转服务】`, `获取到客户端UA`, `添加至缓存`, and `获取 115 下载地址成功`. Redact final CDN URLs and query tokens.
3. **Inbound web/player host evidence** — inspect `/var/log/nginx/access.log` and `/config/logs/moviepilot.log*` for the candidate domains. Nginx access logs can show `Referer`/request lines such as `https://example:4430/service-worker.js` or `/api/v1/plugin/P115StrmHelper/redirect_url?...`, while MoviePilot notification logs often show the configured public link domain.

If normal MP web access shows a new/correct domain but `moviepilot_address` still contains an old domain, conclude that existing/new STRM/plugin notification links may still be generated from the stale configured address. Recommend updating the plugin setting and regenerating/syncing affected STRM files rather than assuming reverse-proxy DNS is the only issue.

## Practical user workflows

- **Browse 115 library:** start at `/`, then inspect `/media`, `/云下载`, `/最近接收`, etc.
- **Magnet/link to 115:** use `/add_offline_task`, then poll `/offline_tasks` and optionally trigger `/manual_transfer` or STRM generation.
- **115 share to library:** use `/add_transfer_share` after user provides a share URL; read response for media recognition and target parent path.
- **Cloud playback:** combine STRM generation with `/redirect_url`/`generate_emby2alist_config` for Emby 302 playback without local full-file storage.
- **Maintenance:** check pending cleanup endpoints first; execute cleanup only after presenting counts and receiving approval.

### Bulk auditing and replacing stale STRM domains

If a public MoviePilot domain changes, audit all `.strm` files rather than checking only one show:

```bash
docker exec -i MoviePilot python - <<'PY'
from pathlib import Path
from collections import Counter
roots=[Path('/ssd/strm'), Path('/media'), Path('/sata14t/保种/other/strm')]
old='qizhidoudou.xyz:4430'
new='qizhidodo.top:4430'
files=[]
for root in roots:
    if not root.exists():
        continue
    for p in root.rglob('*.strm'):
        text=p.read_text(errors='ignore')
        if old in text or old.split(':')[0] in text:
            files.append(p)
print('old_domain_strm_count', len(files))
print(Counter(str(next(r for r in roots if p.is_relative_to(r))) for p in files))
PY
```

For a requested mutation, make a short-lived backup manifest, replace the exact host, and also fix malformed URLs where a space appears after the host:

```bash
docker exec -i MoviePilot python - <<'PY'
from pathlib import Path
from datetime import datetime
import shutil, json
roots=[Path('/ssd/strm'), Path('/media'), Path('/sata14t/保种/other/strm')]
old='qizhidoudou.xyz:4430'; new='qizhidodo.top:4430'
backup_root=Path('/config/strm_domain_backups')/datetime.now().strftime('%Y%m%d_%H%M%S')
backup_root.mkdir(parents=True, exist_ok=True)
changed=[]
for root in roots:
    if not root.exists(): continue
    for p in root.rglob('*.strm'):
        text=p.read_text(errors='ignore')
        newtext=(text.replace(old,new)
                    .replace('qizhidoudou.xyz','qizhidodo.top')
                    .replace('https://qizhidodo.top:4430 /','https://qizhidodo.top:4430/')
                    .replace('http://qizhidodo.top:4430 /','http://qizhidodo.top:4430/'))
        if newtext != text:
            bp=backup_root/Path(str(p).lstrip('/'))
            bp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p,bp)
            p.write_text(newtext)
            changed.append(str(p))
(backup_root/'manifest.json').write_text(json.dumps({'changed_count':len(changed),'changed_files':changed}, ensure_ascii=False, indent=2))
print('changed_count', len(changed)); print('backup_root', backup_root)
PY
```

Always verify after replacement: old domain count must be 0 and all parsed URL hosts should be the new host. If the user approves deleting the backup, remove only the specific timestamped backup directory and verify it is gone.

### Getting and validating a final 115 302 CDN URL

For IPv6-incompatible public MoviePilot domains or external player tests, the user may ask for the final 115 CDN URL. Use `HEAD` with redirects disabled against the STRM URL and return the `Location` only when explicitly requested, because it contains short-lived tokenized parameters.

Important: **115 CDN URLs can be User-Agent-bound.** A URL minted with `Lavf/...` may return `403 Forbidden` when opened by VLC, while a URL minted with `VLC/3.0...` works. When testing a player, mint the URL using that player's UA and then validate with the same UA.

Probe recipe:

```bash
docker exec -i MoviePilot python - <<'PY'
from pathlib import Path
import urllib.request, urllib.error, subprocess, os
p=Path('/ssd/strm/series/国产剧/武林外传 (2006)/Season 1/武林外传 - S01E01-DVD - 第 1 集.strm')
strm=p.read_text(errors='ignore').strip()
ua='VLC/3.0.20 LibVLC/3.0.20'  # change to target player UA
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None
opener=urllib.request.build_opener(NoRedirect)
try:
    opener.open(urllib.request.Request(strm, method='HEAD', headers={'User-Agent':ua}), timeout=20)
    raise SystemExit('no redirect')
except urllib.error.HTTPError as e:
    loc=e.headers.get('Location')
print(loc)
# Optional validation: 1MiB range should return 206 and ffprobe should identify streams.
subprocess.run(['curl','-L','--max-time','30','-A',ua,'-r','0-1048575','-o','/tmp/strmtest.bin',loc], check=False)
subprocess.run(['ffprobe','-v','error','-user_agent',ua,'-show_entries','format=format_name,duration,size:stream=index,codec_type,codec_name,width,height','-of','json',loc], check=False)
PY
```

Successful validation on this instance returned `HTTP 206`, a Matroska header, and `ffprobe` detected H.264 video + AAC audio. A browser may download a tiny file or fail even when the player-specific URL is valid; do not treat browser behavior as definitive playback evidence.

### Emby 302 reverse proxy troubleshooting

For Emby playback through the `Emby 302 反向代理` / `embyreverseproxy` plugin, check both plugin logs and port state:

```bash
docker exec MoviePilot sh -lc "ss -ltnp 2>/dev/null | grep -E '(:8099|:4096|:3000)' || true"
docker exec -i MoviePilot tail -n 200 /config/logs/plugins/embyreverseproxy.log
```

On this instance the plugin logs `EmbyReverseProxy 代理已启动: 0.0.0.0:8099 -> http://172.17.0.1:4096` when healthy. If the latest log is `代理已停止` and port `8099` is not listening, STRM/P115 redirect tests can still pass while Emby clients that are configured to use the 8099 proxy cannot play. Distinguish this from stale STRM-domain failures.

## Pitfalls

1. Plugin config contains cookies, tokens, passwords, generated redirect templates, and possibly API keys. Summarize shape only.
2. OpenAPI references can list more endpoints than the plugin class `get_api()` in source because additional routers/modules may register endpoints; trust live OpenAPI for availability.
3. `get_config` may return `None`; `GET /api/v1/plugin/P115StrmHelper` is better for config shape on this instance.
4. FUSE endpoints should not be treated as harmless; check `fuse_status` and container capabilities first.
5. Cleanup execute endpoints are two-stage by design. List pending batches first, then execute by `request_id` only with user confirmation.
6. Final 115 CDN URLs are temporary and may be bound to the User-Agent used when minting the 302; use the target player's UA for both URL generation and validation.
7. A valid 115 CDN URL may present as `Content-Disposition: attachment` or `application/octet-stream`; browser download behavior is not a reliable playback test. Prefer range requests and `ffprobe`/actual player UA validation.
8. Emby 302 reverse proxy failures can be independent of P115StrmHelper: verify the proxy port is listening before blaming STRM URLs.
