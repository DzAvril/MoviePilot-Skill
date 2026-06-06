# RemoveLink OpenList/Alist precise empty-directory deletion (#33)

## Trigger

Use this reference when working on RemoveLink STRM/cloud-disk cleanup issues, especially OpenList/Alist empty directory cleanup reports like GitHub issue #33.

## Root cause

MoviePilot/OpenList's `/api/fs/remove_empty_directory` semantics are not "delete this directory if empty". It cleans empty directories **under** the provided path. Passing `/test/dir/nulldirectory` will scan/remove children of `nulldirectory`, but will not delete `nulldirectory` itself.

For RemoveLink's STRM/cloud cleanup, changing the path to the parent and calling `remove_empty_directory` is also undesirable: it may recursively scan sibling episode/show folders and waste work or touch unrelated directories.

## Fix pattern

In `plugins/removelink/__init__.py`, route Alist/OpenList empty directory deletion through a helper that preserves the exact target path but forces the storage chain to use the generic remove semantics:

- `_delete_storage_empty_folders(...)` calls `_delete_storage_empty_dir(storage_type, current_item)` instead of `self._storagechain.delete_file(current_item)` for directories.
- `_delete_storage_empty_dir(...)` delegates normally for other storage types.
- For `alist`/`openlist`, clone/copy the `FileItem` and set `type="file"` before `delete_file(...)`, which maps to `/api/fs/remove` in the adapter instead of `/api/fs/remove_empty_directory`.
- Preserve/fill `name` with `Path(path).name` when needed.

This is intentionally a targeted adapter workaround; do not change the traversal to parent-directory cleanup unless the user explicitly approves broader scanning semantics.

## Regression recipe

A local regression can be run without a real OpenList account by stubbing MoviePilot imports and `StorageChain`:

```bash
python3 tests/removelink_storage_empty_dir_regression.py
```

The test should model:

- Deleted STRM/video path: `/test/dir/nulldirectory/movie.mkv`
- Current empty directory: `/test/dir/nulldirectory`
- Mock `delete_file(file_item)` records `/api/fs/remove_empty_directory` when `file_item.type == "dir"`, otherwise `/api/fs/remove`.

Expected assertion:

```text
('/api/fs/remove', '/test/dir/nulldirectory', 'file', 'nulldirectory')
```

and **no** `/api/fs/remove_empty_directory` calls.

## Version/update checklist

For v1 RemoveLink under `plugins/removelink`:

1. Bump `plugin_version` in `plugins/removelink/__init__.py`.
2. Bump the root `package.json` RemoveLink entry version.
3. Add a `history` entry, e.g. `v2.11`: `修复STRM云盘空目录清理调用 remove_empty_directory 无法删除指定空目录的问题`.

## Verification checklist

```bash
python3 tests/removelink_storage_empty_dir_regression.py
python3 -m py_compile plugins/removelink/__init__.py tests/removelink_storage_empty_dir_regression.py
python3 -m json.tool package.json >/tmp/package.json.check
git diff --check
python3 -m py_compile $(find plugins plugins.v2 -name '*.py')
```

After push, reinstall through MoviePilot plugin API and verify RemoveLink shows the new version, `running=true`, and `has_update=false`.

## Issue closure notes

When closing #33-style reports, cite the fix commit and note that the regression proves the exact target directory is deleted via `/api/fs/remove` without parent-directory `remove_empty_directory` scanning. End the comment with the Codex attribution line when Codex performed the implementation, e.g. `Submitted by Codex (gpt-5.5).`
