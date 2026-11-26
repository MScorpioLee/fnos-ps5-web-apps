import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
test('both packaged supervisors consume optional independent ingress and setup',()=>{
 const ps=fs.readFileSync(path.join(root,'psrp/package/app/service.mjs'),'utf8');
 assert.match(ps,/loadSettings\('psrp'/);assert.match(ps,/bootstrapPSRP\(/);assert.match(ps,/startStandalone\(/);assert.match(ps,/psrpEnvironment\(/);
 const ch=fs.readFileSync(path.join(root,'chiaki/gateway.mjs'),'utf8');assert.match(ch,/loadSettings\('chiaki'/);assert.match(ch,/startStandalone\(/);assert.match(ch,/credentials.username/);
 const build=fs.readFileSync(path.join(root,'psrp/build.sh'),'utf8');assert.match(build,/setup\/stage.py/);
 const stage=fs.readFileSync(path.join(root,'chiaki/stage-package.py'),'utf8');assert.match(stage,/setup\/stage.py/);
});
