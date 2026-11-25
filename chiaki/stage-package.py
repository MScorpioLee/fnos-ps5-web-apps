#!/usr/bin/env python3
from pathlib import Path
import shutil,json,zlib,struct
P=Path(__file__).resolve().parent;D=P/'package'
for d in ['app/proxy','app/www','app/ui/images','cmd','config','wizard']: (D/d).mkdir(parents=True,exist_ok=True)
b=P/'source/build-wasm/wasm'
assert (b/'chiaki.wasm').read_bytes()[:8]==b'\x00asm\x01\x00\x00\x00'
shutil.copytree(P/'source/wasm/www',D/'app/www',dirs_exist_ok=True)
# The prebuilt helper executables are unrelated runtime servers and deliberately excluded.
shutil.rmtree(D/'app/www/downloads',ignore_errors=True)
for q in b.glob('chiaki*'):
 if q.is_file():shutil.copy2(q,D/'app/www'/q.name)
for name in ['server.mjs','env.mjs','store.mjs','share.mjs']:shutil.copy2(P/'source/wasm/proxy'/name,D/'app/proxy'/name)
shutil.copy2(P/'gateway.mjs',D/'app/gateway.mjs')
license_dir=D/'app/licenses';license_dir.mkdir(exist_ok=True)
for name in ['COPYING','LICENSE','COPYING.md','LICENSE.md']:
 if (P/'source'/name).exists():shutil.copy2(P/'source'/name,license_dir/name);shutil.copy2(P/'source'/name,D/'LICENSE')
for dep in ['mbedtls','opus']:
 for f in (P/'deps'/dep).glob('*'):
  if f.is_file() and ('LICENSE' in f.name.upper() or 'COPYING' in f.name.upper()):shutil.copy2(f,license_dir/(dep+'-'+f.name))
for dep in ['nanopb','jerasure','gf-complete']:
 for f in (P/'source/third-party'/dep).glob('*'):
  if f.is_file() and ('LICENSE' in f.name.upper() or 'COPYING' in f.name.upper()):shutil.copy2(f,license_dir/(dep+'-'+f.name))
