# Site Cookie Health Notifications and Plugin Ops

Session-tested notes from the user's MoviePilot instance.

## Cookie/connection failure notification

- The installed `AutoDiagnosis` plugin is the built-in path closest to "notify me when a site's cookie/login state or connectivity fails".
- Read config with:

```bash
python3 scripts/mp_request.py GET /api/v1/plugin/AutoDiagnosis --output /tmp/mp_autodiagnosis_config.json
```

- Relevant fields observed:
  - `enabled: true`
  - `notify: on_error` — notify only on abnormal results.
  - `health_check_sites: ['all']` — checks all sites.
  - `cron: 0 6 * * *` — daily at 06:00 on this instance.
- It is scheduled diagnosis, not realtime cookie-drop detection. If the user wants faster feedback, change the cron or implement a low-noise external monitor that only notifies on newly failing/recovered sites.
- `AutoSignIn` can also surface stale cookies indirectly via signin failures, but it is not a general site connectivity monitor.

## Disabling BrushFlow safely

Use the plugin config endpoint rather than editing the DB directly:

```bash
python3 scripts/mp_request.py GET /api/v1/plugin/BrushFlow --output /tmp/mp_brushflow_config.json
python3 - <<'PY'
import json
p='/tmp/mp_brushflow_config.json'
data=json.load(open(p))
data['enabled']=False
data['onlyonce']=False
open('/tmp/mp_brushflow_disable.json','w').write(json.dumps(data,ensure_ascii=False))
PY
python3 scripts/mp_request.py PUT /api/v1/plugin/BrushFlow --json @/tmp/mp_brushflow_disable.json --output /tmp/mp_brushflow_put.json
python3 scripts/mp_request.py GET /api/v1/plugin/BrushFlow --output /tmp/mp_brushflow_after.json
```

Verify:

- Response should contain `{"success": true}`.
- Read-back should show `enabled: false`.
- Logs should include:
  - `Disabled event handler class - app.plugins.brushflow.BrushFlow`
  - `移除插件服务(站点刷流)：站点刷流服务`
  - `移除插件服务(站点刷流)：站点刷流检查服务`

Pitfall: the DB row `systemconfig.key='plugin.BrushFlow'` can show `enabled: false` while `GET /api/v1/plugin/BrushFlow` briefly reports runtime config as enabled during reload. Trust the API mutation plus final read-back and scheduler-removal log.