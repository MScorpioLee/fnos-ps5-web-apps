#!/usr/bin/env python3
from pathlib import Path
import json,shutil,xml.etree.ElementTree as ET
r=Path(__file__).resolve().parent; out=r/'package/app/licenses';out.mkdir(exist_ok=True)
assets=json.loads((r/'source/RemotePlay/obj/project.assets.json').read_text()); roots=[Path(x)for x in assets['packageFolders']];entries=[]
for name,meta in assets['libraries'].items():
 folder=next((x/meta['path'] for x in roots if (x/meta['path']).exists()),None)
 if folder is None:continue
 target=out/'nuget'/name;target.mkdir(parents=True,exist_ok=True)
 for f in folder.rglob('*'):
  if f.is_file() and any(x in f.name.lower() for x in ['license','notice']) and f.stat().st_size<2000000:
   shutil.copy2(f,target/f.name)
 for f in folder.glob('*.nuspec'):shutil.copy2(f,target/f.name)
 entries.append({'package':name,'source':'https://www.nuget.org/packages/'+name.replace('/','/')})
for framework in ['microsoft.netcore.app.runtime.linux-x64','microsoft.aspnetcore.app.runtime.linux-x64']:
 for root in roots:
  folder=root/framework/'10.0.15'
  for f in folder.glob('*'):
   if f.is_file() and any(x in f.name.lower() for x in ['license','notice']):
    d=out/'dotnet'/framework;d.mkdir(parents=True,exist_ok=True);shutil.copy2(f,d/f.name)
(out/'NUGET-PACKAGES.json').write_text(json.dumps(entries,indent=2)+'\n')
# npm includes all build dependencies as an intentionally conservative superset.
mods=r/'source/RemotePlay.Web/node_modules'
for f in mods.rglob('*'):
 if f.is_file() and f.name.lower().startswith(('license','copying','notice')) and f.stat().st_size<1000000:
  d=out/'npm'/f.relative_to(mods);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,d)
print('Third-party NuGet/npm license notices collected')
