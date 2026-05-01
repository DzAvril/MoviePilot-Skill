#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

def load_json_value(val: str):
    if val.startswith('@'):
        path = val[1:]
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return json.loads(val)

def load_bytes_value(val: str):
    if val.startswith('@'):
        path = val[1:]
        with open(path, 'rb') as f:
            return f.read()
    return val.encode('utf-8')

def safe_write(path: str, data: bytes):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    try:
        os.chmod(path, 0o600)
    except PermissionError:
        pass

def read_config():
    host = ''
    key = ''
    cfg_path = os.path.join(os.path.expanduser('~'), '.config', 'mp_skill', 'config')
    if not os.path.exists(cfg_path):
        return host, key
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            for line in f.read().splitlines():
                if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip()
                if k == 'MP_HOST':
                    host = v
                elif k == 'MP_API_KEY':
                    key = v
    except OSError:
        pass
    return host, key

def pick_keys(items):
    if not items:
        return []
    preferred = ['id', 'name', 'title', 'status', 'type', 'tmdb_id', 'year', 'size', 'hash', 'site']
    keys = []
    sample = items[:20]
    key_counts = {}
    for it in sample:
        if isinstance(it, dict):
            for k in it.keys():
                key_counts[k] = key_counts.get(k, 0) + 1
    for k in preferred:
        if k in key_counts:
            keys.append(k)
    for k, _ in sorted(key_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if k not in keys:
            keys.append(k)
        if len(keys) >= 8:
            break
    return keys[:8]

def summarize_list(items, preferred_keys, max_items):
    if not isinstance(items, list):
        return None
    keys = [k for k in preferred_keys if any(isinstance(it, dict) and k in it for it in items)]
    if not keys:
        keys = pick_keys(items)
    preview = []
    for it in items[:max_items]:
        if isinstance(it, dict) and keys:
            preview.append({k: it.get(k) for k in keys})
        else:
            preview.append(it)
    return {
        'type': 'list',
        'item_count': len(items),
        'preview_keys': keys,
        'preview_items': preview,
    }

def compact_json_by_path(data, path, max_items):
    # Path-specific preferences
    prefs = None
    if '/subscribe' in path:
        prefs = ['id', 'name', 'title', 'type', 'status', 'tmdb_id', 'year', 'season',
                 'total_episode', 'finished_episode', 'next_episode', 'quality', 'resolution']
    elif '/search' in path:
        prefs = ['title', 'year', 'type', 'tmdb_id', 'douban_id', 'bangumi_id', 'season',
                 'episode', 'size', 'site', 'seeders', 'score', 'vote']
    elif '/recommend' in path:
        prefs = ['title', 'year', 'type', 'tmdb_id', 'douban_id', 'bangumi_id', 'score', 'vote']

    if prefs:
        # direct list
        if isinstance(data, list):
            return summarize_list(data, prefs, max_items)
        # common list containers
        if isinstance(data, dict):
            for key in ['items', 'results', 'data', 'list']:
                if isinstance(data.get(key), list):
                    inner = summarize_list(data.get(key), prefs, max_items)
                    if inner:
                        return {
                            'type': 'object',
                            'keys': list(data.keys())[:20],
                            'list_key': key,
                            'list_summary': inner,
                        }
    return None

def compact_json(data, max_items):
    if isinstance(data, list):
        keys = pick_keys(data)
        preview = []
        for it in data[:max_items]:
            if isinstance(it, dict) and keys:
                preview.append({k: it.get(k) for k in keys})
            else:
                preview.append(it)
        return {
            'type': 'list',
            'item_count': len(data),
            'preview_keys': keys,
            'preview_items': preview,
        }
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, list) and len(v) > max_items:
                inner = compact_json(v, max_items)
                return {
                    'type': 'object',
                    'keys': list(data.keys())[:20],
                    'large_list_key': k,
                    'large_list_summary': inner,
                }
        return {
            'type': 'object',
            'keys': list(data.keys())[:50],
        }
    return {'type': 'scalar', 'value': data}

