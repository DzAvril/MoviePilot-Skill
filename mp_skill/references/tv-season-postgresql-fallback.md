# MoviePilot TV season subscription PostgreSQL fallback

Use this only when the user explicitly wants a TV season subscription, the exact series/season identity is established, and MoviePilot's normal API cannot hydrate the metadata.

## When this applies

- User asks to subscribe a future/upcoming TV season, e.g. `羊毛战记第三季`.
- Public/TMDB lookup identifies the exact TV show TMDB id and season metadata, or public renewal/production sources establish a future season before MoviePilot/TMDB exposes full season objects.
- MoviePilot endpoints may be unhelpful for that title:
  - `/api/v1/media/search` returns `[]` for Chinese and English aliases.
  - `/api/v1/media/{tmdbid}` returns an empty/null metadata object.
  - `/api/v1/tmdb/seasons/{tmdbid}` can return `[]` even though TMDB's public page shows the season.
  - `/api/v1/search/media/{tmdbid}` returns `未搜索到任何资源`.
- `POST /api/v1/subscribe/` with a correct TV payload returns `未识别到媒体信息` or otherwise fails.
- API/DB duplicate checks confirm the target season is not already present, or reveal that the failed POST actually inserted a row.

Do not use this from title guesses. Establish the exact identity first using durable identifiers: TMDB link/id, English title, year, season number, and episode count.

For renewed-but-not-yet-indexed seasons, public sources may confirm renewal/premiere window before MoviePilot/TMDB season APIs expose a season object. In that case, still anchor the row to the series TMDB id and first-air year, set `season`/`include` to the requested future season (`2` + `S02`, etc.), use bilingual aliases in `keyword`, and report any episode-count assumption explicitly.

## Workflow

1. Resolve identity externally when MoviePilot search fails:
   - Confirm TMDB TV id.
   - Confirm canonical title/aliases.
   - Confirm season number, year/air date, and episode count.

2. Check duplicates before and after any failed normal POST:

```bash
python3 scripts/mp_request.py GET /api/v1/subscribe/ --compact --raw-out /tmp/mp_subscriptions.json

# If PostgreSQL is available, also check by tmdbid/title/keyword/season.
docker exec moviepilot_v2-postgresql-1 sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atf /tmp/mp_check_tv.sql'
```

Important: a `POST /api/v1/subscribe/` response of `{"success":false,"message":"未识别到媒体信息"}` does not always prove no row exists. Check the DB/API read-back before inserting manually.

3. If no row exists, insert a minimal, season-scoped TV subscription:

```sql
insert into subscribe (
  name, year, type, keyword, tmdbid, season, total_episode, lack_episode,
  include, sites, state, date, username, resolution,
  best_version, best_version_full, search_imdbid, description
) values (
  'Silo', '2023', '电视剧', '羊毛战记|末日地堡|Silo', 125988, 3, 10, 10,
  'S03', '[-1]'::json, 'R', to_char(now(), 'YYYY-MM-DD HH24:MI:SS'), 'Hermes',
  '4K|2160p|x2160', 0, 0, 0,
  '《末日地堡 / Silo》第三季，2026，共 10 集。'
) returning id,name,year,type,season,total_episode,lack_episode,keyword,tmdbid,state,resolution;
```

4. Verify through MoviePilot API, not just SQL:

```bash
python3 scripts/mp_request.py GET /api/v1/subscribe/<id> --output /tmp/mp_sub_<id>.json
python3 scripts/mp_request.py GET /api/v1/subscribe/search/<id> --output /tmp/mp_sub_<id>_search_trigger.json
```

`{"success":true,"data":{}}` confirms the search trigger was accepted; it does not mean resources were found.

5. For season subscription read-back, inspect the fields that prove MoviePilot will search the correct target: `name`, `year`, `type`, `tmdbid`, `season`, `state`, `total_episode`, `lack_episode`, `resolution`, `keyword`, `include`, `sites`, and `date`. MoviePilot may normalize the stored `name` to the English/TMDB primary title while Chinese aliases live in `keyword`; that is acceptable when the TMDB id and season guard match.

6. If you do a manual resource search after triggering, filter aliases with real word boundaries and season guards. Do **not** treat a raw substring hit as proof of a match: for `Silo`, `EPSiLON` contains the letters `silo` and can create false positives. Prefer checks like `(?i)(^|[^a-z])silo([^a-z]|$)` on title/subtitle fields plus `S03`, TMDB/media metadata, or Chinese aliases (`羊毛战记`, `末日地堡`) before reporting current resources.

Example read-back shape for a successful future-season fallback:

```text
name='The Day of the Jackal', year='2024', type='电视剧', tmdbid=222766,
season=2, include='S02', total_episode=10, lack_episode=10,
resolution='4K|2160p|x2160', keyword='豺狼的日子|The Day of the Jackal',
state='R', sites=[-1]
```

## Field guidance

- `type`: `电视剧`.
- `year`: series first-air year unless MoviePilot's existing data clearly uses another value.
- `season`: target season number.
- `total_episode` / `lack_episode`: use TMDB/public season count for future seasons.
  - If the requested season is announced/renewed but public TMDB has not yet listed that season or episode count, do **not** claim a confirmed count. Use a conservative placeholder only when the user explicitly wants the subscription now, preferably matching the prior season's episode count, and mention it as an assumption in the report.
- `include`: add season guard such as `S03` / `S02` to avoid matching older seasons.
- `resolution`: reuse this user's common TV target `4K|2160p|x2160` unless requested otherwise.
- `sites`: `[-1]` to search all enabled sites.
- `state`: `R`.

## Session examples

- `羊毛战记 / 末日地堡 / Silo` S03: exact TMDB TV id `125988` and public TMDB seasons page showed season 3 / 2026 / 10 episodes, while MoviePilot media search, `/media/{tmdbid}`, `/tmdb/seasons/{tmdbid}`, and normal `POST /subscribe/` failed. A post-failure DB duplicate check revealed the row had nevertheless been inserted; API read-back `GET /subscribe/{id}` and `/subscribe/search/{id}` verified it. Lesson: after a failed POST, always check API/DB before manual insertion.
- `豺狼的日子 / The Day of the Jackal` S02: exact TMDB TV id `222766` was confirmed, but public TMDB listed only Series 1 and MoviePilot returned empty metadata/resources. Because the user explicitly asked for S02 now, insert a season-scoped fallback with `include='S02'`, all-title aliases in `keyword`, and a conservative placeholder episode count derived from season 1; report that resources are not currently available and the count is provisional if not externally confirmed.

## Reporting

Report compactly:
- exact title/season/year/episode count;
- subscription id;
- that API read-back succeeded;
- whether resources currently exist.

Be explicit when this was a controlled DB fallback or when a failed normal POST nevertheless produced a verified subscription row.
