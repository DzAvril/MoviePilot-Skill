#!/usr/bin/env python3
import argparse
import json
import os
import sys
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
            if args.show_headers:
                for k, v in resp.headers.items():
                    print(f'{k}: {v}')
                print('')
            if args.output:
                with open(args.output, 'wb') as f:
                    f.write(data)
            else:
                sys.stdout.buffer.write(data)
        return 0
    except urllib.error.HTTPError as e:
        data = e.read()
        print(f'HTTP {e.code}', file=sys.stderr)
        if args.output:
            with open(args.output, 'wb') as f:
                f.write(data)
        else:
            sys.stderr.buffer.write(data)
        return 1

if __name__ == '__main__':
    sys.exit(main())
