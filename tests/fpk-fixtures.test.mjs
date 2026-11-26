import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {install,bootstrapPSRP,loadSettings} from '../packaging/setup/settings.mjs';
const root=path.resolve(import.meta.dirname,'..'),password='Fixture-Only-Password!42';
const good={wizard_admin_user:'fixtureadmin',wizard_admin_password:password,wizard_admin_confirm:password};
const node=process.execPath;
test('real lifecycle scripts stage both packages and work before target extraction in private fixtures',()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'ps5-callback-'));
 try{for(const app of ['psrp','chiaki']){
  const pkg=path.join(tmp,app),data=path.join(pkg,'private-data');
  let r=spawnSync('python3',[path.join(root,'packaging/setup/stage.py'),app,pkg],{encoding:'utf8'});assert.equal(r.status,0,r.stderr);
  const wizard=JSON.parse(fs.readFileSync(path.join(pkg,'wizard/install')));const fields=wizard.flatMap(s=>s.items).map(i=>i.field).filter(Boolean);assert(fields.includes('wizard_http_port'));assert(!fields.includes('wizard_external_url'));assert(!fields.some(f=>/ice|udp|domain|ddns/.test(f)));
  // Probe only a fixture's ephemeral ports, never bind/connect an installed application.
  const preload=path.join(pkg,'probe-fixture.mjs');fs.writeFileSync(preload,`import net from 'node:net';const listen=net.Server.prototype.listen;net.Server.prototype.listen=function(p,...rest){return listen.call(this,[10111,10112,10121].includes(p)?0:p,...rest);};`);
  const env={PATH:process.env.PATH,TRIM_APPDEST:path.join(pkg,'not-yet-extracted'),TRIM_PKGVAR:data,TRIM_TEMP_LOGFILE:path.join(pkg,'error.txt'),NODE_OPTIONS:'--import='+preload,...good};
  for(const name of ['install_init','install_callback']){r=spawnSync('sh',[path.join(pkg,'cmd',name)],{env,encoding:'utf8'});assert.equal(r.status,0,r.stderr);assert(!(r.stdout+r.stderr).includes(password));}
  const file=path.join(data,'install-settings.json'),before=fs.readFileSync(file);assert.equal(fs.statSync(file).mode&0o777,0o600);
  for(const name of ['upgrade_init','upgrade_callback','install_callback']){r=spawnSync('sh',[path.join(pkg,'cmd',name)],{env:{...env,wizard_admin_password:'different'},encoding:'utf8'});assert.equal(r.status,0,r.stderr);assert.deepEqual(fs.readFileSync(file),before);}
  for(const name of ['install_init','install_callback','upgrade_init','upgrade_callback'])assert.equal(spawnSync('sh',['-n',path.join(pkg,'cmd',name)]).status,0);
 }}finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
test('bootstrap with a fake database process creates one hash, retry and upgrade keep its password',async()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'ps5-db-'));try{
  const s=await install('psrp',tmp,good,async()=>{}),db=path.join(tmp,'fake.sqlite');let logs='';
  const execute=async sql=>{const r=spawnSync('python3',[path.join(root,'tests/fixtures/fpk-fake-db.py')],{env:{PATH:process.env.PATH,FAKE_DB_PATH:db},input:sql,encoding:'utf8'});logs+=r.stdout+r.stderr;if(r.status!==0)throw Error('fake database failed');};
  await bootstrapPSRP(tmp,s,execute);
  const read=()=>spawnSync('python3',['-c',"import sqlite3,sys,json; print(json.dumps(sqlite3.connect(sys.argv[1]).execute('SELECT username,email,password_hash FROM t_user').fetchall()))",db],{encoding:'utf8'}).stdout;
  const before=read(),rows=JSON.parse(before);assert.equal(rows.length,1);assert.equal(rows[0][0],good.wizard_admin_user);assert.equal(rows[0][2],s.bootstrap.passwordHash);
  // Simulates a crash after COMMIT but before clearing the pending bootstrap marker.
  await bootstrapPSRP(tmp,s,execute);assert.equal(read(),before);assert(!loadSettings('psrp',tmp).bootstrap);
  const upgrade=spawnSync(node,[path.join(root,'packaging/setup/settings.mjs'),'upgrade','psrp'],{env:{TRIM_PKGVAR:tmp,...good,wizard_admin_password:'new-password'},encoding:'utf8'});assert.equal(upgrade.status,0);assert.equal(read(),before);assert(!logs.includes(password));assert(!logs.includes(s.bootstrap.passwordHash));
 }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
