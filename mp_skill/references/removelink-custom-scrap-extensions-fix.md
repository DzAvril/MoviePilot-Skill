# RemoveLink custom scrap extensions fix

Use this note when fixing or verifying RemoveLink issues about custom metadata/scrap files such as `.txt`, `.json`, or Jellyfin/Emby-style `-mediainfo.json` files not being cleaned with the media file.

## Problem

RemoveLink previously had a fixed `SCRAP_EXTENSIONS` list and compared only `Path.suffix.lower()`. That misses multi-suffix/name-ending metadata files such as:

- `Movie Name (2026)-mediainfo.json`
- user-specific `.txt` / `.json` sidecar files

It also means parent-directory cleanup and STRM cloud scrap cleanup ignore user-desired custom scrap files.

## Fix pattern

For v1 `plugins/removelink` fixes, update both:

- `plugins/removelink/__init__.py` `plugin_version`
- root `package.json` `RemoveLink.version` and `history`

Implementation pattern used for v2.8:

1. Add config fields:
   - `custom_scrap_extensions = ""`
   - `_custom_scrap_extensions = []`
2. In `init_plugin()`, load `config.get("custom_scrap_extensions") or ""` and parse it.
3. Add parser supporting newline, comma, and Chinese comma separators:
   - trim whitespace
   - lowercase
   - if an entry starts with neither `.` nor `-`, prefix `.`
   - deduplicate while preserving order
4. Add `_scrap_extensions()` to combine built-in `SCRAP_EXTENSIONS` with parsed custom entries.
5. Add `_is_scrap_file(path)` using `path.name.lower().endswith(extension)` rather than only `path.suffix`; this supports `-mediainfo.json`.
6. Replace scrap-file tests in:
   - `delete_scrap_infos()`
   - `scrape_files_left()` / parent directory cleanup
   - torrent-event filtering for scrap files
   - STRM/cloud scrap cleanup and cloud empty-directory cleanup
7. Add a `VTextarea` to `get_form()`:
   - model: `custom_scrap_extensions`
   - label: `自定义刮削文件后缀`
   - placeholder example: `.txt\n.json\n-mediainfo.json`
8. Add default value `"custom_scrap_extensions": ""`.

## Regression recipe

Local test should stub MoviePilot dependencies, load `plugins/removelink/__init__.py`, and verify:

- parser converts `txt, .json\n-mediainfo.json，xml` to `['.txt', '.json', '-mediainfo.json', '.xml']`
- deleting `Movie Name (2026).mkv` removes:
  - `Movie Name (2026).txt`
  - `Movie Name (2026).json`
  - `Movie Name (2026)-mediainfo.json`
  - built-in `Movie Name (2026).nfo`
- unrelated `Other.json` remains
- a directory containing only custom scrap files is cleaned by `delete_empty_folders()`
- `get_form()` includes `custom_scrap_extensions`

Run:

```bash
cd /opt/data/home/repos/MoviePilot-Plugins-git
python3 -m py_compile plugins/removelink/__init__.py
python3 /tmp/test_removelink_custom_scrap_extensions.py
python3 -m json.tool package.json >/dev/null
git diff --check
```

## Live MoviePilot verification

Deploy to the actual MoviePilot plugin path after backing up:

```bash
TS=$(date +%Y%m%d%H%M%S)
docker exec MoviePilot sh -lc "cp /app/app/plugins/removelink/__init__.py /config/temp/removelink_init.py.${TS}.customscrap.bak"
docker cp /opt/data/home/repos/MoviePilot-Plugins-git/plugins/removelink/__init__.py MoviePilot:/app/app/plugins/removelink/__init__.py
```

Run container regression with MoviePilot's venv, not system Python:

```bash
docker cp /tmp/test_removelink_custom_scrap_container.py MoviePilot:/tmp/test_removelink_custom_scrap_container.py
docker exec MoviePilot sh -lc '/opt/venv/bin/python -m py_compile /app/app/plugins/removelink/__init__.py && /opt/venv/bin/python /tmp/test_removelink_custom_scrap_container.py'
```

Expected marker:

```text
CONTAINER_CUSTOM_SCRAP_REGRESSION_OK
```

Reload the plugin with GET (POST returns 405 on this instance):

```bash
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/reload/RemoveLink --output /tmp/mp_reload_removelink_custom.json
```

Then verify plugin list reads the new version and clean sensitive temp files:

```bash
python3 /opt/data/skills/productivity/moviepilot-api-control/scripts/mp_request.py GET /api/v1/plugin/PluginManagerVue/plugins --output /tmp/mp_plugins_removelink_custom.json
rm -f /tmp/mp_skill_raw_*.json /tmp/mp_*removelink_custom*.json
```

## Pitfalls

- Do not use only `Path.suffix` for custom extensions; it cannot distinguish `-mediainfo.json` from generic `.json`.
- Keep deletion matching constrained by the media file stem/prefix so unrelated `Other.json` is not deleted.
- Reload endpoint for `RemoveLink` on this MoviePilot instance is `GET /api/v1/plugin/reload/RemoveLink`; `POST` returned HTTP 405.
- After `docker cp`, MoviePilot may still show the previous plugin version until the plugin is reloaded.
- Container tests importing MoviePilot plugins should use `/opt/venv/bin/python`; system `python` may miss app dependencies.
