# MoviePilot Plugin Development Workflow

Session-proven workflow for debugging and patching MoviePilot plugin repositories, then testing against the user's live MoviePilot instance.

## Quick read-only inspection of an installed plugin

Use this when the user asks what an installed MoviePilot plugin does, without asking for a bug fix or code change. Prefer the live container source over memory or upstream assumptions, because installed plugins can differ from GitHub.

1. Locate the running MoviePilot container and plugin path:
   ```bash
   docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -i -E 'movie|pilot'
   docker exec -i MoviePilot python - <<'PY'
   import os
   terms=['<Chinese plugin name>','<PluginClassOrId>','<lowercaseid>']
   for base in ['/config/plugins','/config/MoviePilot-Plugins-Private','/app/app/plugins','/app/app']:
       if not os.path.exists(base):
           continue
       print('---BASE', base)
       hits=[]
       for root, dirs, files in os.walk(base, topdown=True):
           dirs[:] = [d for d in dirs if d not in {'.git','__pycache__','node_modules','cache','logs','temp','tmp'}]
           for f in files:
               if not f.endswith(('.py','.json','.yaml','.yml','.md','.vue','.js','.ts')):
                   continue
               p=os.path.join(root,f)
               try:
                   s=open(p,'r',encoding='utf-8',errors='ignore').read(8192)
               except Exception:
                   continue
               if any(t.lower() in s.lower() or t.lower() in p.lower() for t in terms):
                   hits.append(p)
       print('\n'.join(hits[:100]) or '(none)')
   PY
   ```
2. For a large Python plugin, do not paste the whole file into chat. First extract a structural map with `ast`:
   ```bash
   docker exec -i MoviePilot python - <<'PY'
   import ast, pathlib
   p='/app/app/plugins/<plugin_id>/__init__.py'
   s=pathlib.Path(p).read_text(encoding='utf-8', errors='ignore')
   mod=ast.parse(s)
   for node in mod.body:
       if isinstance(node, ast.ClassDef):
           print('Class', node.name)
           for item in node.body:
               if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                   dec=[ast.get_source_segment(s,d).replace('\n',' ') for d in item.decorator_list]
                   print(f'{item.lineno:04d}-{getattr(item,"end_lineno",0):04d} {item.name} dec={dec}')
   PY
   ```
3. Read targeted ranges only: plugin metadata, `get_form`, `get_service`, event handlers (`eventmanager.register`), scheduled task methods, and any companion files. Summarize by user-facing capability, trigger/event, side effects, and risk.
4. If helpful, check whether the plugin is merely installed versus configured/enabled. Search `systemconfig`, `plugindata`, and `userconfig` for the plugin ID, but print only keys/safe snippets; avoid full raw config dumps because plugin configs may contain tokens, cookies, URLs, or credentials.
5. In the answer, distinguish **code capability** from **current runtime state**. If no `plugin.<PluginId>` config or recent log entries are found, say the plugin code is installed but active/enabled status was not proven.

## End-to-end chain

The user's preferred sequence is **local test before commit/push** whenever feasible. Before publishing a plugin fix, try to deploy the patched code into a testable MoviePilot plugin directory, reload the plugin, inspect logs/API/form/config, and verify the behavior. If the environment lacks direct plugin-directory or log access, call that out explicitly and fall back to GitHub push + PluginManagerVue reinstall verification. See `references/plugin-local-testing-prereqs.md` for the prerequisites to make true local testing possible.

1. Inspect GitHub issues for the plugin repo. Prefer open issues, but if there are no open `Stale` issues and the user asks to keep resolving stale backlog, also search closed `Stale` issues: some are stale-closed without an actual fix and can still be resolved with a commit + verification + comment/label cleanup. **Work issue-by-issue unless the user explicitly approves a batch:** read the issue body and comments, state the exact behavior being fixed, reproduce or otherwise validate that behavior locally, then only close that specific issue after the fix is proven. If a prior commit already fixed the behavior (for example a duplicate feature request), verify the issue-to-commit mapping and cite the existing verification rather than making unrelated code changes. Public issues can be read through the GitHub REST API without `gh` auth until rate-limited:
   ```bash
   python3 - <<'PY'
   import urllib.request, json
   url='https://api.github.com/repos/<owner>/<repo>/issues?state=all&per_page=20'
   req=urllib.request.Request(url, headers={'Accept':'application/vnd.github+json','User-Agent':'Hermes'})
   print(json.dumps(json.load(urllib.request.urlopen(req, timeout=20)), ensure_ascii=False, indent=2)[:8000])
   PY
   ```
