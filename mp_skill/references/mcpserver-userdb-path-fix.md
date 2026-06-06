# MCPServer portable `user.db` path fix

Use this note when MCPServer tools that read MoviePilot's SQLite database fail with `数据库文件不存在` or hard-code `/config/user.db`, especially on Windows/exe or non-Docker deployments.

## Root cause

`plugins.v2/mcpserver/tools/database/pt_stats.py` originally resolved the PT statistics DB mostly as `/config/user.db`. That works in Docker, but Windows/exe and other non-Docker deployments store `user.db` under MoviePilot's actual config directory. The MCP server runs as a child process, so it may not automatically know `settings.CONFIG_PATH` unless the parent injects it.

## Fix pattern

1. In `plugins.v2/mcpserver/__init__.py`, build a child-process environment with the MoviePilot config path and DB path:
   - `MCPSERVER_CONFIG_PATH=<settings.CONFIG_PATH>`
   - `MCPSERVER_USER_DB_PATH=<settings.CONFIG_PATH>/user.db`
   - optional aliases: `MOVIEPILOT_CONFIG_PATH`, `MOVIEPILOT_USER_DB_PATH`
2. Start the MCP child with `subprocess.Popen(..., env=self.plugin._build_process_env())`.
3. In `PTStatsTool`, resolve candidates in priority order:
   - explicit DB env vars: `MCPSERVER_USER_DB_PATH`, `MOVIEPILOT_USER_DB_PATH`, `MP_USER_DB_PATH`, `USER_DB_PATH`
   - config-dir env vars: `MCPSERVER_CONFIG_PATH`, `MOVIEPILOT_CONFIG_PATH`, `MOVIEPILOT_CONFIG_DIR`, `MP_CONFIG_PATH`, `MP_CONFIG_DIR`, `CONFIG_PATH`
   - `app.core.config.settings.CONFIG_PATH` if importable
   - Docker/default/local fallbacks such as `/config/user.db`, cwd `user.db`, plugin `user.db`, `~/.moviepilot/user.db`, `~/MoviePilot/user.db`
4. Store attempted candidates on the tool instance and include them in `FileNotFoundError` so users can diagnose the actual path.
5. Bump MCPServer version in both `plugins.v2/mcpserver/__init__.py` and `package.v2.json` history.

## Regression recipe

Create a temp SQLite `user.db`, set `MCPSERVER_USER_DB_PATH` to it, instantiate `PTStatsTool`, and assert `_get_db_connection()` opens it. Then set the env var to a missing path and assert the `FileNotFoundError` includes `已尝试以下候选路径` and the missing candidate.

A known-good script shape was committed as `tests/mcpserver_pt_stats_db_path_regression.py` in DzAvril/MoviePilot-Plugins commit `c4f03b8`.

## Verification commands

```bash
python3 tests/mcpserver_pt_stats_db_path_regression.py
python3 -m py_compile plugins.v2/mcpserver/__init__.py plugins.v2/mcpserver/tools/database/pt_stats.py tests/mcpserver_pt_stats_db_path_regression.py
python3 -m json.tool package.v2.json >/tmp/package.v2.json.check
git diff --check
python3 -m py_compile $(find plugins plugins.v2 -name '*.py')
```

After publishing, reinstall via MoviePilot PluginManagerVue and verify `MCPServer` reports the bumped version, `running=true`, and `has_update=false`.
