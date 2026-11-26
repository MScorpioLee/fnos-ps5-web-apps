// Packaging-only setup. Never print inputs, subprocess output or credentials.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

export function privateJson(file,value){
 const fd=fs.openSync(file,'wx',0o600);
 try{fs.writeFileSync(fd,JSON.stringify(value)+'\n');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
}
export function passwordHash(password){
 // ASP.NET Identity V3 format consumed by PSRP VerifyHashedPassword (HMACSHA512).
 const salt=crypto.randomBytes(16), header=Buffer.alloc(13);header[0]=1;
 header.writeUInt32BE(2,1);header.writeUInt32BE(210000,5);header.writeUInt32BE(16,9);
 return Buffer.concat([header,salt,crypto.pbkdf2Sync(password,salt,210000,32,'sha512')]).toString('base64');
}
function port(raw){
 if(!/^[0-9]+$/.test(String(raw))||Number(raw)<1024||Number(raw)>65535)throw Error('Ports must be integers from 1024 to 65535');
 return Number(raw);
}
export function validate(app,e){
 if(!['psrp','chiaki'].includes(app))throw Error('Unknown package');
 const username=e.wizard_admin_user, email=e.wizard_admin_email||String(username)+'@localhost', password=e.wizard_admin_password;
 if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{2,49}$/.test(username||''))throw Error('Account name must be 3–50 ASCII letters, digits, dot, dash or underscore');
 if(!/^[A-Za-z0-9._+%-]+@[A-Za-z0-9.-]+$/.test(email||'')||email.length>100)throw Error('A valid local login email is required');
 if(typeof password!=='string'||password.length<16||password.length>128||/[\x00-\x1f\x7f]/.test(password)||![/[a-z]/,/[A-Z]/,/[0-9]/,/[^A-Za-z0-9]/].every(r=>r.test(password)))throw Error('Password requires 16–128 characters with upper/lowercase, number and symbol');
 if(password!==e.wizard_admin_confirm)throw Error('Password confirmation does not match');
 return validateNetwork(app,e);
}
export function validateNetwork(app,e){
 if(!['psrp','chiaki'].includes(app))throw Error('Unknown package');
 const settings={version:1,app,servicePort:app==='psrp'?10111:10121,standalonePort:null,basePath:'/app/'+(app==='psrp'?'psrp-web':'chiaki-ng-web')};
 const raw=e.wizard_http_port||'';
 if(raw){
  settings.standalonePort=port(raw);
  if([10111,10112,10121].includes(settings.standalonePort))throw Error('HTTP port overlaps a reserved internal application port');
 }
 return settings;
}
export async function checkPorts(settings){
 const net=await import('node:net');const held=[];
 try{
  for(const p of [settings.servicePort,...(settings.app==='psrp'?[10112]:[]),...(settings.standalonePort!==null?[settings.standalonePort]:[])]){
   const s=net.createServer();await new Promise((resolve,reject)=>{s.once('error',()=>reject(Error('TCP port is unavailable: '+p)));s.listen(p,'127.0.0.1',resolve);});held.push(s);
  }
 }finally{for(const s of held)await new Promise(r=>s.close(r));}
}

