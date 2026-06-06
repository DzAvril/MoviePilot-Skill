# MoviePilot → Hermes notification bridge

Use this when the user wants MoviePilot notifications delivered through Hermes Agent (for example into the current WeChat session) instead of or in addition to Telegram.

## Key findings

- MoviePilot includes a built-in `Webhook` plugin at `/app/app/plugins/webhook/__init__.py`.
- The plugin sends every MoviePilot event registered by `EventType` to a configured URL.
- Its payload shape is:

```json
{
  "type": "<event type>",
  "data": { "...": "event-specific data" }
}
```

- The plugin UI supports only:
  - enabled on/off
  - request method: `POST` or `GET`
  - webhook URL
- It does **not** support custom headers or HMAC signature headers.

## Recommended architecture

Because Hermes dynamic webhooks validate signatures, do not point MoviePilot's built-in Webhook plugin directly at a normal Hermes subscription unless the route is explicitly configured to accept unsigned posts.

Preferred robust setup:

```text
MoviePilot Webhook plugin
        ↓ unsigned local POST
mp-hermes-bridge tiny local service
        ↓ signed Hermes webhook or Hermes/API messaging call
Hermes gateway
        ↓
WeChat / Telegram / chosen delivery channel
```

The bridge can also filter noisy events and format compact user-facing messages.

## Suggested bridge behavior

- Listen only on a local/private interface reachable by the MoviePilot container, e.g. host bridge or Docker network.
- Accept MoviePilot JSON payloads with `type` and `data`.
- Drop or de-duplicate noisy event types if desired.
- Render concise notifications such as download complete, transfer failed, subscription resource found, site errors, and plugin failures.
- Forward to Hermes either by:
  1. signed Hermes webhook subscription with `--deliver-only`, or
  2. Hermes API/server or messaging tool endpoint if available in the running gateway.

## Hermes subscription pattern

For pure forwarding with no LLM cost, create a Hermes webhook subscription using `--deliver-only` and a prompt template that becomes the literal message body. If a bridge signs the request, it can POST to the returned subscription URL.

## Pitfalls

- MoviePilot startup logs can print tokens/passwords; redact logs before summarizing or using them as examples.
- Avoid sending raw MoviePilot event data directly to chat: payloads may include paths, URLs, site data, or secrets depending on event/plugin.
- Telegram relay is possible but less clean: MP → Telegram → Hermes → WeChat can duplicate notifications and is harder to filter reliably.
- Polling MoviePilot APIs from Hermes is simpler but not real-time and needs persistent de-duplication state.
