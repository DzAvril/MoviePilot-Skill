# MoviePilot routine restart playbook

Use when the user asks to restart MP/MoviePilot without requesting an image update.

## Steps

1. Discover the running containers first:

   ```bash
   docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' | grep -Ei 'moviepilot|mp|NAMES'
   ```

2. Capture state before restart:

   ```bash
   docker inspect MoviePilot --format 'Before StartedAt={{.State.StartedAt}} RestartCount={{.RestartCount}} Status={{.State.Status}} Health={{if .State.Health}}{{json .State.Health.Status}}{{else}}none{{end}} Image={{.Image}}'
   ```

3. Restart the app container only, not PostgreSQL/Redis, unless the user explicitly asks for the whole stack:

   ```bash
   docker restart MoviePilot
   ```

4. If Docker returns `Cannot restart container MoviePilot: tried to kill container, but did not receive an exit event`, immediately inspect state. The container may have stopped with exit code 137 even though the restart command failed:

   ```bash
   docker ps -a --filter name=MoviePilot --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
   docker inspect MoviePilot --format 'State={{json .State}}'
   ```

   If it is exited and not restarting/dead, start it explicitly:

   ```bash
   docker start MoviePilot
   ```

5. Verify readiness from Hermes/container network. A direct unauthenticated UI probe returning HTTP 200 is enough for basic restart verification:

   ```bash
   python3 - <<'PY'
   import urllib.request, time
   url='http://172.17.0.1:3000'
   last=None
   for i in range(24):
       try:
           req=urllib.request.Request(url, headers={'User-Agent':'hermes-check'})
           with urllib.request.urlopen(req, timeout=5) as r:
               print('HTTP_OK', r.status, r.geturl())
               raise SystemExit(0)
       except Exception as e:
           last=f'{type(e).__name__}: {e}'
           print('WAIT', i+1, last)
           time.sleep(5)
   print('FAILED', last)
   raise SystemExit(1)
   PY
   ```

6. Check status and bounded logs. Avoid raw long logs; redact secrets and do not stream indefinitely:

   ```bash
   docker ps --filter name=MoviePilot --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
   timeout 20s docker logs --tail 80 MoviePilot 2>&1 | python3 -c "import sys,re; s=sys.stdin.read(); s=re.sub(r'(?i)(api[_-]?key|token|password|passwd|secret)([=:]\\s*)[^\\s,;]+', r'\\1\\2***', s); print(s[-4000:])"
   ```

## Report

Keep the user-facing reply compact:

- State whether MP is back up.
- Mention if `docker restart` failed but `docker start` recovered it.
- Include web/API verification status.
- Summarize only material recent log issues; plugin DEBUG noise is not a core startup failure.
