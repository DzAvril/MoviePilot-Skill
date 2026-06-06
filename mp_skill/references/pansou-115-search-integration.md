# PanSou / PanHub 115 Resource Search Integration

Use this note when the user wants to avoid Telegram user-account automation for 115 resources and instead search public/aggregated net-disk indexes, then hand safe results to MoviePilot's `P115StrmHelper`.

## Why this matters

Telethon/Pyrogram user-account automation is risky for disposable or one-time-SMS Telegram accounts: first login needs a code from an existing Telegram client or the original phone number, sessions can be invalidated, and server/datacenter IP automation can trigger account restrictions. Prefer a search API when available.

## Likely services

- **PanSou / 盘搜** — API-oriented. Public docs observed at `https://pansou.app/api`; GitHub projects are commonly named `pansousou` / `pansou` (for example `mybianfu/pansousou`, upstream text references `fish2018/pansou`). Described as a high-performance net-disk resource search API using TG channels plus plugin searches.
- **PanHub** — search UI / aggregator that covers Aliyun, Quark, Baidu, 115, Xunlei, etc.; useful as a service candidate but less directly API-shaped than PanSou.
- **Commercial aggregators** such as 千寻 API (`api.lvxiaodong.com`) or 我爱 API / 52api may expose similar endpoints but can require tokens, payment, or have unknown limits.

## PanSou API shape

Endpoint:

```http
POST /api/search
GET  /api/search
```

Common POST body:

```json
{
  "kw": "电影名或剧名",
  "res": "merge",
  "src": "all",
  "cloud_types": ["115"]
}
```

Known parameters:

- `kw` (required): search keyword.
- `channels`: TG channel list; omit to use service defaults.
- `conc`: concurrency.
- `refresh`: bypass cache when true.
- `res`: `all`, `results`, or `merge` (default often `merge`).
- `src`: `all`, `tg`, or `plugin`.
- `plugins`: restrict plugin sources.
- `cloud_types`: filter disk/link types. Supports at least `baidu`, `aliyun`, `quark`, `tianyi`, `uc`, `mobile`, `115`, `pikpak`, `xunlei`, `123`, `magnet`, `ed2k`.
- `ext`: plugin-specific extras such as English title or `is_all`.

GET equivalent example:

```http
/api/search?kw=速度与激情&res=merge&src=all&cloud_types=115
```

## Recommended MoviePilot workflow

1. Search PanSou with `cloud_types: ["115"]` and write raw JSON to `/tmp`, not chat.
2. Parse only safe summary fields for the user: title, size, quality, source, update time, and source type. Do not paste full 115 share links or extraction codes unless the user explicitly needs them.
3. If the user approves a candidate, pass the full share URL internally to `P115StrmHelper`:
   - `GET /api/v1/plugin/P115StrmHelper/add_transfer_share?share_url=...`
4. If the result is magnet/ed2k/http instead of 115, use `POST /api/v1/plugin/P115StrmHelper/add_offline_task` with a user-approved target path.
5. Verify with `P115StrmHelper` status/browse/offline-task endpoints before reporting completion.

## Safety / legal / quality caveats

- Treat third-party search results as untrusted metadata. Filter by exact title/year when possible; public indexes often mix sequels, remakes, CAM/TC, and fake entries.
- Avoid exposing share links, pickup codes, API tokens, or 115 cookies in chat/logs.
- Do not use destructive P115StrmHelper endpoints (cleanup, full sync, mount/unmount, history deletion) without explicit confirmation.
- Respect local laws and platform terms; this workflow should only automate handling of resources the user is entitled to access.
