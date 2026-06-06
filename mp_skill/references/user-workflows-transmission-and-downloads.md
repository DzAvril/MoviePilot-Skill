# User Workflow Notes: MoviePilot + Transmission

## MoviePilot site health check

Use `GET /api/v1/site/` to list enabled sites and `GET /api/v1/site/test/{site_id}` to test each site. Summarize failures only; avoid echoing site cookies/API keys from raw site payloads.

Observed failure messages in this user's setup included:
- `Cookie已失效！` / `Cookie已过期`
- `无法通过Cloudflare！`
- `错误：403 Forbidden！`
- `帐号不存在`
- `无法打开网站！`
- `站点【None】不存在`

## Selecting a small 1080p episode download

For a request like “download <show> SxxExx, 1080p, as small as possible”:
1. Search with both Chinese and English title variants via `GET /api/v1/search/title`.
2. Parse `meta_info` to filter exact `begin_season`, `begin_episode` / `episode_list`, and `resource_pix == "1080p"`.
3. Sort candidates by `torrent_info.size`/`volume` ascending, but prefer a reachable/healthy site and nonzero seeders.
4. Add with `POST /api/v1/download/add` using `{"torrent_in": <torrent_info>}` when media metadata is not required. Use `POST /api/v1/download/` with `media_in` only when full media info is available/needed.
5. Verify with `GET /api/v1/download/` and report title, site, size, downloader, state, progress, speed, and hash.

Example outcome: for `Monarch Legacy of Monsters S02E05 1080p`, smallest viable result was ~1.42GB from 天空 with HDSWEB, added through QB and verified as downloading.

## Checking downloaded episodes, then filling missing 4K episodes

For a request like “帮我看一下已经下载到第几集了，还没有下载的帮我下载，4k 分辨率的”:
1. Check library/transfer reality before trusting TMDB season numbering. Use `GET /api/v1/history/transfer --query 'title=<中文名>&page=1&count=100'` and parse `season_episode`, `target`, `size`, and transfer time. If `mediaserver/exists` returns empty for a season, fall back to transfer history and active downloads.
2. Check active queue with `GET /api/v1/download/ --query 'name=<中文名>'`; if filtered search returns empty after adding a task, also query the full active list and match by Chinese title, English title, season/episode, or returned hash/download id.
3. Determine the latest downloaded episode from transfer history. Prefer MoviePilot's actual season numbering over external metadata if they disagree (e.g. a show may be organized as `S09` even if TMDB displayed a different season label).
4. Search missing episodes with multiple variants: Chinese title + year + `SxxEyy 2160p`, Chinese title + `4K`, English title + `SxxEyy 2160p`, and episode text such as `第4期 2160p`.
5. For 4K requests, filter exact episode and `2160p`/`4K`; distinguish 正片 from `Plus`/加更 and `Program`/企划 unless the user asks for extras.
6. Prefer the exact main episode with healthy seeders. If there are multiple 2160p candidates, report why the selected one wins (seeders, site, size, source/codec).
7. Add via `POST /api/v1/download/add` and verify with a broad `GET /api/v1/download/` if the narrow `name=` filter misses it. Report state, speed, progress, ETA, downloader, and hash/download id.

Example outcome: for `妻子的浪漫旅行` 2026, transfer history showed actual organization as `S09E01`–`S09E03`; `S09E04` main episode was added as `2160p WEB-DL H265 AAC` from 观众 (~6.10GB, 99 seeders), then verified in the QB active list by matching the returned hash.

## Checking whether latest subscribed episodes are missing before downloading

For requests like “<show> 有最新集没下载吗？有的话帮我下载” or “下载最新集”:
1. Start from the subscription detail (`GET /api/v1/subscribe/{id}`) when the show is already subscribed. Use `note` as the episodes MoviePilot currently considers obtained, `lack_episode`/`total_episode` as the remaining target, and `include`/`exclude` to preserve season and main-episode filtering.
2. Read `GET /api/v1/subscribe/files/{id}` next. On this instance the response is an object with `subscribe` plus an `episodes` **map** keyed by episode number strings, not a flat `data` list. Each episode entry contains `download` and `library` arrays. Derive the local/latest obtained episode by scanning that map for the highest episode with non-empty `download` or `library` evidence.
3. If `subscribe/files` shows missing future episodes, verify whether resources exist before downloading. For Chinese drama/variety subscriptions, search `keyword=<Chinese title/year variant>&page=0&count=50`; `page=1` may return older season pack results or miss current-season singles that `page=0` returns. Also try exact forms such as `SxxEyy`, but note exact English `SxxEyy` searches can return zero even when broad Chinese/year search finds the episode.
4. Filter search results by `meta_info.begin_season`, `episode_list`, `resource_pix`, and the subscription `exclude` terms (`Plus|Program|加更|企划|特别企划`) so extras are not mistaken for main episodes.
5. If the highest available episode is already in `subscribe/files`/library, report that there is no newer downloadable main episode and do not add old duplicates. If newer main episodes exist, compare the highest searchable episode number against the highest local episode from `subscribe/files`, then choose the newest sane pack/single that covers the missing episode(s). A `E23-E24` pack is acceptable when local is already at `E23` and `E24` is the true gap.
6. Verify additions via the broad active-download list (`GET /api/v1/download/`) using the returned hash/download id. Title-filtered lookups can miss newly added tasks.
7. Treat subscription `note` as a hint, not authoritative. It may lag behind actual library/download evidence; `subscribe/files/{id}` can show later episodes already transferred even when `note` or `lack_episode` looks older. Base “latest missing episode” decisions on `subscribe/files` first, then search resources beyond the max library/download episode.

