# MCPServer MoviePilot API Key Auth Compatibility

## When this applies

Use this note when investigating MoviePilot-Plugins `plugins.v2/mcpserver` issues where the user configured a MoviePilot API token/key in MCPServer and logs say the manual access token validation failed, then username/password fallback also fails.

Representative issue: DzAvril/MoviePilot-Plugins #46.

## Symptom

Logs may show:

```text
使用手动配置的访问令牌
手动配置的访问令牌验证失败，将尝试用户名密码认证
通过用户名密码获取 access token 失败: ... /api/v1/login/access-token ... Connection refused
无法获取 MoviePilot 的 access token
```

The user may say the MCP client connects but tool calls fail, or that MCP tools call MoviePilot at an unreachable `localhost` URL.

## Root cause

MCPServer originally treated the manually configured MoviePilot credential only as a login `access_token` and validated/forwarded it with:

```http
Authorization: Bearer <token>
```

MoviePilot's configured API token/key is accepted by the REST API as:

```http
X-API-KEY: <token>
```

So a valid MoviePilot API key can fail validation if only Bearer auth is attempted. If username/password fallback is unavailable (2FA, wrong internal host/port, port mismatch), server startup or tool execution can fail.

## Fix pattern

In `plugins.v2/mcpserver/__init__.py`:

1. Add a helper that validates manual tokens against `/api/v1/user/current` using both auth styles:
   - `Authorization: Bearer <token>` → return original token.
   - `X-API-KEY: <token>` → return an internal marker such as `apikey:<token>`.
2. Keep `_validate_access_token()` as a bool wrapper for API compatibility.
3. When prerequisites or `_get_moviepilot_access_token()` accept a manual token, store the normalized token returned by the helper, not always the raw token.

In `plugins.v2/mcpserver/utils/http_utils.py`:

1. When `access_token.startswith("apikey:")`, strip the marker and send `X-API-KEY`.
2. Otherwise keep existing Bearer behavior.

Also bump both v2 plugin version locations:

- `plugins.v2/mcpserver/__init__.py`: `plugin_version`
- `package.v2.json`: `MCPServer.version` and history

## Verification recipe

- Run `python3 -m py_compile $(find plugins.v2/mcpserver -name '*.py' -not -path '*/venv/*')`.
- Add a small regression probe for `utils/http_utils.make_request()` with a fake HTTP client:
  - `access_token='apikey:example'` must produce `{'X-API-KEY': 'example'}`.
  - `access_token='example'` must produce `{'Authorization': 'Bearer example'}`.
- If a live MoviePilot container is available, deploy only the touched MCPServer files to `/app/app/plugins/mcpserver/` after backing them up under `/config/temp/`.
- Use a token-safe pipe/config to run a container-side probe that calls `make_request('GET', '/api/v1/user/current', access_token='apikey:<real_api_key>')`; never print the real key.
- Restart/start MCPServer through MoviePilot API and check logs with token/password/cookie redaction.

## Issue comment closure

When closing the issue, include commit link, validation summary, remove stale labels, add `resolved`, close as completed, and end with the attribution line requested by the user, e.g.:

```text
Submitted by Codex (gpt-5.5).
```
