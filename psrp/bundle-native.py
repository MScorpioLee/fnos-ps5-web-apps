#!/usr/bin/env python3
from pathlib import Path
import shutil,subprocess,re,os,json
root=Path(__file__).resolve().parent
app=root/'package/app'
def copy(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst,follow_symlinks=True)
seen_libraries=set()
def libs(binary,dest):
 env={**os.environ}; env.pop('LD_LIBRARY_PATH',None)
 text=subprocess.check_output(['ldd',str(binary)],env=env,text=True)
 for path in re.findall(r'=> (/[^\s]+)',text):
  if Path(path).name not in ['libc.so.6','libm.so.6','libpthread.so.0','libdl.so.2','librt.so.1']:
   standard=Path('/lib/x86_64-linux-gnu')/Path(path).name
   if standard.exists():path=str(standard)
   copy(path,dest/Path(path).name)
   if path in seen_libraries:continue
   seen_libraries.add(path)
   # Preserve the copyright for each bundled Debian dependency.
   q=subprocess.run(['dpkg-query','-S',str(Path(path).resolve())],capture_output=True,text=True)
   if q.returncode:
    q=subprocess.run(['dpkg-query','-S',str(path)],capture_output=True,text=True)
   for line in q.stdout.splitlines():
    pkg=line.split(': ')[0].split(':')[0]; notice=Path('/usr/share/doc')/pkg/'copyright'
    if notice.exists():copy(notice,app/'licenses'/('debian-'+pkg+'-copyright'))
pg=app/'pg'
shutil.copytree('/usr/lib/postgresql/15',pg/'lib/postgresql/15',dirs_exist_ok=True)
shutil.copytree('/usr/share/postgresql/15',pg/'share/postgresql/15',dirs_exist_ok=True)
for f in (pg/'lib/postgresql/15').rglob('*'):
 if f.is_file() and (f.suffix=='.so' or f.parent.name=='bin'):
  try:libs(f,pg/'deps')
  except subprocess.CalledProcessError:pass
ffmpeg=root/'downloads/ffmpeg-debian/usr/bin/ffmpeg'
if not ffmpeg.exists():raise SystemExit('Extract Debian ffmpeg .deb under downloads/ffmpeg-debian first (see build.sh)')
if (app/'ffmpeg').exists():shutil.rmtree(app/'ffmpeg')
copy(ffmpeg,app/'ffmpeg/ffmpeg')
libs(ffmpeg,app/'ffmpeg/lib')
(app/'bin').mkdir(exist_ok=True)
f=app/'bin/ffmpeg';f.write_text('#!/bin/sh\nD="$(CDPATH= cd -- "$(dirname -- "$0")/../ffmpeg" && pwd)"\nexport LD_LIBRARY_PATH="$D/lib"\nexec "$D/ffmpeg" "$@"\n');f.chmod(0o755)
licenses=app/'licenses';licenses.mkdir(exist_ok=True)
for name in ['postgresql-15','ffmpeg']:
 p=Path('/usr/share/doc')/name/'copyright'
 if p.exists():copy(p,licenses/(name+'-copyright'))
copy(root/'source/LICENSE',licenses/'PSRP-MIT')
print('Bundled PostgreSQL15 and FFmpeg plus shared-library closures')
