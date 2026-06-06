# Subscription Auto-Download Diagnostics

Use this when a user says a MoviePilot subscription “一直不能自动下载” or “订阅了没动”. The failure may be UI/status staleness rather than download failure.

## Diagnostic pattern

1. Read the subscription list/detail and capture safe fields only:
   - Current subscriptions: `GET /api/v1/subscribe --output /tmp/mp_subs.json`.
   - If the expected TV subscription is absent, read subscription history before concluding it was never created or already downloaded:
     ```bash
     python3 scripts/mp_request.py GET /api/v1/subscribe/history/%E7%94%B5%E8%A7%86%E5%89%A7 --output /tmp/mp_sub_hist_tv.json
     ```
   - Safe fields: `id`, `name`, `type`, `year`, `tmdbid`, `season`, `total_episode`, `lack_episode`, `completed_episode`, `resolution`, `include`, `exclude`, `sites`, `state`, `note`, `last_update`, `date`, `username`.
   - Future seasons can move to history as a false `0/0` completion; use `references/future-tv-season-false-completion-diagnostics.md` for that case.
2. Search current resources for the title:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/search/title --query 'keyword=<title>&page=0' --output /tmp/mp_search_<slug>.json
   ```
   Parse locally for safe metadata only: target season (`S02`, etc.), episode coverage, 2160p/1080p counts, max seeders, and site spread. Do not paste raw torrent fields. Beware fuzzy matches from unrelated shows; require both title/TMDB context and target-season checks before saying resources exist.
3. For known TMDB media, cross-check metadata/resource grounding:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/media/seasons --query 'mediaid=tmdb:<tmdbid>' --output /tmp/mp_media_seasons_<tmdbid>.json
   python3 scripts/mp_request.py GET /api/v1/search/media/tmdb:<tmdbid> --output /tmp/mp_search_media_<tmdbid>.json
   ```
   If `media/seasons` only returns S01 and a future S02 subscription has `total_episode=0`, treat any completion as suspect until target-season resources/history prove otherwise.
4. Check active downloads:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/download/ --output /tmp/mp_downloads.json
   python3 scripts/mp_request.py GET /api/v1/download/clients --output /tmp/mp_dl_clients.json
   ```
5. Check transfer history, not only download history. Completed downloads may already be removed from the downloader and may not appear in `/api/v1/history/download` keyword-filtered results, while transfer history confirms actual organization:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/history/transfer --query 'page=1&count=300' --output /tmp/mp_hist_transfer.json
   python3 scripts/mp_request.py GET /api/v1/history/download --query 'page=1&count=300' --output /tmp/mp_hist_download.json
   ```
   Filter locally by `title`, `tmdbid`, known English title, and target season/episode tokens (`S02`, `S02E`, `Season 2`). Summarize episodes, dates, and whether entries have `download_hash`.
6. Compare three numbers:
   - Resource max episode currently searchable for the target season.
   - Local/transfer/download-history max episode already organized or downloaded for the target season.
   - Subscription `total_episode - local_max` vs `lack_episode`; if `total_episode=0`, do not use this arithmetic as proof of completion.

## Interpreting results

- If resource max episode equals local/transfer max episode and `lack_episode == total_episode - local_max`, then auto-download is probably healthy; remaining episodes have not appeared yet.
- If a future season subscription shows `total_episode=0`, `lack_episode=0`, or lands only in subscription history with `state=null`, treat “达成/完成” as suspicious rather than proof of success. Cross-check the target season (`S02`, etc.) specifically in current resources and histories; a same-title same-TMDB first-season completion count can make MoviePilot report a future season as complete even when no target-season resource exists.
- If manual subscription search finds matching resources but finishes with `匹配完成，共匹配到 0 个资源`, inspect the subscription's missing episode set before blaming filters. MoviePilot can log many candidate torrents as rule-matched, then discard them because they only cover episodes already present locally; the remaining `lack_episode` may be future/unavailable episodes.
- Distinguish the two automatic paths:
  - Frequent subscription refresh in `SUBSCRIBE_MODE=spider` mainly consumes site homepage/cache results and can miss fast-moving TV episodes after tracker homepages roll over.
  - Full subscription title search is controlled by `SUBSCRIBE_SEARCH=true` and `SUBSCRIBE_SEARCH_INTERVAL`; a 24-hour interval can be too slow for daily/fast-updating dramas. If resources exist and manual search succeeds but scheduled auto-search lags, recommend lowering the interval conservatively (usually 3–6 hours) rather than changing quality rules.
