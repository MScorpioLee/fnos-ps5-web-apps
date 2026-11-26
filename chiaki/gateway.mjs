import http from 'node:http';
import net from 'node:net';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
import {loadSettings,checkPorts} from './setup/settings.mjs';
import {startStandalone} from './setup/standalone.mjs';
for(const k of Object.keys(process.env))if(k.startsWith('wizard_'))delete process.env[k];
const here=path.dirname(fileURLToPath(import.meta.url));
const data=process.env.TRIM_PKGVAR;
if(!data) throw Error('TRIM_PKGVAR required');
process.umask(0o077); fs.mkdirSync(data,{recursive:true});
const credentialFile=path.join(data,'credentials.json');
const settings=loadSettings('chiaki',data);
await checkPorts(settings);
if(!fs.existsSync(credentialFile)) {
 fs.writeFileSync(credentialFile,JSON.stringify({email:'admin@localhost',password:crypto.randomBytes(24).toString('base64url')}),{mode:0o600,flag:'wx'});
}
if(!fs.lstatSync(credentialFile).isFile())throw Error('Unsafe credentials file');
fs.chmodSync(credentialFile,0o600);
const credentials=JSON.parse(fs.readFileSync(credentialFile,'utf8'));
if(!credentials.email || !credentials.password || credentials.password.length<16)throw Error('Invalid bootstrap credentials (minimum 16 characters)');
Object.assign(process.env,{
 CHIAKI_WASM_BIND:'127.0.0.1',CHIAKI_WASM_PORT:'10121',CHIAKI_WASM_LAN_HTTPS:'false',
 CHIAKI_AUTH_ENABLED:'true',CHIAKI_AUTH_ALLOW_REGISTER:'false',CHIAKI_RELAY_ALLOW_WAN:'false',
 CHIAKI_DB_DIR:data,CHIAKI_ADMIN_USER:credentials.username||'admin',CHIAKI_ADMIN_EMAIL:credentials.email,
 CHIAKI_ADMIN_PASSWORD:fs.existsSync(path.join(data,'chiaki.sqlite'))?'':credentials.password,CHIAKI_TRUST_PROXY:'on',
 CHIAKI_WASM_ROOT:path.join(here,'www'),CHIAKI_WASM_WWW:path.join(here,'www')
});
const upstream=await import('./proxy/server.mjs');
const upstreamHandle=await upstream.startServers();
const independent=await startStandalone(settings);
const prefix='/app/chiaki-ng-web';
const security={
 'Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp',
 'Cross-Origin-Resource-Policy':'same-origin','X-Content-Type-Options':'nosniff',
 'Permissions-Policy':'gamepad=(self), fullscreen=(self)',
 'Cache-Control':'no-store'
};
function check(req){
 // Only the Unix socket is exposed to fnOS; loopback upstream retains independent authentication.
 // Gateway identity is mandatory, not accepted on a public TCP socket.
 if(!/^\d+$/.test(String(req.headers['x-trim-userid']||'')) || !/^(1|true)$/i.test(String(req.headers['x-trim-isadmin']||'')))return 403;
 const proto=String(req.headers['x-forwarded-proto']||'').split(',')[0].trim();
 if(proto!=='https')return 426;
 const raw=req.url||'/';
 if(raw!==prefix && !raw.startsWith(prefix+'/'))return 404;
 if(req.headers.origin) {
  try {if(new URL(req.headers.origin).protocol!=='https:' || new URL(req.headers.origin).host!==req.headers.host)return 403;}
  catch{return 403;}
 }
 if(!['GET','HEAD','OPTIONS'].includes(req.method) && !req.headers.origin)return 403;
 return 0;
}
function headers(req){
 const h={...req.headers,'x-forwarded-proto':'https'};
 // Do not forward attacker-controlled proxy identity chains to upstream.
 delete h['x-forwarded-host'];delete h['x-forwarded-for'];delete h['forwarded'];
 return h;
}
const gateway=http.createServer((req,res)=>{
 const code=check(req);if(code){res.writeHead(code,security);res.end(code===426?'Open this application through the fnOS HTTPS gateway':'Forbidden');return;}
 if(req.url===prefix){res.writeHead(308,{...security,Location:prefix+'/'});res.end();return;}
 const proxy=http.request({hostname:'127.0.0.1',port:10121,path:req.url.slice(prefix.length),method:req.method,headers:headers(req)},up=>{
  const h={...up.headers,...security};
  if(h.location?.startsWith('/'))h.location=prefix+h.location;
  res.writeHead(up.statusCode,h);up.pipe(res);
 });
 proxy.on('error',()=>{if(!res.headersSent)res.writeHead(502,security);res.end('Upstream unavailable');});
 req.pipe(proxy);
});
gateway.on('upgrade',(req,socket,head)=>{
 const code=check(req);if(code){socket.end(`HTTP/1.1 ${code} Forbidden\r\nConnection: close\r\n\r\n`);return;}
 const target=net.connect(10121,'127.0.0.1',()=>{
  const h=headers(req);
  target.write(`${req.method} ${req.url.slice(prefix.length)} HTTP/1.1\r\n`+Object.entries(h).map(([k,v])=>`${k}: ${v}\r\n`).join('')+'\r\n');
  if(head.length)target.write(head);socket.pipe(target);target.pipe(socket);
 });
 target.on('error',()=>socket.destroy());socket.on('error',()=>target.destroy());
 socket.on('close',()=>target.destroy());target.on('close',()=>socket.destroy());
});
const socketPath=path.join(process.env.TRIM_APPDEST||here,'app.sock');
if(fs.existsSync(socketPath))fs.unlinkSync(socketPath);
await new Promise((resolve,reject)=>{gateway.once('error',reject);gateway.listen(socketPath,resolve);});
fs.chmodSync(socketPath,0o660);
// nginx worker is www-data on fnOS. Grant only connect/traverse access;
// never join shared groups, chmod 777, or expose the private data directory.
execFileSync('/usr/bin/setfacl',['-m','u:www-data:--x',path.dirname(socketPath)]);
execFileSync('/usr/bin/setfacl',['-m','u:www-data:rw-',socketPath]);
fs.writeFileSync(path.join(data,'ready'),String(process.pid),{mode:0o600});
console.log('fnOS gateway socket ready; HTTPS + NAS admin identity + Chiaki account required');
let closing=false;
async function stop(){if(closing)return;closing=true;independent?.closeIndependent();gateway.close();await upstreamHandle.close();try{fs.unlinkSync(socketPath);}catch{}try{fs.unlinkSync(path.join(data,'ready'));}catch{}process.exit(0);}
process.on('SIGTERM',stop);process.on('SIGINT',stop);
