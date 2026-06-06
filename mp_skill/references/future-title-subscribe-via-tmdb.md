# Future / unreleased title subscription via TMDB fallback

Use this workflow when the user asks to search a title, and if no resources exist yet, subscribe to it anyway.

## When to use

- `GET /api/v1/search/title` returns `未搜索到任何资源`.
- The title is upcoming / unreleased / newly announced.
- A direct MoviePilot media search by title is empty, but public sources can identify a TMDB entry.

## Workflow

1. **Try MoviePilot title search first**
   ```bash
   python3 scripts/mp_request.py GET /api/v1/search/title \
     --query 'keyword=<title>&page=0' --compact --raw-out /tmp/mp_search.json
   ```
   If resources exist, summarize them instead of creating a subscription immediately.

2. **Resolve the title externally if MoviePilot has no hit**
   Use current web search to find the authoritative TMDB or IMDb page, especially for upcoming shows/movies.
   For `斯图尔特未能拯救宇宙`, web lookup identified:
   - TMDB TV: `287620`
   - IMDb: `tt27497393`
   - English title: `Stuart Fails to Save the Universe`
   - First air date: `2026-07-23`
   - Seasons / episodes: `1 / 10`

3. **Pull canonical metadata from MoviePilot by TMDB id**
   ```bash
   python3 scripts/mp_request.py GET /api/v1/media/287620 \
     --query 'type_name=电视剧&title=斯图尔特未能拯救宇宙&year=2026' \
     --compact --raw-out /tmp/mp_media_287620.json
   ```
   This can return usable TMDB-backed metadata even when `/api/v1/media/search?title=...` is empty.

4. **Run exact resource search by TMDB id before subscribing**
   ```bash
   python3 scripts/mp_request.py GET /api/v1/search/media/287620 \
     --query 'mtype=电视剧&title=Stuart Fails to Save the Universe&year=2026&season=1&area=title' \
     --compact --raw-out /tmp/mp_search_precise.json
   ```
   If this still returns `未搜索到任何资源`, proceed to subscription.

5. **Create the subscription with a minimal TMDB-grounded payload**
   Example payload for an upcoming TV series:
   ```json
   {
     "name": "斯图尔特未能拯救宇宙",
     "year": "2026",
     "type": "电视剧",
     "tmdbid": 287620,
     "season": 1,
     "total_episode": 10,
     "keyword": "Stuart Fails to Save the Universe",
     "poster": "https://image.tmdb.org/t/p/original/iQbTbwmLX5Nh1nlH21YUJPWt3Zo.jpg",
     "backdrop": "https://image.tmdb.org/t/p/original/2ngdvUiEKW8Q37ta8BBdydE2cuq.jpg",
     "vote": 0,
     "description": "《生活大爆炸》衍生剧，预计 2026-07-23 首播。",
     "sites": [-1],
     "best_version": 0,
     "search_imdbid": 0,
     "start_episode": 0,
     "lack_episode": 0,
     "state": "R",
     "resolution": null,
     "quality": null,
     "effect": null,
     "include": null,
     "exclude": null
   }
   ```

   Submit with:
   ```bash
   python3 scripts/mp_request.py POST /api/v1/subscribe/ \
     --json @/tmp/payload.json --compact --raw-out /tmp/mp_subscribe_resp.json
   ```

6. **Read back the created subscription**
   ```bash
   python3 scripts/mp_request.py GET /api/v1/subscribe/<id> \
     --compact --raw-out /tmp/mp_sub_<id>.json
   ```

## What to tell the user

Keep the result short:
- searched resources first;
- no current resources found;
- subscription created successfully;
- mention title, type, year/season, and subscription id.

## Pitfalls

- `GET /api/v1/media/search?title=...` may return an empty list for upcoming titles even when `GET /api/v1/media/{tmdbid}` works.
- For future titles, external current-source lookup can be necessary to obtain the TMDB id before MoviePilot can be used effectively.
- After creation, MoviePilot may normalize the stored subscription name to the English/TMDB primary title. Verify by reading back `GET /api/v1/subscribe/<id>` instead of assuming the submitted Chinese title remains unchanged.
- Prefer verifying by TMDB id and season metadata rather than only by localized title strings.
- Localized Chinese aliases may have to be resolved to the canonical English TMDB title before MoviePilot becomes useful. Example: `绿灯军团` maps to TMDB TV `95350` / `Lanterns` (2026). In that case, a Chinese MoviePilot title search can return nothing, while a broad English search like `Lanterns` is noisy and full of unrelated “lantern” matches. The durable path is: confirm the exact TMDB TV result externally, call `GET /api/v1/media/<tmdbid>`, then run the exact `GET /api/v1/search/media/<tmdbid>` check before creating the subscription.
