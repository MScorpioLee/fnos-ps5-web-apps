import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import net from 'node:net';
import crypto from 'node:crypto';
import {spawn, spawnSync} from 'node:child_process';
import {loadSettings,psrpEnvironment,bootstrapPSRP,checkPorts} from './setup/settings.mjs';
import {startStandalone} from './setup/standalone.mjs';
for(const k of Object.keys(process.env))if(k.startsWith('wizard_'))delete process.env[k];
if(!process.env.TRIM_APPDEST||!process.env.TRIM_PKGVAR)throw Error('TRIM_APPDEST and TRIM_PKGVAR required');
fs.mkdirSync(process.env.TRIM_PKGVAR,{recursive:true,mode:0o700});
const A=fs.realpathSync(process.env.TRIM_APPDEST), V=fs.realpathSync(process.env.TRIM_PKGVAR);
process.env.TRIM_APPDEST=A;process.env.TRIM_PKGVAR=V;
const pgb=path.join(A,'pg/lib/postgresql/15/bin');
const pgEnv={...process.env,LD_LIBRARY_PATH:path.join(A,'pg/deps')};
const pidFile=path.join(V,'supervisor.pid'), sock=path.join(A,'app.sock');
fs.mkdirSync(V,{recursive:true,mode:0o700});
const alive=pid=>{if(!/^\d+$/.test(String(pid))||Number(pid)<2)return false;try{const stat=fs.readFileSync('/proc/'+pid+'/stat','utf8');if(stat.slice(stat.lastIndexOf(')')+2).startsWith('Z'))return false;process.kill(Number(pid),0);return true}catch{return false}};
function ownedPid(file,command,argument){
 try{const pid=fs.readFileSync(file,'utf8').trim();if(!alive(pid))return '';const status=fs.readFileSync('/proc/'+pid+'/status','utf8');const uid=Number(status.match(/^Uid:\s+(\d+)/m)?.[1]);if(uid!==process.getuid())return '';const argv=fs.readFileSync('/proc/'+pid+'/cmdline','utf8').split('\0');if(!argv.includes(command)||argument&&!argv.includes(argument))return '';const environ=fs.readFileSync('/proc/'+pid+'/environ','utf8').split('\0');if(!environ.includes('TRIM_PKGVAR='+V))return '';return pid}catch{return ''}
}
const readPid=()=>ownedPid(pidFile,path.join(A,'service.mjs'),'serve');
const unixHealth=()=>new Promise(resolve=>{const r=http.get({socketPath:sock,path:'/app/psrp-web/healthz',headers:{'x-trim-userid':'local-lifecycle','x-trim-isadmin':'true'},timeout:1000},res=>{let b='';res.on('data',c=>b+=c);res.on('end',()=>{try{resolve(res.statusCode===200&&JSON.parse(b).status==='ok')}catch{resolve(false)}})});r.on('timeout',()=>r.destroy());r.on('error',()=>resolve(false))});
if(process.argv[2]==='start'){
 if(alive(readPid())){if(await unixHealth())process.exit(0);console.error('Existing supervisor is unhealthy; stop before restarting');process.exit(1)}
 // A stale pathname must never satisfy startup readiness.
 try{fs.unlinkSync(sock)}catch(e){if(e.code!=='ENOENT')throw e}
 const log=fs.openSync(path.join(V,'service.log'),'a',0o600);
 const c=spawn(process.execPath,[import.meta.filename,'serve'],{detached:true,stdio:['ignore',log,log],env:process.env});c.unref();
 for(let n=0;n<120;n++){await new Promise(r=>setTimeout(r,500));if(readPid()===String(c.pid)&&await unixHealth())process.exit(0);if(!alive(c.pid))break;}
 if(readPid()===String(c.pid))process.kill(c.pid,'SIGTERM');
 console.error('PSRP startup failed; inspect '+path.join(V,'service.log'));process.exit(1);
}
if(process.argv[2]==='stop'){
 const pid=readPid();if(alive(pid))process.kill(Number(pid),'SIGTERM');
 for(let n=0;n<100&&alive(pid);n++)await new Promise(r=>setTimeout(r,500));
 if(alive(pid)){console.error('Supervisor did not stop cleanly');process.exit(1)}process.exit(0);
}
if(process.argv[2]==='status'){
 let ok=alive(readPid())&&fs.existsSync(sock);
 ok&&=Boolean(ownedPid(path.join(V,'backend.pid'),path.join(A,'backend/RemotePlay')));
 ok&&=Boolean(ownedPid(path.join(V,'postgres.pid'),path.join(pgb,'postgres')));
 if(ok)ok=await unixHealth();
 process.exit(ok?0:3);
}
if(process.argv[2]!=='serve')process.exit(1);
if(process.getuid()===0)throw Error('Refusing root service; use package user');
fs.writeFileSync(pidFile,String(process.pid),{mode:0o600});
const children=[];let stopping=false,independent=null;
const settings=loadSettings('psrp',V);
const run=(exe,args,env=process.env)=>new Promise((resolve,reject)=>{const c=spawn(exe,args,{env,stdio:'inherit'});c.on('error',reject);c.on('exit',code=>code===0?resolve():reject(Error(exe+' exited '+code)))});
const launch=(exe,args,env,file)=>{const c=spawn(exe,args,{env,stdio:'inherit'});children.push(c);fs.writeFileSync(path.join(V,file),String(c.pid),{mode:0o600});c.on('error',e=>{console.error(e);shutdown(1)});c.on('exit',()=>{if(!stopping){console.error('Service exited: '+exe);shutdown(1)}});return c};
async function shutdown(code=0){
 if(stopping)return;stopping=true;
 if(independent)independent.closeIndependent();
 for(const c of children.toReversed()){
  if(c.exitCode!==null||c.signalCode)continue;
  c.kill('SIGTERM');
  for(let i=0;i<70&&c.exitCode===null&&!c.signalCode;i++)await new Promise(r=>setTimeout(r,500));
  if(c.exitCode===null&&!c.signalCode)c.kill('SIGKILL');
 }
 for(const f of [sock,pidFile,path.join(V,'backend.pid'),path.join(V,'postgres.pid')])try{fs.unlinkSync(f)}catch{}
 process.exit(code);
}
process.on('SIGTERM',()=>shutdown());process.on('SIGINT',()=>shutdown());
try{
 // Check all loopback listeners before initializing or connecting to a database.
 await checkPorts(settings);
 const secretsFile=path.join(V,'secrets.json');
 if(!fs.existsSync(secretsFile))fs.writeFileSync(secretsFile,JSON.stringify({database:crypto.randomBytes(32).toString('hex'),jwt:crypto.randomBytes(64).toString('hex')}),{mode:0o600,flag:'wx'});
 fs.chmodSync(secretsFile,0o600);const secrets=JSON.parse(fs.readFileSync(secretsFile));
 const data=path.join(V,'postgres'); const pgSocket=path.join(V,'pgsocket'); fs.mkdirSync(pgSocket,{recursive:true,mode:0o700});
 if(!fs.existsSync(path.join(data,'PG_VERSION'))){
  const pw=path.join(V,'.pg-password');fs.writeFileSync(pw,secrets.database,{mode:0o600});
  try{await run(path.join(pgb,'initdb'),['-D',data,'-U','psrp','--pwfile='+pw,'--auth-local=trust','--auth-host=scram-sha-256','--encoding=UTF8','--locale=C.UTF-8','-L',path.join(A,'pg/share/postgresql/15')],pgEnv)}finally{fs.unlinkSync(pw)}
 }
 launch(path.join(pgb,'postgres'),['-D',data,'-h','127.0.0.1','-p','10112','-k',pgSocket,'-c','max_connections=30','-c','shared_buffers=64MB','-c','unix_socket_permissions=0700'],pgEnv,'postgres.pid');
 let ready=false;
 for(let i=0;i<120;i++){const r=spawnSync(path.join(pgb,'pg_isready'),['-h','127.0.0.1','-p','10112','-U','psrp'],{env:pgEnv,stdio:'ignore'});if(r.status===0){ready=true;break}await new Promise(r=>setTimeout(r,250))}if(!ready)throw Error('PostgreSQL startup timeout');
 const dbEnv={...pgEnv,PGPASSWORD:secrets.database};
 const exists=spawnSync(path.join(pgb,'psql'),['-h','127.0.0.1','-p','10112','-U','psrp','-d','postgres','-Atc',"SELECT 1 FROM pg_database WHERE datname='psrp'"],{env:dbEnv,encoding:'utf8'});
 if(exists.status!==0)throw Error('Cannot query private PG cluster');
 if(exists.stdout.trim()!=='1')await run(path.join(pgb,'createdb'),['-h','127.0.0.1','-p','10112','-U','psrp','psrp'],dbEnv);
 const work=path.join(V,'backend');fs.mkdirSync(path.join(work,'wwwroot'),{recursive:true,mode:0o700});
 const env=psrpEnvironment(settings,{...process.env,HOME:V,TMPDIR:V,ASPNETCORE_ENVIRONMENT:'Production','Logging__LogLevel__Microsoft.AspNetCore':'Warning','Logging__LogLevel__Microsoft.EntityFrameworkCore':'Warning',ASPNETCORE_CONTENTROOT:work,DOTNET_PROCESSOR_COUNT:'2',ConnectionStrings__DB:`Host=127.0.0.1;Port=10112;Database=psrp;Username=psrp;Password=${secrets.database}`,JWT__Secret:secrets.jwt,JWT__Issuer:'RemotePlay',JWT__Audience:'RemotePlayClient',PATH:path.join(A,'bin')+':'+process.env.PATH});
 delete env.LD_LIBRARY_PATH;
 await run(path.join(A,'dbtool/RemotePlay.DBTool'),[],env);
 await bootstrapPSRP(V,settings,async sql=>{
  // No password/hash in process arguments, subprocess output or PG error-statement logs.
  const r=spawnSync(path.join(pgb,'psql'),['-X','-q','-v','ON_ERROR_STOP=1','-h','127.0.0.1','-p','10112','-U','psrp','-d','psrp','-f','-'],{env:{...dbEnv,PGOPTIONS:'-c log_statement=none -c log_min_error_statement=panic -c log_min_messages=panic'},input:sql,encoding:'utf8',stdio:['pipe','pipe','pipe'],timeout:30000});
  if(r.status!==0)throw Error('Local account initialization failed; existing accounts have not been overwritten');
 });
 launch(path.join(A,'backend/RemotePlay'),[],env,'backend.pid');
 for(let i=0;i<120;i++){try{const r=await fetch('http://127.0.0.1:10111/healthz');if(r.ok){ready=true;break}}catch{}ready=false;await new Promise(r=>setTimeout(r,250))}if(!ready)throw Error('Backend startup timeout');
 const prefix='/app/psrp-web';
 function sameOrigin(req){
  if(req.headers['sec-fetch-site']==='cross-site')return false;
  if(!req.headers.origin)return true;
  try{const origin=new URL(req.headers.origin);return origin.host===req.headers.host&&['https:','http:'].includes(origin.protocol)}catch{return false}
 }
 function authorize(req,res){
  if(!['GET','HEAD','OPTIONS'].includes(req.method)&&!sameOrigin(req)){res.writeHead(403);res.end('Cross-origin request denied');return false}
  // Headers are trusted ONLY on the local Unix socket owned by this package.
  if(!req.headers['x-trim-userid']||!['true','1'].includes(String(req.headers['x-trim-isadmin']).toLowerCase())){res.writeHead(403);res.end('fnOS administrator session required');return false}return true;
 }
 function mapped(req){const u=new URL(req.url,'http://localhost');if(u.pathname===prefix)u.pathname='/';else if(u.pathname.startsWith(prefix+'/'))u.pathname=u.pathname.slice(prefix.length);return u.pathname+u.search}
 function proxy(req,res){
  const headers={...req.headers};for(const h of Object.keys(headers))if(h.startsWith('x-trim-'))delete headers[h];
  const up=http.request({host:'127.0.0.1',port:10111,path:mapped(req),method:req.method,headers},r=>{res.writeHead(r.statusCode,r.headers);r.pipe(res)});up.on('error',()=>{res.writeHead(502);res.end('Backend unavailable')});req.pipe(up);
 }
 const server=http.createServer((req,res)=>{
  if(!authorize(req,res))return;
  const u=mapped(req);if(/^\/(api|hubs|healthz|hls)(\/|\?|$)/i.test(u)){proxy(req,res);return}
  let relative;try{relative=decodeURIComponent(u.split('?')[0])}catch{res.writeHead(400);res.end();return}
  const root=path.join(A,'www');let f=path.resolve(root,'.'+relative);
  if(!f.startsWith(root+path.sep)&&f!==root){res.writeHead(403);res.end();return}
  if(!fs.existsSync(f)||fs.statSync(f).isDirectory())f=path.join(root,'index.html');
  const mime={'.html':'text/html; charset=utf-8','.js':'application/javascript','.css':'text/css','.json':'application/json','.webmanifest':'application/manifest+json','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.wasm':'application/wasm'};
  res.writeHead(200,{'Content-Type':mime[path.extname(f)]||'application/octet-stream','Cache-Control':'no-cache','X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin'});fs.createReadStream(f).pipe(res);
 });
 server.on('upgrade',(req,socket,head)=>{
  if(!sameOrigin(req)){socket.end('HTTP/1.1 403 Forbidden\r\n\r\n');return}
  if(!req.headers['x-trim-userid']||!['true','1'].includes(String(req.headers['x-trim-isadmin']).toLowerCase())){socket.end('HTTP/1.1 403 Forbidden\r\n\r\n');return}
  if(!/^\/hubs\//.test(mapped(req))){socket.end('HTTP/1.1 404 Not Found\r\n\r\n');return}
  const up=net.connect(10111,'127.0.0.1',()=>{let h=`${req.method} ${mapped(req)} HTTP/${req.httpVersion}\r\n`;for(const[k,v]of Object.entries(req.headers))if(!k.startsWith('x-trim-'))h+=`${k}: ${v}\r\n`;up.write(h+'\r\n');if(head.length)up.write(head);socket.pipe(up);up.pipe(socket)});up.on('error',()=>socket.destroy());socket.on('error',()=>up.destroy());socket.on('close',()=>up.destroy());up.on('close',()=>socket.destroy());
 });
 if(fs.existsSync(sock))fs.unlinkSync(sock);await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(sock,resolve)});fs.chmodSync(sock,0o600);
 const acl=spawnSync('/usr/bin/setfacl',['-m','u:www-data:rw',sock],{encoding:'utf8'});if(acl.status!==0)throw Error('Cannot grant fnOS nginx user access to gateway socket: '+acl.stderr);
 independent=await startStandalone(settings,{staticRoot:path.join(A,'www')});
 console.log('PSRP native services ready: Unix gateway + loopback backend/private PostgreSQL; optional loopback independent entry. No public TCP listener.');
}catch(e){console.error(e);await shutdown(1)}
