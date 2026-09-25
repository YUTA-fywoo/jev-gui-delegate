/** Auditable public entry for the dedicated CUA tool. No caller-supplied code.
 * Literal request JSON is checked by the Hook; contracts use the original
 * strict Python schema, authorization checks, and Chrome task controller.
 */
import {readFileSync,lstatSync} from 'node:fs';
import path from 'node:path';
const delegate=await import(new URL('./chrome_delegate.mjs',import.meta.url).href+'?strict=4');

function fail(reason){const e=new Error(reason);e.safeReason=reason;throw e;}
function keys(value,allowed){
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!allowed.includes(k)))fail('GATEWAY_INVALID_REQUEST');
}
export function presentation(result){
  // Keep one copy of counters. Full results and all diagnostics stay local;
  // retained tab identities/reasons and warnings are never hidden.
  if(!result.tab_cleanup||!result.usage)return result;
  const tab_cleanup=Object.fromEntries(Object.entries(result.tab_cleanup).filter(([key,value])=>
    !key.startsWith('tabs_')||typeof value!=='number'||result.usage[key]!==value));
  return {...result,tab_cleanup};
}
export function readContract(filename){
  if(typeof filename!=='string'||!path.isAbsolute(filename)||path.extname(filename).toLowerCase()!=='.json'||filename.startsWith('\\\\')||filename.slice(2).includes(':'))fail('GATEWAY_CONTRACT_PATH_DENIED');
  let current=path.resolve(filename);
  while(true){if(lstatSync(current).isSymbolicLink())fail('GATEWAY_CONTRACT_LINK_DENIED');const parent=path.dirname(current);if(parent===current)break;current=parent;}
  if(lstatSync(filename).size>1_000_000)fail('GATEWAY_CONTRACT_TOO_LARGE');
  return JSON.parse(readFileSync(filename,'utf8'));
}
export async function dispatch({browser,request},output){
  let result;
  try{
    keys(request,['operation','contract_path','arguments']);
    if(request.operation==='run_task'){
      if(request.arguments!==undefined)fail('GATEWAY_INVALID_REQUEST');
      result=await delegate.run_task({browser,contract:readContract(request.contract_path)});
    }else if(['resume_task','cancel_task','diagnose_task','close_created_tab'].includes(request.operation)){
      if(request.contract_path!==undefined)fail('GATEWAY_INVALID_REQUEST');
      keys(request.arguments,['resume_token','wait_seconds','continue_task','user_released_control','input_updates','decision_override']);
      if(request.operation==='close_created_tab')keys(request.arguments,['resume_token']);
      result=await delegate[request.operation](request.arguments);
    }else fail('GATEWAY_OPERATION_UNSUPPORTED');
  }catch(error){result={status:'blocked',escalation_reason:error?.safeReason||'GATEWAY_REQUEST_FAILED',resume_token:null};}
  // Only machine-generated task results enter the model context.
  output.write(presentation(result));
}
