# MoviePilot Subscription Workflows

Session-proven patterns for adding subscriptions safely through the MoviePilot REST API.

## Add a TV season subscription from a fuzzy title

1. Search MoviePilot media first, not TMDB directly, so titles match the instance's metadata naming:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/media/search --query "title=<user title>&type=media&page=1&count=10" --output /tmp/mp_media_search.json
   ```
2. Pick the intended result by title/year/type and note its `tmdb_id` / `tmdbid`.
   - Example: user said “龙之家族”; MoviePilot/TMDB title was `权力的游戏前传：龙族`, `tmdb_id=94997`, type `电视剧`.
3. For TV shows, fetch season metadata before subscribing:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/tmdb/seasons/<tmdbid> --output /tmp/mp_tmdb_seasons.json
   ```
   Use `season_number`, `episode_count`, and `air_date` to populate/confirm the season.
4. Check existing subscriptions to avoid duplicates:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/subscribe/ --compact --raw-out /tmp/mp_subscriptions.json
   ```
   Search the raw response for the `tmdbid` and related titles.
5. Build a JSON payload file rather than putting a large body inline. Reuse the user's existing subscription defaults when visible (e.g. resolution, sites, state), but do not invent sensitive values.
   Typical TV season payload fields:
   ```json
   {
     "name": "<MoviePilot title>",
     "year": "<year>",
     "type": "电视剧",
     "tmdbid": 94997,
     "season": 3,
     "total_episode": 8,
     "lack_episode": 8,
     "resolution": "4K|2160p|x2160",
     "sites": [-1],
     "state": "R",
     "best_version": 0,
     "search_imdbid": 0
   }
   ```
6. Add the subscription and save the response:
   ```bash
   python3 scripts/mp_request.py POST /api/v1/subscribe/ --json @/tmp/payload.json --output /tmp/mp_subscribe_resp.json
   ```
7. Verify by fetching the returned subscription id:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/subscribe/<id> --output /tmp/mp_subscribe_detail.json
   ```

## Domestic variety shows with messy season numbering

Chinese/domestic variety metadata can disagree across TMDB, tracker titles, and the user's organized library. For current-season subscriptions, do not blindly trust TMDB's `season_number` when tracker resources and transfer history consistently use another season code.

Recommended workflow:

1. Search the media title in MoviePilot and fetch TMDB seasons as usual.
2. Cross-check the user's actual library/transfer history (`/api/v1/history/transfer`) and recent tracker search results for canonical filename season/episode patterns, e.g. `S09E04`.
3. If TMDB says the year season is `season_number=8` but library/resources use `S09`, subscribe with the resource/library season (`season: 9`) so MoviePilot searches the same identifiers that trackers publish.
4. Add an `include` guard for the chosen season code, e.g. `"include": "S09"`, to avoid matching older seasons or the TMDB-only season number.
5. Exclude non-main-program variants when the user wants 正片/current episode, e.g. `"exclude": "Plus|Program|加更|企划|特别企划"`.
6. Set `resolution` to the user's target (`"4K|2160p|x2160"` for 4K) and keep `sites: [-1]` unless the user requests specific sites.
7. Use `note` to mark already present/handled episodes and set `lack_episode` accordingly; verify the stored subscription via `GET /api/v1/subscribe/{id}`.

Session-proven example: 《妻子的浪漫旅行》/2026. TMDB `97199` reported 2026 as season 8, but the user's transfer history and tracker resources used `S09E01`–`S09E04`. The correct subscription used `season: 9`, `include: "S09"`, `exclude: "Plus|Program|加更|企划|特别企划"`, `resolution: "4K|2160p|x2160"`, `total_episode: 10`, and marked E01–E04 in `note`.

## Current domestic variety: download aired resources first, then subscribe remaining episodes

For requests like “下载<综艺>最新/已有资源并订阅”, combine resource download and subscription state in one pass:

1. Search `/api/v1/search/title` and parse only safe fields from the saved JSON. Prefer main-program resources at the user's usual quality target (often `2160p WEB-DL`) and high-seeder/site-healthy results.
2. Exclude side programs and specials explicitly when selecting torrents and when creating the subscription: `Plus|Kids|萌娃|加更|先导|Part|特别|衍生` is a proven baseline for 《爸爸当家》第五季-style resources.
3. Add the aired main episodes via `/api/v1/download/add` with `torrent_in` if MoviePilot cannot recognize `media_info` from tracker titles. Verify active downloads by broad aliases (Chinese title, English title, season code, release team), because all tasks may normalize to the same display title.
4. Resolve TMDB metadata if normal media search fails. TMDB can have the show as a long-running series where season 5 is current, but `/api/v1/media/search` returns no local result. Fetch `/api/v1/tmdb/seasons/<tmdbid>` to confirm season number, air date, and episode count.
5. When POST subscription fails with `未识别到媒体信息` for the Chinese title/year, retry with the TMDB primary English title and the show's first-air year while keeping the target `tmdbid`, `season`, and episode counts. On this instance, `Daddy at Home` + `year: 2022` + `tmdbid: 201781` + `season: 5` created the subscription and MoviePilot normalized it back to `爸爸当家`.
6. Mark already-added/available main episodes in `note` and `completed_episode`, set `lack_episode` to the remaining episode count, and verify the stored subscription via `GET /api/v1/subscribe/{id}`.

## Pitfalls

- Domestic variety shows often have special episodes/Plus/Program entries and TMDB season drift. Prefer the season code used by tracker resources and the user's organized files when subscribing to new episodes.
- `127.0.0.1` inside a Hermes Docker container is the container, not the host. If MoviePilot runs on the Docker host, use the reachable host-gateway address (e.g. `http://172.17.0.1:3000`) configured in `~/.config/mp_skill/config`.
- Do not ask the user for or echo `MP_API_KEY`; rely on the configured helper.
- `/docs`, `/redoc`, and `/openapi.json` may be frontend/404 on some MoviePilot deployments; the OpenAPI JSON can be under `/api/v1/openapi.json`.
- Chinese aliases may not equal MoviePilot's canonical title. Confirm via media search and season metadata before subscribing.
- Newly released/current theatrical movies may have no `/api/v1/search/title` resources but still resolve in `/api/v1/media/search`; for “帮我订阅” after a no-resource result, use the media-search TMDB result to build a movie subscription (`type: 电影`, `tmdbid`, `year`, `sites: [-1]`, `state: R`) and verify after add.
- If MoviePilot cannot recognize the user-provided Chinese title and public/TMDB lookup only yields loose English-name guesses or unrelated near matches, do **not** force a fallback subscription from translation guesswork. First report the failed checks and ask for a durable identifier such as English title, year, poster/screenshot, Douban link, or TMDB link. Only use PostgreSQL/minimal-row fallback after the exact movie identity is established.
- A successful add may return only `{success, message, data:{id}}`; fetch `/api/v1/subscribe/<id>` to confirm the actual stored fields before reporting back. On this instance that detail endpoint can return the subscription object directly rather than wrapped under `data`, so handle both shapes.
- For future TV seasons, MoviePilot can fail to hydrate valid TMDB-backed metadata: Chinese/English media search may return `[]`, `/media/{tmdbid}` may return an empty object, `/tmdb/seasons/{tmdbid}` may return `[]`, and normal `POST /subscribe/` may return `未识别到媒体信息`. If public TMDB has established the exact TV id/season/year/episode count, use `references/tv-season-postgresql-fallback.md`: check API and PostgreSQL duplicates, remember that a failed POST may still have inserted a row, then verify the final row through `GET /api/v1/subscribe/{id}` and optionally trigger `/subscribe/search/{id}`.
