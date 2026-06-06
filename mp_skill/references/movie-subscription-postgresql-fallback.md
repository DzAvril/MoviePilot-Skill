# MoviePilot movie subscription PostgreSQL fallback

Use this only when the normal MoviePilot subscription API cannot create a requested movie subscription but the user explicitly wants the subscription added and the live instance uses PostgreSQL.

## When this applies

- User asks to subscribe a movie, often an upcoming/future title.
- `/api/v1/media/search` cannot resolve the Chinese/English title or returns `[]`.
- Public/TMDB lookup identifies a plausible movie TMDB id.
- `POST /api/v1/subscribe/` with `name/year/type/tmdbid/sites/state` fails with `未识别到媒体信息` or times out without creating anything.
- `/api/v1/subscribe/` read-back confirms no duplicate exists.

Do **not** use this for TV seasons unless the season/episode fields are carefully mapped, and do not use it if the database backend is unknown.

## Workflow

1. Verify the target MoviePilot container and database backend. On this user's instance the Postgres container is typically `moviepilot_v2-postgresql-1`.
2. Check for an existing subscription first, both by API and DB if necessary:

```bash
python3 scripts/mp_request.py GET /api/v1/subscribe/ --compact --raw-out /tmp/mp_subscriptions.json

docker exec moviepilot_v2-postgresql-1 sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select id,name,year,type,keyword,tmdbid,state from subscribe where lower(coalesce(name,'"'"''"'"') || '"'"' '"'"' || coalesce(keyword,'"'"''"'"')) like '"'"'%backroom%'"'"' or coalesce(name,'"'"''"'"') like '"'"'%后室%'"'"' or coalesce(keyword,'"'"''"'"') like '"'"'%后室%'"'"';"'
```

3. Insert a minimal movie subscription row. Keep it conservative: `type='电影'`, `sites='[-1]'::json`, `state='R'`, `best_version=0`, `best_version_full=0`, `search_imdbid=0`, and include both Chinese/English keywords when title aliases are uncertain.

Example used for `Backrooms` / `后室`:

```bash
docker exec moviepilot_v2-postgresql-1 sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "insert into subscribe (name, year, type, keyword, tmdbid, include, sites, state, date, username, best_version, best_version_full, search_imdbid) values ('"'"'Backrooms'"'"', '"'"'2026'"'"', '"'"'电影'"'"', '"'"'后室|Backrooms|The Backrooms'"'"', 1083381, '"'"'后室|Backrooms|中文|中字'"'"', '"'"'[-1]'"'"'::json, '"'"'R'"'"', to_char(now(), '"'"'YYYY-MM-DD HH24:MI:SS'"'"'), '"'"'Hermes'"'"', 0, 0, 0) returning id,name,year,type,keyword,tmdbid,state;"'
```

4. Verify through the MoviePilot API, not just SQL:

```bash
python3 scripts/mp_request.py GET /api/v1/subscribe/<id> --output /tmp/mp_sub_<id>.json
python3 scripts/mp_request.py GET /api/v1/subscribe/ --compact --raw-out /tmp/mp_subscriptions_final.json
```

5. Optionally trigger a subscription search once:

```bash
python3 scripts/mp_request.py GET /api/v1/subscribe/search/<id> --output /tmp/mp_sub_<id>_search_trigger.json
```

`{"success":true,"data":{}}` is a successful trigger response, not evidence that resources were found.

## Reporting

Be explicit that this is a DB fallback because MoviePilot's normal API could not resolve metadata. Report the read-back subscription id and any missing metadata such as poster/overview. Do not imply the resource was downloaded unless active-download verification proves it.

## Pitfalls

- `POST /api/v1/subscribe/` can time out or return `未识别到媒体信息` for a valid future TMDB id if MoviePilot cannot hydrate metadata. Always read back the subscription list before falling back.
- A public TMDB page can be valid while MoviePilot `GET /api/v1/media/{tmdbid}` returns an all-null placeholder object. Treat that as “MoviePilot cannot hydrate this title yet”, not as proof the public TMDB id is wrong. Reconfirm the id/title/cast from the public page, then proceed with the DB fallback only after duplicate checks.
- When a future movie has multiple working titles or localized clue titles, preserve them in `keyword` and, conservatively, `include` so later resource searches can match any release naming. Example pattern: `逃出绝命街|The End of Oak Street|Flowervale Street|Oak Street` for TMDB movie `1101383`.
- Search result raw JSON may contain tracker cookies/passkeys. Store to `/tmp` and summarize safe fields only.
- Direct DB writes bypass app-level validation. Use only minimal, schema-compatible fields and verify via the API immediately afterward.
