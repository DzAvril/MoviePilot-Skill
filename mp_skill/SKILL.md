---
name: mp_skill
description: Control a self-hosted MoviePilot instance via its REST API using X-API-KEY. Use for managing subscriptions, downloads, search/discovery, media/library info, transfers, storage, users, sites, plugins, tasks, and dashboard statistics on a local MoviePilot server.
---

# MoviePilot X-API-KEY Control

## Quick Start (Token-Safe)

1. Configure host and X-API-KEY in a local config file (best practice):

Config path: `~/.config/mp_skill/config`

Format:
```env
MP_HOST=http://192.168.1.93:3001
MP_API_KEY=your_x_api_key
```

Environment overrides (optional):
- `MOVIEPILOT_URL` or `MP_HOST`
- `MP_API_KEY`

2. Use the request helper for all API calls (X-API-KEY header):
- Script: `scripts/mp_request.py`
- It attaches auth safely and avoids echoing secrets.

## Large Response Handling (Auto-Compact)

When JSON responses are large, the script automatically:
- Saves the raw response to a file
- Prints a compact summary (counts + key fields preview)

You can also force compacting:
`--compact --raw-out /tmp/mp_skill_raw.json`

### Smart Summaries for Common Endpoints

The compact preview is tuned for:
- Subscriptions (`/subscribe*`)
- Search results (`/search*`)
- Recommendations (`/recommend*`)

For other endpoints, the summary falls back to generic key previews.

3. Minimize token usage:
- Use `references/api_index.md` to pick a capability area, then open only that file under `references/api/`.
- Only open `references/openapi.json` when you need schema or parameter details.
- For large responses, use `--output` to write to a file instead of streaming into context.

## Core Workflow

1. Identify the task category (subscriptions, downloads, search, library, storage, sites, plugins, workflows, etc.).
2. Find the endpoint using `references/api_index.md`, then open only the specific `references/api/<area>.md`.
3. For subscription, download, plugin, P115, Docker/restart, or site-health tasks, check the focused workflow references below before mutating state.
4. Call with `scripts/mp_request.py`.
5. If request body or params are unclear, consult `references/openapi.json` for the exact schema.
6. Write large resource/search/site responses to disk and summarize only safe fields; torrent and site records can contain cookies, passkeys, tokens, or download URLs.

### Example Call Patterns

```bash
# Read-only info
python3 scripts/mp_request.py GET /api/v1/user/current

# With query string
python3 scripts/mp_request.py GET /api/v1/search --query "keyword=Inception&type=movie&page=1&count=10"

# With JSON body (inline)
python3 scripts/mp_request.py POST /api/v1/subscribe/ --json '{"name":"Example","type":"movie"}'

# With JSON body (file) and write response to disk to reduce token usage
python3 scripts/mp_request.py POST /api/v1/subscribe/ --json @/tmp/payload.json --output /tmp/resp.json
```

## Common Capabilities (Most Used)

- Subscriptions: list, add, update, remove, and status queries.
- Search and discovery: TMDB, Douban, Bangumi searches and recommendations.
- Downloads: active tasks, add tasks, delete tasks, and history.
- Library and media: media info, seasons and episodes, library status.
- Transfers: transfer jobs, histories, and manual transfers.
- Storage: storage status, browse directories, usage, mount or drive checks.
- Dashboard: CPU, memory, network, storage stats, running services.
- Users and sites: user management and site configs.
- Tasks and plugins: workflows, tasks, and plugin status.

## Auth Safety Rules

- Never request the user’s API key in chat.
- Never echo keys in commands or logs.
- Use `--no-auth` only for public endpoints.

## References

Core endpoint references:
- `references/api_index.md` — Primary routing index to find the right capability file.
- `references/api/*.md` — One file per capability area (open only what you need).
- `references/openapi.json` — Filtered schema containing only X-API-KEY supported endpoints.
- `references/moviepilot-skill-maintenance.md` — Live OpenAPI refresh, validation, secret-scan, and contribution notes.

Focused workflow references imported from the production/local skill:
- Subscriptions and episodes: `references/subscription-workflows.md`, `references/subscription-auto-download-diagnostics.md`, `references/future-tv-season-false-completion-diagnostics.md`, `references/tv-season-postgresql-fallback.md`, `references/movie-subscription-postgresql-fallback.md`, `references/future-movie-subscription-db-readback-without-docker.md`, `references/future-title-subscribe-via-tmdb.md`, `references/future-title-clue-disambiguation-and-duplicate-check.md`, `references/unrecognized-fuzzy-movie-subscription.md`, `references/tv-episode-update-status-check.md`, `references/latest-episode-download-workflow.md`.
- Search/download/recommendation actions: `references/movie-resource-search-download-workflow.md`, `references/user-workflows-transmission-and-downloads.md`, `references/session-notes-media-downloads-sites.md`, `references/weekend-movie-recommendation-continuation.md`.
- Site, runtime, Docker, and notification diagnostics: `references/site-cookie-health-and-plugin-ops.md`, `references/moviepilot-high-cpu-diagnostics.md`, `references/moviepilot-ui-api-hang-recovery.md`, `references/moviepilot-cookiecloud-host-update.md`, `references/moviepilot-image-restart-and-self-update.md`, `references/moviepilot-routine-restart.md`, `references/moviepilot-to-hermes-notifications.md`, `references/moviepilot-wechatclawbot-hermes-coexistence.md`.
- Plugin development/runtime fixes: `references/plugin-development-workflow.md`, `references/plugin-runtime-diagnostics.md`, `references/plugin-local-testing-prereqs.md`, `references/plugin-issue-triage-for-codex.md`, `references/mcpserver-*.md`, `references/removelink-*.md`, `references/qbcommand-scheduled-speed-limit-fix.md`.
- P115/STRM and media-server helpers: `references/p115strmhelper-api-playbook.md`, `references/p115-strm-emby302-playback-diagnostics.md`, `references/pansou-115-search-integration.md`, `references/zspace-core-adapter-diagnostics.md`.

Scripts:
- `scripts/mp_request.py` — token-safe request helper with compact output and configurable timeout.
- `scripts/refresh_openapi_refs.py` — Regenerate `references/api_index.md`, `references/api/*.md`, and `references/openapi.json` from a live MoviePilot `/api/v1/openapi.json`.
- `scripts/list_p115_mcp_tools.py` — Token-safe urllib probe for P115StrmHelper's MCP SSE `tools/list`.

## Maintaining This Skill

MoviePilot and plugins can add or remove API endpoints over time. When a live server is available, refresh the API references before making endpoint-specific changes:

```bash
python3 scripts/refresh_openapi_refs.py --host http://127.0.0.1:3000
```

The refresh script keeps only operations that advertise `api_key_header` security, matching this skill's X-API-KEY workflow. Review the diff after regenerating because plugin-specific endpoints may appear or disappear depending on the MoviePilot instance.
