#!/usr/bin/env python3
"""Refresh MoviePilot skill API references from a live OpenAPI document.

The generated references intentionally include only operations that advertise
`api_key_header` security, because the skill authenticates with X-API-KEY.
"""
import argparse
import collections
import json
import os
from pathlib import Path
import urllib.request

HTTP_METHODS = {"get", "post", "put", "delete", "patch"}
API_KEY_SCHEME = "api_key_header"


def load_config_host() -> str:
    cfg_path = Path.home() / ".config" / "mp_skill" / "config"
    if not cfg_path.exists():
        return ""
    for line in cfg_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "MP_HOST":
            return value.strip()
    return ""


def fetch_openapi(base_url: str) -> dict:
    url = base_url.rstrip("/") + "/api/v1/openapi.json"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def operation_uses_x_api_key(operation: dict) -> bool:
    for requirement in operation.get("security") or []:
        if API_KEY_SCHEME in requirement:
            return True
    return False


def filter_x_api_key_openapi(openapi: dict) -> dict:
    filtered = dict(openapi)
    paths = {}
    for path, path_item in openapi.get("paths", {}).items():
        kept = {}
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            if operation_uses_x_api_key(operation):
                kept[method] = operation
        if kept:
            paths[path] = kept
    filtered["paths"] = dict(sorted(paths.items()))
    return filtered


def category_for(path: str, operation: dict) -> str:
    tags = operation.get("tags") or []
    if tags:
        return str(tags[0])
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        return parts[2]
    return parts[0] if parts else "other"


def op_line(method: str, path: str, operation: dict) -> str:
    summary = operation.get("summary") or operation.get("operationId") or ""
    summary = " ".join(str(summary).split())
    return f"- `{method.upper()} {path}`" + (f" — {summary}" if summary else "")


def write_references(skill_dir: Path, filtered: dict) -> None:
    refs = skill_dir / "references"
    api_dir = refs / "api"
    api_dir.mkdir(parents=True, exist_ok=True)

    grouped = collections.defaultdict(list)
    for path, path_item in filtered.get("paths", {}).items():
        for method, operation in path_item.items():
            cat = category_for(path, operation)
            grouped[cat].append((path, method, operation))

    for old in api_dir.glob("*.md"):
        old.unlink()

    index_lines = ["# MoviePilot API Index", "", "Only X-API-KEY supported endpoints are included.", ""]
    for cat in sorted(grouped):
        filename = f"{cat}.md"
        index_lines.append(f"- `{cat}` -> `references/api/{filename}`")
        lines = [f"## {cat}", ""]
        for path, method, operation in sorted(grouped[cat], key=lambda x: (x[0], x[1])):
            lines.append(op_line(method, path, operation))
        lines.append("")
        (api_dir / filename).write_text("\n".join(lines), encoding="utf-8")

    (refs / "api_index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    (refs / "openapi.json").write_text(
        json.dumps(filtered, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh MoviePilot X-API-KEY OpenAPI references")
    parser.add_argument("--host", default=os.environ.get("MOVIEPILOT_URL") or os.environ.get("MP_HOST") or load_config_host(), help="MoviePilot base URL")
    parser.add_argument("--skill-dir", default=str(Path(__file__).resolve().parents[1]), help="Path to mp_skill directory")
    parser.add_argument("--input", help="Use an existing OpenAPI JSON file instead of fetching from host")
    args = parser.parse_args()

    if args.input:
        openapi = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        if not args.host:
            raise SystemExit("MP_HOST/MOVIEPILOT_URL is not set and --host was not provided")
        openapi = fetch_openapi(args.host)

    filtered = filter_x_api_key_openapi(openapi)
    write_references(Path(args.skill_dir), filtered)
    print(f"refreshed {len(filtered.get('paths', {}))} X-API-KEY paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
