# Session Notes: Media download selection and site health

Use these notes when the user asks for practical MoviePilot actions (not just recommendations): verify actual resources, prefer working sites, and confirm mutations.

## Site health workflow

1. List active sites:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/site/ --compact --raw-out /tmp/mp_sites.json
   ```
2. Test one site by ID:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/site/test/<site_id> --compact --raw-out /tmp/mp_site_test.json
   ```
3. For all active sites, iterate `/api/v1/site/test/{id}` and summarize failures by site name/domain/message. Do not print cookies, API keys, RSS passkeys, or full site records.
4. Common failure messages observed:
   - `Cookie已失效！` / `Cookie已过期` → ask user to refresh cookie or provide credentials out-of-band.
   - `无法通过Cloudflare！` → needs browser/Cloudflare clearance or CookieCloud refresh.
   - `403 Forbidden` / `无法打开网站！` → site/network/account problem.
   - `帐号不存在` on M-Team can correlate with tracker passkey/credential failures in download clients.
5. Cookie refresh endpoint requires username/password and optional code:
   ```bash
   GET /api/v1/site/cookie/{site_id}?username=...&password=...&code=...
   ```
   Never ask the user to paste credentials in chat; prefer a local config file with restrictive permissions.

## Episode resource selection workflow

When the user asks to download a specific TV episode:

1. Search with precise English and Chinese/title terms, including `SxxEyy` and desired resolution:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/search/title \
     --query "keyword=Monarch.Legacy.of.Monsters.S02E05%201080p&page=0" \
     --compact --raw-out /tmp/mp_search_episode.json
   ```
2. Parse candidates from `data[*]` and filter:
   - `meta_info.resource_pix == "1080p"` (or requested resolution)
   - `meta_info.begin_season` and `begin_episode` match, or `episode_list` contains the episode
   - exclude wrong seasons/collections/full-season packs unless explicitly requested
3. Compare candidate tradeoffs:
   - Smaller size is good, but low seed count can be too slow.
   - If the user says the small one is slow, switch to the highest-seeder 1080p candidate even if larger.
   - Report site, size, seeders, title/team, and why selected.
4. Add download via `/api/v1/download/add` using only the selected `torrent_info` (plus TMDB/Douban IDs if present):
   ```json
   {"torrent_in": <selected torrent_info>}
   ```
   ```bash
   python3 scripts/mp_request.py POST /api/v1/download/add \
     --json @/tmp/payload.json --compact --raw-out /tmp/download_resp.json
   ```
5. Verify by listing active downloads:
   ```bash
   python3 scripts/mp_request.py GET /api/v1/download/ --compact --raw-out /tmp/downloads.json
   ```
   Summarize hash, state, progress, speed, ETA, size, and downloader.

## User preference observed

For this user, MoviePilot-backed answers should use actual search/site/download data. For episode downloads, default to 1080p with smaller size, but consider seeders; if speed is poor, choose a higher-seeder release even if it is 2x larger.
