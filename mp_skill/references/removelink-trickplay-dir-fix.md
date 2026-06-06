# RemoveLink trickplay directory cleanup fix

Use this note when handling MoviePilot-Plugins `RemoveLink` issues about Jellyfin/Emby preview-image/trickplay folders not being deleted, or errors like:

```text
IsADirectoryError: [Errno 21] Is a directory: '<media-title>.trickplay'
清理刮削文件发生错误：[Errno 21] Is a directory: '.../.trickplay'
```

## Root cause

`RemoveLink.delete_scrap_infos()` and `delete_empty_folders()` originally treated all scrape-related artifacts as files and called `Path.unlink()`. Jellyfin can generate media-adjacent `<video-stem>.trickplay/` directories. Calling `unlink()` on these directories raises `IsADirectoryError`, so associated trickplay folders remain undeleted.

## Fix pattern

For `plugins/removelink/__init__.py`:

1. Import `shutil`.
2. Add a class-level directory suffix allowlist:

```python
SCRAP_DIR_SUFFIXES = [
    ".trickplay",
]
```

3. In `scrape_files_left(path)`, treat directories with suffixes in `SCRAP_DIR_SUFFIXES` as scrape artifacts; non-allowlisted directories should still return `False`.
4. In `delete_scrap_infos(path)`, when a same-prefix item is a directory and suffix is in `SCRAP_DIR_SUFFIXES`, delete it with `shutil.rmtree(file)` and log `删除刮削目录`.
5. In `delete_empty_folders(path)`, when clearing a directory that contains only scrape artifacts, use `shutil.rmtree()` for directories and `unlink()` for files.
6. Bump both versions for this v1 plugin:
   - `plugins/removelink/__init__.py`: `plugin_version`
   - root `package.json`: `RemoveLink.version` and history

## Regression recipe

Create a temp media folder containing:

```text
Season 01/
  Show S01E01 - 1080p.nfo
  Show S01E01 - 1080p.trickplay/1.bif
```

Call `delete_scrap_infos(Path('Season 01/Show S01E01 - 1080p.mkv'))` with `_delete_scrap_infos=True`; verify both `.nfo` and `.trickplay/` are gone.

Also verify parent cleanup with a folder that contains only `poster.jpg` and `<stem>.trickplay/`; calling `delete_empty_folders()` should remove the scrape files/directories and then the empty parent without `IsADirectoryError`.

## Live MoviePilot verification

After patching local git files:

```bash
python3 -m py_compile plugins/removelink/__init__.py
python3 -m json.tool package.json >/dev/null
```

Deploy to the live container only after backing up:

```bash
ts=$(date +%Y%m%d%H%M%S)
docker exec MoviePilot sh -lc "cp /app/app/plugins/removelink/__init__.py /config/temp/removelink_init.py.$ts.trickplay.bak"
docker cp plugins/removelink/__init__.py MoviePilot:/app/app/plugins/removelink/__init__.py
```

Run a container-side regression using MoviePilot's venv so app dependencies resolve:

```bash
docker exec MoviePilot sh -lc '/opt/venv/bin/python /tmp/test_removelink_trickplay_container.py'
```

Expected output:

```text
CONTAINER_TRICKPLAY_REGRESSION_OK
```

Read back the plugin list with `scripts/mp_request.py` and confirm `RemoveLink` reports the bumped version and `running` status. Delete temporary scripts and raw API response files after verification.
