/** Task-level adapter for the documented official Chrome Browser Use API.
 * Call inside cua_repl with an already bound, authorized Chrome Tab object.
 * No browser endpoint/credential extraction, local TCP server, screenshots,
 * global pointer/system clipboard, browser-profile access, or arbitrary page scripts.
 */
import {spawn} from 'node:child_process';
const {ChromeSurfaces,OfficialTabDriver:ChromeTabDriver}=await import(new URL('./chrome_driver.mjs',import.meta.url).href+'?rev=14');
export const OfficialTabDriver=ChromeTabDriver;
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {readFileSync,existsSync} from 'node:fs';

const ROOT=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const PYTHON=path.join(ROOT,'.venv','Scripts','python.exe');
const sessions=new Map();
function fail(reason){const e=new Error(reason);e.safeReason=reason;throw e;}
function environment(){
  const source=JSON.parse(readFileSync(path.join(ROOT,'gui_delegate','chrome-runtime.json'),'utf8')).env;
  const out={PYTHONUTF8:'1'};
  for(const key of ['PATH','SYSTEMROOT','SYSTEMDRIVE','WINDIR','PROGRAMFILES','PROGRAMFILES(X86)',
    'PROGRAMW6432','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA']){
    if(typeof source[key]==='string')out[key]=source[key];
  }
  return out;
}
function child(){return spawn(PYTHON,['-u','-m','gui_delegate.chrome_worker'],{
  cwd:ROOT,env:environment(),windowsHide:true,stdio:['pipe','pipe','pipe'],shell:false});}
function send(p,message){if(!p.stdin.writable)fail('CHROME_SESSION_DISCONNECTED');p.stdin.write(JSON.stringify(message)+'\n');}

function cleanError(error){
  if(error?.safeReason)return error.safeReason;
  if(/does not support command/.test(String(error?.message||'')))return 'CHROME_BACKEND_CAPABILITY_UNAVAILABLE';
  // Inspect locally, never return raw exception strings which can contain page data.
  if(/interrupt|user.*control|user.*took over|stopp?ed.*extension|extension.*stopp?ed|turn.*ended|session.*ended/i.test(String(error?.message||'')))return 'CHROME_SESSION_INTERRUPTED';
  return 'CHROME_DRIVER_ERROR';
}

// Stream callbacks only enqueue protocol data. Browser API calls are executed
// by pump() in the CURRENT tool invocation, including after resume. Keeping
// browser calls inside the first invocation's stdout callback causes a stale
// host tool context on a later resume.
function attach(p,state){
  let buffer='';state.messages=[];state.waiter=null;
  const push=message=>{if(state.waiter){const resolve=state.waiter;state.waiter=null;resolve(message);}else state.messages.push(message);};
  state.receive=()=>state.messages.length?Promise.resolve(state.messages.shift()):new Promise(resolve=>{state.waiter=resolve;});
  p.stderr.on('data',()=>{});
  p.stdout.setEncoding('utf8');
  p.stdout.on('data',chunk=>{
    buffer+=chunk;
    if(buffer.length>2_000_000){push({type:'fatal',reason:'CHROME_PROTOCOL_INVALID'});p.stdin.end();return;}
    let index;
    while((index=buffer.indexOf('\n'))>=0){
      const line=buffer.slice(0,index);buffer=buffer.slice(index+1);
      try{push(JSON.parse(line));}catch{push({type:'fatal',reason:'CHROME_PROTOCOL_INVALID'});p.stdin.end();}
    }
  });
  p.on('exit',()=>{state.exited=true;push({type:'fatal',reason:'CHROME_WORKER_EXITED'});});
  p.on('error',()=>push({type:'fatal',reason:'CHROME_WORKER_START_FAILED'}));
}

async function pump(state){
  const p=state.process;
  while(true){
    const message=await state.receive();
    if(message.type==='started'){state.token=message.resume_token;sessions.set(state.token,state);continue;}
    if(message.type==='browser_request'){
      if(!state.active){send(p,{id:message.id,ok:false,error:'CHROME_SESSION_NOT_RUNNING'});continue;}
      try{send(p,{id:message.id,ok:true,value:await state.driver.dispatch(message.method,message.payload)});}
      catch(error){send(p,{id:message.id,ok:false,error:cleanError(error)});}
      continue;
    }
    if(message.type==='fatal'){
      state.active=false;
      state.latest={status:'blocked',escalation_reason:message.reason,resume_token:state.token||null};
      return await finish(state);
    }
    if(message.type==='result'){
      state.latest=message.value;
      if(message.value.status==='running')continue;
      state.active=false;
      await finish(state);
      if(['paused','escalated','needs_confirmation'].includes(state.latest.status)){
        try{await state.driver.tab.markHandoff();}catch{}
      }else p.stdin.end();
      return state.latest;
    }
    state.active=false;p.stdin.end();
    state.latest={status:'blocked',escalation_reason:'CHROME_PROTOCOL_INVALID',resume_token:state.token||null};return await finish(state);
  }
}

async function finish(state){
  const terminal=['completed','cancelled','failed','blocked'].includes(state.latest.status);
  try{state.latest.tab_cleanup=await state.driver.cleanup({terminal,reason:state.latest.escalation_reason});}
  catch{state.latest={...state.latest,status:'blocked',escalation_reason:'CHROME_VIEWPORT_RESTORE_REQUIRED',tab_cleanup:{...state.driver.lifecycle.summary(),warning:'CHROME_VIEWPORT_RESTORE_REQUIRED'}};}
  await state.driver.lifecycle.handoffRetained(state.latest.escalation_reason);
  const stats=state.driver.lifecycle.stats();state.latest.usage={...state.latest.usage,...stats};
  if(state.token){
    try{await control('record_chrome_cleanup',{resume_token:state.token,stats});}
    catch{state.latest.tab_cleanup.log_status='unavailable';}
  }
  return state.latest;
}

