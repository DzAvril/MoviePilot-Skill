# Weekend Movie Recommendation Continuation Notes

Use this when the user resumes a WeChat movie recommendation thread with shorthand such as “继续 #12”, “继续上次推荐”, or a prior numbered recommendation topic.

## Workflow

1. Search recent sessions first, not only exact text matches. If exact `#12` search returns empty, inspect recent WeChat sessions and title/preview summaries for the matching recommendation thread.
2. Load MoviePilot recommendations and availability before answering:
   - Candidate feeds: `/api/v1/recommend/douban_movie_hot`, `/api/v1/recommend/douban_showing`, `/api/v1/recommend/tmdb_trending`, `/api/v1/recommend/douban_movie_top250`.
   - Resource verification: `/api/v1/search/title?keyword=<title>&page=0` for each short-list title.
3. For WeChat, keep the final recommendation compact: ranked bullets, one-line reason, and the best availability signals. Avoid dumping raw JSON or long endpoint details.
4. Summarize only safe fields from search results: total result count, resolution mix, source types (`BluRay`, `WEB-DL`, `UHD`, `REMUX`), HDR/DV/Atmos signals, site spread, and seeder maximum if present.
5. Prefer titles with abundant resources and clear quality options. If a search title is ambiguous, state that it needs an exact filter before download.

## Ambiguity Pitfall

MoviePilot title search can mix sequels/remakes with the intended title. Example: searching `疯狂动物城` returned many results dominated by `疯狂动物城2`; do not present that as verified availability for the first movie without an exact-title/year filter. Mark it as “needs exact filtering” before download.

## Useful Local Pattern

For multiple candidate checks, write each raw search result to `/tmp/search_<title>.json`, then parse safe summary fields from `data[*].meta_info` and `data[*].torrent_info` instead of pasting raw results into chat.