/** Real worker/resume transport with controlled browser and no model calls. */
import assert from 'node:assert/strict';
import {run_task,resume_task,diagnose_task} from '../chrome_delegate.mjs';
const origin='http://127.0.0.1:60002';let serial=0,uncertain=false;
const opened=[];
const browser={async nameSession(){},tabs:{async new(){
  const state={url:'about:blank',closed:false,clicks:0};
  const raw={role:'link',name:'Destination',automation_id:'destination',enabled:true,visible:true,password:false,value:null,checked:null,
    attributes:{tag:'a',type:'',href:origin+'/done',submit:'false',text:'Destination'}};
  const locator={async count(){return 1;},async isVisible(){return true;},async isEnabled(){return true;},
    async evaluate(){return {tag:'a',type:'',id:'destination',role:'link',name:'Destination',password:false,value:null,checked:null,href:origin+'/done',submit:'false'};},
    async click(){state.clicks++;state.url=origin+'/done';if(uncertain)throw new Error('Synthetic uncertain mouse return');}};
  const tab={id:String(++serial),state,async goto(url){state.url=url;},async url(){return state.url;},async getJsDialog(){},async close(){state.closed=true;},async markHandoff(){},
    playwright:{async evaluate(fn){
      if(fn.name==='documentState')return {url:state.url,ready:'complete',length:12,controls:1};
      if(fn.name==='publicPagePayload'){assert.equal(state.closed,false);return {url:state.url,title:'Destination',format:'text',content:'Result text.',true_length:12,truncated:false};}
      return {url:state.url,controls:[raw],overflow:false};},locator(){return locator;}}};opened.push(tab);return tab;
}}};
const contract={goal:'Open the observed destination',mode:'goal',observation_policy:'public_ui',
  target:{driver:'browser',connection:'official_chrome',url:origin+'/start'},scope:{origins:[origin],actions:['click']},
  success:[{kind:'url_path',equals:'/done'}],budget:{steps:3,jev_calls:0,seconds:60}};
const complete=await run_task({browser,contract});
assert.equal(complete.status,'completed',JSON.stringify(complete));assert.deepEqual(complete.completed,['goal_001']);
assert.equal(complete.usage.jev_requests,0);assert.equal(opened[0].state.clicks,1);assert.equal(complete.verification[0].passed,true);
assert.equal(complete.page.content,'Result text.');assert.equal(complete.page.url,origin+'/done');
const stored=await resume_task({resume_token:complete.resume_token,continue_task:true});
assert.deepEqual(stored.page,complete.page);
uncertain=true;
const paused=await run_task({browser,contract});assert.equal(paused.status,'escalated');assert.equal(paused.escalation_reason,'CHROME_DRIVER_ERROR');
const diagnostic=await diagnose_task({resume_token:paused.resume_token});assert.equal(diagnostic.checkpoint.phase,'dispatched');
const resumed=await resume_task({resume_token:paused.resume_token,continue_task:true});
assert.equal(resumed.status,'completed',JSON.stringify(resumed));assert.deepEqual(resumed.completed,['goal_001']);
assert.equal(opened[1].state.clicks,1);assert.equal(resumed.verification[0].passed,true);
assert.equal(resumed.usage.actions,1);
console.log(JSON.stringify({status:'PASS',checks:8,mode:'real goal worker and resume, fake browser, zero model calls; uncertain action reconciled without replay'}));
