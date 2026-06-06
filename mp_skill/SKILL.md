---
name: mp_skill
description: "Use when controlling a self-hosted MoviePilot instance via its REST API with X-API-KEY: subscriptions, search/discovery, downloads, transfers, storage, sites, plugins, workflows, dashboard statistics, and API-backed diagnostics."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [moviepilot, media, api, subscriptions, downloads]
    related_skills: []
---

# MoviePilot X-API-KEY Control

## Overview

This skill controls a self-hosted MoviePilot instance through its REST API using the `X-API-KEY` header. It is designed for safe, repeatable agent operations: inspect state first, make scoped API calls, avoid leaking credentials, and verify the result from MoviePilot rather than guessing.

The bundled references are intentionally small:
- generated endpoint docs for API routing;
- a compact set of reusable workflows for subscriptions, downloads, plugins, and site health;
- maintenance notes for refreshing the OpenAPI-derived files.

Environment-specific incident notes and one-off production case studies should stay in a local/private skill or separate knowledge base, not in this distributable skill.

## When to Use

Use this skill when the user asks to:
- list, create, update, diagnose, or remove MoviePilot subscriptions;
- search media resources and trigger downloads through MoviePilot;
- inspect downloads, transfers, storage, dashboard, sites, users, tasks, or plugins;
- troubleshoot subscription completion, missing episodes, plugin runtime problems, or site-cookie health using MoviePilot APIs;
- refresh MoviePilot API references from a live instance.

Do **not** use this skill for:
- direct torrent-client control when the user explicitly wants Transmission/qBittorrent RPC instead of MoviePilot;
- media-server operations unrelated to MoviePilot;
- plugin source-code changes without also using a software-development workflow.

## Configuration

Configure the MoviePilot host and API key in a local file:

```env
# ~/.config/mp_skill/config
MP_HOST=http://127.0.0.1:3000
MP_API_KEY=your_x_api_key
```

Environment overrides are also supported:
- `MOVIEPILOT_URL` or `MP_HOST`
- `MP_API_KEY`

## Token-Safe Request Helper

Use `scripts/mp_request.py` for API calls. It attaches `X-API-KEY` safely, avoids printing secrets, supports JSON bodies, writes large responses to files, and can compact common response shapes.

```bash
# Read-only info
python3 scripts/mp_request.py GET /api/v1/user/current

# Query string
python3 scripts/mp_request.py GET /api/v1/search --query "keyword=Inception&type=movie&page=1&count=10"

# JSON body
python3 scripts/mp_request.py POST /api/v1/subscribe/ --json '{"name":"Example","type":"movie"}'

# Large response: write raw JSON to disk and print a compact summary
python3 scripts/mp_request.py GET /api/v1/subscribe --compact --raw-out /tmp/mp_subscribe.json
```

## Core Workflow

1. **Classify the task.** Decide whether this is subscription, search/download, transfer, storage, site, plugin, dashboard, or workflow work.
2. **Find the endpoint.** Start with `references/api_index.md`, then open only the relevant file under `references/api/`.
3. **Check reusable workflow docs** for high-risk areas such as subscriptions, downloads, plugins, and site cookies.
4. **Call MoviePilot with `scripts/mp_request.py`.** Prefer read-only calls first.
5. **For mutations, verify with a follow-up read.** Do not treat a successful POST/PUT/DELETE alone as final proof.
6. **Keep secrets out of logs.** Torrent/site records may contain cookies, passkeys, tokens, or private URLs; write raw output to disk and summarize safe fields only.

## Common Capabilities

| Area | Typical operations | Endpoint reference |
| --- | --- | --- |
| Subscriptions | list, add, edit, delete, check completion/history | `references/api/subscribe.md` |
| Search/discovery | TMDB/Douban/Bangumi/search/recommendations | `references/api/search.md`, `references/api/discover.md`, `references/api/tmdb.md` |
| Downloads/torrents | active tasks, add/delete tasks, history | `references/api/download.md`, `references/api/torrent.md` |
| Transfers/library | transfer jobs, history, manual transfer, media metadata | `references/api/transfer.md`, `references/api/media.md` |
| Sites/users/plugins | site config/status, users, plugins, tasks | `references/api/site.md`, `references/api/user.md`, `references/api/plugin.md` |
| System/dashboard | CPU, memory, storage, service status | `references/api/dashboard.md`, `references/api/system.md`, `references/api/storage.md` |

## References

Core API references:
- `references/api_index.md` — routing index for capability areas.
- `references/api/*.md` — generated endpoint summaries by area; open only what you need.
- `references/openapi.json` — filtered OpenAPI schema for endpoints that support `api_key_header`.
- `references/moviepilot-skill-maintenance.md` — refresh, validation, and contribution workflow.

Reusable workflow references:
- `references/subscription-workflows.md` — add/update/check subscriptions safely.
- `references/subscription-auto-download-diagnostics.md` — diagnose why a subscription did or did not auto-download.
- `references/future-tv-season-false-completion-diagnostics.md` — investigate future-season false completion states.
- `references/latest-episode-download-workflow.md` — find and download the latest available episode.
- `references/movie-resource-search-download-workflow.md` — search resources and trigger MoviePilot-backed downloads.
- `references/plugin-development-workflow.md` — plugin development and packaging conventions.
- `references/plugin-runtime-diagnostics.md` — runtime/plugin API diagnostics.
- `references/site-cookie-health-and-plugin-ops.md` — site-cookie and plugin-ops checks.

Scripts:
- `scripts/mp_request.py` — token-safe API request helper with compact output and timeout support.
- `scripts/refresh_openapi_refs.py` — regenerate `references/openapi.json`, `references/api_index.md`, and `references/api/*.md` from a live MoviePilot instance.

## Maintaining API References

MoviePilot and installed plugins can add or remove endpoints. When a live server is available, refresh the generated references before endpoint-specific edits:

```bash
python3 scripts/refresh_openapi_refs.py --host http://127.0.0.1:3000
```

The refresh script keeps only operations that advertise `api_key_header` security, matching this skill's `X-API-KEY` workflow. Review the diff after regenerating because plugin-specific endpoints may appear or disappear depending on the source instance.

## Common Pitfalls

1. **Guessing completion from the subscription card alone.** Check subscription history, download/transfer state, and episodes when completion looks suspicious.
2. **Streaming huge API responses into chat.** Use `--output`, `--raw-out`, or `--compact` for large search/site/torrent responses.
3. **Using query-string API keys.** This skill is built around `X-API-KEY`; do not leak keys in URLs.
4. **Mutating before inspecting.** Read current state first, then perform the smallest scoped change, then verify.
5. **Treating local incident notes as portable docs.** Keep one-off environment-specific case studies out of the public skill package.

## Verification Checklist

- [ ] Host and `X-API-KEY` are configured without exposing secrets.
- [ ] Endpoint was selected from `references/api_index.md` or the relevant `references/api/*.md` file.
- [ ] Read-only state was inspected before any mutation.
- [ ] Mutation, if any, was followed by a read-back verification.
- [ ] Large or sensitive responses were saved to disk and summarized safely.
- [ ] For endpoint changes, generated API references were refreshed and reviewed.
