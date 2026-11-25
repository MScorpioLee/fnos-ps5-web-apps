#!/usr/bin/env python3
import requests,tarfile,io,pathlib,hashlib,json,os
P=pathlib.Path(__file__).resolve().parent
S=requests.Session()
if os.environ.get('BUILD_PROXY'):S.proxies={'http':os.environ['BUILD_PROXY'],'https':os.environ['BUILD_PROXY']}
expected=json.loads((P/'SOURCES.json').read_text()) if (P/'SOURCES.json').exists() else []
expected={r['repo']:r['sha256'] for r in expected}
pins=[('CSystem77/Chiaki-NG-Web','70669b47a16376768001db229e3e8c3baf3e5238','source'),('nanopb/nanopb','e9e6eb5b4b57c69afe6161094e3996e322701e87','source/third-party/nanopb'),('streetpea/jerasure','505ccb4bc69eee8d7ea40a6089a056b99671134f','source/third-party/jerasure'),('streetpea/gf-complete','fa54a4670a5705c84abf6c24b92b0cd479625478','source/third-party/gf-complete'),('Mbed-TLS/mbedtls','8b3f26a5ac38d4fdccbc5c5366229f3e01dafcc0','deps/mbedtls'),('xiph/opus','v1.5.2','deps/opus')]
records=[]
for repo,rev,dest in pins:
 url=f'https://codeload.github.com/{repo}/tar.gz/{rev}'
 cache=P/'archives';cache.mkdir(exist_ok=True);archive=cache/(repo.replace('/','-')+'-'+rev+'.tar.gz')
 if archive.exists():content=archive.read_bytes()
 else:
  r=S.get(url,timeout=(15,60));r.raise_for_status();content=r.content;archive.write_bytes(content)
 digest=hashlib.sha256(content).hexdigest()
 if repo in expected and digest!=expected[repo]:raise RuntimeError('Archive checksum mismatch: '+repo)
 t=tarfile.open(fileobj=io.BytesIO(content));base=t.getmembers()[0].name.split('/')[0]
 out=P/dest;out.mkdir(parents=True,exist_ok=True)
 for m in t.getmembers():
  name=m.name.partition('/')[2]
  if not name:continue
  assert '..' not in name.split('/') and not name.startswith('/'),name
  if m.issym() or m.islnk():
   # Unused packaging symlinks are deliberately omitted.
   continue
  m.name=name;t.extract(m,out)
 records.append(dict(repo=repo,revision=rev,path=dest,sha256=digest));print(repo,rev,flush=True)
(P/'SOURCES.json').write_text(json.dumps(records,indent=2)+'\n')
