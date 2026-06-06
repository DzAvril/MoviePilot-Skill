---
name: mp_skill
description: Control a self-hosted MoviePilot instance via its REST API using X-API-KEY. Use for subscriptions, downloads, search/discovery, media/library checks, site/plugin operations, Docker-aware diagnostics, and token-safe MoviePilot troubleshooting workflows.
---

# MoviePilot X-API-KEY Control

## Overview

Use this skill for operating a self-hosted MoviePilot instance through `/api/v1/*` endpoints with `X-API-KEY` authentication. It provides a token-safe request helper, OpenAPI-derived endpoint references, and a curated set of reusable workflows for subscriptions, downloads, plugin/runtime diagnostics, site health, and selected media-server integrations.

Keep `SKILL.md` as the routing/index layer. Endpoint details belong in `references/api/*.md` or `references/openapi.json`; durable scenario playbooks belong in `references/*.md`; reusable utilities belong in `scripts/`. Do not commit one-off session notes, local environment diaries, or single-issue fix logs into this repo skill.

## Quick Start (Token-Safe)

1. Configure host and X-API-KEY in a local config file:

Config path: `~/.config/mp_skill/config`

```env
MP_HOST=http://127.0.0.1:3000
MP_API_KEY=your_x_api_key
```

Environment overrides:

- `MOVIEPILOT_URL` or `MP_HOST`
- `MP_API_KEY`

2. Use the request helper for API calls:

```bash
python3 scripts/mp_request.py GET /api/v1/user/current
```

The helper attaches auth safely, supports `--query`, `--json`, `--output`, `--compact`, `--raw-out`, and `--timeout`, and avoids printing secrets.

## Core Workflow

1. Identify the task category: subscriptions, downloads, search, media/library, storage, sites, plugins, workflows, dashboard, etc.
2. Use `references/api_index.md` to find the relevant capability file under `references/api/`.
3. For subscription work, read `references/subscription-workflows.md` and the scenario-specific notes below before mutating state.
4. Call endpoints with `scripts/mp_request.py`.
5. If request body or query parameters are unclear, inspect `references/openapi.json` for exact schemas.
6. Write large responses to disk with `--output` or use `--compact --raw-out`; parse and summarize only non-secret fields.
7. Verify any mutation by reading back MoviePilot state.

## Curated Scenario References

### Subscriptions and media acquisition

- `references/subscription-workflows.md` — general subscription add/update/read-back workflow.
- `references/subscription-auto-download-diagnostics.md` — diagnose “订阅了但没动/达成了但是否真的下载完”: compare active subscriptions, subscription history, target-season resources, active downloads, download history, and transfer history.
- `references/future-tv-season-false-completion-diagnostics.md` — future/unreleased TV seasons can move to history as `total_episode=0` / `lack_episode=0` false-complete; verify exact Sxx resources and download/transfer evidence before saying a season downloaded.
- `references/future-title-subscribe-via-tmdb.md` — TMDB-grounded workflow for upcoming/unreleased titles when title search has no resources.
- `references/latest-episode-download-workflow.md` — “下载最新集/有最新集就下”.
- `references/tv-episode-update-status-check.md` — compare searchable max episode with local/library/transfer max episode.
- `references/movie-resource-search-download-workflow.md` — safe resource search parsing and `/download/add` workflow.

### Runtime/plugin diagnostics

- `references/plugin-runtime-diagnostics.md` — installed plugin logs/config, redacted config reads, and third-party HTTP reproduction.
- `references/plugin-development-workflow.md` — source-level plugin bug fixing and verification.
- `references/plugin-local-testing-prereqs.md` — local prerequisites for plugin development and regression checks.
- `references/site-cookie-health-and-plugin-ops.md` — site cookie/login/connectivity notifications and safe plugin config operations.
- `references/moviepilot-high-cpu-diagnostics.md` — correlate CPU/thread spikes with monitor tasks, plugins, and stuck scheduler jobs.
- `references/moviepilot-ui-api-hang-recovery.md` — distinguish static UI from blocked `/api/v1/*` backend and recover safely.
- `references/moviepilot-image-restart-and-self-update.md` and `references/moviepilot-routine-restart.md` — Docker image update/restart workflows and readiness verification.