def main():
    p = argparse.ArgumentParser(description='MoviePilot API request helper')
    p.add_argument('method', help='HTTP method, e.g. GET, POST')
    p.add_argument('path', help='API path, e.g. /api/v1/user/current')
    p.add_argument('--query', help='Raw query string, e.g. "a=1&b=2"')
    p.add_argument('--json', dest='json_body', help='JSON string or @file.json')
    p.add_argument('--data', dest='raw_body', help='Raw body string or @file')
    p.add_argument('--form', dest='form_body', help='Form-encoded body, e.g. "a=1&b=2"')
    p.add_argument('--no-auth', action='store_true', help='Do not attach auth headers')
    p.add_argument('--output', help='Write response body to file')
    p.add_argument('--show-headers', action='store_true', help='Print response headers')
    p.add_argument('--compact', action='store_true', help='Compact large JSON responses')
    p.add_argument('--max-bytes', type=int, default=50000, help='Threshold for compacting (bytes)')
    p.add_argument('--max-items', type=int, default=20, help='Preview items for large lists')
    p.add_argument('--raw-out', help='Write raw response to file when compacting')
    args = p.parse_args()

    cfg_host, cfg_key = read_config()
    base = os.environ.get('MOVIEPILOT_URL') or os.environ.get('MP_HOST') or cfg_host
    api_key = os.environ.get('MP_API_KEY') or cfg_key
    if not base:
        print('MOVIEPILOT_URL or MP_HOST is not set', file=sys.stderr)
        sys.exit(2)

    url = args.path
    if not url.startswith('http://') and not url.startswith('https://'):
        url = base.rstrip('/') + '/' + args.path.lstrip('/')

    query_items = []
    if args.query:
        query_items.extend(urllib.parse.parse_qsl(args.query, keep_blank_values=True))

    headers = {}
    if not args.no_auth:
        if not api_key:
            print('MP_API_KEY is not set (use --no-auth for public endpoints)', file=sys.stderr)
            sys.exit(2)
        headers['X-API-KEY'] = api_key

    if query_items:
        parsed = urllib.parse.urlsplit(url)
        merged = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True) + query_items
        url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(merged), parsed.fragment))

    body = None
    if args.json_body and (args.raw_body or args.form_body):
        print('Use only one of --json, --data, or --form', file=sys.stderr)
        sys.exit(2)
    if args.raw_body and args.form_body:
        print('Use only one of --data or --form', file=sys.stderr)
        sys.exit(2)

    if args.json_body:
        payload = load_json_value(args.json_body)
        body = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    elif args.form_body:
        body = args.form_body.encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    elif args.raw_body:
        body = load_bytes_value(args.raw_body)

    req = urllib.request.Request(url, data=body, method=args.method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            content_type = resp.headers.get('Content-Type', '')
            if args.show_headers:
                for k, v in resp.headers.items():
                    print(f'{k}: {v}')
                print('')
            should_compact = args.compact
            if not should_compact and content_type.startswith('application/json'):
                if len(data) >= args.max_bytes:
                    should_compact = True
            if should_compact and content_type.startswith('application/json'):
                raw_path = args.output or args.raw_out
                if not raw_path:
                    raw_path = f'/tmp/mp_skill_raw_{int(time.time())}.json'
                safe_write(raw_path, data)
                try:
                    parsed = json.loads(data.decode('utf-8'))
                except json.JSONDecodeError:
                    parsed = None
                summary = {
                    'raw_file': raw_path,
                    'size_bytes': len(data),
                }
                if parsed is not None:
                    path_only = urllib.parse.urlsplit(url).path
                    path_summary = compact_json_by_path(parsed, path_only, args.max_items)
                    summary['summary'] = path_summary or compact_json(parsed, args.max_items)
                else:
                    summary['summary'] = {'type': 'unknown', 'note': 'Failed to parse JSON'}
                sys.stdout.write(json.dumps(summary, ensure_ascii=False) + '\n')
            else:
                if args.output:
                    safe_write(args.output, data)
                else:
                    sys.stdout.buffer.write(data)
        return 0
    except urllib.error.HTTPError as e:
        data = e.read()
        print(f'HTTP {e.code}', file=sys.stderr)
        if args.output:
            safe_write(args.output, data)
        else:
            sys.stderr.buffer.write(data)
        return 1

if __name__ == '__main__':
    sys.exit(main())