2. Obtain source locally. Prefer SSH clone when it works:
   ```bash
   git clone git@github.com:<owner>/<repo>.git /opt/data/home/repos/<repo>
   ```
3. If SSH auth succeeds but clone/fetch times out or reports `fetch-pack: unexpected disconnect while reading sideband packet`, fall back to codeload zip and Python stdlib unzip (the Hermes container may not have `/usr/bin/unzip`):
   ```bash
   BASE=/opt/data/home/repos
   mkdir -p "$BASE"
   python3 - <<'PY'
   import urllib.request
   owner='DzAvril'; repo='MoviePilot-Plugins'; branch='main'
   url=f'https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}'
   req=urllib.request.Request(url, headers={'User-Agent':'Hermes'})
   with urllib.request.urlopen(req, timeout=60) as r, open(f'/tmp/{repo}.zip','wb') as f:
       while chunk := r.read(1024*1024):
           f.write(chunk)
   PY
   rm -rf "$BASE/MoviePilot-Plugins" "$BASE/MoviePilot-Plugins-main"
   python3 - <<'PY'
   import zipfile, pathlib
   repo='MoviePilot-Plugins'
   with zipfile.ZipFile(f'/tmp/{repo}.zip') as z:
       z.extractall('/opt/data/home/repos')
   pathlib.Path('/opt/data/home/repos/MoviePilot-Plugins-main').rename('/opt/data/home/repos/MoviePilot-Plugins')
   PY
   ```
4. Locate plugin code and issue-related symbols:
   ```bash
   cd /opt/data/home/repos/MoviePilot-Plugins
   find plugins plugins.v2 -maxdepth 3 -type f | sort
   grep -R "<plugin-or-error-keyword>" -n plugins plugins.v2 | head -50
   ```
5. Make the minimal local code change. For updates that MoviePilot should detect, bump **both** version locations:
   - Plugin source file: update class-level `plugin_version` in the plugin's `__init__.py`.
   - Correct market manifest: v1 plugins under `plugins/` use root `package.json`; v2 plugins under `plugins.v2/` use `package.v2.json`.
   - Add/update the matching `history` entry in the same manifest.
   Missing either the source `plugin_version` or the manifest version can make MoviePilot fail to update, keep showing the old version, or produce inconsistent PluginManagerVue results.
6. Run syntax checks before deploying:
   ```bash
   python3 -m py_compile $(find plugins plugins.v2 -name '*.py')
   ```
7. If the source was obtained from a zip fallback, convert to a real git working tree before pushing. HTTPS clone with a token-backed `GIT_ASKPASS` can succeed even when SSH clone previously timed out; if HTTPS push returns `403 Permission denied`, try SSH push because this user's SSH auth has worked for `DzAvril/MoviePilot-Plugins`:
   ```bash
   git clone --depth 1 --filter=blob:none https://github.com/DzAvril/MoviePilot-Plugins.git /opt/data/home/repos/MoviePilot-Plugins-git
   # apply patch, bump plugin_version and correct package manifest, commit
   git remote set-url origin git@github.com:DzAvril/MoviePilot-Plugins.git
   GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=30' git push origin main
   ```
   Never embed or echo the GitHub token in commands/logs; read it from the local out-of-band config and redact it from any output.
8. If working from a GitHub zip rather than a git clone, generate reviewable patches by diffing against the zip member:
   ```bash
   python3 - <<'PY'
   import zipfile, pathlib, difflib
   zip_path='/tmp/MoviePilot-Plugins.zip'
   member='MoviePilot-Plugins-main/plugins/<plugin>/__init__.py'
   cur_path=pathlib.Path('/opt/data/home/repos/MoviePilot-Plugins/plugins/<plugin>/__init__.py')
   with zipfile.ZipFile(zip_path) as z:
       old=z.read(member).decode('utf-8').splitlines(True)
   new=cur_path.read_text(encoding='utf-8').splitlines(True)
   print(''.join(difflib.unified_diff(old, new, fromfile='a/plugins/<plugin>/__init__.py', tofile='b/plugins/<plugin>/__init__.py')))
   PY
   ```
