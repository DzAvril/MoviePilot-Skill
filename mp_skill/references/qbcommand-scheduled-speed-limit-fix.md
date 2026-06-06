# QbCommand Scheduled Speed Limit Fix

Session-proven fix/verification recipe for `DzAvril/MoviePilot-Plugins` QbCommand requests such as issue #37: users want downloader speed limits to run on schedules, not only pause/resume schedules.

## Problem

`QbCommand` supported cron fields for pausing/resuming downloaders, and manual/initial upload/download speed limit values. It did not expose scheduled speed-limit start/end controls. A naive implementation that calls `set_limit()` during plugin initialization also breaks the desired "limit only during this time window" behavior because saving/enabling the plugin applies the limit immediately.

Related issues:
- #37: "下载器远程操作定时任务设置是否可以设置限速周期"
- #24: similar request for scheduled speed-limit switching

## Fix pattern

For v2 QbCommand (`plugins.v2/qbcommand`, manifest `package.v2.json`):

1. Add plugin fields/config keys:
   - `_limit_cron`
   - `_unlimit_cron`
2. Load and persist them alongside `_pause_cron` and `_resume_cron` in `init_plugin()` / `update_config()` payloads.
3. Change `get_service()` from early-return pause/resume branches to an accumulating `services = []` list, so pause, resume, limit, and unlimit schedules can coexist.
4. Add scheduled handlers:
   - `apply_speed_limit()` -> `set_limit(self._upload_limit, self._download_limit)`
   - `clear_speed_limit()` -> `set_limit(0, 0)`
5. Add form fields near existing pause/resume cron controls:
   - `limit_cron` label: `限速开始周期`
   - `unlimit_cron` label: `限速取消周期`
6. Important semantic guard: if `limit_cron` is configured, do **not** call `set_limit()` during plugin initialization/config save. Let the scheduled handler apply the limit at the requested time. If no `limit_cron` is configured, preserve the old immediate-apply behavior.
7. Bump both versions:
   - `plugins.v2/qbcommand/__init__.py`: `plugin_version`
   - `package.v2.json`: `QbCommand.version` and `history`

## Local regression idea

Use a small fake downloader service and instantiate `QbCommand` (or a subclass that overrides `service_info` / downloader type helpers):

- Set `_enabled=True`, `_limit_cron='0 18 * * *'`, `_unlimit_cron='0 8 * * *'`, `_upload_limit=256`, `_download_limit=1024`.
- Assert `get_service()` returns `DownloaderLimit` and `DownloaderUnlimit` with funcs bound to `apply_speed_limit` and `clear_speed_limit`.
- Call `apply_speed_limit()` and assert fake downloader received `(download_limit=1024, upload_limit=256)`.
- Call `clear_speed_limit()` and assert fake downloader received `(0, 0)`.
- Assert `get_form()` contains both `limit_cron` and `unlimit_cron` models.

Expected marker used in session: `QBCOMMAND_LIMIT_CRON_REGRESSION_OK`.

## Live MoviePilot verification

1. Back up and deploy patched file:
   ```bash
   docker exec MoviePilot sh -lc 'mkdir -p /config/temp && cp /app/app/plugins/qbcommand/__init__.py /config/temp/qbcommand_init.py.$(date +%Y%m%d%H%M%S).bak'
   docker cp plugins.v2/qbcommand/__init__.py MoviePilot:/app/app/plugins/qbcommand/__init__.py
   docker exec MoviePilot sh -lc '/opt/venv/bin/python -m py_compile /app/app/plugins/qbcommand/__init__.py'
   ```
2. Run a container-side fake-downloader regression with `PYTHONPATH=/app /opt/venv/bin/python` so the real MoviePilot plugin imports are used. Expected marker: `CONTAINER_QBCOMMAND_LIMIT_CRON_OK`.
3. Reload through MoviePilot API:
   ```bash
   python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/reload/QbCommand --compact --raw-out /tmp/mp_reload_qb.json
   ```
4. Verify plugin list and form:
   - `PluginManagerVue/plugins` shows `QbCommand <new-version>`, `status=running`, `has_update=false`.
   - `/api/v1/plugin/form/QbCommand` includes form models `limit_cron` and `unlimit_cron`.

## Pitfalls

- `get_service()` originally used multiple early returns; adding a limit schedule as another branch can accidentally drop pause/resume schedules. Accumulate services instead.
- Do not immediately apply a nonzero limit on init when a schedule exists; that contradicts the feature request.
- This repo may have stale-labeled issues that are already closed but unresolved as feature requests. If no open stale issues exist, closed `Stale` issues with reproducible/implementable requests may still be worth resolving; comment, remove `Stale`, add `resolved`, and leave/ensure closed as completed.
- `raw.githubusercontent.com/main/package.v2.json` may show stale content immediately after push; use GitHub Contents API or commit-SHA URLs for version verification.
