# MoviePilot Plugin Local Testing Prerequisites

Use this note when the user wants plugin issues fixed and tested locally before publishing to GitHub / MoviePilot market.

## Preferred workflow for this user

The user prefers plugin fixes to be tested locally against MoviePilot before committing/pushing when possible:

1. Inspect issue and source.
2. Patch in a real git working tree.
3. Run local static checks.
4. Deploy the patched plugin to a testable MoviePilot instance or plugin directory.
5. Reload/restart only what is needed.
6. Verify behavior via API, form/config, logs, and actual plugin side effects.
7. Only then bump versions, commit, push, update MoviePilot through PluginManagerVue, and close/comment the issue.

## Prerequisites that make local testing effective

### 1. Writable plugin directory from Hermes

Hermes needs access to the actual MoviePilot plugin directory or a staging/test plugin directory. Without this, testing is limited to push-to-GitHub then reinstall through MoviePilot, which is not true pre-commit local testing.

Useful access patterns:

- Mount MoviePilot plugin/config directory into Hermes.
- Or expose the host path discovered from `docker inspect`.
- Or use `docker cp` / `docker exec` if Docker access is available.

### 2. Readable MoviePilot logs

Many plugin fixes need log-level verification. Provide one of:

- MoviePilot logs directory mounted read-only into Hermes.
- Docker logs access for the MoviePilot container.
- A stable MoviePilot log API endpoint if available.

### 3. Safe test environment or fixtures

For plugins that mutate downloads, files, subscriptions, or site state, avoid testing directly on production data unless the user explicitly accepts risk.

Prefer:

- Test MoviePilot instance with separate config/database.
- Test qBittorrent/Transmission instance or disposable tasks.
- Fixture media directories and sample files.
- Backup original plugin config before mutation and restore after testing.

### 4. Stable reload/deploy mechanism

Known useful endpoints for the user's current MoviePilot instance:

```bash
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/installed --compact --raw-out /tmp/mp_plugins_installed.json
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/PluginManagerVue/plugins --compact --raw-out /tmp/mp_plugins.json
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/PluginManagerVue/online_info/<PluginId> --compact --raw-out /tmp/mp_online_info.json
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py POST /api/v1/plugin/PluginManagerVue/reinstall --json '{"plugin_id":"<PluginId>"}' --compact --raw-out /tmp/mp_reinstall.json
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/form/<PluginId> --compact --raw-out /tmp/mp_form.json
```

Also try plugin reload where available:

```bash
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/reload/<PluginId> --compact --raw-out /tmp/mp_reload.json
```

### 5. Docker-assisted live plugin patching

When Hermes has Docker socket access to the host, use it to make pre-commit local validation concrete:

1. Identify the actual loaded plugin path inside MoviePilot, usually `/app/app/plugins/<plugin_id>` for installed online plugins.
2. Back up the target files into `/config/temp` before overwriting them.
3. `docker cp` patched files from the git worktree into the MoviePilot container.
4. Run `python -m py_compile` inside the container on the deployed files.
5. Reload/start/restart only the affected plugin through MoviePilot plugin APIs when possible; restart the whole MoviePilot container only if plugin reload is insufficient.
6. Verify with sanitized Docker logs and plugin APIs. Do not print env vars, raw plugin config, token-bearing status responses, cookies, passkeys, or torrent URLs.
7. If the live test surfaces an environment-only problem (for example an existing plugin venv missing dependencies and the plugin only installs dependencies during venv creation), document it separately from the source fix and avoid bundling unrelated changes unless they are required for the issue.

## Static checks before deploy/commit

At minimum:

```bash
python3 -m py_compile plugins/<plugin>/__init__.py
```

For broader safety:

```bash
python3 -m py_compile $(find plugins plugins.v2 -name '*.py')
```

Also verify:

- Correct version bump pair: plugin source `plugin_version` + correct manifest version.
- v1 plugins under `plugins/` use root `package.json`.
- v2 plugins under `plugins.v2/` use `package.v2.json`.
- Matching `history` entry exists in the manifest.
- `git diff` only contains intended changes.

## Docker access tradeoff

If the user wants Hermes to manage all host containers, Docker socket access is useful, but raw `/var/run/docker.sock` access is effectively host-root equivalent. Prefer Docker Socket Proxy for day-to-day use and only enable high-risk APIs temporarily.

For MoviePilot plugin testing, the safest powerful setup is:

- Docker/container management via socket proxy for list/logs/restart/inspect.
- Direct mount of MoviePilot plugin directory with write access.
- Direct mount of MoviePilot logs with read-only access.
- Temporary `docker exec` only when needed for deep debugging.