9. Test against MoviePilot at the configured host (for this user, reachable from Hermes at `http://172.17.0.1:3000`) using the token-safe helper, never echoing API keys:
   ```bash
   python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/installed --compact --raw-out /tmp/mp_plugins_installed.json
   python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/PluginManagerVue/online_info/<PluginId> --compact --raw-out /tmp/online_info.json
   python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/PluginManagerVue/plugins --compact --raw-out /tmp/plugins.json
   python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py POST /api/v1/plugin/PluginManagerVue/reinstall --json '{"plugin_id":"<PluginId>"}' --compact --raw-out /tmp/reinstall.json
   python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/form/<PluginId> --compact --raw-out /tmp/plugin_form.json
   ```
   Verify after reinstall that PluginManagerVue's plugin list, `online_info`, `last_reload`, and the plugin form/config all reflect the new version/changed fields. When Docker socket access is available, prefer true pre-commit local testing for contained plugin changes: back up the actual plugin file in `/config/temp`, `docker cp` the patched file into `/app/app/plugins/<plugin>`, run `python -m py_compile` inside the MoviePilot container, reload/start the plugin through API endpoints, and inspect sanitized Docker logs for the expected behavior before committing/pushing. Never dump container env, plugin configs, auth tokens, cookies, or full status payloads; parse and redact/drop secret-like fields.
10. For hot-deployed local verification, do not trust `PluginManagerVue/online_info/<PluginId>` as the sole source of truth. It can continue showing the published market metadata/version even after the in-container plugin file has been replaced and reloaded successfully. Prefer this verification order: (a) inspect `/app/app/plugins/<plugin>/__init__.py` in the container, (b) reload the plugin (on this user's instance `GET /api/v1/plugin/reload/<PluginId>` works), (c) check PluginManagerVue's live plugin list/status, and (d) confirm the reload/version in sanitized MoviePilot logs. Treat `online_info` as market state, not definitive live-code state, during local hot-patch testing.
11. After pushing a manifest version bump, verify remote state with the GitHub API or `git ls-remote`, not only `raw.githubusercontent.com/main/...`: GitHub raw CDN can remain stale for minutes and MoviePilot/PluginManagerVue may still show the old version until that cache refreshes. A commit-SHA raw URL or GitHub Contents API can show the new version immediately.
12. If direct deployment is needed, first verify whether Hermes can see MoviePilot's mounted plugin directory. If not, produce a patch/diff and ask the user to copy it or mount the plugin path into Hermes. In this environment, Docker CLI may exist but fail to connect to `/var/run/docker.sock`; do not assume container filesystem access.

## Current known repo

- `DzAvril/MoviePilot-Plugins` can be inspected via GitHub API.
- SSH authentication to `git@github.com` succeeded in this environment, but clone/fetch timed out with sideband disconnect; codeload zip download succeeded.
- Local extracted path used: `/opt/data/home/repos/MoviePilot-Plugins`.
- A real git clone can be placed at `/opt/data/home/repos/MoviePilot-Plugins-git` for commits/pushes.
- Top-level structure includes `plugins/`, `plugins.v2/`, `icons/`, `package.json`, `package.v2.json`, and `README.md`.

## Pitfalls

- Seeing GitHub issues is not enough to analyze a plugin bug; get the actual source first.
- Public GitHub API may hit unauthenticated rate limits (`HTTP 403: rate limit exceeded`). Use `gh`/token if available, or wait/fallback to already downloaded source.
- The Hermes container may lack `unzip`; use Python `zipfile`.
- MoviePilot plugin APIs vary by installed plugins. Refresh/read plugin endpoints before assuming a specific reload/test route.
- For repository-backed plugin updates, remember the dual version bump: plugin source `plugin_version` and the correct package manifest (`plugins/` → `package.json`, `plugins.v2/` → `package.v2.json`). Changing only one is insufficient for MoviePilot update detection.
- `raw.githubusercontent.com/<branch>/...` may remain stale after a successful push. Verify with GitHub API (`/contents/package.json?ref=main`), `git ls-remote`, or a commit-SHA raw URL; wait before relying on MoviePilot/PluginManagerVue update status if it still reports the old version.
- Some `Stale` issues are already closed but not truly resolved. If no open stale issue exists, a closed stale feature/bug can be a valid target when the fix is locally reproducible/verifiable; after publishing, post the verification comment, remove `Stale`, add `resolved`, and ensure the issue is closed as completed.
- Do not let a broad hardening patch stand in for issue-driven work. If the user flags that changes are not clearly tied to GitHub issues, immediately roll back uncommitted/generalized edits, restore any direct container deployments by reinstalling/reloading the published plugin version, and restart from one issue's body/comments with a repro and minimal fix.
- Duplicate/overlapping stale issues can be closed without a new commit only when an existing pushed commit directly implements the requested behavior and the prior verification is concrete; the closing comment must cite that commit and verification, not imply new work was done.
- Do not expose MoviePilot API keys, site cookies, torrent URLs, or plugin secrets in logs or chat.
