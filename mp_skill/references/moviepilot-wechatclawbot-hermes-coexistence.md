# MoviePilot WeChat ClawBot and Hermes coexistence

Use this when the user asks whether MoviePilot's `wechatclawbot` notification/channel can reuse a WeChat/ClawBot account that is already bound to Hermes Agent.

## Finding

MoviePilot's WeChat ClawBot integration is not just an outbound notification sender. In the current core implementation (`app/modules/wechatclawbot/wechatclawbot.py`), the client:

- stores its own login state (`bot_token`, `account_id`, `sync_buf`) in `FileCache` keyed by the MoviePilot notification config name;
- starts a background polling thread after login;
- calls `ILinkClient.poll_updates(...)` to pull incoming WeChat messages;
- forwards each incoming message into MoviePilot's local message endpoint (`/api/v1/message?...source=<config_name>`);
- maintains known targets and per-user context tokens for later sending.

Because it owns a polling cursor/session, treat it as a **primary WeChat backend**, not as a passive notification-only transport.

## Recommendation

Do **not** bind the same WeChat account / same ClawBot login session directly to both Hermes Gateway and MoviePilot WeChat ClawBot.

Risky topology:

```text
WeChat / ClawBot -> Hermes
                -> MoviePilot WeChat ClawBot
```

Possible symptoms:

- Hermes silently stops receiving WeChat messages;
- MoviePilot and Hermes compete for the same message stream/cursor;
- duplicate replies;
- dropped or delayed messages;
- one side appears online while the other owns the effective polling state.

Safe topologies:

```text
WeChat / ClawBot -> Hermes
MoviePilot -> Webhook/bridge -> Hermes -> WeChat
```

or:

```text
WeChat account A / ClawBot A -> Hermes
WeChat account B / ClawBot B -> MoviePilot
```

## If the user only wants MoviePilot notifications in the Hermes WeChat chat

Prefer MoviePilot's Webhook plugin or a small local bridge into Hermes, then let Hermes deliver to WeChat. See `references/moviepilot-to-hermes-notifications.md` for bridge notes.

## Verification pointers

- In a source checkout, inspect `app/modules/wechatclawbot/wechatclawbot.py` around `WechatClawBot.__init__`, `_start_polling`, `_poll_loop`, and `get_status`.
- Check whether MoviePilot is configured with `MessageChannel.WechatClawBot`/`wechatclawbot` before enabling it on a Hermes-owned WeChat account.
