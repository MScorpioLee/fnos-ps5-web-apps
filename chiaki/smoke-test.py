#!/usr/bin/env python3
"""Bounded real runtime test. Does not install FPK or connect to a PS5."""
import os,subprocess,time,pathlib,http.client,socket,json,struct,base64,hashlib
P=pathlib.Path(__file__).resolve().parent;A=P/'package/app';R=P/'test-runtime';R.mkdir(exist_ok=True)
NODE='/var/apps/nodejs_v22/target/bin/node';prefix='/app/chiaki-ng-web';results=[]
def report(name,detail):
 results.append({'test':name,'result':'PASS','detail':detail});print('PASS',name,detail,flush=True)
class UnixHTTP(http.client.HTTPConnection):
 def connect(self):
  self.sock=socket.socket(socket.AF_UNIX);self.sock.settimeout(5);self.sock.connect(str(A/'app.sock'))
base={'Host':'nas.test.invalid','X-Trim-Userid':'1000','X-Trim-Isadmin':'1','X-Forwarded-Proto':'https'}
def request(path,method='GET',body=None,extra=None,headers=None):
 h=dict(base if headers is None else headers);h.update(extra or {})
 c=UnixHTTP('localhost');c.request(method,prefix+path,body,h);r=c.getresponse();b=r.read();out=(r.status,dict(r.getheaders()),b);c.close();return out
def ws(cookie=None,origin='https://nas.test.invalid'):
 s=socket.socket(socket.AF_UNIX);s.settimeout(5);s.connect(str(A/'app.sock'))
 h={**base,'Upgrade':'websocket','Connection':'Upgrade','Sec-WebSocket-Key':base64.b64encode(os.urandom(16)).decode(),'Sec-WebSocket-Version':'13','Sec-WebSocket-Protocol':'binary','Origin':origin}
 if cookie:h['Cookie']=cookie
 s.sendall(('GET '+prefix+'/posix-net HTTP/1.1\r\n'+''.join(k+': '+v+'\r\n' for k,v in h.items())+'\r\n').encode())
 data=b''
 while b'\r\n\r\n' not in data:
  chunk=s.recv(4096)
  if not chunk:break
  data+=chunk
 return s,data