### Integrations

- `references/p115strmhelper-api-playbook.md` — P115StrmHelper API discovery and operational playbook.
- `references/pansou-115-search-integration.md` — 115 net-disk resource search via PanSou/PanHub-style APIs.
- `references/zspace-core-adapter-diagnostics.md` — ZSpace/极影视 auth/header-token/library-folder probes.

## Request Patterns

```bash
# Read-only info
python3 scripts/mp_request.py GET /api/v1/user/current

# With query string
python3 scripts/mp_request.py GET /api/v1/search/title --query 'keyword=Inception&page=0' --output /tmp/mp_search.json

# With JSON body inline
python3 scripts/mp_request.py POST /api/v1/subscribe/ --json '{"name":"Example","type":"movie"}'

# With JSON body from a file and response written to disk
python3 scripts/mp_request.py POST /api/v1/subscribe/ --json @/tmp/payload.json --output /tmp/resp.json
```

## Large Response Handling

Large MoviePilot responses can include tracker cookies, RSS passkeys, torrent URLs, and other secrets. Prefer:

```bash
python3 scripts/mp_request.py GET /api/v1/search/title --query 'keyword=<title>&page=0' --output /tmp/mp_search.json
python3 scripts/mp_request.py GET /api/v1/subscribe --compact --raw-out /tmp/mp_subscriptions.json
```

Then parse `/tmp` JSON locally and report only safe fields: title, year, season/episode, resolution, source, size, seeders, site name, state, progress, and timestamps.

## Maintaining API References

MoviePilot and installed plugins can add/remove endpoints. Refresh references from a live server with:

```bash
python3 scripts/refresh_openapi_refs.py --host http://127.0.0.1:3000
```

Review regenerated diffs before committing because plugin endpoints vary by instance.

## Reference Curation Rules

- Commit reusable workflows that are broadly useful to MoviePilot operators.
- Keep case studies, single-issue patch notes, and local-environment notes out of the shared repo skill unless they are generalized into a playbook.
- If a workflow needs more than a few paragraphs, put it in `references/*.md` and link it here.
- If content is specific to one user's machine, keep it in the user-local skill or memory instead.

## Auth Safety Rules

- Never request the user's API key in chat.
- Never echo API keys, cookies, RSS passkeys, tokens, or torrent URLs in logs/summaries.
- Prefer config files or environment variables over inline secret-bearing commands.
- Use `--no-auth` only for public endpoints.

## Common Pitfalls

1. **Loading `openapi.json` first.** It is large; use `references/api_index.md` and the narrow `references/api/*.md` files first.
2. **Trusting subscription UI/status alone.** `note`, `last_update`, and even history completion can be stale or misleading. Cross-check download and transfer evidence.
3. **Future TV season false completion.** A season with `total_episode=0` and `lack_episode=0` can be marked complete without downloading anything; see `future-tv-season-false-completion-diagnostics.md`.
4. **Fuzzy search false positives.** `S02` hits from generic English queries can belong to unrelated titles. Require exact TMDB/media/title/year/season validation before acting.
5. **Leaking secrets from raw responses.** Always write large responses to files and parse safe fields.
6. **Mutating without read-back verification.** Verify add/update/delete/download actions with a follow-up API read.
7. **Assuming plugin endpoints are universal.** Plugin APIs depend on the installed plugin set and version.
8. **Treating Docker `Up` as ready.** MoviePilot can be up while nginx/API is still initializing; poll the correct network context and interpret fast unauthenticated `401/403` as reachability.

## Verification Checklist

- [ ] Credentials are supplied via config/env and not exposed in commands or output.
- [ ] Endpoint was selected via `api_index.md` and relevant `references/api/<area>.md`.
- [ ] Large/search/site responses were saved to files and summarized safely.
- [ ] Subscription/download conclusions are backed by active state plus history/transfer evidence where relevant.
- [ ] Fuzzy resource matches were exact-filtered before download/subscription actions.
- [ ] Mutations were verified by read-back.
- [ ] New reusable MoviePilot knowledge was generalized before being added to `references/`, `scripts/`, or this `SKILL.md`.
