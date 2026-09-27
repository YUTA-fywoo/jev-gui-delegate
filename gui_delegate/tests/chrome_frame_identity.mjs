import assert from 'node:assert/strict';
import {OfficialTabDriver} from '../chrome_driver.mjs';
import {readControls} from '../chrome_dom.mjs';

const URL='https://fixture.invalid/page';
const PATH='html:nth-of-type(1) > body:nth-of-type(1) > div:nth-of-type(1) > iframe:nth-of-type(1)';
function fixture(overrides={}){
  const child={role:'button',name:'Frame action',automation_id:'frame-action',enabled:true,visible:true,password:false,value:null,checked:null,
    attributes:{tag:'button',type:'button',submit:'false',href:'',text:'Frame action'}};
  const outer={...child,name:'Page action',automation_id:'page-action'};
  const frame={role:'iframe',name:'',automation_id:'',enabled:true,visible:true,password:false,value:null,checked:null,
    attributes:{tag:'iframe',type:'',name_attr:'',src:'',raw_src:'',srcdoc:'false',frame_path:PATH,...overrides}};
  const state={clicks:0,reads:0,matches:1,identity:{id:frame.automation_id,name:frame.attributes.name_attr,src:frame.attributes.raw_src,srcdoc:frame.attributes.srcdoc}};
  const frameLoc={async count(){return state.matches;},async evaluate(){return {...state.identity};}};
  const buttonLoc={async count(){return 1;},async isVisible(){return true;},async isEnabled(){return true;},
    async evaluate(){return {tag:'button',id:child.automation_id,type:'button',role:child.role,name:child.name,password:false,value:null,checked:null,href:'',submit:'false'};},
    async click(){state.clicks++;}};
  const inner={locator(selector){
    if(selector==='html')return {async evaluate(){state.reads++;return {url:'about:blank',controls:[child],overflow:false};}};
    assert.equal(selector,'[id="frame-action"]');return buttonLoc;
  }};
  const source={async evaluate(){return {url:URL,controls:[outer,frame],overflow:false};},
    locator(selector){
      if(selector===PATH)return frameLoc;
      if(selector==='iframe[name="duplicate"]')return {async count(){return 2;}};
      if(selector==='iframe[src="/inside"]')return frameLoc;
      throw new Error('Unexpected selector: '+selector);
    },
    frameLocator(selector){assert.ok([PATH,'iframe[src="/inside"]'].includes(selector));return inner;}};
  const tab={id:'known',async url(){return URL;},async getJsDialog(){},playwright:source};
  const contract={target:{tab_id:'known',url:URL},scope:{origins:['https://fixture.invalid'],actions:['click']}};
  const driver=new OfficialTabDriver(tab,contract);
  return {driver,state,frame,async observe(){await driver.dispatch('bind',{tab_id:'known',url:URL,origins:contract.scope.origins});return driver.dispatch('observe',{});}};
}
const tests=[];
async function check(name,fn){await fn();tests.push({name,status:'PASS'});}
await check('read-only document without children still yields a frame path',async()=>{
  const doc={URL},html={nodeType:1,tagName:'HTML',parentElement:null,getRootNode:()=>doc};
  const body={nodeType:1,tagName:'BODY',parentElement:html,getRootNode:()=>doc};
  const container={nodeType:1,tagName:'DIV',parentElement:body,getRootNode:()=>doc};
  const frame={nodeType:1,tagName:'IFRAME',parentElement:container,getRootNode:()=>doc,
    matches:()=>true,getAttribute:()=>null,hasAttribute:()=>false,closest:()=>null,
    getBoundingClientRect:()=>({width:300,height:150})};
  const root={ownerDocument:doc,querySelectorAll:()=>[frame]};
  const oldStyle=globalThis.getComputedStyle;
  globalThis.getComputedStyle=()=>({visibility:'visible',display:'block'});
  try{assert.equal(readControls(root).controls[0].attributes.frame_path,PATH);}
  finally{if(oldStyle===undefined)delete globalThis.getComputedStyle;else globalThis.getComputedStyle=oldStyle;}
});
await check('anonymous visible iframe preserves page and child controls',async()=>{
  const f=fixture(),obs=await f.observe();
  assert.deepEqual(obs.controls.map(c=>c.name),['Page action','','Frame action']);
  const child=obs.controls.find(c=>c.name==='Frame action');
  await f.driver.dispatch('act',{operation:'click',control_id:child.id});
  assert.equal(f.state.reads,1);assert.equal(f.state.clicks,1);
});
await check('duplicate frame names fall back to observed structural identity',async()=>{
  const f=fixture({name_attr:'duplicate'});assert.equal((await f.observe()).controls.length,3);
});
await check('relative src uses the raw DOM attribute',async()=>{
  const f=fixture({raw_src:'/inside',src:'https://fixture.invalid/inside'});assert.equal((await f.observe()).controls.length,3);
});
await check('explicit about blank retains parent origin',async()=>{
  const f=fixture({src:'about:blank'});assert.equal((await f.observe()).controls.length,3);
});
await check('unapproved frame origin is never read',async()=>{
  const f=fixture({raw_src:'https://outside.invalid/',src:'https://outside.invalid/'});
  await assert.rejects(f.observe(),/CHROME_ORIGIN_DENIED/);assert.equal(f.state.reads,0);
});
await check('public UI keeps main page with explicitly opaque outside frame',async()=>{
  const f=fixture({raw_src:'https://outside.invalid/',src:'https://outside.invalid/'});
  f.driver.contract.observation_policy='public_ui';const obs=await f.observe();
  assert.equal(f.state.reads,0);assert.equal(obs.controls.length,2);
  assert.equal(obs.controls.find(c=>c.role==='iframe').attributes.frame_access,'origin_out_of_scope');
});
await check('nonunique fallback refuses observation',async()=>{
  const f=fixture();f.state.matches=2;
  await assert.rejects(f.observe(),/CHROME_FRAME_IDENTITY_UNAVAILABLE/);assert.equal(f.state.reads,0);
});
await check('frame replaced after observation cannot receive an action',async()=>{
  const f=fixture(),obs=await f.observe();f.state.identity.src='https://outside.invalid/';
  await assert.rejects(f.driver.dispatch('act',{operation:'click',control_id:obs.controls.find(c=>c.name==='Frame action').id}),/CHROME_FRAME_CHANGED/);
  assert.equal(f.state.clicks,0);
});
await check('frame identity changing during observation is refused',async()=>{
  const f=fixture();f.state.identity.name='changed';
  await assert.rejects(f.observe(),/CHROME_FRAME_CHANGED/);assert.equal(f.state.reads,0);
});
console.log(JSON.stringify({status:'PASS',mode:'controlled adapter regression tests',tests}));
