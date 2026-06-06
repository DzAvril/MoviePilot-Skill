# Future-title clue disambiguation + duplicate subscription check

Use this when the user gives an incomplete movie clue such as actor/cast, partial Chinese title, or "这部帮我订阅" after a failed first match.

## When to use

- Initial MoviePilot title search matched the wrong title or an unrelated foreign title.
- The user corrects with cast clues like "郑恺主演的".
- The user asks to subscribe, but the exact canonical title is still uncertain.

## Workflow

1. **Resolve the exact title from current public sources first**
   - Use current web search with the actor + partial title clue.
   - Prefer authoritative movie pages such as Douban/Baidu Baike/TMDB result snippets to confirm:
     - Chinese title
     - year / release date
     - type (movie vs TV)
     - key cast clue actually matches
   - Example: `郑恺 消失的人 电影` resolves to `消失的人 (2026)` with Douban subject `36965301`.

2. **Check whether it is already subscribed before creating anything**
   - Query `GET /api/v1/subscribe` and search the list for the resolved title/year/type.
   - If an existing subscription is found, stop the create flow and report the existing subscription id/status.
   - Do not create a second near-duplicate subscription just because the user said "帮我订阅" again.

3. **Check current resources after title resolution**
   - Run `GET /api/v1/search/title?keyword=<title> <year>`.
   - If needed, run exact media-id search such as `GET /api/v1/search/media/<tmdbid>` after resolving the canonical media id from the existing subscription or MoviePilot metadata.
   - Report clearly whether the state is:
     - already subscribed + no resources yet
     - already subscribed + resources exist
     - not subscribed + no resources yet
     - not subscribed + resources exist

4. **Only create the subscription if no existing one matches**
   - If no existing subscription is found and no resources exist yet, proceed with the TMDB-grounded subscription workflow.

## What to tell the user

Keep it compact:
- exact title identified;
- whether it was already subscribed;
- subscription id if present;
- whether resources currently exist.

## Pitfalls

- A broad `search/title` query can surface the wrong film entirely, especially foreign titles sharing a Chinese phrase.
- For this class of request, the user's cast correction is a strong disambiguation signal; treat it as authoritative enough to re-resolve the title before any mutation.
- `GET /api/v1/douban/{doubanid}` can confirm the title/year/type and synopsis, but it may not always expose a usable `tmdb_id`; an existing MoviePilot subscription may already contain the canonical `tmdbid`, so check subscriptions early.
- "帮我订阅" does **not** mean "blindly create a new subscription". Always perform the duplicate check first.
