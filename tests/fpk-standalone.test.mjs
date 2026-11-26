import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import net from 'node:net';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const listen=s=>new Promise(r=>s.listen(0,'127.0.0.1',r));
const close=s=>new Promise(r=>{s.closeAllConnections?.();s.close(r);});
function request(port,p,headers={},method='GET') {return new Promise((resolve,reject)=>{const r=http.request({host:'127.0.0.1',port,path:p,method,headers:{Host:'play.example:8888','X-Forwarded-Proto':'https',...headers}},res=>{let body='';res.on('data',c=>body+=c);res.on('end',()=>resolve({status:res.statusCode,headers:res.headers,body}));});r.on('error',reject);r.end();});}
function ws(port,p,headers={}){return new Promise((resolve,reject)=>{const s=net.connect(port,'127.0.0.1',()=>s.write(`GET ${p} HTTP/1.1\r\nHost: play.example:8888\r\nX-Forwarded-Proto: https\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nOrigin: https://play.example:8888\r\n${Object.entries(headers).map(([k,v])=>k+': '+v+'\r\n').join('')}\r\n`));s.once('data',d=>{resolve(d.toString());s.destroy();});s.once('error',reject);s.setTimeout(3000,()=>{s.destroy();reject(Error('WebSocket timeout'));});});}
for(const app of ['psrp','chiaki'])test(app+' independent entry validates authority/origin/app auth and strips trusted identity',async()=>{
 const {startStandalone}=await import('../packaging/setup/standalone.mjs');
 const prefix='/app/'+(app==='psrp'?'psrp-web':'chiaki-ng-web'),origin='https://play.example:8888';
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'ps5-http-'));fs.writeFileSync(path.join(temp,'index.html'),'<html>fake application</html>');
 let observed;const backend=http.createServer((req,res)=>{observed={url:req.url,headers:req.headers};
  if(req.url==='/api/auth/me'){res.writeHead(req.headers.authorization==='Bearer VALID'?200:401,{'Content-Type':'application/json'});res.end(JSON.stringify({success:req.headers.authorization==='Bearer VALID',data:{userId:'fixture'}}));return;}
  if(req.url==='/api/meta'){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({authEnabled:true,user:req.headers.cookie==='chiaki_sid=VALID'?{id:1}:null}));return;}
  res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify({success:true}));
 });
 backend.on('upgrade',(req,socket)=>{observed={url:req.url,headers:req.headers};socket.end('HTTP/1.1 101 Switching Protocols\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n');});
 await listen(backend);let entry;
 try{
  entry=await startStandalone({app,standalonePort:0,servicePort:backend.address().port,basePath:prefix},{staticRoot:temp});const port=entry.address().port;
  assert.equal(entry.address().address,'127.0.0.1');
  const login=app==='psrp'?'/api/auth/login':'/api/login', auth=app==='psrp'?{Authorization:'Bearer VALID'}:{Cookie:'chiaki_sid=VALID'};
  assert.equal((await request(port,prefix+'/api/protected',{'X-Trim-Userid':'1','X-Trim-Isadmin':'true'})).status,401);
  assert.equal((await request(port,prefix+login,{},'POST')).status,403);
  assert.equal((await request(port,prefix+login,{Origin:'https://evil.invalid'},'POST')).status,403);
  assert.equal((await request(port,prefix+login,{Origin:origin,Host:'play.example'},'POST')).status,403);
  assert.equal((await request(port,prefix+login,{Origin:origin,'X-Forwarded-Proto':'http'},'POST')).status,426);
  assert.equal((await request(port,prefix+login,{Origin:origin,'X-Forwarded-Proto':'https,http'},'POST')).status,426);
  assert.equal((await request(port,prefix+login,{Origin:origin,'X-Forwarded-Host':'evil.invalid'},'POST')).status,403);
  assert.equal((await request(port,prefix+login,{Origin:origin},'POST')).status,200);
  assert.equal((await request(port,prefix+'/api/auth/register',{Origin:origin,...auth},'POST')).status,403);
  assert.equal((await request(port,prefix+'/api/register',{Origin:origin,...auth},'POST')).status,403);
  assert.equal((await request(port,prefix+'/api/protected',{Origin:origin,...auth,'X-Trim-Userid':'1','X-Trim-Isadmin':'true','X-Forwarded-Host':'play.example:8888',Forwarded:'host=evil.invalid'})).status,200);
  assert.equal(observed.headers['x-trim-userid'],undefined);assert.equal(observed.headers['x-trim-isadmin'],undefined);assert.equal(observed.headers.forwarded,undefined);assert.equal(observed.headers.host,'play.example:8888');assert.equal(observed.headers['x-forwarded-proto'],'https');assert.equal(observed.url,'/api/protected');
  assert.equal((await request(port,'/wrong/api/protected',auth)).status,404);
  assert.equal((await request(port,prefix+'/api/protected',{...auth,Origin:'https://play.example'})).status,403);
  assert.equal((await request(port,prefix+'/api/protected',{...auth,Host:'other.example:9999',Origin:'https://other.example:9999'})).status,200);
  assert.match(await ws(port,prefix+'/hubs/controller'),/401/);
  const token=app==='psrp'?'?access_token=VALID':'';
  assert.match(await ws(port,prefix+'/hubs/controller'+token,auth),/101/);assert.equal(observed.headers['x-trim-userid'],undefined);
 }finally{if(entry)await close(entry);await close(backend);fs.rmSync(temp,{recursive:true,force:true});}
});
