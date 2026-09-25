/** Resource ownership and verified-checkpoint cleanup. No model decisions. */
import {digest,stop} from './chrome_dom.mjs';

const signature=data=>digest([data.url,data.controls.map(c=>[c.role,c.name,c.automation_id,c.frame_url,c.value,c.checked,c.attributes.href,c.attributes.files])]);
export class TaskTabs{
  constructor(contract,{mayClose=()=>true,maxOpen=8}={}){
    this.contract=contract;this.mayClose=mayClose;this.maxOpen=maxOpen;this.records=new Map();this.completed=[];
    this.counts={tabs_created:0,tabs_closed_during_run:0,tabs_closed_at_end:0,tabs_closed_explicitly:0,tabs_peak_owned:0};
  }
  track(driver,tab,owned=false){
    const id=String(tab.id);let record=this.records.get(id);
    if(!record){record={id,driver,tab,owned,guard:null,keep:null,edited:false,closed:false};this.records.set(id,record);
      if(owned){this.counts.tabs_created++;this.counts.tabs_peak_owned=Math.max(this.counts.tabs_peak_owned,this.openOwned().length);}}
    return record;
  }
  openOwned(){return [...this.records.values()].filter(r=>r.owned&&!r.closed);}
  beforeCreate(){if(this.interrupted)stop('CHROME_SESSION_INTERRUPTED');if(this.openOwned().length>=this.maxOpen)stop('CHROME_TASK_TAB_LIMIT');}
  observed(driver,tab,data){
    const record=this.track(driver,tab);record.guard=signature(data);record.url=data.url;
    if(data.controls.some(c=>c.password))record.keep='sensitive_control';
  }
  edited(tab){const r=this.records.get(String(tab.id));if(r)r.edited=true;}
  preserve(tab,reason){const r=this.records.get(String(tab.id));if(r)r.keep=reason;}
  closed(tab,kind){const r=this.records.get(String(tab.id));if(r&&!r.closed){r.closed=true;if(r.owned)this.counts[kind]++;}}
  stats(){return {...this.counts,tabs_retained:this.openOwned().length,tabs_cleanup_deferred:this.openOwned().filter(r=>r.defer).length};}
  summary(){return {...this.stats(),retained:this.openOwned().map(r=>({tab_id:r.id,reason:r.keep||(r.edited?'edited_form':r.defer||'still_needed')}))};}
  async handoffRetained(reason){
    if(this.interrupted||!this.mayClose(true)||/USER_|INTERRUPT|INFLIGHT|SESSION_DISCONNECTED/.test(reason||''))return;
    for(const r of this.openOwned()){
      if(r.hostMarked||r.keep==='deliverable'||r.keep==='handoff')continue;
      try{await r.tab.markHandoff();r.hostMarked=true;}catch{r.handoffUnavailable=true;}
    }
  }
  checkpoint(completed){
    const expected=this.contract.steps.slice(0,completed.length).map(s=>s.id);
    if(completed.length<this.completed.length||JSON.stringify(completed)!==JSON.stringify(expected))stop('CHROME_CHECKPOINT_INVALID');
    this.completed=[...completed];
  }
  needed(r,surfaces){
    const name=[...surfaces.drivers].find(([,d])=>d===r.driver)?.[0];
    const future=this.contract.steps.slice(this.completed.length);
    const steps=future.filter(s=>(s.surface||'main')===name);
    const finals=(this.contract.success||[]).filter(p=>(p.surface||'main')===name);
    const current=String(r.driver.tab.id)===r.id;
    if(current&&(steps.length||finals.length))return true;
    if(steps.some(s=>s.op==='close_tab'||(s.after||[]).some(p=>p.kind==='tab_count'))||finals.some(p=>p.kind==='tab_count'))return true;
    for(const s of steps.filter(s=>s.op==='switch_tab')){
      const input=this.contract.inputs?.[s.input_ref];
      if(!input||input.pending||input.captured||input.value===r.url)return true;
    }
    return finals.some(p=>p.kind==='url'&&(p.equals===r.url||this.contract.inputs?.[p.input_ref]?.value===r.url));
  }
  async sweep(surfaces,{terminal=false,reason=null}={}){
    if(this.interrupted)return this.summary();
    if(reason&&/USER_|INTERRUPT|INFLIGHT|PROTOCOL|WORKER_|SESSION_DISCONNECTED|SESSION_TIMEOUT/.test(reason)){
      for(const r of this.openOwned())r.defer='interrupted_or_uncertain';return this.summary();
    }
    for(const r of this.openOwned()){
      if(!this.mayClose(terminal)){r.defer='stop_or_cancel_active';break;}
      if(r.keep||r.edited||r.defer)continue;
      if(!terminal&&this.needed(r,surfaces))continue;
      if(!r.guard){r.defer='observation_unavailable';continue;}
      try{
        if(await r.tab.getJsDialog()){r.defer='dialog_open';continue;}
        // A separate observer avoids changing the active driver's controls or history.
        const observer=new r.driver.constructor(r.tab,r.driver.contract,r.driver.browser);
        const now=await observer.observe();
        if(signature(now)!==r.guard){r.keep='page_changed_or_user_takeover';continue;}
        if(!this.mayClose(terminal)){r.defer='stop_or_cancel_active';break;}
        await r.tab.close();
        this.closed(r.tab,terminal?'tabs_closed_at_end':'tabs_closed_during_run');
        r.driver.tabs.delete(r.id);
      }catch(error){
        r.defer='close_unavailable';
        // Never retry a close with an uncertain result, or continue after takeover.
        if(/interrupt|user.*control|user.*took|stopp?ed|session.*ended/i.test(String(error?.message||''))){this.interrupted=true;break;}
      }
    }
    return this.summary();
  }
}
