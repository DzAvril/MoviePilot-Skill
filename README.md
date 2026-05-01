# MoviePilot-Skill

`mp_skill` is an agent skill for controlling a self-hosted MoviePilot instance via REST API using `X-API-KEY`.

## Skill Location

The skill source lives in:
`<workspace>/mp_skill`

To enable discovery, place or link `mp_skill` inside your agent’s skill search path.
Example:
`$AGENT_HOME/skills/mp_skill` (or the agent-specific skills directory)

## Configuration

Create a local config file (best practice):
`~/.config/mp_skill/config`

Example:
```
MP_HOST=http://192.168.1.93:3001
MP_API_KEY=your_x_api_key
```

Environment overrides:
- `MOVIEPILOT_URL` or `MP_HOST`
- `MP_API_KEY`

## Notes

Only endpoints that support `X-API-KEY` are included in the skill references.

## Updating API References

MoviePilot and installed plugins can change the OpenAPI schema. Refresh the bundled references from a live instance with:

```bash
cd mp_skill
python3 scripts/refresh_openapi_refs.py --host http://your-moviepilot-host:3000
```

The refresh script filters the live OpenAPI document to operations that support the `api_key_header` security scheme, then regenerates:

- `references/openapi.json`
- `references/api_index.md`
- `references/api/*.md`
