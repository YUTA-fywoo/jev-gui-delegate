/** Public page payload and bounded DOM settling, adapted from
 * jkudish/jev-browser src/navigate.ts (MIT). See vendor provenance.
 * Browser access stays on the official Codex API; all page evaluation is read-only.
 */
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));

export function documentState(){
  return {ready:document.readyState,url:document.URL,title:document.title,
    length:document.body?.innerText?.length||0,
    controls:document.querySelectorAll('a,button,input,select,textarea').length};
}

export async function settle(tab,{maxMs=4000}={}){
  const deadline=Date.now()+maxMs;let previous=null,stable=0;
  while(Date.now()<deadline){
    const state=await tab.playwright.evaluate(documentState);
    const fingerprint=JSON.stringify(state);
    stable=fingerprint===previous?stable+1:0;previous=fingerprint;
    if(state.ready!=='loading'&&state.length>0&&stable>=1)return;
    await pause(250);
  }
}

export function publicPagePayload(){
  let content=document.body?.innerText||'';
  // Native time elements and custom relative-time components can render their
  // text in shadow DOM. Their visible host's datetime is public page evidence.
  const times=[];
  for(const el of document.querySelectorAll?.('[datetime]')||[]){
    const box=el.getBoundingClientRect(),style=getComputedStyle(el);
    if(!box.width||!box.height||style.display==='none'||style.visibility==='hidden'||el.closest('[hidden],[inert],[aria-hidden="true"]'))continue;
    const datetime=el.getAttribute('datetime')||'';
    if(!/^\d{4}-\d{2}-\d{2}(?:T[0-9:.+Z-]+)?$/.test(datetime))continue;
    const context=(el.parentElement?.innerText||el.getAttribute('title')||el.innerText||'').trim().replace(/\s+/g,' ').slice(0,240);
    times.push('[datetime '+datetime+'] '+context);
  }
  if(times.length)content+='\n\n'+[...new Set(times)].join('\n');
  const maxChars=16000;
  return {url:document.URL,title:document.title,format:'text',
    content:content.slice(0,maxChars),true_length:content.length,
    truncated:content.length>maxChars};
}

export async function capturePublicPage(tab,origins){
  await settle(tab);
  const before=await tab.url();
  if(!origins.includes(new URL(before).origin))throw new Error('PAGE_ORIGIN_CHANGED');
  const page=await tab.playwright.evaluate(publicPagePayload);
  if(page.url!==before||await tab.url()!==before)throw new Error('PAGE_CHANGED_DURING_CAPTURE');
  return {...page,tab_id:String(tab.id)};
}
