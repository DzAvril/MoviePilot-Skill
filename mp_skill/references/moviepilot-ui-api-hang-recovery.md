# MoviePilot UI/API hang recovery

Use this note when the MoviePilot web UI loads static assets or a login shell but pages/API calls hang, time out, or show 502.

## Symptom pattern

- `/` returns HTML/JS/CSS quickly, but `/api/v1/*` endpoints hang, return nginx 499/502, or time out.
- Browser may show login/dashboard shell but never finishes loading data.
- Direct unauthenticated API probes should normally return fast `401`; a slow timeout is a backend event-loop/startup blockage, not an auth failure.
- In host-network containers, probing `127.0.0.1:3000` from Hermes can be misleading; probe the user-facing host/IP or `172.17.0.1:3000`, and optionally probe inside the MoviePilot container.

## Fast triage

1. Verify layers separately:
   - Static UI: `GET /`
   - Public API: `GET /api/v1/login/wallpapers`
   - Protected API: `GET /api/v1/user/current` should return fast `401` when unauthenticated.
2. Check nginx access log for `/api/v1/*` `499`/`502` while `/assets/*` is `200`.
3. Check direct backend from inside the container (`127.0.0.1:3001`) to separate nginx from Uvicorn/backend blockage.
4. Tail bounded/redacted logs for plugin reinitialization or repeated plugin slow operations. Repeated `p115strmhelper` slow 115 calls such as `life_behavior_detail_app` can keep the API unresponsive even when the UI shell is served.

## Safe recovery order

1. Back up config before edits. Legacy/some deployments use `/config/user.db`, but newer MoviePilot V2 instances may use PostgreSQL even while `/config/user.db` still exists. Do not assume raw SQLite is authoritative.
2. Prefer MoviePilot's own config operator inside the container for active config reads/writes when the app imports successfully:
   ```bash
   docker exec MoviePilot python3 - <<'PY'
   from app.db.systemconfig_oper import SystemConfigOper
   from app.schemas.types import SystemConfigKey
   op = SystemConfigOper()
   installed = op.get(SystemConfigKey.UserInstalledPlugins) or []
   print(len(installed), installed[:10])
   PY
   ```
   If this reports PostgreSQL connection logs, update via `SystemConfigOper().set(...)` rather than editing `/config/user.db` directly; otherwise the UI may keep reinstalling plugins from the real DB state.
3. Temporarily disable high-risk startup/dashboard plugins in active `systemconfig` and remove them from `UserInstalledPlugins` if necessary. In the observed incident the useful quarantine set was:
   - `P115StrmHelper`
   - `MCPServer`
   - `PluginHeatMonitor`
   - `PluginAutoUpdate`
   - `PluginReload` when it is retriggering plugin reloads
4. For JSON config rows, set obvious booleans like `enabled`, `enable`, `update`, `onlyonce`, and plugin-specific monitor flags to `false`; for MCPServer also disable dashboard auto-refresh/plugin tools when present. Also scrub dashboard/plugin-order references if the UI or loader keeps trying to import disabled plugins.
5. If the plugin still starts via hot-load/auto-update, quarantine its runtime/source directory temporarily, but **move all matching plugin directories out of plugin roots**, including renamed `.disabled_*` copies. MoviePilot's dependency scanner can still inspect renamed folders under `/app/app/plugins`, `/config/plugins`, `/config/temp/plugin_backup`, or `/config/plugins_backup`; those stale copies can trigger PIP conflict checks and plugin reinitialization even when the canonical plugin folder is absent.
6. Restart MoviePilot. If Docker reports `tried to kill container, but did not receive an exit event`, inspect state; the container may already be `Exited (137)`, then start it explicitly.
7. Verify success by checking that:
   - `/` returns `200`
   - `/api/v1/login/wallpapers` returns fast `200`
   - `/api/v1/user/current` returns fast `401` unauthenticated

## Restoring quarantined plugins

When the user says the plugins are necessary, do **not** restore the entire suspect set at once. Explain that restoring all suspected startup plugins can immediately re-hang `/api/v1/*`, then recover by restoring one plugin at a time:

1. Confirm the baseline API is healthy (`/`, public API, protected `401`).
2. Restore exactly one plugin's active config and source directory.
3. Restart or reload only what is required.
4. Wait through startup and verify the three probes again.
5. If API hangs, roll that plugin back before trying the next one.

For P115StrmHelper specifically, logs showing PIP/runtime conflicts such as `numpy`/`pillow`/`pyyaml` version mismatches followed by `正在重新初始化插件` or `cannot join thread before it is started` indicate dependency/reinit blockage. Do not patch MoviePilot core dependency logic as a first move; first remove all stale P115StrmHelper copies from plugin roots, update active config through `SystemConfigOper`, and re-verify.

## Reporting

Tell the user whether the UI shell, public API, and protected API are each reachable. Label plugin quarantine as a temporary recovery action and name the suspected blocking plugin(s). If a plugin is necessary, propose staged restoration with rollback rather than claiming it was permanently deleted. Avoid dumping raw MoviePilot logs because startup logs can include secrets from config/env.