shutil.copy2(P/'SOURCES.json',license_dir/'SOURCES.json')
(D/'manifest').write_text('''appname=chiaki-ng-web
version=1.10.0-1
display_name=Chiaki-NG Web (Native)
desc=Native PS4/PS5 browser Remote Play; HTTPS gateway and administrator login required.
platform=x86
source=thirdparty
maintainer=MScorpioLee
maintainer_url=https://github.com/MScorpioLee/fnos-ps5-web-apps
os_min_version=1.2.0
install_dep_apps=nodejs_v22
checkport=false
ctl_stop=true
disable_authorization_path=true
desktop_uidir=ui
desktop_applaunchname=chiaki-ng-web.main
''')
(D/'config/privilege').write_text(json.dumps({'defaults':{'run-as':'package'},'username':'chiaki-ng-web','groupname':'chiaki-ng-web'},indent=2))
(D/'config/resource').write_text('{}\n')
(D/'app/ui/config').write_text(json.dumps({'.url':{'chiaki-ng-web.main':{'title':'Chiaki-NG Web','icon':'images/icon_{0}.png','type':'url','protocol':'','gatewayPrefix':'/app/chiaki-ng-web','gatewaySocket':'app.sock','url':'/app/chiaki-ng-web/','allUsers':False,'control':{'accessPerm':'readonly'}}}},indent=2))
# Small original icon, not a copied vendor trademark.
def png(n):
 raw=b''.join(b'\0'+b''.join(bytes((45,130,220,255) if (n//5<x<4*n//5 and n//3<y<2*n//3) else (18,24,38,255)) for x in range(n)) for y in range(n))
 def c(t,v):return struct.pack('>I',len(v))+t+v+struct.pack('>I',zlib.crc32(t+v)&0xffffffff)
 return b'\x89PNG\r\n\x1a\n'+c(b'IHDR',struct.pack('>IIBBBBB',n,n,8,6,0,0,0))+c(b'IDAT',zlib.compress(raw))+c(b'IEND',b'')
for n,name in [(64,'ICON.PNG'),(256,'ICON_256.PNG')]:
 (D/name).write_bytes(png(n));(D/f'app/ui/images/icon_{n}.png').write_bytes(png(n))
main='''#!/bin/bash
set -eu
umask 077
: "${TRIM_APPDEST:?}" "${TRIM_PKGVAR:?}"
NODE=/var/apps/nodejs_v22/target/bin/node
PID="$TRIM_PKGVAR/service.pid"
running() {
 [ -f "$PID" ] || return 1
 p=$(cat "$PID")
 case "$p" in ''|*[!0-9]*) return 1;; esac
 [ -r "/proc/$p/cmdline" ] || return 1
 tr '\\0' '\\n' <"/proc/$p/cmdline" | grep -Fxq "$TRIM_APPDEST/gateway.mjs" && kill -0 "$p" 2>/dev/null
}
case "${1:-}" in
 start)
  mkdir -p "$TRIM_PKGVAR"; chmod 700 "$TRIM_PKGVAR"
  running && exit 0
  [ -x "$NODE" ] || { printf '%s\\n' 'nodejs_v22 runtime missing' >"${TRIM_TEMP_LOGFILE:-$TRIM_PKGVAR/error.log}"; exit 1; }
  cd "$TRIM_APPDEST"
  rm -f "$TRIM_APPDEST/app.sock" "$TRIM_PKGVAR/ready"
  nohup "$NODE" "$TRIM_APPDEST/gateway.mjs" >>"$TRIM_PKGVAR/service.log" 2>&1 </dev/null &
  p=$!; printf '%s\\n' "$p" >"$PID"
  for i in $(seq 1 50); do
   if [ -S "$TRIM_APPDEST/app.sock" ] && [ -f "$TRIM_PKGVAR/ready" ] && kill -0 "$p" 2>/dev/null; then exit 0; fi
   kill -0 "$p" 2>/dev/null || break
   sleep 0.1
  done
  kill "$p" 2>/dev/null || true
  printf '%s\\n' 'Chiaki startup failed: check persistent service.log' >"${TRIM_TEMP_LOGFILE:-$TRIM_PKGVAR/error.log}"
  exit 1;;
 stop)
  if running; then
   kill "$p"
   for i in $(seq 1 50); do kill -0 "$p" 2>/dev/null || break; sleep 0.1; done
   if kill -0 "$p" 2>/dev/null; then kill -KILL "$p"; fi
  fi
  rm -f "$PID" "$TRIM_APPDEST/app.sock" "$TRIM_PKGVAR/ready";;
 status) running && exit 0; exit 3;;
 *) exit 1;;
esac
'''
(D/'cmd/main').write_text(main)
for name in ['install_init','install_callback','upgrade_init','upgrade_callback','uninstall_init','uninstall_callback']:
 (D/'cmd'/name).write_text('#!/bin/sh\n# Deliberately retain TRIM_PKGVAR: credentials, SQLite pairing/profile data.\nexit 0\n')
for q in (D/'cmd').iterdir():q.chmod(0o755)
(D/'wizard/install').write_text(json.dumps([{'stepTitle':'HTTPS / account','items':[{'type':'tips','helpText':'Open through fnOS HTTPS gateway as NAS administrator. First start creates private credentials.json under application var; retrieve locally over SSH. Registration disabled. PS5 link PIN required. Safari is not guaranteed.'}]}]))
(D/'wizard/uninstall').write_text(json.dumps([{'stepTitle':'Retain data','items':[{'type':'tips','helpText':'This package never deletes credentials, pairing keys or SQLite data. Back up the application var directory before uninstalling; do not select fnOS system data cleanup.'}]}]))
print('Staged real WASM:',(b/'chiaki.wasm').stat().st_size,'bytes')
