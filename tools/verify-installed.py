#!/usr/bin/env python3
"""Read-only local acceptance checks. These do NOT verify a PS5 streaming session."""
import argparse
import http.client
import json
from pathlib import Path
import re
import socket
import sys
from urllib.parse import urljoin, urlsplit


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path):
        super().__init__('localhost', timeout=12)
        self.socket_path = str(socket_path)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def request(sock, path, headers):
    connection = UnixHTTPConnection(sock)
    try:
        connection.request('GET', path, headers=headers)
        response = connection.getresponse()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
    finally:
        connection.close()


def verify(app, uid):
    target = Path('/var/apps') / app / 'target'
    sock = target / 'app.sock'
    prefix = '/app/' + app + '/'
    headers = {'Host': 'localhost', 'Origin': 'https://localhost', 'X-Forwarded-Proto': 'https',
               'X-Trim-Userid': str(uid), 'X-Trim-Isadmin': 'true'}
    result = {'application': app, 'checks': [], 'pairing_verified': False,
              'streaming_verified': False, 'gamepad_verified': False}

    def check(name, passed, **details):
        result['checks'].append({'name': name, 'passed': bool(passed), **details})

    check('installed_target', target.is_dir())
    check('gateway_socket', sock.exists() and sock.is_socket())
    if not sock.exists():
        result['passed'] = False
        return result
    status, _, _ = request(sock, prefix, {'Host': 'localhost', 'X-Forwarded-Proto': 'https'})
    check('reject_missing_gateway_identity', status in (401, 403), status=status)
    nonadmin = {**headers, 'X-Trim-Isadmin': 'false'}
    status, _, _ = request(sock, prefix, nonadmin)
    check('reject_nonadmin', status in (401, 403), status=status)
    status, response_headers, body = request(sock, prefix, headers)
    is_html = 'text/html' in response_headers.get('content-type', '')
    check('authorized_html', status == 200 and is_html and b'<html' in body.lower(),
          status=status, bytes=len(body), content_type=response_headers.get('content-type'))
    check('not_fnos_invalid_token_placeholder', body.strip() != b'invalid token')
    if app == 'chiaki-ng-web':
        check('coop', response_headers.get('cross-origin-opener-policy') == 'same-origin')
        check('coep', response_headers.get('cross-origin-embedder-policy') in ('require-corp', 'credentialless'))
    html = body.decode('utf-8', errors='replace') if is_html else ''
    assets = []
    for match in re.finditer(r'(?:src|href)=[\"\x27]([^\"\x27]+)', html):
        value = match.group(1)
        if not urlsplit(value).path.endswith(('.js', '.css')):
            continue
        location = urljoin(prefix, value)
        if urlsplit(location).scheme:
            check('local_script_or_stylesheet', False, asset=value)
            continue
        check('asset_within_gateway_prefix', location.startswith(prefix), asset=location)
        if location.startswith(prefix) and location not in assets:
            assets.append(location)
    for asset in assets[:8]:
        status, asset_headers, asset_body = request(sock, asset, headers)
        mime = asset_headers.get('content-type', '')
        check('asset_load', status == 200 and len(asset_body) > 0 and 'text/html' not in mime,
              asset=asset, status=status, bytes=len(asset_body), content_type=mime)
    if app == 'chiaki-ng-web':
        status, wasm_headers, wasm = request(sock, prefix + 'chiaki.wasm', headers)
        check('real_webassembly_module', status == 200 and wasm[:4] == b'\0asm',
              status=status, bytes=len(wasm), content_type=wasm_headers.get('content-type'))
    result['passed'] = all(item['passed'] for item in result['checks'])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('app', choices=['psrp-web', 'chiaki-ng-web'])
    parser.add_argument('--admin-uid', required=True, type=int)
    parser.add_argument('--output')
    args = parser.parse_args()
    result = verify(args.app, args.admin_uid)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text + '\n')
        destination.chmod(0o600)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
