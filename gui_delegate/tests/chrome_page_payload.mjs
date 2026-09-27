import assert from 'node:assert/strict';
import {capturePublicPage,publicPagePayload,documentState} from '../chrome_page.mjs';
let reads=0,closed=false;
const url='https://example.org/article';
const payload={url,title:'Article',format:'text',content:'Observed text',true_length:13,truncated:false};
const tab={id:'observed-tab',async url(){return url;},playwright:{async evaluate(fn){
  assert.equal(closed,false);reads++;
  if(fn===documentState)return {ready:reads===1?'loading':'complete',url,length:13,controls:5};
  assert.equal(fn,publicPagePayload);return payload;
}}};
assert.deepEqual(await capturePublicPage(tab,['https://example.org']),{...payload,tab_id:'observed-tab'});
assert.ok(reads>=4);
await assert.rejects(capturePublicPage(tab,['https://other.invalid']),/PAGE_ORIGIN_CHANGED/);
const moving={async url(){return url;},playwright:{async evaluate(fn){return fn===documentState?{ready:'complete',url,length:13,controls:5}:{...payload,url:url+'?changed'};}}};
await assert.rejects(capturePublicPage(moving,['https://example.org']),/PAGE_CHANGED_DURING_CAPTURE/);
globalThis.document={URL:url,title:'Long article',body:{innerText:'x'.repeat(17000)}};
try{const value=publicPagePayload();assert.equal(value.content.length,16000);assert.equal(value.true_length,17000);assert.equal(value.truncated,true);}
finally{delete globalThis.document;}
const timeElement=(hidden=false)=>({getBoundingClientRect:()=>({width:hidden?0:90,height:20}),closest:()=>null,
  getAttribute:name=>name==='datetime'?'2026-09-25T17:48:57Z':null,parentElement:{innerText:'Maintainer released this'}});
globalThis.document={URL:url,title:'Release',body:{innerText:'Release contents'},querySelectorAll:()=>[timeElement(),timeElement(true)]};
globalThis.getComputedStyle=()=>({display:'inline',visibility:'visible'});
try{
  const value=publicPagePayload();assert.match(value.content,/datetime 2026-09-25T17:48:57Z/);assert.match(value.content,/Maintainer released this/);
  assert.equal(value.content.match(/datetime/g).length,1);assert.equal(value.true_length,value.content.length);
}finally{delete globalThis.document;delete globalThis.getComputedStyle;}
console.log(JSON.stringify({status:'PASS',mode:'unit regression: bounded settling, observed content, origin change, truncation and visible datetime controls'}));
