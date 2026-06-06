# Future TV Season False-Completion Diagnostics

Use this when a future/unreleased TV season subscription appears to have “达成”, disappears from the active subscription list, or shows `total_episode=0` / `lack_episode=0` despite the season not being released.

## Symptom Pattern

- `GET /api/v1/subscribe/` no longer contains the title, but `GET /api/v1/subscribe/history/电视剧` contains one or more rows.
- The history row is season-scoped, for example `season: 2` and `include: S02`.
- `total_episode` and `lack_episode` are `0`.
- `completed_episode` may be non-zero because MoviePilot can carry completed episode counts from another season on the same TMDB series.
- Active downloads and transfer history do not show the target season.

This is usually a **false completion**: MoviePilot treated `0 missing of 0 total` as complete, not actual download completion.

## Diagnostic Workflow

1. Read active subscriptions and search by Chinese title, English title, and TMDB id:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/subscribe --compact --raw-out /tmp/mp_subscriptions.json
   ```
   If absent, continue to subscription history rather than concluding it was never subscribed.

2. Read TV subscription history and filter locally, keeping only safe fields:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/subscribe/history/%E7%94%B5%E8%A7%86%E5%89%A7 --output /tmp/mp_sub_hist_tv.json
   ```
   Report fields: `id`, `name`, `keyword`, `tmdbid`, `season`, `include`, `resolution`, `total_episode`, `lack_episode`, `completed_episode`, `date`, `description`.

3. Check active downloads:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/download/ --output /tmp/mp_downloads.json
   ```
   Empty active downloads are not proof of completion; they only mean nothing is downloading now.

4. Check download and transfer history across enough rows to avoid only seeing recent items:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/history/download --query 'page=1&count=200' --output /tmp/mp_hist_download_p1.json
   python3 scripts/mp_request.py GET /api/v1/history/transfer --query 'page=1&count=200' --output /tmp/mp_hist_transfer_p1.json
   ```
   Filter by Chinese title, English title, TMDB id, and explicit season markers such as `S02`. If only S01 entries exist, say so directly.

5. Verify current resources with both fuzzy and exact searches:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/search/title --query 'keyword=<中文名>&page=0' --output /tmp/mp_search_cn.json
   python3 scripts/mp_request.py GET /api/v1/search/title --query 'keyword=<English Title>&page=0' --output /tmp/mp_search_en.json
   python3 scripts/mp_request.py GET /api/v1/search/media/tmdb:<tmdbid> --output /tmp/mp_search_exact.json
   ```
   Treat fuzzy hits containing `S02` as suspicious until the recognized media/title also matches. Generic English words can match unrelated shows.

6. If the TMDB id is known, check season metadata:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/media/seasons --query 'mediaid=tmdb:<tmdbid>' --output /tmp/mp_media_seasons_<tmdbid>.json
   ```
   If MoviePilot only returns S01, a future S02 `0/0` completion is not evidence of actual release or download.

## Interpretation Rules

- Active subscription absent + history row with target `season/include` + `total_episode=0` and `lack_episode=0` + no target-season downloads/transfers = false completion.
- `completed_episode` is not reliable for a future season if the same TMDB series has a previously completed season. Cross-check the explicit season in torrent/history entries.
- Fuzzy search results are availability hints only; unrelated S02 titles can appear when the query contains common words. Require exact media match or title/year/season validation before claiming resources exist.
- If exact TMDB search returns no resources, do not say “downloaded”; say the season has no matching resources yet and the subscription needs to be recreated or held with corrected metadata.
- Subscription history IDs are history-row IDs, not guaranteed live subscription IDs. Do not call `/api/v1/subscribe/{id}` or `/api/v1/subscribe/files/{id}` on a history ID and treat the result as that history item; ID collisions can return an unrelated current subscription.

## Remediation

For unreleased/future seasons, avoid creating a subscription that can collapse to `0/0` complete:

- Prefer a season-scoped subscription with explicit `include` such as `S02`.
- If the API supports it, set a realistic `total_episode` once known; otherwise record that `0/0` can falsely complete.
- After creating/recreating, immediately read back the active subscription. If it moves straight to history, inspect history before reporting success.
- If MoviePilot cannot hydrate a valid future season via the normal API, use a database fallback only after duplicate checks and read-back verification.

## Reporting Template

- **状态**: active subscription present/absent; history row id/date if present.
- **为什么“达成”**: explain `0/0` and any cross-season `completed_episode` contamination.
- **下载证据**: active downloads, download history, transfer history; explicitly list which season/episodes were found.
- **资源证据**: fuzzy/exact search result and whether matches are exact or unrelated.
- **下一步**: recreate/fix subscription, or wait for resources if no exact target-season resources exist.

## Session-Proven Example

《豺狼的日子 / The Day of the Jackal》S02 had history rows with `season=2`, `include=S02`, `total_episode=0`, `lack_episode=0`, and `completed_episode=10`. Active subscriptions no longer contained it. Download history only showed S01 E01-E10 from 2024, transfer history had no Jackal rows across the checked pages, and exact TMDB resource search returned 0. Correct conclusion: S02 was falsely marked complete; it was not downloaded.
