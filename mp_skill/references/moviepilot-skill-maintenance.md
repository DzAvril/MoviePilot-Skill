# MoviePilot Skill Maintenance Notes

Use these notes when improving `mp_skill` from a live MoviePilot instance.

## Live OpenAPI Refresh Workflow

1. Fetch the live schema from the MoviePilot server:
   ```bash
   python3 scripts/refresh_openapi_refs.py --host http://172.17.0.1:3000
   ```
   If `MP_HOST` is configured in `~/.config/mp_skill/config`, `--host` can be omitted.

2. Confirm the generated references match all live X-API-KEY operations:
   ```bash
   python3 - <<'PY'
   import json, urllib.request, pathlib
   repo=json.loads(pathlib.Path('references/openapi.json').read_text())
   with urllib.request.urlopen('http://172.17.0.1:3000/api/v1/openapi.json', timeout=15) as r:
       live=json.load(r)
   def xpaths(data):
       out=set()
       for p,ops in data.get('paths',{}).items():
           for m,op in ops.items():
               if m.lower() in ['get','post','put','delete','patch'] and any('api_key_header' in sec for sec in (op.get('security') or [])):
                   out.add(p); break
       return out
   print('filtered repo paths', len(repo['paths']))
   print('live x-api-key paths', len(xpaths(live)))
   print('missing after refresh', len(xpaths(live)-set(repo['paths'])))
   print('extra after refresh', len(set(repo['paths'])-xpaths(live)))
   PY
   ```

3. Run lightweight validation:
   ```bash
   python3 -m py_compile scripts/mp_request.py scripts/refresh_openapi_refs.py
   python3 scripts/mp_request.py GET / --no-auth --output /tmp/mp_home_test.html
   ```

4. Check for accidental secrets before committing:
   ```bash
   git diff | grep -Ei 'MP_API_KEY|X-API-KEY|api[_-]?key|token' || true
   git diff --check
   ```

## Contribution Pitfalls

- Live OpenAPI includes auth schemes beyond X-API-KEY. Keep skill references scoped to operations with `api_key_header` so the skill remains compatible with `MP_API_KEY` only.
- Plugin endpoints are instance-dependent; regenerated references may add/remove plugin APIs. Mention this in commit/PR notes.
- Do not stage `__pycache__/` after running `py_compile`; remove it before commit.
- If `git commit` fails with “Author identity unknown”, set repo-local identity, e.g.:
  ```bash
  git config user.name "Hermes Agent"
  git config user.email "hermes-agent@users.noreply.github.com"
  ```
- If `git push` over HTTPS fails with “could not read Username for 'https://github.com'”, ask the user to configure a GitHub PAT/credential helper, switch the remote to SSH with a usable key, or apply the generated `git format-patch` manually.
