import assert from 'node:assert/strict';
import {OfficialTabDriver} from '../chrome_delegate.mjs';

const URL='https://fixture.invalid/test';
function fixture(){
  const c={role:'button',name:'Save locally',automation_id:'save',enabled:true,visible:true,password:false,value:null,checked:null,
    attributes:{tag:'button',type:'button',group:'',submit:'false',href:'',text:'Save locally'}};
  const state={url:URL,controls:[c],count:1,calls:0,probe:{role:'button',name:'Save locally',tag:'button',id:'save',type:'button',password:false,value:null,checked:null,href:'',submit:'false'}};
  const loc={and(){return this;},async count(){return state.count;},async evaluate(){return state.probe;},async isVisible(){return true;},async isEnabled(){return true;},async click(){state.calls++;}};
  const tab={id:'known',async url(){return state.url;},async getJsDialog(){return undefined;},playwright:{async evaluate(){return {overflow:false,controls:state.controls};},getByRole(){return loc;},locator(){return loc;}}};
  const contract={target:{tab_id:'known',url:URL},scope:{origins:['https://fixture.invalid'],actions:['click','key']}};
  const d=new OfficialTabDriver(tab,contract);
  return {d,state,contract};
}
async function bound(){const f=fixture();await f.d.dispatch('bind',{tab_id:'known',url:URL,origins:f.contract.scope.origins});const observed=await f.d.dispatch('observe',{});f.id=observed.controls[0].id;return f;}
const cases=[];
async function check(name,fn){await fn();cases.push({name,status:'PASS'});}
await check('reject arbitrary method',async()=>{const f=await bound();await assert.rejects(f.d.dispatch('eval',{code:'danger'}),/CHROME_UNSUPPORTED_ACTION/);assert.equal(f.state.calls,0);});
await check('reject origin change before reading',async()=>{const f=await bound();f.state.url='https://outside.invalid/';await assert.rejects(f.d.dispatch('observe',{}),/CHROME_ORIGIN_DENIED/);});
await check('reject ambiguous current match',async()=>{const f=await bound();f.state.count=2;await assert.rejects(f.d.dispatch('act',{control_id:f.id,operation:'click'}),/CHROME_AMBIGUOUS_CONTROL/);assert.equal(f.state.calls,0);});
await check('reject replaced link destination',async()=>{const f=await bound();f.state.probe.href='https://outside.invalid/';await assert.rejects(f.d.dispatch('act',{control_id:f.id,operation:'click'}),/CHROME_CONTROL_STALE/);assert.equal(f.state.calls,0);});
await check('reject input becoming a password',async()=>{const f=await bound();f.state.probe.password=true;await assert.rejects(f.d.dispatch('act',{control_id:f.id,operation:'click'}),/CHROME_PASSWORD_CONTROL/);assert.equal(f.state.calls,0);});
await check('reject unknown observed identity',async()=>{const f=await bound();await assert.rejects(f.d.dispatch('act',{control_id:'invented',operation:'click'}),/CHROME_CONTROL_STALE/);assert.equal(f.state.calls,0);});
await check('reject arbitrary hotkey',async()=>{const f=await bound();await assert.rejects(f.d.dispatch('act',{control_id:f.id,operation:'key',value:'Control+L'}),/CHROME_INPUT_NOT_ALLOWED/);assert.equal(f.state.calls,0);});
await check('correct observed action issues once',async()=>{const f=await bound();await f.d.dispatch('act',{control_id:f.id,operation:'click'});assert.equal(f.state.calls,1);});
await check('changed visible label invalidates evidence',async()=>{const f=await bound();f.state.probe.name='Different action';await assert.rejects(f.d.dispatch('act',{control_id:f.id,operation:'click'}),/CHROME_CONTROL_STALE/);assert.equal(f.state.calls,0);});
await check('history outside this task cannot be read',async()=>{const f=await bound();f.contract.scope.actions.push('back');await assert.rejects(f.d.dispatch('act',{operation:'back'}),/CHROME_HISTORY_OUTSIDE_TASK/);});
await check('outside-origin assets never bundled',async()=>{const f=await bound();let bundled=false;f.contract.scope.actions.push('assets');f.d.tab.capabilities={async get(){return {async documentation(){return '';},async list(){return {assets:[{id:'x',kind:'image',url:'https://unapproved.invalid/file'}]};},async bundle(){bundled=true;}};}};await assert.rejects(f.d.dispatch('act',{operation:'assets'}),/CHROME_ORIGIN_DENIED/);assert.equal(bundled,false);});
await check('known native-dialog host fault returns without action',async()=>{const f=await bound();f.d.lastUrl=URL;f.d.tab.getJsDialog=async()=>({type:'alert'});f.contract.scope.actions.push('dialog_dismiss');await assert.rejects(f.d.dispatch('act',{operation:'dialog_dismiss'}),/CHROME_JS_DIALOG_HOST_BLOCKED/);assert.equal(f.state.calls,0);});
await check('unsafe current geometry never emits pointer input',async()=>{const f=await bound();f.contract.scope.actions.push('hover');f.d.point=async()=>{throw new Error('CHROME_GEOMETRY_UNSAFE');};await assert.rejects(f.d.dispatch('act',{control_id:f.id,operation:'hover'}),/CHROME_GEOMETRY_UNSAFE/);assert.equal(f.state.calls,0);});
console.log(JSON.stringify({status:'PASS',mode:'controlled fake-tab guard tests; not browser or API success',tests:cases}));