- Subscription fields such as `note` and `last_update` can look stale even after later episodes were downloaded and transferred. Treat transfer history and library presence as stronger evidence than the subscription detail display.
- Active downloads being empty is not a failure if transfer history shows recent successful imports; it often means tasks already completed and were cleaned up.
- A TV season can be falsely marked “completed/达成” when MoviePilot has no season metadata yet: e.g. a future S02 subscription may show `total_episode=0`, `lack_episode=0`, and a misleading `completed_episode` inherited from S01. Do not report this as downloaded. Verify with current media seasons (`/api/v1/media/seasons?mediaid=tmdb:<tmdbid>`), exact media resource search, active downloads, download history, and transfer history.
- Subscription history IDs are history-row IDs, not guaranteed live subscription IDs. Do not call `/api/v1/subscribe/{id}` or `/api/v1/subscribe/files/{id}` on a history ID and treat the result as that history item; ID collisions can return an unrelated current subscription. Use history fields plus independent searches/history checks for read-back.
- For domestic shows with English tracker titles, parse both Chinese title and English title/resource patterns (e.g. `A Splendid Match`) and episode ranges like `S01E20-E21`.

## Changing subscription search interval

When the diagnosis points to the scheduled full-title subscription search being too infrequent, change the MoviePilot setting instead of loosening quality filters:

1. Inspect the current config inside the container:
   ```bash
   docker exec MoviePilot sh -lc "grep -n 'SUBSCRIBE_SEARCH' /config/app.env || true"
   ```
2. Back up `/config/app.env`, then add or update the interval. MoviePilot's env file convention uses quoted values:
   ```bash
   docker exec MoviePilot sh -lc 'cp /config/app.env /config/app.env.bak.$(date +%Y%m%d%H%M%S)'
   # then set:
   # SUBSCRIBE_SEARCH='True'
   # SUBSCRIBE_SEARCH_INTERVAL='6'
   ```
3. Restart MoviePilot so scheduler jobs are rebuilt from the config:
   ```bash
   docker restart MoviePilot
   ```
4. Verify with the MoviePilot virtualenv Python, not the system Python, because `/usr/local/bin/python` may not have MoviePilot dependencies:
   ```bash
   docker exec MoviePilot sh -lc '/opt/venv/bin/python - <<"PY"
   from app.core.config import settings
   print("SUBSCRIBE_SEARCH", settings.SUBSCRIBE_SEARCH)
   print("SUBSCRIBE_SEARCH_INTERVAL", settings.SUBSCRIBE_SEARCH_INTERVAL)
   PY'
   ```

Use 6 hours as the conservative default; 3 hours is more aggressive. Avoid much lower values unless the user accepts higher tracker search load.

## Reporting style

Start with whether the chain is actually broken. Then report:
- Subscription state and rules.
- Resource max episode and quality coverage.
- Local/transfer max episode and recent successful episodes.
- Whether the remaining missing count matches unreleased/unavailable episodes.
- If you changed scheduler/config state, separate **已执行的改动** from **建议**, and include the verification value read back from MoviePilot.

Avoid saying “没自动下载” unless transfer/download evidence proves it. If it is only a UI/status mismatch, call that out explicitly.

## Session-proven examples

- 《良陈美锦》/2026 (`tmdbid=283952`) looked like it was not auto-downloading because the subscription detail had stale-looking `last_update` and `note`. Search showed resources through E22; transfer history showed E17–E22 downloaded/organized, including E21–E22 at 2026-05-14 02:55–02:57. `total_episode=36`, local max E22, and `lack_episode=14` matched exactly, so the correct conclusion was: auto-download was working; E23+ had not appeared yet and the subscription display was misleading.
- The Day of the Jackal / 《豺狼的日子》 S02 (`tmdbid=222766`) looked “达成” in subscription history, but the row had `total_episode=0`, `lack_episode=0`, `completed_episode=10`, `include=S02`, and `state=null`. Current media seasons only returned S01 with 10 episodes; active downloads were empty; download history only showed S01E01-E10; transfer history had no S02/Jackal hits; exact media search returned no resources. Correct conclusion: S02 was not downloaded; MoviePilot falsely completed a future/unknown season by carrying same-title/S01 completion context.