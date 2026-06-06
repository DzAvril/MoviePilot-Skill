# MoviePilot Image Pull, Restart, and In-Container Self-Update Notes

Use when the user asks to pull/restart MoviePilot and the Docker image tag appears unchanged.

## Observed pattern

- `docker pull jxxghp/moviepilot-v2:latest` can report `Image is up to date` and the image labels may still show the previous MoviePilot version, e.g. `org.opencontainers.image.version=2.11.0`.
- On container restart, MoviePilot's entrypoint may still perform an in-container program/frontend update from GitHub, for example:
  - dependency install/upgrade via `pip install -r /app/requirements.txt`
  - frontend download such as `MoviePilot-Frontend/releases/download/vX.Y.Z/dist.zip`
  - backend download such as `tags/vX.Y.Z.zip`
- In this case Docker image ID and OCI labels remain unchanged, while the live app files can move to the newer app/frontend version.

## Verification workflow

1. Capture pre-pull state:
   ```bash
   docker inspect MoviePilot --format '{{.Image}} {{index .Config.Labels "org.opencontainers.image.version"}} {{index .Config.Labels "org.opencontainers.image.created"}} {{index .Config.Labels "org.opencontainers.image.revision"}}'
   docker image inspect jxxghp/moviepilot-v2:latest --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.version"}} {{index .Config.Labels "org.opencontainers.image.created"}} {{index .Config.Labels "org.opencontainers.image.revision"}}'
   ```
2. Pull the image and compare image ID/labels.
3. Restart/recreate as requested.
4. During startup, expect temporary `Connection refused`/`502 Bad Gateway` on `/api/v1/*` while dependencies/resources/plugin reloads finish. Frontend/backend downloads through `PROXY_HOST` can take several minutes; avoid declaring failure while `curl ... MoviePilot-Frontend/.../dist.zip | busybox unzip` or resource-download commands are still active. If needed, inspect progress inside the container:
   ```bash
   docker exec -i MoviePilot sh -lc 'ps -eo pid,ppid,stat,etime,cmd | grep -E "curl|unzip|nginx|MoviePilot" | grep -v grep; du -sh /tmp/tmp.* 2>/dev/null || true'
   ```
5. Poll until either:
   - `/` returns `200`, and
   - an authenticated helper call such as `scripts/mp_request.py GET /api/v1/user/current --compact` succeeds. If probing without auth, `/api/v1/*` returning `401`/`403` means the API is reachable, not broken.
6. Verify the live app version from `/app/version.py` as a separate plane from Docker labels:
   ```bash
   docker exec -i MoviePilot sh -lc "grep -E '^(APP_VERSION|FRONTEND_VERSION)' /app/version.py 2>/dev/null || true"
   ```
   Recent images may run the backend as a process named `MoviePilot` rather than a visible `python app/main.py`, so process checks should include `MoviePilot`, not just Python command lines.
7. Inspect startup logs for self-update evidence, but redact secrets conservatively. Do not use an over-broad `KEY=` regex that matches package names like `tiktoken`; prefer matching whole env-var names or known secret prefixes. Treat plugin warnings such as MCPServer token retries or missing optional plugin modules separately from core service readiness if the Web/API probes pass.
8. Summarize Docker plane and application plane separately:
   - Docker plane: image ID and labels changed or unchanged.
   - App plane: logs show frontend/backend self-update version and service readiness.

## Known benign/partial warnings

- A startup line like `rm: cannot remove '/app/app/plugins/<bind-mounted-plugin>': Device or resource busy` can occur when a plugin path is a bind mount. If `Application startup complete` follows and probes pass, report it as a warning rather than a failed update.

## Reporting example

```text
镜像仓库返回已是最新，Docker image ID/label 未变；重启后 MoviePilot entrypoint 自更新到了前端 vX.Y.Z / 后端 tags/vX.Y.Z.zip。Web UI 200，API 未带认证返回 401，说明服务已恢复。另有一个 bind-mounted plugin 的 Device busy 清理警告，目前不影响启动。
```
