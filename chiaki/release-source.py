#!/usr/bin/env python3
"""Release corresponding source, never runtime credentials or prebuilt helper binaries."""
from pathlib import Path
import tarfile
P=Path(__file__).resolve().parent
out=P/'chiaki-ng-web-corresponding-source.tar.gz'
allowed=['source','deps','patches','SOURCES.json','LICENSE','README.md','TEST-REPORT.md','gateway.mjs','fetch-sources.py','apply-patches.py','stage-package.py','build.sh','smoke-test.py','lifecycle-test.py','release-source.py','.gitignore']
def filtered(info):
 parts=info.name.split('/')
 if any(x in parts for x in ['build-wasm','tools','.git','__pycache__','downloads']):return None
 if any(info.name.endswith(x) for x in ['.wasm','.exe','.dll','.so','.o','.a','.sqlite','.db','.key','.pem']):return None
 return info
with tarfile.open(out,'w:gz') as t:
 # stage-package.py/build.sh now reference these shared original packaging sources.
 t.add(P.parent/'packaging/setup',arcname='packaging/setup',filter=filtered)
 t.add(P.parent/'LICENSE',arcname='LICENSE',filter=filtered)
 for name in allowed:
  q=P/name
  if q.exists():t.add(q,arcname='chiaki/'+name,filter=filtered)
print(out,'bytes=',out.stat().st_size)
