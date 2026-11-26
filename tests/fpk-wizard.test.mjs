import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {install,checkPorts,loadSettings,psrpEnvironment,bootstrapPSRP} from '../packaging/setup/settings.mjs';
const root=path.resolve(import.meta.dirname,'..');
const setup=path.join(root,'packaging/setup/settings.mjs');
const password='Temporary-Test-Password!42';
const good={wizard_admin_user:'localadmin',wizard_admin_email:'admin@example.invalid',wizard_admin_password:password,wizard_admin_confirm:password};
function fixture(){const v=fs.mkdtempSync(path.join(os.tmpdir(),'ps5-wizard-'));return {v,cleanup:()=>fs.rmSync(v,{recursive:true,force:true})};}
const noPorts=async()=>{}; // Unit tests do not bind installed production ports.
test('default first install keeps gateway-only and stores no plaintext PSRP password',async()=>{
 const f=fixture();try{await install('psrp',f.v,good,noPorts);const p=path.join(f.v,'install-settings.json'),s=JSON.parse(fs.readFileSync(p));assert.equal(s.servicePort,10111);assert.equal(s.standalonePort,null);assert(!('externalUrl' in s));assert.equal(fs.statSync(p).mode&0o777,0o600);assert(!fs.readFileSync(p,'utf8').includes(password));assert(s.bootstrap.passwordHash);const secrets=JSON.parse(fs.readFileSync(path.join(f.v,'secrets.json')));assert.equal(secrets.database.length,64);assert.equal(secrets.jwt.length,128);assert.equal(fs.statSync(path.join(f.v,'secrets.json')).mode&0o777,0o600);
 const hash=Buffer.from(s.bootstrap.passwordHash,'base64'),salt=hash.subarray(13,29);assert.equal(hash[0],1);assert.equal(hash.readUInt32BE(1),2);assert.deepEqual(crypto.pbkdf2Sync(password,salt,hash.readUInt32BE(5),32,'sha512'),hash.subarray(29));
 }finally{f.cleanup();}
});
const invalid=[{wizard_admin_confirm:'wrong'},{wizard_admin_password:'weak',wizard_admin_confirm:'weak'},{wizard_admin_user:'bad\nname'},{wizard_admin_email:'not-email'},{wizard_http_port:'0'},{wizard_http_port:'65536'},{wizard_http_port:'10112'},{wizard_http_port:'10111'},{wizard_http_port:'10121'},{wizard_http_port:'-1'},{wizard_http_port:'18080;id'},{wizard_http_port:'1023'}];
for(const [i,extra] of invalid.entries())test('invalid input rejected without secret logs #'+i,()=>{const f=fixture();try{const r=spawnSync(process.execPath,[setup,'install','psrp'],{encoding:'utf8',env:{PATH:process.env.PATH,TRIM_APPDEST:root,TRIM_PKGVAR:f.v,...good,...extra}});assert.notEqual(r.status,0);assert(!fs.existsSync(path.join(f.v,'install-settings.json')));assert(!(r.stdout+r.stderr).includes(password));assert(!(r.stdout+r.stderr).includes('user:secret'));}finally{f.cleanup();}});
test('custom local reverse-proxy port persists with no domain/DDNS requirement',async()=>{
 for(const app of ['psrp','chiaki']){const f=fixture();try{const id=app==='psrp'?'psrp-web':'chiaki-ng-web';const s=await install(app,f.v,{...good,wizard_http_port:'20110'},noPorts);assert.equal(s.standalonePort,20110);assert(!('externalUrl' in s));assert.equal(s.basePath,`/app/${id}`);assert(!('iceMin' in s));}finally{f.cleanup();}}
});
test('occupied optional HTTP port fails closed',async()=>{const tcp=net.createServer();await new Promise(r=>tcp.listen(0,'127.0.0.1',r));try{await assert.rejects(checkPorts({app:'fixture',servicePort:0,standalonePort:tcp.address().port}));}finally{tcp.close();}});
test('backend env removes wizard secrets; bootstrap INSERT is guarded and retry safe',async()=>{
 const f=fixture();try{
  const s=await install('psrp',f.v,good,noPorts),loaded=loadSettings('psrp',f.v),env=psrpEnvironment(loaded,{wizard_admin_password:password});
  assert.equal(env.ASPNETCORE_URLS,'http://127.0.0.1:10111');assert(!Object.keys(env).some(k=>k.startsWith('wizard_')));assert(!Object.keys(env).some(k=>k.startsWith('WebRTC__')));
  let count=0;await bootstrapPSRP(f.v,s,async sql=>{count++;assert(sql.includes('LOCK TABLE t_user'));assert(sql.includes('WHERE NOT EXISTS (SELECT 1 FROM t_user)'));assert(!/UPDATE\s+t_user/i.test(sql));assert(!sql.includes(password));assert(sql.includes(Buffer.from(s.bootstrap.passwordHash).toString('hex')));});
  assert.equal(count,1);assert(!loadSettings('psrp',f.v).bootstrap);await bootstrapPSRP(f.v,loadSettings('psrp',f.v),async()=>{throw Error('must not run twice');});
 }finally{f.cleanup();}
});
test('retained accounts and upgrade cannot reset passwords/settings',async()=>{
 for(const app of ['psrp','chiaki']){const f=fixture();try{
  await install(app,f.v,good,noPorts);const before=fs.readFileSync(path.join(f.v,'install-settings.json'));const cred=app==='chiaki'?fs.readFileSync(path.join(f.v,'credentials.json')):null;
  await install(app,f.v,{...good,wizard_admin_password:'DIFFERENT-secret',wizard_admin_confirm:'DIFFERENT-secret'},async()=>{throw Error('must not probe retained ports');});assert.deepEqual(fs.readFileSync(path.join(f.v,'install-settings.json')),before);
  if(cred){assert.deepEqual(fs.readFileSync(path.join(f.v,'credentials.json')),cred);assert.equal(fs.statSync(path.join(f.v,'credentials.json')).mode&0o777,0o600);}
  const r=spawnSync(process.execPath,[setup,'upgrade',app],{env:{TRIM_PKGVAR:f.v,wizard_admin_password:'changed'},encoding:'utf8'});assert.equal(r.status,0,r.stderr);assert.deepEqual(fs.readFileSync(path.join(f.v,'install-settings.json')),before);
 }finally{f.cleanup();}}
});
