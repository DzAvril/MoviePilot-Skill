# RemoveLink stale hardlink state fix

Use this note when handling RemoveLink reports where hardlink cleanup hangs or stops after the user manually deletes files in quick succession.

## Issue pattern

DzAvril/MoviePilot-Plugins #12:

- User manually deletes the source file first.
- Before RemoveLink finishes processing, the user also manually deletes the hardlink.
- `file_state` can still contain the hardlink path even though the filesystem path is gone.
- Old behavior: cleanup loop calls `file.unlink()` on the stale path, raises `FileNotFoundError`, and interrupts the current cleanup/deletion-queue flow; monitoring appears stuck until MoviePilot restarts.

## Root cause

RemoveLink iterated `file_state` entries with the deleted inode and unconditionally unlinked matched paths:

```python
file = Path(path)
file.unlink()
```

A watchdog/manual-deletion race can leave stale state. Treating a missing linked path as fatal is wrong because the desired end state is already true: the hardlink is gone.

## Fix pattern

Keep the change issue-scoped:

1. Centralize tracked hardlink deletion in a helper equivalent to `_unlink_tracked_file(file, state_key, action) -> bool`.
2. Preserve exclude-dir checks before deletion.
3. Catch `FileNotFoundError`, remove the stale `file_state` entry, log a warning, and return `False` so notification/history/torrent side effects are not run for a file that was already gone.
4. Catch broader `OSError`, log and return `False` without crashing the batch.
5. On successful unlink, remove the `file_state` entry and return `True`.
6. Use the helper in both delayed deletion (`_execute_delayed_deletion`) and immediate deletion (`handle_deleted`) paths.
7. Bump both `plugins/removelink/__init__.py::plugin_version` and root `package.json` `RemoveLink.version`/history because RemoveLink is a v1 plugin under `plugins/`.

## Regression recipe

A standalone test can import the plugin with stubs for MoviePilot/watchdog modules, then exercise both flows:

- delayed path: create source + state entries for a missing stale hardlink and a live hardlink using the source inode; delete source; run `_execute_delayed_deletion`; assert the stale state entry is removed, live hardlink is deleted, and `task.processed` is true.
- immediate path: set `_delayed_deletion=False`; create `file_state` entries for deleted source and stale missing hardlink; call `handle_deleted(source)`; assert both stale entries are removed without raising.

Also run:

```bash
python3 -m py_compile plugins/removelink/__init__.py
python3 -m json.tool package.json >/tmp/package.json.valid
git diff --check
```

## MoviePilot verification

After push, verify repository state with GitHub Contents API or commit-SHA raw URL, then reinstall/reload in MoviePilot:

```bash
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py POST /api/v1/plugin/PluginManagerVue/reinstall --json '{"plugin_id":"RemoveLink"}' --compact --raw-out /tmp/removelink_reinstall.json
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/PluginManagerVue/plugins --compact --raw-out /tmp/removelink_plugins.json
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/reload/RemoveLink --compact --raw-out /tmp/removelink_reload.json
```

Parse `PluginManagerVue/plugins` and confirm `RemoveLink` is `running`, expected version is shown, and `has_update=false`.

## Issue closure notes

For stale-closed GitHub issues, it is still valid to comment and close as completed after a real fix is pushed and verified. Remove `Stale`, add `resolved`, and include commit link plus verification summary with the Codex attribution line.