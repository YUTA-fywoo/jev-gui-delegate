import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {run_task} from '../chrome_delegate.mjs';
const folder=mkdtempSync(path.join(tmpdir(),'jev-output-conflict-')),file=path.join(folder,'existing.txt');
writeFileSync(file,'existing user content');
let serial=0;
const origin='http://127.0.0.1:60002';
const browser={async nameSession(){},tabs:{async new(){
  let url='about:blank';return {id:String(++serial),async goto(value){url=value;},async url(){return url;},async getJsDialog(){},async close(){},async markHandoff(){},
    playwright:{async evaluate(){return {url,controls:[{role:'status',name:'Ready',automation_id:'ready',enabled:true,visible:true,password:false,value:null,checked:null,attributes:{tag:'div',type:'',href:'',text:'Ready'}}],overflow:false};},async domSnapshot(){return 'replacement must not be written';}}};
}}};
const contract={goal:'Verify immutable output conflict releases the executor',target:{driver:'browser',connection:'official_chrome',url:origin+'/'},
scope:{origins:[origin],actions:['export','read'],write_roots:[folder]},inputs:{output:{kind:'path',value:file}},
steps:[{id:'export',intent:'Export observed page',op:'export',input_ref:'output',browser_options:{export_format:'dom_snapshot'},after:[{kind:'file',input_ref:'output'}]}],
success:[{kind:'file',input_ref:'output'}],budget:{steps:2,jev_calls:0,seconds:60}};
const conflict=await run_task({browser,contract});
assert.equal(conflict.status,'blocked',JSON.stringify(conflict));assert.equal(conflict.escalation_reason,'CHROME_OUTPUT_EXISTS');
assert.equal(readFileSync(file,'utf8'),'existing user content');
const check={...contract,steps:[{id:'read',intent:'Verify the executor is released',op:'read',target:{role:'status',name:'Ready'},after:[{kind:'url',equals:origin+'/'}]}],success:[{kind:'url',equals:origin+'/'}]};
const next=await run_task({browser,contract:check});assert.equal(next.status,'completed',JSON.stringify(next));
console.log(JSON.stringify({status:'PASS',checks:4,mode:'real worker conflict lifecycle with controlled page; existing output preserved, next task not blocked'}));
