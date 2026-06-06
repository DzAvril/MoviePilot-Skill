# TV episode update status check

Use this when the user asks “更新到哪一集了” / “现在到第几集了” for an actively airing TV show.

## Goal

Report two separate states:

1. **Latest available resources on tracker/search** — highest episode present in search results.
2. **Local/subscription state** — what MoviePilot has already organized/downloaded or still lacks.

This avoids saying “updated to X” when resources exist but the user's library is only at Y.

## Workflow

1. Search resources by Chinese title:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/search/title \
     --query 'keyword=<title>&page=1&count=10' \
     --compact --raw-out /tmp/mp_<slug>_search.json
   ```
2. Parse `/tmp/..._search.json` locally, never paste raw search output. Extract safe fields only:
   - `meta_info.episode_list` max episode
   - `meta_info.resource_pix`, `resource_type`
   - `torrent_info.site_name`, `seeders`, `size`, `pubdate`
   - title/description only if safe and useful
3. Check subscription list for matching title:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/subscribe --compact --raw-out /tmp/mp_subs.json
   ```
   If a subscription ID is found, read it:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/subscribe/<id> --compact --raw-out /tmp/mp_sub_<id>.json
   ```
   Useful fields: `total_episode`, `start_episode`, `lack_episode`, `note`, `state`, `resolution`, `last_update`.
4. Check active downloads:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/download --compact --raw-out /tmp/mp_downloads.json
   ```
5. Check transfer history for local/library max episode:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/history/transfer \
     --query 'page=1&count=100' \
     --compact --raw-out /tmp/mp_hist_transfer.json
   ```
   Parse paths/titles for `SxxEyy` and title matches; summarize only episode numbers and dates, not full paths unless asked.

## Response shape

Keep it compact:

- **结论**: “资源到第 N 集；本地目前到第 M 集。”
- **已查到**: latest resource group(s), resolution, seeders/site if useful.
- **注意**: active downloads / subscription mismatch / missing episodes.
- Offer to download missing episodes only if resources exist and no active download already covers them.

## Pitfalls

- Do not treat subscription `lack_episode` alone as latest available episode. It may be a target/missing marker, not current tracker availability.
- Do not answer only from search results if the user likely cares about their local MoviePilot state.
- Do not paste raw search previews: they can contain tracker cookies, passkeys, or torrent URLs.
- Search results may include batches (`S01E01-S01E19`) and pairs (`S01E19-S01E20`); compute the maximum from `episode_list`, not from visual sorting.
