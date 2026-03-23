# MoviePilot-Skill

`mp_skill` is a Codex skill for controlling a self-hosted MoviePilot instance via REST API using `X-API-KEY`.

## Skill Location

The skill source lives in:
`/Users/xuzhi/Documents/workspace/MoviePilot-Skill/mp_skill`

Symlink for Codex discovery:
`/Users/xuzhi/.codex/skills/mp_skill`

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
