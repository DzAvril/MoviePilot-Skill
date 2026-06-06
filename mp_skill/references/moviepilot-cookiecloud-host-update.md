# MoviePilot CookieCloud Host Update

Use this when the user asks to change the CookieCloud domain/host used by MoviePilot or when CookieCloud-backed plugins (e.g. ZvideoHelper/Douban) still use an old domain.

## Key facts from live diagnosis

MoviePilot may contain CookieCloud host settings in two different places:

1. Runtime env file inside the container/config bind mount:
   - `/config/app.env`
   - line: `COOKIECLOUD_HOST='http://<host>:3333'`
   - `app.core.config.settings.COOKIECLOUD_HOST` is sourced from this at process startup; a MoviePilot restart may be required for the running process to use the changed value.

2. Config Center plugin settings in SQLite:
   - database: `/config/user.db`
   - table/key: `systemconfig.key='plugin.ConfigCenter'`
   - JSON field: `COOKIECLOUD_HOST`
   - This can contain an older public domain even when `settings.COOKIECLOUD_HOST` uses a local bridge address.

Do not print `COOKIECLOUD_KEY`, `COOKIECLOUD_PASSWORD`, API tokens, or cookie values. Redact them as `[REDACTED]`.

## Safe discovery

```bash
docker exec -i MoviePilot python - <<'PY'
from app.core.config import settings
print('runtime COOKIECLOUD_HOST=', settings.COOKIECLOUD_HOST)
PY

docker exec -i MoviePilot python - <<'PY'
from pathlib import Path
p=Path('/config/app.env')
if p.exists():
    for line in p.read_text(errors='ignore').splitlines():
        if line.startswith('COOKIECLOUD_HOST='):
            print(line)
PY

docker exec -i MoviePilot python - <<'PY'
import sqlite3, json
con=sqlite3.connect('/config/user.db')
row=con.execute("select value from systemconfig where key='plugin.ConfigCenter'").fetchone()
if row:
    cfg=json.loads(row[0])
    print('ConfigCenter COOKIECLOUD_HOST=', cfg.get('COOKIECLOUD_HOST'))
PY
```

## Verify the new host from the relevant network namespace

External DNS/proxy behavior can differ from inside the MoviePilot container. Probe from inside MoviePilot before reporting failure:

```bash
docker exec -i MoviePilot python - <<'PY'
import urllib.request
url='http://NEW_HOST:3333'
try:
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Hermes-check/1.0'}), timeout=8) as r:
        print('OK', r.status, r.geturl())
except Exception as e:
    print('FAIL', type(e).__name__, str(e)[:160])
PY
```

## Update both locations

```bash
NEW='http://qizhidodo.top:3333'

docker exec -i MoviePilot python - <<'PY'
import os, sqlite3, json
new=os.environ['NEW']
con=sqlite3.connect('/config/user.db')
cur=con.cursor()
row=cur.execute("select value from systemconfig where key='plugin.ConfigCenter'").fetchone()
if row:
    cfg=json.loads(row[0])
    old=cfg.get('COOKIECLOUD_HOST')
    cfg['COOKIECLOUD_HOST']=new
    cur.execute("update systemconfig set value=? where key='plugin.ConfigCenter'", (json.dumps(cfg, ensure_ascii=False),))
    con.commit()
    print('updated ConfigCenter COOKIECLOUD_HOST', old, '=>', new)
else:
    print('plugin.ConfigCenter row not found')
PY

docker exec -i MoviePilot sh -c "python - <<'PY'
from pathlib import Path
import os, re
new=os.environ['NEW']
p=Path('/config/app.env')
text=p.read_text()
replacement=f\"COOKIECLOUD_HOST='{new}'\"
text2=re.sub(r'^COOKIECLOUD_HOST=.*$', replacement, text, flags=re.M)
if text2 == text and 'COOKIECLOUD_HOST=' not in text:
    text2 = text.rstrip() + '\n' + replacement + '\n'
p.write_text(text2)
print('updated /config/app.env COOKIECLOUD_HOST')
PY"
```

Pass `NEW` into the container command via environment or inline it carefully; never inline secrets. After updating, read both values back. Tell the user that a MoviePilot restart may be required for the running process to reload `/config/app.env`.

## Browser upload failure / container health triage

When the user says CookieCloud upload fails in the browser, first separate the CookieCloud container/API from client-network reachability:

```bash
# 1) Find the service and host port
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' | grep -Ei 'cookie|3333|NAMES'

# 2) Probe the host-published API from Hermes; if proxies are configured, test both proxied and no-proxy behavior.
python3 - <<'PY'
import urllib.request, json
for base in ['http://172.17.0.1:3333', 'http://qizhidodo.top:3333']:
    print('###', base)
    try:
        payload=json.dumps({'uuid':'__hermes_probe__','encrypted':'probe'}).encode()
        req=urllib.request.Request(base+'/update', data=payload, method='POST', headers={'Content-Type':'application/json','User-Agent':'HermesProbe/1.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            print('POST /update', r.status, r.read(200).decode('utf-8','replace'))
    except Exception as e:
        print(type(e).__name__, str(e))
PY

# 3) Probe from inside MoviePilot because its network/proxy/DNS can differ from the browser and Hermes.
docker exec MoviePilot sh -lc 'python - <<"PY"
import urllib.request
for url in ["http://127.0.0.1:3333/", "http://qizhidodo.top:3333/"]:
    print("###", url)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"MPProbe/1.0"}), timeout=8) as r:
            print("HTTP", r.status, r.read(200).decode("utf-8","replace"))
    except Exception as e:
        print(type(e).__name__, str(e))
PY'
```

Interpretation from live case:

- Container was healthy when `easychen_cookiecloud` was Up, `/update` returned `{"action":"done"}`, `/get/<uuid>` returned the encrypted JSON, and MoviePilot could read the same URL.
- Browser/client failure can still happen if the public domain resolves only to IPv6 (`AAAA`) and the browser network lacks IPv6, or if the system/browser proxy routes `http://<domain>:3333` and returns `502 Bad Gateway`.
- In that case, advise the user to open `http://<domain>:3333/` in the same browser; success is `Hello World!API ROOT =`. If it fails, fix client routing: add the CookieCloud domain/port to proxy direct rules, use a LAN host/IP URL such as `http://<NAS-IP>:3333`, or add a working IPv4 A record/port forward for the domain.
- Clean up synthetic probe files such as `/data/api/data/__hermes_probe__.json` after testing.

## Pitfalls

- Do not rely only on host-side DNS/curl. A domain that looks broken from Hermes/host can still work from inside the MoviePilot container due to DNS/proxy differences.
- Do not label browser upload failures as container failures until `/update` and `/get/<uuid>` have been tested against the service from at least one local/container network path.
- If `qizhidodo.top:3333` or another CookieCloud domain returns 502 only through Hermes/system proxy, suspect proxy routing rather than CookieCloud itself; retest with proxy env vars unset before concluding.
- If DNS returns only an IPv6 AAAA record, explicitly consider clients without IPv6 and recommend LAN IP or IPv4 A record/forwarding.
- Do not assume the Config Center plugin row controls the active runtime; `settings.COOKIECLOUD_HOST` may still reflect `/config/app.env` until restart.
- Do not paste raw ConfigCenter JSON because it often contains GitHub tokens, API tokens, CookieCloud credentials, and other secrets.
