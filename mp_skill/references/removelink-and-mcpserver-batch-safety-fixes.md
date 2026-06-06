# RemoveLink state-safety and MCPServer startup-safety fixes

Session note for future MoviePilot plugin bug-fix work. This records reusable patterns discovered while batch-fixing stale issues, not a completed-work log.

## RemoveLink hardlink deletion safety

Symptoms covered by this class of bugs:

- hardlink cleanup hangs or leaves stale state after source deletion;
- source/hardlink deletion behaves incorrectly across mounted folders/NAS paths;
- excluded directory matching is too broad because it uses substring checks;
- plugin reload/save/stop executes delayed deletion tasks immediately, bypassing the delay window and risking deletes during downloads/moves.

Reusable fix pattern:

1. Track file identity with both `st_dev` and `st_ino`; do not rely on inode alone across mounts/filesystems.
2. Keep `deleted_device` in delayed deletion tasks so delayed execution uses the same identity comparison.
3. Centralize matching in helpers equivalent to:
   - `_same_file_identity(file_info, inode, device)`
   - `_matching_link_paths(deleted_inode, deleted_device, source_path)`
   - `_delete_linked_file(file, source_path, immediate=False)`
4. Use path-boundary comparisons for configured monitor/exclude directories:
   - normalize with `Path(...).expanduser()`, `os.path.normpath`, `os.path.normcase`;
   - compare via `os.path.commonpath`, not `exclude_dir in str(path)`.
5. In service teardown/reload, discard pending delayed deletion tasks instead of executing them immediately. Plugin reloads and config saves are not user confirmation to delete early.
6. For private double-underscore methods in container regression scripts, remember Python name-mangling: call `plugin._RemoveLink__is_excluded(...)`, not `plugin.__is_excluded(...)`.

Verification recipe:

- Local: create source + hardlink in a temp dir, store `FileInfo(st_dev, st_ino, now)`, assert matching returns only the hardlink and excludes the source path.
- Re-organize/re-hardlink regression: create source + old library hardlink + new library hardlink for a normal non-BDMV `.mkv`; set the new path `add_time` later than the old path but earlier than the delayed deletion task timestamp; delete the old link; assert delayed deletion preserves the new link and produces no notification/history/torrent/scrap side effects. This catches watcher event ordering where create arrives before delete processing.
- Path exclusion: assert `/media/foo` does not match `/media/foo2`, while `/media/foo/bar.mkv` matches `/media/foo`.
- Reload safety: enqueue a `DeletionTask`, call teardown/destructor path, assert queue is cleared but linked file still exists.
- Watcher-backend compatibility: force `watchdog` imports to fail, provide a stub `watchfiles.watch`, and assert RemoveLink still imports, initializes monitoring, and starts cleanly. This should exist both as a repository regression script and as a container-side live check against `/app/app/plugins/removelink/__init__.py` so the deployed code path is proven, not just the worktree copy.
- Run `py_compile`, JSON manifest validation, and `git diff --check`.
- Container: copy a small regression script into MoviePilot and run with `/opt/venv/bin/python`, using the actual deployed `app.plugins.removelink.RemoveLink`. For issue #43-style fixes, run the script before and after hot-copying the patch if possible: pre-patch should delete the new hardlink / show side effects, post-patch should preserve the link with zero side effects, then reload with `GET /api/v1/plugin/reload/RemoveLink` and verify logs show the new version. For watcher-backend compatibility fixes, prefer a container script that blocks `watchdog` via a custom import hook rather than merely deleting `sys.modules`, because the base image may still have watchdog installed and otherwise mask the fallback path.

## RemoveLink watchdog -> watchfiles compatibility

Symptoms covered by this class of bugs:

- plugin import/startup fails on newer MoviePilot images with `ModuleNotFoundError: No module named 'watchdog'`;
- MoviePilot image/runtime ships `watchfiles` but not `watchdog`, so monitor-based plugins break at import time.

Reusable fix pattern:

1. Keep the existing `watchdog` path as the preferred implementation when available.
2. Wrap the `watchdog` imports in `try/except ImportError`.
3. In the fallback path, provide a minimal observer adapter around `watchfiles.watch(...)` that maps `Change.added`/`deleted` events into the plugin's expected `on_created`/`on_deleted` callback shape.
4. Keep the fallback API-compatible with the plugin's current observer lifecycle (`schedule`, `start`, `stop`, `join`) so the rest of the plugin stays unchanged.
5. Bump both `plugin_version` and the correct package manifest entry/history when publishing the fix.

Live-verification notes:

- During local hot-patch testing, backup the in-container plugin file to `/config/temp/...`, `docker cp` the patched file into `/app/app/plugins/removelink/__init__.py`, run `/opt/venv/bin/python -m py_compile`, then reload via `GET /api/v1/plugin/reload/RemoveLink`.
- Verify the live version from PluginManagerVue's plugin list and sanitized MoviePilot logs (`加载插件：RemoveLink 版本：...`). `PluginManagerVue/online_info/RemoveLink` can stay on the published market version until the GitHub/package metadata is updated, so do not use it as the only success criterion.

## MCPServer startup command and database path safety

Symptoms covered by this class of bugs:

- logs expose `--auth-token` or `--access-token` values because the process command is logged verbatim;
- MCP tools that query MoviePilot's SQLite database fail in environments where the server subprocess cannot infer the DB location, especially Windows/container path differences.

Reusable fix pattern:

1. Add a command formatter that redacts values after secret-bearing options such as `--auth-token` and `--access-token` before logging.
2. Build subprocess command with an explicit `--database-path` argument, usually `Path(settings.CONFIG_PATH) / "user.db"` inside MoviePilot.
3. Add `--database-path` CLI handling to both Streamable HTTP (`server.py`) and SSE (`sse_server.py`) entrypoints.
4. In each entrypoint, set `os.environ["MOVIEPILOT_DB_PATH"] = database_path` when supplied so existing tool code can consume the location without invasive rewrites.
5. Version bump rules still apply: MCPServer is v2, so bump both `plugins.v2/mcpserver/__init__.py::plugin_version` and `package.v2.json` `MCPServer.version`/history.

Verification recipe:

- Local stub test: instantiate `ProcessManager` with `_config` containing fake `auth_token` and `access_token`; assert `_build_start_command()` includes `--database-path /config/user.db`; assert `_format_command_for_log(cmd)` contains `[REDACTED]` and not the fake secrets.
- Container test: run the same assertions against actual `app.plugins.mcpserver.ProcessManager` with `/opt/venv/bin/python` and `settings.CONFIG_PATH`.
- Reload MCPServer via MoviePilot API and verify plugin list shows the expected version, `status=running`, and `has_update=false`.

## Batch-fix discipline

When several issues may be covered by one hardening patch, do not auto-close all plausible issues. Before closing each issue, map the issue body to the exact fixed behavior and include the verification that covers it. For client-specific or environment-specific reports that still cannot be locally reproduced, leave them open/unchanged and report the validation gap to the user.