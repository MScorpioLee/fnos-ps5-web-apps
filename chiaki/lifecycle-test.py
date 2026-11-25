#!/usr/bin/env python3
import subprocess,os,pathlib,socket
p=pathlib.Path(__file__).resolve().parent;app=p/'package/app';var=p/'test-runtime';env={**os.environ,'TRIM_APPDEST':str(app),'TRIM_PKGVAR':str(var)};cmd=str(p/'package/cmd/main');rows=[]
def run(arg,expected):
 r=subprocess.run([cmd,arg],env=env,capture_output=True,text=True)
 assert r.returncode==expected,(arg,r.returncode,r.stdout,r.stderr)
 rows.append(f'{arg}: exit {r.returncode}')
try:
 run('status',3);run('bad-command',1);run('start',0);run('start',0);run('status',0);run('stop',0);run('status',3)
 assert (var/'chiaki.sqlite').exists();assert not (app/'app.sock').exists();rows.append('Persistent SQLite retained after stop; socket removed')
 with socket.socket() as s:
  s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',10121));s.listen();run('start',1);run('status',3);run('stop',0)
 rows.append('Port conflict refused (no random/wildcard fallback)')
 for q in (p/'package/cmd').iterdir():subprocess.run(['bash','-n',str(q)],check=True)
 for q in [app/'gateway.mjs',*(app/'proxy').glob('*.mjs')]:subprocess.run(['/var/apps/nodejs_v22/target/bin/node','--check',str(q)],check=True)
 rows.append('All lifecycle shell + native Node syntax checks passed')
finally:
 subprocess.run([cmd,'stop'],env=env,capture_output=True)
 (p/'logs/lifecycle-test.log').write_text('\n'.join(rows)+'\n')
print('\n'.join(rows))
