# Unrecognized fuzzy movie subscription

Use this when the user gives only a bare/fuzzy movie title and asks to subscribe it.

## Workflow

1. Verify MoviePilot API reachability with a harmless authenticated read such as `/api/v1/user/current`.
2. Search MoviePilot metadata first:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/media/search --query "title=<title>&type=media&page=1&count=10" --output /tmp/mp_media_<slug>.json
   ```
3. Check existing subscriptions before creating anything:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/subscribe/ --compact --raw-out /tmp/mp_subscriptions_<slug>.json
   ```
4. If metadata search is empty but the title looks like a normal movie request, a minimal movie subscription attempt is acceptable:
   ```json
   {
     "name": "<title>",
     "type": "电影",
     "sites": [-1],
     "state": "R",
     "best_version": 0,
     "search_imdbid": 0
   }
   ```
5. If POST `/api/v1/subscribe/` returns `未识别到媒体信息`, stop cleanly. Report that no subscription was created and ask for a stronger identifier: English title, year, Douban/TMDB link, or poster/screenshot.

## Pitfalls

- Do not report success unless a create response returns an id and a read-back confirms the subscription.
- Do not keep probing unrelated search engines after MoviePilot and TMDB-style searches fail; the useful next input is a stronger identifier from the user.
- Do not use database fallback/manual insert without a confirmed TMDB/media identity. The fallback is for known future titles that MoviePilot cannot hydrate, not unknown or possibly mistyped titles.
