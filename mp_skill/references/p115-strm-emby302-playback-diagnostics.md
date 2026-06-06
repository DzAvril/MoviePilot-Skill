# P115 STRM + Emby 302 Playback Diagnostics

Use this when a MoviePilot/Emby item backed by P115 STRM URLs cannot play, especially when the user suspects a domain or 302 issue.

## Proven diagnostic sequence

1. **Check the STRM files directly inside the MoviePilot container** before assuming the plugin config is current:
   ```bash
   docker exec -i MoviePilot python - <<'PY'
   from pathlib import Path
   import urllib.parse, collections, re, time
   root = Path('/ssd/strm')
   title_terms = ['武林外传']
   files = []
   for p in root.rglob('*.strm'):
       if any(t.lower() in str(p).lower() for t in title_terms):
           files.append(p)
   hosts = collections.Counter()
   old = []
   for p in files:
       c = p.read_text(errors='ignore').strip()
       u = urllib.parse.urlparse(c)
       hosts[f'{u.scheme}://{u.netloc}'] += 1
       if 'qizhidoudou.xyz' in c:
           old.append(str(p))
   print('count', len(files))
   print('hosts', dict(hosts))
   print('old_domain_count', len(old))
   for p in sorted(files)[:5]:
       c = p.read_text(errors='ignore').strip()
       red = re.sub(r'([?&](?:apikey|api_key|token|sign|cookie|receive_code)=)[^&\s]+', r'\1[REDACTED]', c, flags=re.I)
       red = re.sub(r'(pickcode=)([^&\s]+)', lambda m: m.group(1)+m.group(2)[:5]+'***', red, flags=re.I)
       print(p, red)
   PY
   ```
   A plugin setting such as `moviepilot_address` may be stale while existing STRM files already contain the correct domain.

2. **Test one STRM URL without following redirects** to prove whether P115StrmHelper can issue a fresh 302:
   ```bash
   docker exec -i MoviePilot python - <<'PY'
   from pathlib import Path
   import urllib.request, urllib.error, urllib.parse
   p = Path('/ssd/strm/series/国产剧/武林外传 (2006)/Season 1/武林外传 - S01E01-DVD - 第 1 集.strm')
   url = p.read_text(errors='ignore').strip()
   class NoRedirect(urllib.request.HTTPRedirectHandler):
       def redirect_request(self, req, fp, code, msg, headers, newurl):
           return None
   opener = urllib.request.build_opener(NoRedirect)
   req = urllib.request.Request(url, method='HEAD', headers={'User-Agent':'Lavf/59.27.100'})
   try:
       r = opener.open(req, timeout=20); print('status', r.status); loc = r.headers.get('Location')
   except urllib.error.HTTPError as e:
       print('status', e.code); loc = e.headers.get('Location')
   if loc:
       u = urllib.parse.urlparse(loc)
       print('location_host', u.netloc)
       print('location_path', urllib.parse.unquote(u.path)[:200])
   PY
   ```
   `302 -> cdnfhnfile.115cdn.net/...` means the STRM/P115StrmHelper layer is healthy.

3. **Check P115StrmHelper plugin logs** for recent 302 activity, but know the limitation: it logs client UA, cache, and final 115 CDN URL; it may not log the inbound Host/domain.
   ```bash
   docker exec -i MoviePilot python - <<'PY'
   from pathlib import Path
   import re
   p = Path('/config/logs/plugins/p115strmhelper.log')
   for i,l in list(enumerate(p.read_text(errors='ignore').splitlines(),1))[-500:]:
       if '302跳转服务' in l or 'redirect_url' in l:
           l = re.sub(r'([?&](?:apikey|api_key|token|sign|cookie|pickcode|receive_code)=)[^&\s]+', r'\1[REDACTED]', l, flags=re.I)
           print(i, l[:1200])
   PY
   ```

4. **Use nginx access logs to infer web/domain usage** when plugin logs lack Host data:
   ```bash
   docker exec -i MoviePilot python - <<'PY'
   from pathlib import Path
   for p in [Path('/var/log/nginx/access.log'), Path('/config/logs/moviepilot.log')]:
       if not p.exists(): continue
       print('\n###', p)
       for i,l in enumerate(p.read_text(errors='ignore').splitlines(),1):
           if 'redirect_url' in l or 'qizhidodo' in l or 'qizhidoudou' in l:
               print(i, l[:1000])
   PY
   ```

5. **Check Emby 302 reverse proxy status/logs**. On this instance the plugin is `embyreverseproxy`, log path is `/config/logs/plugins/embyreverseproxy.log`, default proxy port is `8099`, and it proxies to Emby at `http://172.17.0.1:4096`.
   ```bash
   docker exec -i MoviePilot python - <<'PY'
   from pathlib import Path
   import re
   p = Path('/config/logs/plugins/embyreverseproxy.log')
   lines = p.read_text(errors='ignore').splitlines()
   for i,l in list(enumerate(lines,1))[-250:]:
       l = re.sub(r'([?&](?:api_key|apikey|token|X-Emby-Token|DeviceId|MediaSourceId|PlaySessionId)=)[^&\s]+', r'\1[REDACTED]', l, flags=re.I)
       print(i, l[:1600])
   PY
   docker exec MoviePilot sh -lc "ss -ltnp 2>/dev/null | grep -E '(:8099|:4096|:3000)' || netstat -ltnp 2>/dev/null | grep -E '(:8099|:4096|:3000)'"
   ```
   If logs say `EmbyReverseProxy 代理已停止` and port `8099` is not listening while Emby `4096` is listening, playback failures through the proxy are likely due to the reverse proxy being stopped, not bad STRM URLs.

## Interpretation notes

- Existing STRM files can be correct (`qizhidodo.top:4430`) even if P115StrmHelper's stored `moviepilot_address` still shows an old domain (`qizhidoudou.xyz`). Report these as separate facts.
- If direct STRM HEAD returns a 302 to `cdnfhnfile.115cdn.net`, do not blame the P115StrmHelper layer without additional evidence.
- EmbyReverseProxy successful playback logs look like `PlaybackInfo: STRM 已强制 DirectPlay` followed by `302 重定向: item_id=... -> https://cdnfhnfile.115cdn.net/...`.
- Redact API keys, tokens, pickcodes, Emby tokens/session IDs, cookies, and final 115 query strings when summarizing logs.
