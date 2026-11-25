#!/usr/bin/env python3
from pathlib import Path
import difflib,tarfile,json
P=Path(__file__).resolve().parent;S=P/'source'; patches=P/'patches';patches.mkdir(exist_ok=True)
records=json.loads((P/'SOURCES.json').read_text())
def pristine(rel):
 for r in sorted(records,key=lambda r:len(r['path']),reverse=True):
  full='source/'+rel
  if full.startswith(r['path']+'/'):
   archive=P/'archives'/(r['repo'].replace('/','-')+'-'+r['revision']+'.tar.gz')
   if not archive.exists():return None
   with tarfile.open(archive) as t:
    root=t.getmembers()[0].name.split('/')[0]
    return t.extractfile(root+'/'+full[len(r['path'])+1:]).read().decode()
def edit(rel,fn):
 p=S/rel;old=p.read_text();new=fn(old)
 if new!=old:p.write_text(new)
 baseline=pristine(rel)
 if baseline is not None and new!=baseline:
  (patches/(rel.replace('/','_')+'.patch')).write_text(''.join(difflib.unified_diff(baseline.splitlines(True),new.splitlines(True),fromfile='a/'+rel,tofile='b/'+rel)))
# Use locally fetched pinned dependencies: no implicit git clone at configure time.
edit('CMakeLists.txt',lambda s:s.replace('GIT_REPOSITORY https://github.com/Mbed-TLS/mbedtls.git','SOURCE_DIR "${CMAKE_SOURCE_DIR}/../deps/mbedtls"\n            # GIT_REPOSITORY removed; pinned by SOURCES.json').replace('GIT_REPOSITORY https://github.com/xiph/opus.git','SOURCE_DIR "${CMAKE_SOURCE_DIR}/../deps/opus"\n        # GIT_REPOSITORY removed; pinned by SOURCES.json'))
# Follow upstream build-wasm.sh's ABI fix.
edit('third-party/gf-complete/src/gf_cpu.c',lambda s:s.replace('int gf_cpu_identify(void)\n{\n    gf_cpu_identified = 1;\n    return 0;\n}', 'void gf_cpu_identify(void)\n{\n    gf_cpu_identified = 1;\n}'))
edit('wasm/proxy/server.mjs',lambda s:s.replace('"Path=/",','"Path=/app/chiaki-ng-web/",').replace('if (secure) parts.push("Secure");','parts.push("Secure");').replace('if (err && err.code === "EADDRINUSE" && wantPort !== 0) {','if (false) {').replace('\t\t\treturn decodeURIComponent(trimmed.slice(eq + 1));','\t\t\ttry { return decodeURIComponent(trimmed.slice(eq + 1)); } catch { return ""; }'))
# Relative assets already work under trailing slash. Patch explicit absolute API/WS links only.
edit('wasm/www/index.html',lambda s:s.replace('<body>','<body>\n<a href="https://github.com/MScorpioLee/fnos-ps5-web-apps" target="_blank" rel="noopener" style="position:fixed;bottom:4px;right:8px;z-index:9999;font:11px sans-serif;color:#aaa">Source / AGPL-3.0</a>',1) if 'Source / AGPL-3.0' not in s else s)
edit('wasm/www/app.js',lambda s:s.replace('"/api/','"/app/chiaki-ng-web/api/').replace('location.host}/share-sig','location.host}/app/chiaki-ng-web/share-sig').replace('location.host}/posix-net','location.host}/app/chiaki-ng-web/posix-net').replace('"/psn-account-id','"/app/chiaki-ng-web/psn-account-id').replace('location.origin}/#share=', 'location.origin}/app/chiaki-ng-web/#share=').replace('fallback: "/downloads/chiaki-proxy-windows.exe"', 'fallback: null').replace('fallback: "/downloads/chiaki-proxy-linux"', 'fallback: null'))
