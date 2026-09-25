/** Real Python worker and controller over stdio; browser objects are controlled. */
import assert from 'node:assert/strict';
import {run_task,resume_task,diagnose_task,close_created_tab,cancel_task} from '../chrome_delegate.mjs';
const origin='http://127.0.0.1:60001';let serial=0;
const opened=[];
const browser={async nameSession(){},tabs:{async new(){
  const state={url:'about:blank',closed:false};
  const t={id:String(++serial),state,async goto(value){state.url=value;},async url(){return state.url;},async getJsDialog(){return undefined;},async close(){assert.equal(state.closed,false);state.closed=true;},async markHandoff(){},playwright:{async evaluate(){return {url:state.url,controls:[{role:'status',name:'Fixture status',automation_id:'status',enabled:true,visible:true,password:false,value:null,checked:null,attributes:{tag:'div',type:'',href:'',text:'ready'}}],overflow:false};}}};opened.push(t);return t;
}}};
const pages=['a','b','c','d'];
const steps=pages.flatMap((p,index)=>[
  ...(index?[{id:'open_'+p,op:'new_tab',intent:'Open disposable page '+p,input_ref:p,after:[{kind:'url',equals:origin+'/'+p}]}]:[]),
  {id:'read_'+p,op:'read',intent:'Verify page '+p,target:{role:'status',name:'Fixture status'},after:[{kind:'url',equals:origin+'/'+p}]}]);
const contract={goal:'Synthetic protocol check: release temporary pages during one task',target:{driver:'browser',connection:'official_chrome',url:origin+'/a'},
  scope:{origins:[origin],actions:['read','new_tab']},inputs:Object.fromEntries(pages.map(p=>[p,{value:origin+'/'+p}])),steps,
  success:[{kind:'url',equals:origin+'/d'}],budget:{steps:20,jev_calls:0,seconds:40}};
const output=await run_task({browser,contract});
assert.equal(output.status,'completed',JSON.stringify(output));
assert.equal(output.completed.length,7);assert.equal(output.usage.jev_requests,0);
assert.equal(output.usage.tabs_created,4);assert.equal(output.usage.tabs_closed_during_run,3);
assert.equal(output.usage.tabs_closed_at_end,1);assert.equal(output.usage.tabs_peak_owned,2);assert.equal(output.usage.tabs_retained,0);
assert.ok(opened.every(t=>t.state.closed));
const resumed=await resume_task({resume_token:output.resume_token,continue_task:true});
assert.equal(resumed.status,'completed');assert.equal(resumed.usage.actions,7);
assert.equal(opened.length,4); // no new page or replay, even with a terminating pipe
const diagnostic=await diagnose_task({resume_token:output.resume_token});
assert.equal(diagnostic.result.usage.tabs_closed_at_end,1);assert.equal(diagnostic.result.usage.tabs_closed_during_run,3);
const repeated=await close_created_tab({resume_token:output.resume_token});assert.equal(repeated.closed_created_tabs,0);
const pauseContract=structuredClone(contract);pauseContract.scope.actions.push('fill');
pauseContract.inputs.pending_text={value:'',pending:true};
pauseContract.steps=[steps[0],{id:'pending',op:'fill',intent:'Wait for authorized text',input_ref:'pending_text',target:{role:'textbox',name:'Draft'},after:[{kind:'value',target:{role:'textbox',name:'Draft'},input_ref:'pending_text'}]}];
pauseContract.success=[{kind:'url',equals:origin+'/a'}];
const paused=await run_task({browser,contract:pauseContract});assert.equal(paused.status,'escalated');assert.equal(paused.escalation_reason,'INPUT_TEXT_REQUIRED');
assert.equal(opened.at(-1).state.closed,false);
const cancelled=await cancel_task({resume_token:paused.resume_token});assert.equal(cancelled.status,'cancelled');assert.equal(cancelled.usage.tabs_closed_at_end,1);assert.equal(opened.at(-1).state.closed,true);
console.log(JSON.stringify({status:'PASS',mode:'real worker/controller/checkpoints/diagnostics/cancel; controlled browser, no Jev request',result:output,cancel_result:cancelled},null,2));
