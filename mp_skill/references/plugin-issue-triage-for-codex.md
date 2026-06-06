# MoviePilot Plugin GitHub Issue Triage for Codex Delegation

Use this note when the user asks to let Codex fix “remaining MP plugin issues” or to list issues that can be closed with local verification.

## Goal

Pick issues where a coding agent can reproduce the reported behavior with local mocks/regression scripts, then have Hermes review, test, and verify against MoviePilot when appropriate. Do not choose issues that require a real private tracker page, Android/Windows/NAS client behavior, or screenshots only unless the issue includes enough logs/HTML/fixtures to model locally.

## Workflow

1. Load `github-issues`, `codex`, `systematic-debugging`, and this MoviePilot skill.
2. Pull repository state and issue details before acting:
   ```bash
   git status --short
   git pull --ff-only origin main
   # Use GitHub REST/gh; fetch issue body plus comments and labels.
   ```
3. Filter out issues already labeled `resolved` unless the user explicitly asks to audit them.
4. Classify each unresolved issue:
   - **High local-closure fit:** exact stack trace/log, deterministic input/output, code path in plugin source, can mock MoviePilot/storage/downloader/SQLite/HTTP calls.
   - **Medium fit:** likely fixable with defensive logic but true environment differs; label the proof as partial.
   - **Low fit:** depends on real tracker HTML not provided, site credentials, Android/Windows GUI, SMB/NFS/inotify semantics, or user configuration screenshots only.
5. Prefer one issue per commit. If a previous commit already covers another issue, only close that issue after mapping the issue report to the exact code path and citing the existing proof.
6. When delegating to Codex, include: repo path, issue number/title/body summary, exact expected behavior, allowed files, required version bumps, required regression script shape, and `do not commit/push` unless explicitly desired.
7. After Codex returns, Hermes must independently review `git diff`, run the regression script, run `py_compile`, JSON validation for manifests, `git diff --check`, and if safe, reinstall/reload the plugin in MoviePilot and read back version/running state.

## Good Local-Closure Candidates Observed in DzAvril/MoviePilot-Plugins

These are patterns, not permanent status; always re-check live issue labels/comments and current code first.

- **RemoveLink storage/STRM path issues:** mock `StorageChain`, STRM path mappings, and filesystem events. Example: Alist/OpenList empty directory deletion must call precise `/api/fs/remove` semantics rather than parent `remove_empty_directory` scanning.
- **MCPServer token/auth startup issues:** mock MoviePilot `/api/v1/user/current` and login endpoints; verify Bearer access token and `X-API-KEY` manual token paths without printing secrets.
- **MCPServer tool schema compatibility:** generate all MCP tool schemas locally and assert provider constraints (e.g. no invalid top-level combinators or provider-rejected schema shapes). Mock user info with base64 avatar to ensure large/base64 fields are omitted or replaced.
- **MCPServer media search/download defensive handling:** mock MoviePilot search/download responses with `None`, missing fields, HTTP 200 + business failure, or BT-site-specific incomplete data; assert the tool returns clear failure text instead of false success or TypeError.
- **MCPServer SQLite path portability:** use a temp SQLite fixture and monkeypatch environment/path detection to avoid hard-coded `/config/user.db` assumptions. When fixing, inject `settings.CONFIG_PATH` into the MCP child process environment and make errors list all attempted `user.db` candidates; see `references/mcpserver-userdb-path-fix.md`.
- **ContractCheck official-team matching:** when an issue supplies exact official group keywords, unit-test title/team matching and aggregate count/size using fixture HTML or direct `torrent_title_size` fixtures.

## Poor Local-Closure Candidates

Avoid promising closure without more evidence when the report depends on:

- Private tracker live pages/statistics with no HTML sample.
- NAS/SMB/NFS/inotify behavior observed only from a different host.
- Android/Windows client UI connection failures without reproducible protocol logs.
- Screenshots only, missing logs, or pure configuration questions.

## Verification Artifacts

For local closure, create a deterministic script under `tests/` or `/tmp` that stubs external dependencies and asserts the exact issue behavior. Keep the script small and runnable with `python3 <script>`. For plugin version updates, remember: v1 plugins under `plugins/` use root `package.json`; v2 plugins under `plugins.v2/` use `package.v2.json`.
