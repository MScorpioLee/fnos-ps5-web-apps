#!/usr/bin/env python3
from pathlib import Path
import hashlib,os,json
p=Path(__file__).resolve().parent/'package'
for f in p.rglob('*'):
 if f.is_symlink():continue
 if f.is_dir():f.chmod(0o755)
 elif f.is_file():
  executable=f.read_bytes()[:4]==b'\x7fELF' or f.parent.name=='cmd' or f.name=='ffmpeg' and f.parent.name=='bin'
  f.chmod(0o755 if executable else 0o644)
# Keep only one copy of the self-contained runtime. Symlinks remain inside package.
for f in (p/'app/dbtool').iterdir():
 other=p/'app/backend'/f.name
 if f.is_file() and not f.is_symlink() and other.is_file() and f.read_bytes()==other.read_bytes():
  f.unlink();f.symlink_to('../backend/'+f.name)
manifest=[]
for f in sorted((p/'app').rglob('*')):
 if f.is_file() and not f.is_symlink():manifest.append({'path':str(f.relative_to(p/'app')),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size})
(p/'app/licenses/BUNDLE-INVENTORY.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Normalized package and deduplicated runtime:',len(manifest),'regular files')
