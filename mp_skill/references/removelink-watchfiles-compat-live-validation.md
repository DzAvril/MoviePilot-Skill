# RemoveLink #47 watchfiles compatibility live validation

Session-proven recipe for validating a RemoveLink compatibility fix against a live upgraded MoviePilot instance when the target bug is specifically about missing `watchdog` and fallback to `watchfiles`.

## When to use

- MoviePilot has been upgraded and the user wants more than a static code diff.
- Local repo tests pass, but you still need to prove the deployed plugin works in the running container.
- The bug report is about optional dependency compatibility (`watchdog` absent, `watchfiles` present).

## What mattered in this session

1. After a MoviePilot image update, `/api/v1/*` may move through a startup sequence like:
   - `502 Bad Gateway` for a while
   - later `401 Unauthorized` on unauthenticated probes

   Treat that `401` as a **good sign**: nginx can now reach the backend and the API is alive; switch to authenticated verification instead of continuing to debug startup.

2. For runtime plugin truth, check **plugin list/runtime logs**, not only market metadata:
   - `GET /api/v1/plugin/PluginManagerVue/plugins` reflected `RemoveLink.version = 2.13` after reload
   - MoviePilot logs showed `加载插件：RemoveLink 版本：2.13`
   - but `GET /api/v1/plugin/PluginManagerVue/online_info/RemoveLink` still showed `plugin_version = 2.12`

   `online_info` is market/upstream metadata and can legitimately lag or stay old when you have only hot-deployed local code.

3. For true pre-publish live validation, hot-copy the patched plugin into the running container, compile it, reload it, and then run a container-side regression script against the **deployed** file under `/app/app/plugins/<plugin>/__init__.py`.

## Recommended live-validation sequence

1. Verify API recovery
   - If direct unauthenticated probes stop returning `502` and start returning `401/403`, stop treating startup as broken.
2. Inspect current runtime state
   - `plugin/installed`
   - `plugin/form/<PluginId>`
   - `plugin/PluginManagerVue/plugins`
3. Back up deployed plugin file into `/config/temp/...`.
4. `docker cp` the patched file into `/app/app/plugins/removelink/__init__.py`.
5. Run container-side syntax check with `/opt/venv/bin/python -m py_compile`.
6. Reload with `GET /api/v1/plugin/reload/RemoveLink`.
7. Verify runtime version using:
   - plugin list (`PluginManagerVue/plugins`)
   - bounded logs containing `加载插件：RemoveLink 版本：...`
8. Run a container-side compatibility regression against the deployed file.

## Important testing detail: block watchdog imports for real

If the MoviePilot container already has `watchdog` installed, simply deleting `watchdog` from `sys.modules` is not enough. Python will re-import it from site-packages and your fallback path never executes.

Use a `MetaPathFinder` that raises `ModuleNotFoundError` for `watchdog` / `watchdog.*`, then load the deployed plugin file by path. This reliably exercises the `watchfiles` fallback even inside a container where `watchdog` is installed.

Minimal pattern:

```python
import importlib.abc
import importlib.util
import sys
from pathlib import Path

class BlockWatchdogFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "watchdog" or fullname.startswith("watchdog."):
            raise ModuleNotFoundError(f"No module named {fullname!r}")
        return None

sys.meta_path.insert(0, BlockWatchdogFinder())
for name in list(sys.modules):
    if name == "watchdog" or name.startswith("watchdog."):
        del sys.modules[name]

plugin_file = Path('/app/app/plugins/removelink/__init__.py')
spec = importlib.util.spec_from_file_location('removelink_live_plugin', plugin_file)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
```

Then install your stubs for `watchfiles`, `app.plugins._PluginBase`, `app.schemas`, etc., call `RemoveLink().init_plugin(...)`, and assert the fallback watcher path was used.

## Interpretation rules

- `plugin/form/<PluginId>` succeeding proves the plugin is loadable through MoviePilot.
- `PluginManagerVue/plugins` is the better runtime truth source for the loaded version after a hot deploy.
- `online_info/<PluginId>` is not sufficient evidence of loaded version during local hot-patch validation.
- If logs show `加载插件：RemoveLink 版本：2.13` and the plugin list reports `2.13`, the live runtime accepted the patch even if market metadata still says `2.12`.
