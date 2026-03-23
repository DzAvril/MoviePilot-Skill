---
name: mp_skill
description: Control a self-hosted MoviePilot instance via its REST API using X-API-KEY. Use for managing subscriptions, downloads, search/discovery, media/library info, transfers, storage, users, sites, plugins, tasks, and dashboard statistics on a local MoviePilot server.
---

# MoviePilot X-API-KEY Control

## Quick Start (Token-Safe)

1. Configure host and X-API-KEY in a local config file (best practice):

Config path: `~/.config/mp_skill/config`

Format:
```\nMP_HOST=http://192.168.1.93:3001\nMP_API_KEY=your_x_api_key\n```

Environment overrides (optional):
- `MOVIEPILOT_URL` or `MP_HOST`
- `MP_API_KEY`

2. Use the request helper for all API calls (X-API-KEY header):
- Script: `scripts/mp_request.py`
- It attaches auth safely and avoids echoing secrets.

3. Minimize token usage:
- Use `references/api_index.md` to pick a capability area, then open only that file under `references/api/`.
- Only open `references/openapi.json` when you need schema or parameter details.
- For large responses, use `--output` to write to a file instead of streaming into context.

## Core Workflow

1. Identify the task category (subscriptions, downloads, search, library, storage, etc.).
2. Find the endpoint using `references/api_index.md`, then open only the specific `references/api/<area>.md`.
3. Call with `scripts/mp_request.py`.
4. If request body or params are unclear, consult `references/openapi.json` for the exact schema.

### Example Call Patterns

```bash
# Read-only info
python3 /Users/xuzhi/Documents/workspace/MoviePilot-Skill/mp_skill/scripts/mp_request.py GET /api/v1/user/current

# With query string
python3 /Users/xuzhi/Documents/workspace/MoviePilot-Skill/mp_skill/scripts/mp_request.py GET /api/v1/search --query "keyword=Inception&type=movie&page=1&count=10"

# With JSON body (inline)
python3 /Users/xuzhi/Documents/workspace/MoviePilot-Skill/mp_skill/scripts/mp_request.py POST /api/v1/subscribe/ --json '{"name":"Example","type":"movie"}'

# With JSON body (file) and write response to disk to reduce token usage
python3 /Users/xuzhi/Documents/workspace/MoviePilot-Skill/mp_skill/scripts/mp_request.py POST /api/v1/subscribe/ --json @/tmp/payload.json --output /tmp/resp.json
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

- `references/api_index.md` — Primary routing index to find the right capability file.
- `references/api/*.md` — One file per capability area (open only what you need).
- `references/openapi.json` — Filtered schema containing only X-API-KEY supported endpoints.