export function existing(app,v){return ['install-settings.json',...(app==='psrp'?['postgres/PG_VERSION']:['chiaki.sqlite','credentials.json'])].some(f=>fs.existsSync(path.join(v,f)));}
export async function install(app,v,e=process.env,probe=checkPorts){
 if(!['psrp','chiaki'].includes(app)||!v)throw Error('Missing package setup context');
 fs.mkdirSync(v,{recursive:true,mode:0o700});
 if(existing(app,v)){
  // Only an explicit network opt-in may change retained configuration; never credentials.
  if(e.wizard_http_port){
   const next=validateNetwork(app,e),old=loadSettings(app,v);await probe(next);
   replaceSettings(v,{...old,...next});return next;
  }
  return;
 }
 const settings=validate(app,e);await probe(settings);
 if(app==='psrp'){
  settings.bootstrap={username:e.wizard_admin_user,email:e.wizard_admin_email||e.wizard_admin_user+'@localhost',passwordHash:passwordHash(e.wizard_admin_password)};
  const secretFile=path.join(v,'secrets.json');
  if(!fs.existsSync(secretFile))privateJson(secretFile,{database:crypto.randomBytes(32).toString('hex'),jwt:crypto.randomBytes(64).toString('hex')});
 }
 else privateJson(path.join(v,'credentials.json'),{username:e.wizard_admin_user,email:e.wizard_admin_email||e.wizard_admin_user+'@localhost',password:e.wizard_admin_password});
 privateJson(path.join(v,'install-settings.json'),settings);
 return settings;
}
export function cleanEnvironment(env){return Object.fromEntries(Object.entries(env).filter(([k])=>!k.startsWith('wizard_')));}
export function loadSettings(app,v){
 const file=path.join(v,'install-settings.json');
 if(!fs.existsSync(file))return {version:1,app,servicePort:app==='psrp'?10111:10121,standalonePort:null,basePath:'/app/'+(app==='psrp'?'psrp-web':'chiaki-ng-web')};
 if(!fs.lstatSync(file).isFile())throw Error('Unsafe installation settings file');
 fs.chmodSync(file,0o600);const s=JSON.parse(fs.readFileSync(file,'utf8'));
 // Reuse the field validator for stored network configuration, never its bootstrap password.
 const network=validateNetwork(app,{wizard_http_port:s.standalonePort===null?'':String(s.standalonePort)});
 if(s.app!==app||s.version!==1||s.servicePort!==network.servicePort||s.basePath!==network.basePath)throw Error('Invalid installation settings');
 return s;
}
export function psrpEnvironment(settings,env){
 const result={...cleanEnvironment(env),ASPNETCORE_URLS:'http://127.0.0.1:'+settings.servicePort};
 return result;
}
export async function bootstrapPSRP(v,settings,execute){
 if(!settings.bootstrap)return;
 const b=settings.bootstrap;
 // UTF-8 hex literals eliminate quoting/SQL injection and keep plaintext out of SQL.
 const literal=s=>"convert_from(decode('"+Buffer.from(s,'utf8').toString('hex')+"','hex'),'UTF8')";
 const sql=`BEGIN; LOCK TABLE t_user IN EXCLUSIVE MODE;
 INSERT INTO t_user (id,username,email,password_hash,created_at,is_active)
 SELECT ${literal(crypto.randomUUID())},${literal(b.username)},${literal(b.email)},${literal(b.passwordHash)},CURRENT_TIMESTAMP,true
 WHERE NOT EXISTS (SELECT 1 FROM t_user);
 COMMIT;`;
 await execute(sql);
 // Crash after SQL commit is safe: the guarded INSERT will not overwrite an account.
 const updated={...settings};delete updated.bootstrap;
 replaceSettings(v,updated);
}
function replaceSettings(v,updated){
 const tmp=path.join(v,'.install-settings-'+crypto.randomBytes(8).toString('hex'));
 try{privateJson(tmp,updated);fs.renameSync(tmp,path.join(v,'install-settings.json'));}finally{if(fs.existsSync(tmp))fs.unlinkSync(tmp);}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{
  const action=process.argv[2],app=process.argv[3],v=process.env.TRIM_PKGVAR;
  if(!v||!['psrp','chiaki'].includes(app))throw Error('Missing setup context');
  if(action==='install')await install(app,v);
  else if(action==='validate'){
   if(!existing(app,v))await checkPorts(validate(app,process.env));
   else if(process.env.wizard_http_port)await checkPorts(validateNetwork(app,process.env));
  }
  else if(action!=='upgrade')throw Error('Invalid setup action'); // Upgrade never seeds or resets accounts.
 }
 catch{console.error('Installation settings rejected: check account/password confirmation (16–128 mixed characters), optional HTTP port (1024–65535, available), and private data permissions.');process.exitCode=1;}
}

