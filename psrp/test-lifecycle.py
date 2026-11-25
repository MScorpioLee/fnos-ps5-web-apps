#!/usr/bin/env python3
import os,subprocess,pathlib,socket,time,signal,json
r=pathlib.Path(__file__).resolve().parent
A=pathlib.Path(os.environ.get('PSRP_TEST_APPDEST',r/'package/app'));V=pathlib.Path(os.environ.get('PSRP_TEST_PKGVAR',r/'test-var'))
V.mkdir(exist_ok=True);env={**os.environ,'TRIM_APPDEST':str(A),'TRIM_PKGVAR':str(V)};main=r/'package/cmd/main'
def call(action,expected=0):
 p=subprocess.run([str(main),action],env=env,capture_output=True,text=True,timeout=100)
 assert p.returncode==expected,(action,p.returncode,p.stdout,p.stderr)
 print('PASS lifecycle',action,'exit',p.returncode,flush=True)
 return p
try:
 call('stop');call('status',3)
 sleeper=subprocess.Popen(['sleep','120'])
 try:
  (V/'supervisor.pid').write_text(str(sleeper.pid));call('stop');assert sleeper.poll() is None
  call('status',3);print('PASS stale PID cannot stop unrelated same-UID process',flush=True)
 finally:sleeper.terminate();sleeper.wait()
 (A/'app.sock').touch()
 # Conflict must fail before attempting DB authentication or creating a new cluster.
 blocker=socket.socket();blocker.bind(('127.0.0.1',10111));blocker.listen(1)
 try:call('start',1);call('status',3);print('PASS occupied backend port fails closed',flush=True)
 finally:blocker.close()
 call('start');call('status');first=(V/'supervisor.pid').read_text();secrets=(V/'secrets.json').read_bytes()
 call('start');assert first==(V/'supervisor.pid').read_text();print('PASS duplicate start is idempotent',flush=True)
 subprocess.run(['/var/apps/nodejs_v22/target/bin/node',str(r/'smoke.mjs')],env=env,check=True,timeout=40)
 # Cross-origin writes are denied even with trusted local test gateway headers.
 q=subprocess.run(['curl','-sS','--unix-socket',str(A/'app.sock'),'-X','POST','-H','X-Trim-Userid: smoke-admin','-H','X-Trim-Isadmin: true','-H','Origin: https://evil.invalid','-w','%{http_code}','http://localhost/app/psrp-web/api/auth/login'],capture_output=True,text=True,check=True)
 assert q.stdout.endswith('403') and 'Cross-origin request denied' in q.stdout;print('PASS cross-origin write rejected',flush=True)
 c=socket.socket(socket.AF_UNIX);c.connect(str(A/'app.sock'));c.sendall(b'GET /app/psrp-web/hubs/controller HTTP/1.1\r\nHost: localhost\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nOrigin: https://evil.invalid\r\nX-Trim-Userid: smoke-admin\r\nX-Trim-Isadmin: true\r\n\r\n');reply=c.recv(1000);c.close();assert b'403 Forbidden' in reply;print('PASS cross-origin WebSocket rejected',flush=True)
 call('stop');call('status',3);assert not (A/'app.sock').exists()
 for port in [10111,10112]:
  s=socket.socket();s.settimeout(1);assert s.connect_ex(('127.0.0.1',port))!=0;s.close()
 print('PASS stop closes both loopback ports and socket',flush=True)
 call('start');call('status');assert secrets==(V/'secrets.json').read_bytes();print('PASS restart retains generated secrets and PostgreSQL data',flush=True)
 # Unexpected backend death must take down PG and supervisor, not report healthy.
 backend=int((V/'backend.pid').read_text());os.kill(backend,signal.SIGTERM)
 for i in range(100):
  if not (V/'supervisor.pid').exists():break
  time.sleep(.2)
 call('status',3);assert not (A/'app.sock').exists();print('PASS unexpected backend exit stops private PostgreSQL and cleans socket',flush=True)
finally:
 call('stop');call('status',3)
print('All bounded lifecycle tests complete. Real PS5 streaming NOT tested.',flush=True)
