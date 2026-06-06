# Movie resource search and download workflow

Use this when the user asks whether a movie/TV title has downloadable resources, asks to download one of the options, or says “没有就订阅”.

## Resource check

1. Search by title and write raw output to a temp file. **Suppress helper stdout/stderr to a private log** because even `--output` can print compact previews containing nested `torrent_info.site_cookie`, `enclosure`, `page_url`, passkeys, or other site secrets:
   ```bash
   cd /opt/data/skills/productivity/moviepilot-api-control
   python3 scripts/mp_request.py GET /api/v1/search/title \
     --query 'keyword=<title>&page=0' \
     --output /tmp/mp_search_<slug>.json \
     >/tmp/mp_search_<slug>.log 2>&1
   ```
   Do not paste the helper log into chat; parse only the saved JSON with a local safe-field script.
2. Do **not** use `--compact` for raw search results in chat-facing sessions unless you have verified the helper will not preview secret-bearing torrent fields. Search payloads can include tracker cookies and direct download URLs.
3. If the title may be misspelled, newly released, or colloquial (e.g. `阿麽` vs `阿嬷`), first verify the canonical title/year via current public sources, then search MoviePilot using several safe variants. For very recent theatrical films, no tracker results is expected; report that plainly and offer subscription or official streaming checks instead of broad noisy searches.
4. **Do not over-normalize ambiguous title phrases into seasons.** If the user says something like “最后一季/最后一击/最终章/特别篇” and the phrase could be part of a title, search the exact Chinese phrase and punctuation variants first (`惩罚者 最后一击`, `惩罚者：最后一击`, `The Punisher One Last Kill`) before assuming a TV season such as `S02`. If the first search yields a plausible exact-title special/movie, correct the interpretation and summarize that result set rather than continuing with season resources.
5. **For Chinese titles with a movie/TV name collision, disambiguate through media metadata before downloading.** Use `/api/v1/media/search --query 'title=<title>&type=media&page=1&count=10'` to identify the intended `type=电影`, year, TMDB id, and English title. If exact `/api/v1/search/media/{tmdbid}` returns no resources or only an empty shell, fall back to `/api/v1/search/title` with English-title + year variants (for example `My Own Swordsman 2011`, `My Own Swordsman The Movie 2011`, `<Chinese title> 2011 1080p`) and then filter locally. Penalize/exclude TV-series signals such as `S01`, `E01`, `全81集`, `Complete`, `PACK`, or the TV year when the user asked for the movie edition.
6. Parse the saved JSON locally and summarize only safe fields:
   - title / release name
   - site display name
   - size in GiB
   - seeders/peers
   - resolution, source, encode, audio, HDR/HQ/REMUX effects
   - volume factor/freeleech labels, if present
4. If matching resources exist, **do not subscribe automatically** even if the user said “没有就订阅”. Present the best options or proceed to download if the user specified a choice.
5. If no matching resources exist, then add or verify a subscription using the subscription endpoints and read back the result.

## Selecting and adding a download

1. Select the exact result from the saved search JSON with deterministic filters from the user’s choice (size, site, seeders, resolution, team, title). Save the selected object to `/tmp/mp_selected_<slug>.json`.
2. For search results that lack recognized `media_info`, add with `/api/v1/download/add` using only:
   ```json
   {"torrent_in": <selected torrent_info>}
   ```
   Example:
   ```bash
   python3 scripts/mp_request.py POST /api/v1/download/add \
     --json @/tmp/mp_download_<slug>_payload.json \
     --output /tmp/mp_download_<slug>_response.json
   ```
3. Summarize the add response with only `success`, `message`, and non-secret status fields.

## Verification

1. First try `GET /api/v1/download/` with a query name if useful, but do not rely on English title matching; MoviePilot/clients may rename tasks with Chinese titles.
2. If filtered verification returns zero, fetch all current downloads and locally match on any known title aliases/segments such as Chinese title, English title, release team, or file name fragments.
3. Report concise safe verification fields: display title, state, progress, size, and maybe speed/ETA if returned. Redact hashes to a short prefix if shown.

## Pitfalls

- `scripts/mp_request.py --compact` can still preview nested `torrent_info` fields from search results, including site cookies and download URLs. In practice, even `--output` may print a JSON summary/preview to stdout that includes secret-bearing nested fields. Redirect helper stdout/stderr to a private temp log and never quote that log; inspect the saved JSON only through a safe-field parser.
- `/api/v1/search/title` may return `media_info: null` for newly released or not-yet-recognized movies; `/api/v1/download/add` with `torrent_in` is the right endpoint in that case.
- English-name filtered active-download queries can miss tasks after the downloader renames them to Chinese titles; verify against the full active list before saying the add failed.
