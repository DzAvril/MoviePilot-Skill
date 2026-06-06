# RemoveLink exclude directory path-boundary fix

Use this note when handling RemoveLink issues where an `exclude_dirs` / “不删除目录” entry incorrectly matches a similarly named sibling path.

## Issue pattern

Example from DzAvril/MoviePilot-Plugins #14 problem 1:

- Monitor/source path: `/aaa/test`
- Hardlink/media path: `/aaa/test1`
- Exclude directory configured as: `/aaa/test`
- Old behavior: files under `/aaa/test1` were logged as “在不删除目录中，不处理” because `exclude_dir in str(file_path)` did substring matching.
- Correct behavior: `/aaa/test` should exclude only itself and children like `/aaa/test/sub/...`; it must not exclude siblings like `/aaa/test1` or `/aaa/test-child`.

## Root cause

`RemoveLink.__is_excluded()` used substring matching:

```python
if exclude_dir and exclude_dir in str(file_path):
    return True
```

This treats `/aaa/test` as a keyword rather than a directory boundary.

## Fix pattern

Keep the fix minimal and issue-scoped:

1. Add path normalization helper that does not require paths to exist:
   ```python
   os.path.normcase(os.path.normpath(str(Path(config_path).expanduser())))
   ```
2. Compare with `os.path.commonpath([normalized_path, normalized_base]) == normalized_base`.
3. Strip empty/whitespace-only config lines.
4. Do not bundle unrelated hardlink/state/reload hardening into this issue.

## Regression recipe

Local test should prove both the old failure and new behavior:

```python
plugin.exclude_dirs = "/aaa/test"
assert plugin._RemoveLink__is_excluded(Path("/aaa/test/movie.nfo")) is True
assert plugin._RemoveLink__is_excluded(Path("/aaa/test/sub/movie.nfo")) is True
assert plugin._RemoveLink__is_excluded(Path("/aaa/test1/movie.nfo")) is False
assert plugin._RemoveLink__is_excluded(Path("/aaa/test-child/movie.nfo")) is False
```

Container verification on this user’s MoviePilot should import the live plugin from `/app/app/plugins/removelink`, call the same assertions, then reload via:

```bash
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/reload/RemoveLink --compact --raw-out /tmp/mp_reload_removelink_issue14.json
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/PluginManagerVue/plugins --compact --raw-out /tmp/mp_plugins_removelink_issue14.json
```

Verify plugin list shows `RemoveLink <new-version>`, `status=running`, `has_update=false`.

## Closure boundary

If the same GitHub issue also reports platform-specific watcher behavior such as 飞牛/NFS “新增有反应，删除无反应”, do **not** claim that is fixed by this path-boundary patch unless that environment is actually reproduced. Comment explicitly that only the path mis-match portion was fixed and verified.