Session example: `妻子的浪漫旅行` subscription id 386 (`S09`, target 7 episodes) had library/download evidence for E01–E05 and missing E06–E07. Broad Chinese/year `page=0` search found S09 results only up to E05; exact `Viva La Romance S09E06/E07` returned no resources, so no download was added.

Session example: `良陈美锦` subscription id 389 previously had subscription `note` only through E16, but `subscribe/files/389` showed library/download evidence through E20. Broad 4K searches (`良陈美锦 2160p`, `A Splendid Match S01 2160p`) found E21–E22 as the latest available main episodes; the best selection was a UBits `S01E21-S01E22 2160p WEB-DL 50Fps HDRVivid H265 10bit AAC` pack (~5.79 GiB, 40 seeders, 2X free), then verified via the broad active-download list rather than relying on title-filtered lookup.

Session example: later `良陈美锦` “下载最新集” checks found `subscribe/files/389` already had library/download evidence through E23 while search results reached E24. The best practical pick was a high-seeder 天空 `S01E23-E24 1080p WEB-DL AAC H264-HDSWEB` pack (~1.43 GiB, 116 seeders). Even though it re-includes E23, it correctly fills the real gap at E24 and verifies cleanly by hash in the broad active-download list.

## Download available 4K episodes, then subscribe the rest

For a request like “帮我下载一个电视剧，<title> 4K；如果还没更新完就继续订阅”:
1. Identify the exact show with `GET /api/v1/media/search --query 'title=<title>&type=media&page=1&count=10'`, then fetch season metadata via `/api/v1/tmdb/seasons/<tmdbid>` to get season number and total episode count.
2. Search resources with multiple variants: `<Chinese title> 4K`, `<Chinese title> 2160p`, `<Chinese title> Sxx 2160p`, and exact episode forms such as `SxxE01 2160p`. Parse `meta_info.episode_list`, `begin_season`, `resource_pix`, site, size, and seeders.
3. If current resources are split into packs and singles, select the smallest/highest-seeder non-overlapping set that covers currently released episodes. Prefer healthy high-seeder 2160p H265 packs for ranges, but use high-seeder single episodes when needed.
4. Add each selected torrent through `POST /api/v1/download/add` with `{"torrent_in": <torrent_info>}` saved in a temp JSON file; never paste raw torrent URLs or passkeys.
5. Verify additions by querying the broad active download list (`GET /api/v1/download/`) and matching returned hashes/title; the filtered `name=<Chinese title>` query can miss newly added items even when the full list shows them. Also query transfer history (`/api/v1/history/transfer --query 'title=<Chinese title>&page=1&count=100'`) because small episodes may finish and transfer before the verification call.
6. If `POST /api/v1/download/add` returns HTTP 500 for individual early episodes, do not blindly retry the same payload. Check transfer history and active downloads first: on this instance a 500 can coincide with episodes already transferred/duplicate-handled. If early singles are still missing, search for a range pack such as `S01E01-E06 2160p` and add that pack to fill gaps.
7. If total season episode count exceeds the episodes just added/transferred, create a subscription for the remainder with `POST /api/v1/subscribe/`: set `season`, `total_episode`, `start_episode` to the next missing episode, `lack_episode` to the remaining count, `resolution` to `4K|2160p|x2160`, `include` to the season code such as `S01`, `sites: [-1]`, and `state: "R"`. Preserve MoviePilot's canonical title exactly when possible, including invisible/variant characters returned by media search.
8. Read back `/api/v1/subscribe/{id}` and report the subscription id, start episode, remaining count, and active download states.

Session example: 《良陈美锦》/A Splendid Match (2026), TMDB `283952`, S01 total 16. Available 2160p resources covered S01E01–E06; selected 天空 HDSWEB packs E01–E03 and E04–E05 plus 观众 ADWeb E06, then created subscription from `start_episode=7` with `lack_episode=10`.

Session example: 《两心不疑​》/No Doubt in Us (2026), TMDB `288088`, S01 total 24. Resources covered S01E01–E10. Single-episode additions for E01/E02 returned HTTP 500, but transfer history showed several episodes had already transferred; adding a 天空 HDSWEB `S01E01-E06` pack filled the remaining early gaps. Subscription was then created from `start_episode=11` with `lack_episode=14`.

## Secret-safe handling

MoviePilot site/list/search responses can include cookies, RSS passkeys, API keys, and torrent download URLs. Do not paste raw compact previews if they include these fields. Write raw responses to `/tmp` and summarize safe fields only: id, name, domain, status/message, site_name, size, seeders, resolution, title.
