# Latest Episode Download Workflow

Use for prompts like “下载最新集”, “有最新集就下”, or “帮我下最新更新的一集/两集”.

## Goal

Determine the highest episode already present locally for a subscribed show, compare it with current searchable resources, and add the newest practical resource that covers the real gap.

## Steps

1. Find the subscription id with `GET /api/v1/subscribe` if the user only gave a title.
2. Read `GET /api/v1/subscribe/{id}` for season, note, target totals, and include/exclude rules.
3. Read `GET /api/v1/subscribe/files/{id}`.
   - On this instance the payload shape is:
     - `subscribe`: subscription metadata
     - `episodes`: object keyed by episode number strings (`"1"`, `"2"`, ...)
   - Each `episodes[ep]` entry may contain `download` and `library` arrays.
   - Compute the local max episode from the highest episode where either array is non-empty.
4. Search resources broadly with `GET /api/v1/search/title --query 'keyword=<title>&page=0&count=50'` and, if needed, title variants including year or English title.
5. Parse only safe fields from the saved JSON: season, episode list, resolution, site, seeders, size, title.
6. Compute the search max episode from `meta_info.episode_list` and keep only the target season.
7. If `search_max <= local_max`, report that there is no newer downloadable main episode.
8. If `search_max > local_max`, select the newest practical result that covers the missing episode(s):
   - Prefer healthy seeders and sane size over rigid exact-single matching.
   - Accept a small overlap pack like `E23-E24` when local is already at `E23` and `E24` is the real gap.
   - Avoid suspicious tiny files/samples unless no proper source exists.
9. Add via `POST /api/v1/download/add` using `{"torrent_in": <torrent_info>}`.
10. Verify with the broad active download list (`GET /api/v1/download/`) by matching returned hash or download id, not only filtered title search.

## Pitfalls

- `subscribe.note` can lag behind reality. Treat it as a hint only.
- `subscribe/files/{id}` is not a flat list on this instance; code that expects `data[]` will misread it.
- `search/title` can return a top-level object with the actual results under `data`; do not assume `items`.
- Title-filtered active-download lookups can miss a freshly added task; broad list + hash match is safer.
- The latest practical source may be 1080p even if older episodes were 4K. Match the user’s request first; if unspecified, download the newest sane source rather than stalling for ideal specs.

## Session example

`良陈美锦` (subscription id `389`):
- `subscribe/files/389` showed library/download evidence through `E23`.
- Broad search showed resources through `E24`.
- Best practical pick: 天空 `A Splendid Match S01E23-E24 2026 1080p WEB-DL AAC H264-HDSWEB` (~1.43 GiB, 116 seeders).
- Added successfully and verified in `/api/v1/download/` as `downloading` by hash.
