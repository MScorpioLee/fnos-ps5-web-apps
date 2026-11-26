import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {install,loadSettings} from '../packaging/setup/settings.mjs';
test('retained install accepts explicit network opt-in without changing its existing password',async()=>{
 const v=fs.mkdtempSync(path.join(os.tmpdir(),'ps5-retained-'));try{
  fs.writeFileSync(path.join(v,'chiaki.sqlite'),'existing fixture database');
  const credentials={username:'olduser',email:'old@localhost',password:'Existing-Fixture-Password!42'};fs.writeFileSync(path.join(v,'credentials.json'),JSON.stringify(credentials),{mode:0o600});const before=fs.readFileSync(path.join(v,'credentials.json'));
  await install('chiaki',v,{wizard_http_port:'20130',wizard_admin_password:'must-not-be-used'},async()=>{});
  assert.equal(loadSettings('chiaki',v).standalonePort,20130);assert.deepEqual(fs.readFileSync(path.join(v,'credentials.json')),before);assert.equal(fs.readFileSync(path.join(v,'chiaki.sqlite'),'utf8'),'existing fixture database');
 }finally{fs.rmSync(v,{recursive:true,force:true});}
});