async function control(operation,args){
  const p=child();let raw='';p.stdout.setEncoding('utf8');p.stdout.on('data',s=>{raw+=s;});p.stderr.on('data',()=>{});
  const done=new Promise((resolve,reject)=>{p.on('error',()=>reject(new Error('CHROME_CONTROL_START_FAILED')));
    p.on('exit',()=>{try{resolve(JSON.parse(raw));}catch{reject(new Error('CHROME_CONTROL_PROTOCOL_INVALID'));}});});
  send(p,{action:'control',operation,arguments:args});p.stdin.end();return await done;
}

export async function run_task({tab,browser,contract}){
  if(contract?.target?.connection!=='official_chrome')fail('CHROME_IDENTITY_MISMATCH');
  const checkedContract=JSON.parse(JSON.stringify(contract));
  if([...sessions.values()].some(x=>x.active))fail('CHROME_TASK_ALREADY_ACTIVE');
  const existingId=checkedContract.target.tab_id;
  checkedContract.target.tab_id=existingId||'new-tab-preflight';
  for(const target of Object.values(checkedContract.targets||{}))if(target.connection==='official_chrome'&&!target.tab_id)target.tab_id='new-tab-preflight';
  const preflight=await control('validate_chrome_contract',{contract:checkedContract});
  const stopped=reason=>({status:'escalated',completed:[],remaining:(checkedContract.steps||[]).map(s=>s.id),evidence_refs:[],usage:{},escalation_reason:reason,resume_token:null});
  if(!preflight.valid){
    if(preflight.resume_token){const {valid,...result}=preflight;return result;}
    return {...stopped(preflight.reason),status:preflight.status||'blocked'};
  }
  let openedHere=false;
  try{if(!tab){
    if(!browser)fail('CHROME_CODEX_SESSION_REQUIRED');
    await browser.nameSession('🌐 Jev task');
    if(existingId){
      const existing=(await browser.user.openTabs()).find(t=>String(t.id)===existingId);
      if(!existing)fail('CHROME_TAB_CLOSED');
      tab=await browser.user.claimTab(existing);
    }
    else {tab=await browser.tabs.new();openedHere=true;await tab.goto(checkedContract.target.url);}
    checkedContract.target.tab_id=String(tab.id);
  }}catch(error){
    const result=stopped(cleanError(error));
    if(openedHere){
      result.tab_cleanup={retained:[{tab_id:String(tab.id),reason:'initial_navigation_unverified'}]};
      try{
        if(result.escalation_reason!=='CHROME_SESSION_INTERRUPTED'&&!existsSync(path.join(ROOT,'gui_delegate','private','STOP'))&&await tab.url()==='about:blank'&&!await tab.getJsDialog()){
          await tab.close();result.tab_cleanup={tabs_closed_at_end:1,retained:[]};
        }
      }catch{}
    }
    return result;
  }
  if(String(tab.id)!==checkedContract.target.tab_id)fail('CHROME_IDENTITY_MISMATCH');
  const p=child(),state={active:true,process:p};
  state.driver=new ChromeSurfaces(tab,checkedContract,browser,{rootCreated:openedHere,
    mayClose:terminal=>!existsSync(path.join(ROOT,'gui_delegate','private','STOP'))&&(terminal||!state.token||!existsSync(path.join(ROOT,'gui_delegate','private',state.token.slice(0,32),'cancel')))});
  attach(p,state);
  send(p,{action:'run',contract:checkedContract});return await pump(state);
}

export async function resume_task(args){
  if(!args.continue_task)return await control('resume_task',args);
  const state=sessions.get(args.resume_token);
  // An idempotent resume of a finished task must not wait for a closed pipe or
  // reopen/replay the GUI. The Python service still validates the request.
  if(state&&!state.active&&['completed','cancelled','blocked','failed'].includes(state.latest?.status))
    return await control('resume_task',{...args,wait_seconds:0});
  if(!state||state.exited)fail('CHROME_SESSION_REBIND_REQUIRED');
  if(state.active)fail('CHROME_TASK_ALREADY_ACTIVE');
  // Python service remains authoritative for user release and immutable scope.
  state.active=true;
  let response;
  try{response=await control('resume_task',{...args,wait_seconds:0});}
  catch(error){state.active=false;throw error;}
  if(response.type==='fatal'||['blocked','failed','cancelled'].includes(response.status)){
    state.active=false;return response;
  }
  if(args.user_released_control===true)state.driver.lifecycle.interrupted=false;
  return await pump(state);
}

export async function cancel_task(args){
  const result=await control('cancel_task',args),state=sessions.get(args.resume_token);
  if(state&&['completed','cancelled','blocked','failed'].includes(result.status)){
    state.active=false;state.latest=result;const out=await finish(state);state.process.stdin.end();return out;
  }
  return result;
}
export async function diagnose_task(args){return await control('diagnose_task',args);}

export async function close_created_tab({resume_token}){
  const state=sessions.get(resume_token);
  if(!state)fail('CHROME_SESSION_REBIND_REQUIRED');
  if(state.active||!['completed','cancelled','blocked','failed'].includes(state.latest?.status))fail('CHROME_CLEANUP_NOT_READY');
  const before=state.driver.lifecycle.stats().tabs_closed_at_end;
  await finish(state);
  return {status:'completed',closed_created_tabs:state.driver.lifecycle.stats().tabs_closed_at_end-before,tab_cleanup:state.latest.tab_cleanup};
}
