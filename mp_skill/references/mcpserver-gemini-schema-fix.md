# MCPServer Gemini CLI Tool Schema Compatibility

## When this applies

Use this note when investigating MoviePilot-Plugins `plugins.v2/mcpserver` issues where Gemini CLI fails while listing/registering MCP tools with an error like:

```text
Failed to list or register tools for MCP server ... Error: type and anyOf cannot be both populated
No tools registered from MCP server
```

Representative issue: DzAvril/MoviePilot-Plugins #23.

## Root cause

Gemini CLI converts MCP tool `inputSchema` into Gemini function declarations. At least some Gemini CLI versions reject a JSON schema node when it contains both:

```json
{
  "type": "object",
  "anyOf": [...]
}
```

In MCPServer, `query-pt-stats` used a top-level object schema with `anyOf` to express “provide `site_domain` or `site_name`”. That is valid JSON Schema, but not accepted by Gemini CLI's function declaration conversion, so registering all MCP tools can fail even though other clients accept the schema.

## Fix pattern

In `plugins.v2/mcpserver/tools/database/pt_stats.py`:

1. Remove top-level `anyOf` from `PTStatsTool.tool_info.inputSchema`.
2. Keep a normal object schema with `site_domain` and `site_name` string properties.
3. Move the mutual-choice requirement into property/root descriptions, e.g. “必须提供 site_domain 或 site_name；如果同时提供，优先使用 site_domain”.
4. Do not remove runtime validation: `_get_single_site_stats()` should still return an error text if both arguments are missing.

Also bump both v2 plugin version locations:

- `plugins.v2/mcpserver/__init__.py`: `plugin_version`
- `package.v2.json`: `MCPServer.version` and history

## Verification recipe

Minimum source/container checks:

- Run `python3 -m py_compile plugins.v2/mcpserver/tools/database/pt_stats.py plugins.v2/mcpserver/__init__.py`.
- Run a regression script that imports `PTStatsTool().tool_info.inputSchema` and asserts:
  - `schema["type"] == "object"`
  - `"anyOf" not in schema`
  - `site_domain` and `site_name` remain in `properties`
  - no schema node recursively contains both `type` and `anyOf`
- Validate `package.v2.json` with `python3 -m json.tool`.
- If a live MoviePilot container is available, back up and deploy:
  - `/app/app/plugins/mcpserver/__init__.py`
  - `/app/app/plugins/mcpserver/tools/database/pt_stats.py`
- Container verification can use `/opt/venv/bin/python` with `PYTHONPATH` including MCPServer venv site-packages and `/app`, then instantiate `ToolManager().list_tools()` and recursively assert every tool schema has no `type` + `anyOf` conflict. Avoid printing credentials or raw config.
- Reload MCPServer through MoviePilot API and read back `PluginManagerVue/plugins`; expect `MCPServer <new_version>`, `status=running`, `has_update=false`.

Important: those checks prove the root-cause schema conflict is removed, but they are not a full Gemini CLI end-to-end reproduction. For this specific issue, do not claim the live Gemini CLI path is verified unless one of these succeeds before closure:

1. Run the actual Gemini CLI against the live MCPServer and confirm tool registration/listing no longer prints `type and anyOf cannot be both populated` or `No tools registered`.
2. If Gemini model auth is unavailable, run Gemini CLI's local MCP/tool-declaration conversion code (from the installed `@google/gemini-cli` package version matching the issue) against the MCPServer tool list and confirm conversion succeeds.

If neither is possible, explicitly label the result as schema/root-cause verification only and avoid closing the issue as fully verified without user approval.

## Issue comment closure

When closing the issue, include commit link, validation summary, remove stale labels, add `resolved`, close as completed, and end with:

```text
Submitted by Codex (gpt-5.5).
```