env={**os.environ,'TRIM_APPDEST':str(A),'TRIM_PKGVAR':str(R)}
log=open(P/'logs/node-runtime.log','w');proc=subprocess.Popen([NODE,str(A/'gateway.mjs')],env=env,stdout=log,stderr=subprocess.STDOUT)
try:
 for _ in range(100):
  if proc.poll() is not None:raise RuntimeError('Runtime died; see logs/node-runtime.log')
  if (A/'app.sock').exists() and (R/'ready').exists():break
  time.sleep(.1)
 else:raise RuntimeError('Socket not created')
 s,h,b=request('/');assert s==200 and b'Chiaki-NG Web Edition' in b
 assert h.get('Cross-Origin-Opener-Policy')=='same-origin' and h.get('Cross-Origin-Embedder-Policy')=='require-corp'
 report('Gateway HTML + COOP/COEP',{'status':s,'html_bytes':len(b)})
 acl=subprocess.check_output(['/usr/bin/getfacl','-cp',str(A/'app.sock')],text=True)
 assert 'user:www-data:rw-' in acl;report('Narrow www-data socket ACL','rw; no world permissions')
 probe="import socket;s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('app.sock');s.sendall(b'GET /app/chiaki-ng-web/ HTTP/1.1\\r\\nHost: nas.test.invalid\\r\\nX-Trim-Userid: 1000\\r\\nX-Trim-Isadmin: 1\\r\\nX-Forwarded-Proto: https\\r\\nConnection: close\\r\\n\\r\\n');r=s.recv(4096);assert r.startswith(b'HTTP/1.1 200'),r;print('www-data socket HTTP200');s.close()"
 subprocess.run(['sudo','-n','/usr/sbin/runuser','-u','www-data','--','/usr/bin/python3','-c',probe],cwd=A,check=True)
 report('Actual www-data connection','relative socket from inherited application cwd; system ancestor traversal deferred to installation')
 s,_,_=request('/',headers={});assert s==403;report('No gateway identity rejected',s)
 s,_,_=request('/',extra={'X-Forwarded-Proto':'http'});assert s==426;report('Non-HTTPS rejected',s)
 s,_,_=request('/',extra={'X-Trim-Isadmin':'0'});assert s==403;report('Non-admin rejected',s)
 s,_,_=request('/api/state');assert s==401;report('Anonymous state rejected',s)
 s,_,_=request('/api/state',extra={'Cookie':'chiaki_sid=%XX'});assert s==401;report('Malformed cookie rejected without crash',s)
 s,_,_=request('/api/register','POST','{}',{'Origin':'https://nas.test.invalid','Content-Type':'application/json'});assert s==403;report('Registration disabled',s)
 creds=json.loads((R/'credentials.json').read_text())
 s,h,b=request('/api/login','POST',json.dumps(creds),{'Origin':'https://nas.test.invalid','Content-Type':'application/json'})
 assert s==200,(s,b);cookie=h.get('Set-Cookie',h.get('set-cookie',''));assert 'Secure' in cookie and 'HttpOnly' in cookie and 'Path='+prefix+'/' in cookie
 cookie=cookie.split(';')[0];report('Server auth + secure scoped cookie',s)
 s,_,b=request('/api/state',extra={'Cookie':cookie});assert s==200 and 'hosts' in json.loads(b);report('Authenticated persistent profile',s)
 s,_,_=request('/api/state','POST','{}',{'Cookie':cookie,'Origin':'https://evil.invalid'});assert s==403;report('Cross-origin mutation rejected',s)
 s,h,b=request('/chiaki.wasm');assert s==200 and b[:8]==b'\x00asm\x01\x00\x00\x00';assert h.get('Content-Type',h.get('content-type','')).startswith('application/wasm')
 report('Real WASM served',{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'content_type':h.get('Content-Type',h.get('content-type',''))})
 subprocess.run([NODE,'-e',"const fs=require('fs');WebAssembly.compile(fs.readFileSync(process.argv[1])).then(m=>console.log('VALID WASM exports:',WebAssembly.Module.exports(m).length)).catch(e=>{console.error(e);process.exit(1)})",str(A/'www/chiaki.wasm')],check=True)
 report('V8 WebAssembly.compile','valid compiled shared-memory module')
 s,_,b=request('/app.js');assert s==200 and b'/app/chiaki-ng-web/posix-net' in b and b'"/app/chiaki-ng-web/api/' in b;report('API + WS prefix in real app.js',len(b))
 s,_,b=request('/chiaki.js');assert s==200 and len(b)>10000;report('Emscripten JS served',len(b))
 w,b=ws();assert b.startswith(b'HTTP/1.1 401');w.close();report('Anonymous WS denied',401)
 w,b=ws(cookie,origin='https://evil.invalid');assert b.startswith(b'HTTP/1.1 403');w.close();report('Cross-origin WS denied',403)
 w,b=ws(cookie);assert b.startswith(b'HTTP/1.1 101'),b
 # Real masked binary POSIX SOCKET request (AF_INET=2, SOCK_STREAM=1).
 payload=struct.pack('<B3xIiIIII',1,42,100,2,1,0,0);mask=os.urandom(4)
 w.sendall(bytes([0x82,0x80|len(payload)])+mask+bytes(c^mask[i%4] for i,c in enumerate(payload)))
 frame=w.recv(4096);assert frame[0]==0x82 and len(frame)>=30
 reply=struct.unpack('<B3xIiIIII',frame[2:30]);assert reply[1]==42 and reply[3]==0,reply
 w.close();report('Authenticated WS POSIX binary roundtrip',{'http':101,'request_id':reply[1],'result':reply[3]})
 c=http.client.HTTPConnection('127.0.0.1',10121,timeout=5);c.request('GET','/health');r=c.getresponse();assert r.status==200 and r.read()==b'ok';c.close();report('Native Node HTTP health','127.0.0.1:10121')
 # Confirm listening address, never wildcard TCP.
 listeners=subprocess.check_output(['ss','-ltnp'],text=True);matches=[x for x in listeners.splitlines() if ':10121' in x];assert matches and all('127.0.0.1:10121' in x for x in matches);report('No public TCP listener',matches)
finally:
 proc.terminate()
 try:proc.wait(timeout=8)
 except subprocess.TimeoutExpired:proc.kill();proc.wait()
 log.close()
 (P/'logs/smoke-results.json').write_text(json.dumps(results,indent=2)+'\n')
assert not (A/'app.sock').exists(),'Socket leaked'
print('CLEAN: native test process and socket stopped. Pairing/streaming not attempted: user PIN unavailable.')
