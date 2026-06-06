# Future movie subscription read-back + DB fallback when Docker is unavailable

Use this when subscribing an upcoming movie where MoviePilot cannot hydrate metadata normally and Docker socket access is unavailable from Hermes.

## Trigger pattern

- Public/TMDB lookup identifies the movie confidently (title, year, TMDB id, cast clue).
- `/api/v1/media/search` returns `[]` and `/api/v1/search/title` has no exact resources.
- `POST /api/v1/subscribe/` returns `未识别到媒体信息` despite a TMDB-grounded payload.
- Docker CLI cannot access `/var/run/docker.sock`, so the normal `docker exec ... psql` fallback path is blocked.

## Workflow

1. **Always re-check subscriptions by TMDB id before inserting anything**
   - API list read-back can miss the exact title if MoviePilot normalizes to English.
   - Use `/api/v1/subscribe/media/tmdb:<tmdbid>?title=<localized title>` and/or search the full `/api/v1/subscribe/` output for `tmdbid`, Chinese title, and English title.
   - If a subscription exists, stop and report the existing id/status. Do not insert a duplicate.

2. **If Docker is unavailable, use MoviePilot env API for DB coordinates — secret-safe**
   - `GET /api/v1/system/env` exposes `DB_TYPE`, host, port, database, username, password.
   - Do not print raw env output in chat; redact password/token/cache URLs.
   - In this user's topology, MoviePilot may report PostgreSQL host as `127.0.0.1` from inside its container; from Hermes, the host is often reachable as `172.17.0.1:<port>`.

3. **Direct PostgreSQL probe without installing globally**
   - Use an ephemeral dependency runner, e.g. `uv run --with 'psycopg[binary]' python ...`, to avoid mutating the base Python environment.
   - Query by `tmdbid` first, then title aliases:
     ```sql
     select id,name,year,type,keyword,tmdbid,state
     from subscribe
     where tmdbid = <tmdbid>
        or coalesce(name,'') like '%<localized title>%'
        or coalesce(keyword,'') ilike '%<english alias>%';
     ```

4. **Only insert if both API and DB show no existing row**
   - Follow `movie-subscription-postgresql-fallback.md` for minimal insert fields.
   - Include alias keywords such as localized title, TMDB English title, and former working titles.
   - Verify through `GET /api/v1/subscribe/<id>` after insertion.

5. **Resource verification for future English titles is noisy**
   - Broad `/api/v1/search/title?keyword=The End of Oak Street` can return unrelated titles matching common tokens like “The/End/Legend”.
   - Treat resource existence as proven only if title/subtitle contains a strong alias (`Oak Street`, `Flowervale`, localized title, or exact TMDB match). Otherwise report “no exact resources yet.”

## Session-proven example

`逃出绝命街` / `The End of Oak Street` / former working title `Flowervale Street`, TMDB `1101383`, year `2026`, starring Anne Hathaway. Normal MoviePilot media/search and subscription POST failed to hydrate metadata, but read-back showed an existing normalized subscription as `The End of Oak Street`, id `397`, state `R`, with keyword aliases. Exact resource filtering found no matching resources yet.
