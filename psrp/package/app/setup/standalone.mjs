// Optional independent HTTP ingress for a SAME-HOST HTTPS reverse proxy.
// Never reuse the fnOS identity-header gateway on TCP. No firewall/UPnP changes.
import http from 'node:http';
import net from 'node:net';
import fs from 'node:fs';
import path from 'node:path';
const security={
 'Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp',
 'Cross-Origin-Resource-Policy':'same-origin','X-Content-Type-Options':'nosniff',
 'Referrer-Policy':'no-referrer','Cache-Control':'no-store',
 'Permissions-Policy':'gamepad=(self), fullscreen=(self)'
};
export async function startStandalone(settings,{staticRoot}={}){
 if(settings.standalonePort===null)return null;
 const prefix=settings.basePath,target=settings.servicePort;
 const deny=(res,status)=>{res.writeHead(status,security);res.end(status===401?'Application login required':'Independent entry request denied');};
 function route(req,upgrade=false){
  // Only this loopback-only listener may trust the local HTTPS reverse proxy.
  // Host is never a fnOS identity. Origin must match its complete HTTPS authority.
  if(!['127.0.0.1','::ffff:127.0.0.1'].includes(req.socket.remoteAddress))return {error:403};
  if(req.headers['x-forwarded-proto']!=='https')return {error:426};
  const host=String(req.headers.host||'');let external;
  if(!host||/[\s,@/\\?#]/.test(host))return {error:421};
  try{external=new URL('https://'+host);if(external.host!==host.toLowerCase())return {error:421};}catch{return {error:421};}
  if(req.headers['x-forwarded-host']&&req.headers['x-forwarded-host']!==host)return {error:403};
  if(req.headers['sec-fetch-site']==='cross-site')return {error:403};
  if(req.headers.origin&&req.headers.origin!==external.origin)return {error:403};
  if((upgrade||!['GET','HEAD','OPTIONS'].includes(req.method))&&req.headers.origin!==external.origin)return {error:403};
  const raw=(req.url||'').split('?')[0];
  if(!raw.startsWith('/')||/%2e|%2f|%5c|\\|\/\.{1,2}(?:\/|$)/i.test(raw))return {error:400};
  let url;try{url=new URL(req.url,'http://localhost');}catch{return {error:400};}
  if(url.pathname!==prefix&&!url.pathname.startsWith(prefix+'/'))return {error:404};
  const relative=url.pathname.slice(prefix.length)||'/';
  if(/^\/api\/(?:auth\/)?register\/?$/i.test(relative))return {error:403};
  return {url,relative,mapped:relative+url.search};
 }
 function headers(req,ws=false){
  const external=new URL('https://'+req.headers.host);
  const result={};
  for(const [k,v] of Object.entries(req.headers)){
   if(k.startsWith('x-trim-')||k.startsWith('x-forwarded-')||['forwarded','proxy-authorization','proxy-connection','x-real-ip','host'].includes(k))continue;
   if(!ws&&['connection','upgrade','keep-alive','te','trailer','transfer-encoding'].includes(k))continue;
   result[k]=v;
  }
  return {...result,host:external.host,'x-forwarded-proto':'https'};
 }
 async function authenticated(req,info){
  try{
   const h=headers(req),opts={headers:h,signal:AbortSignal.timeout(3000),redirect:'error'};
   if(settings.app==='psrp'){
    const token=/^Bearer (.+)$/i.exec(String(req.headers.authorization||''))?.[1]||info.url.searchParams.get('access_token');
    if(!token)return false;opts.headers={Authorization:'Bearer '+token};
    const response=await fetch('http://127.0.0.1:'+target+'/api/auth/me',opts);
    if(!response.ok)return false;const body=await response.json();return body.success===true||body.Success===true;
   }
   const response=await fetch('http://127.0.0.1:'+target+'/api/meta',opts);
   if(!response.ok)return false;const body=await response.json();return body.authEnabled===true&&Boolean(body.user?.id);
  }catch{return false;}
 }
 function publicRequest(req,info){
  const p=info.relative.toLowerCase();
  if(settings.app==='psrp')return req.method==='POST'&&['/api/auth/login','/api/auth/refresh'].includes(p);
  return req.method==='POST'&&p==='/api/login'||req.method==='GET'&&p==='/api/meta';
 }
 function proxy(req,res,mapped){
  const up=http.request({host:'127.0.0.1',port:target,path:mapped,method:req.method,headers:headers(req)},r=>{
   const h={...r.headers,...security};delete h['access-control-allow-origin'];delete h['access-control-allow-credentials'];
   if(h.location?.startsWith('/')&&!h.location.startsWith('//'))h.location=prefix+h.location;
   if(h['set-cookie'])h['set-cookie']=h['set-cookie'].map(c=>c.replace(/;\s*Path=\/([^;]*)/i,'; Path='+prefix+'/'));
   res.writeHead(r.statusCode,h);r.pipe(res);
  });
  up.setTimeout(30000,()=>up.destroy());up.on('error',()=>{if(!res.headersSent)deny(res,502);else res.destroy();});req.on('aborted',()=>up.destroy());req.pipe(up);
 }
 const attempts={start:0,count:0};
 const server=http.createServer(async(req,res)=>{
  try{
   const info=route(req);if(info.error){deny(res,info.error);return;}
   if(req.method==='OPTIONS'){deny(res,403);return;}
   const api=/^\/(api|hubs|hls)(\/|$)/i.test(info.relative)||settings.app==='chiaki'&&info.relative==='/psn-account-id';
   const isPublic=publicRequest(req,info);
   if(isPublic&&req.method==='POST'){
    if(Date.now()-attempts.start>60000){attempts.start=Date.now();attempts.count=0;}
    if(++attempts.count>30){deny(res,429);return;}
   }
   if(api&&!isPublic&&!await authenticated(req,info)){deny(res,401);return;}
   if(settings.app==='chiaki'||api){proxy(req,res,info.mapped);return;}
   if(!['GET','HEAD'].includes(req.method)){deny(res,405);return;}
   const root=fs.realpathSync(staticRoot),relative=decodeURIComponent(info.relative),file=path.resolve(root,'.'+relative);
   if(file!==root&&!file.startsWith(root+path.sep)){deny(res,403);return;}
   let chosen=file;if(!fs.existsSync(chosen)||fs.statSync(chosen).isDirectory())chosen=path.join(root,'index.html');
   if(!fs.realpathSync(chosen).startsWith(root+path.sep)){deny(res,403);return;}
   const mime={'.html':'text/html; charset=utf-8','.js':'application/javascript','.css':'text/css','.wasm':'application/wasm','.json':'application/json','.webmanifest':'application/manifest+json','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon'};
   res.writeHead(200,{...security,'Content-Type':mime[path.extname(chosen)]||'application/octet-stream'});
   if(req.method==='HEAD')res.end();else fs.createReadStream(chosen).on('error',()=>res.destroy()).pipe(res);
  }catch{if(!res.headersSent)deny(res,502);else res.destroy();}
 });
 const sockets=new Set();server.on('connection',s=>{sockets.add(s);s.once('close',()=>sockets.delete(s));});
 server.closeIndependent=()=>{for(const s of sockets)s.destroy();server.close();};
 server.on('upgrade',async(req,socket,head)=>{
  const info=route(req,true);
  if(info.error||!await authenticated(req,info)){socket.end(`HTTP/1.1 ${info.error||401} Rejected\r\nConnection: close\r\n\r\n`);return;}
  if(settings.app==='psrp'&&!/^\/hubs\//i.test(info.relative)){socket.end('HTTP/1.1 404 Not Found\r\n\r\n');return;}
  const up=net.connect(target,'127.0.0.1',()=>{
   const h=headers(req,true);up.write(`${req.method} ${info.mapped} HTTP/1.1\r\n`+Object.entries(h).map(([k,v])=>`${k}: ${v}\r\n`).join('')+'\r\n');if(head.length)up.write(head);socket.pipe(up);up.pipe(socket);
  });
  up.on('error',()=>socket.destroy());socket.on('error',()=>up.destroy());socket.once('close',()=>up.destroy());up.once('close',()=>socket.destroy());
 });
 server.on('clientError',(_e,s)=>s.end('HTTP/1.1 400 Bad Request\r\n\r\n'));
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(settings.standalonePort,'127.0.0.1',resolve);});
 return server;
}
