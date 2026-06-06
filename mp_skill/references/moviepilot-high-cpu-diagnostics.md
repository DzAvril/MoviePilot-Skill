# MoviePilot High-CPU Diagnostics

Use this when a self-hosted MoviePilot container has sustained high CPU or high thread count. The useful pattern is: separate Docker/container load from in-process MoviePilot threads, then correlate those threads with MoviePilot schedulers, directory watchers, and plugin logs.

## Fast triage

```bash
# Confirm the container and overall load
docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}} {{.PIDs}}' | grep -E '^MoviePilot '
docker ps --filter name=MoviePilot --format 'table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'

# Inspect high-CPU threads inside the MoviePilot process
docker exec MoviePilot sh -lc 'pid=$(pidof MoviePilot); echo PID=$pid; ps -T -p $pid -o pid,tid,pcpu,pmem,comm | sort -k3 -nr | head -n 30'

# Check lifecycle/health
docker inspect MoviePilot --format 'RestartCount={{.RestartCount}} StartedAt={{.State.StartedAt}} Health={{if .State.Health}}{{json .State.Health}}{{else}}none{{end}}'
```

Interpretation notes:
- Threads named `notify-rs poll` point to `watchfiles`/inotify-style watchers, not a separate Linux process.
- A main `MoviePilot` thread plus multiple `notify-rs poll` threads consuming CPU often means directory/plugin/P115 STRM watchers plus normal schedulers are busy.
- A large `PIDs` count and many Python threads are not enough by themselves; use `ps -T` and logs to find what is active.

## Watcher/inotify checks

```bash
# Count inotify descriptors and watched entries for the MoviePilot process
docker exec MoviePilot sh -lc '
  pid=$(pidof MoviePilot)
  for fd in /proc/$pid/fd/*; do
    t=$(readlink "$fd" 2>/dev/null)
    [ "$t" = "anon_inode:inotify" ] && printf "%s " ${fd##*/} && grep -c "^inotify" /proc/$pid/fdinfo/${fd##*/}
  done | sort -k2 -nr
'

# Identify code paths that use watchfiles/watchdog
docker exec MoviePilot sh -lc 'grep -Rni "watchfiles\|watch(" /app/app /config/plugins 2>/dev/null | head -n 80'
```

Common sources on this instance/class of setups:
- MoviePilot core plugin directory monitor (`app/core/plugin.py`) uses `watchfiles.watch`.
- P115StrmHelper service monitors (`app/plugins/p115strmhelper/service/__init__.py`) use `watchfiles.watch`.
- MoviePilot local directory monitor can use watchdog `PollingObserver` in compatibility mode, which is CPU-expensive on large directories.

## Logs to correlate

```bash
# Recent high-signal container logs; redact anything that looks secret before sharing
docker logs --since 30m --timestamps MoviePilot 2>&1 \
  | sed -E 's/(TOKEN|PASSWORD|PASS|COOKIE|KEY|SECRET|API[_-]?KEY)=([^ ]+)/\1=***REDACTED***/Ig' \
  | tail -n 200

# Directory monitor and plugin monitor startup/activity
docker exec MoviePilot sh -lc 'grep -RniE "目录监控|兼容模式|Polling|watchfiles|监控生活|目录上传|transfer_monitor|maximum number of running instances|新增订阅搜索" /config/logs/moviepilot.log /config/logs/plugins/*.log 2>/dev/null | tail -n 200'
```

High-value log signatures:
- `Execution of job "新增订阅搜索" skipped: maximum number of running instances reached` means a prior subscription-search job is still running; later scheduled invocations are being skipped. This can keep CPU elevated even if no obvious download is active.
- `使用兼容模式(轮询)监控 <path>` on large media directories indicates polling directory monitors; reduce monitored paths or switch to fast mode if the filesystem supports it.
- P115StrmHelper logs such as `【监控生活事件】`, `【目录上传】`, and repeated Emby refresh failures can indicate duplicate/expensive monitor paths and repeated media-server refresh attempts.
- Plugin LLM recognizers that log repeated auth/key failures (for example ChatGPT `所有API密钥均已失效`) can drag out subscription recognition/search workflows.

## Inspect relevant config safely

Avoid printing raw tokens/cookies from `systemconfig`. Use targeted keys and redact secrets.

```bash
docker exec MoviePilot python - <<'PY'
import sqlite3, json
c=sqlite3.connect('/config/user.db')
for key in ['plugin.P115StrmHelper', 'plugin.DirMonitor', 'plugin.LinkMonitor', 'plugin.ChatGPT']:
    r=c.execute('select value from systemconfig where key=?', (key,)).fetchone()
    if not r:
        continue
    try:
        d=json.loads(r[0])
    except Exception:
        continue
    print('\n###', key)
    for k in sorted(d):
        if any(s in k.lower() for s in ['enabled','monitor','path','cron','interval','sync','process','batch','mediaserver','recognize']):
            v=d[k]
            if any(s in k.lower() for s in ['token','cookie','key','password','pass','secret']):
                v='***REDACTED***'
            print(f'{k}={repr(v)[:300]}')
PY
```

For P115StrmHelper specifically, look for whether these are all enabled at once:
- `monitor_life_enabled`
- `transfer_monitor_enabled`
- `directory_upload_enabled`
- broad `monitor_life_paths`, `transfer_monitor_paths`, or `directory_upload_path`

## Safe remediation order

1. If the user only asked for diagnosis, report evidence and do not change settings.
2. If they want immediate relief, restart MoviePilot to release stuck scheduler jobs and stale watcher threads, then verify `docker stats`, `ps -T`, and recent logs.
3. Reduce overlapping monitors before disabling major workflows:
   - Keep only the P115StrmHelper monitor modes that are actually needed.
   - Avoid monitoring both generated STRM trees and media-library trees if they trigger each other.
   - Reduce or remove very broad paths such as large `/sata*` trees.
4. Increase the schedule interval for expensive jobs such as `新增订阅搜索`; 5 minutes can be too aggressive if a full search takes longer than one interval.
5. Fix plugin auth/config failures that prolong recognizers/searches, e.g. invalid ChatGPT/OpenAI keys used by media recognition.
6. For MoviePilot directory monitors using compatibility polling on large folders, switch to fast mode only if the underlying filesystem supports it; otherwise reduce paths or accept lower responsiveness.

## Reporting pattern

Keep the user-facing report compact:
- Current CPU/PIDs and top thread names.
- Top evidence from logs: stuck scheduled job, polling monitors, P115StrmHelper monitor modes, plugin auth failures.
- Clear root-cause likelihood: e.g. "watchfiles/目录监控 + 卡住的新增订阅搜索" vs downloads/QB.
- Ordered suggestions, separating read-only diagnosis from actions that require permission (restart/config changes).
