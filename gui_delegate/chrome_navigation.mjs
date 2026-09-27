/** Follow the new page opened by a navigation action, as in jkudish/jev-browser.
 * The official host has no popup event. Reconcile fresh tab metadata instead;
 * never adopt a pre-existing tab, and never infer ownership or close a claimed tab.
 */
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function urlConditions(raw,contract){
  let url;try{url=new URL(raw);}catch{return false;}
  const conditions=(contract.success||[]).filter(p=>['url','url_path','url_path_prefix','url_query'].includes(p.kind));
  if(!conditions.length)return false;
  return conditions.every(p=>{
    const expected=p.input_ref?contract.inputs?.[p.input_ref]?.value:p.equals;
    if(p.kind==='url')return raw===expected;
    if(p.kind==='url_path')return url.pathname===expected;
    if(p.kind==='url_path_prefix'){
      const prefix=expected.replace(/\/+$/,'')+'/';
      return url.pathname.startsWith(prefix)&&url.pathname.length>prefix.length;
    }
    const values=url.searchParams.getAll(p.parameter);
    if(values.length!==1)return false;
    if(values[0]===expected)return true;
    try{return decodeURIComponent(values[0])===expected;}catch{return false;}
  });
}
export function newDestination(tab,before,contract,href,searchValue){
  if(before.has(String(tab.id)))return false;
  let url;try{url=new URL(tab.url);}catch{return false;}
  if(!contract.scope.origins.includes(url.origin)||url.username||url.password)return false;
  if(href){
    const observed=new URL(href);
    // Extra site-added tracking is harmless; every observed query parameter
    // must still match so a different ?id= or search term cannot be substituted.
    if(url.origin===observed.origin&&url.pathname===observed.pathname&&
      [...observed.searchParams.keys()].every(key=>JSON.stringify(url.searchParams.getAll(key))===JSON.stringify(observed.searchParams.getAll(key))))return true;
  }
  // A search can be an intermediate step in a larger goal whose final success
  // predicates describe a detail page. Match the actual verified search text,
  // not only final URL predicates, and reject duplicated query parameters.
  if(typeof searchValue==='string'&&searchValue.trim()){
    for(const key of url.searchParams.keys()){
      const values=url.searchParams.getAll(key);
      if(values.length!==1)continue;
      if(values[0]===searchValue)return true;
      try{if(decodeURIComponent(values[0])===searchValue)return true;}catch{}
    }
  }
  return urlConditions(tab.url,contract);
}
export async function watchNavigation(driver,control,operation,value){
  if(driver.contract.observation_policy!=='public_ui'||!driver.browser?.user?.openTabs)return null;
  const link=operation==='click'&&control.role==='link'&&control.attributes.target==='_blank'&&control.attributes.href;
  const search=operation==='key'&&value==='Enter'&&control.attributes.public_search==='true';
  if(!link&&!search)return null;
  return {before:new Set((await driver.browser.user.openTabs()).map(t=>String(t.id))),source:await driver.tab.url(),href:link||null,
    searchValue:search&&typeof control.value==='string'?control.value:null};
}
export async function followNavigation(driver,watch,{maxMs=4000}={}){
  if(!watch)return false;
  const deadline=Date.now()+maxMs;
  do{
    // A click may update tracking parameters on its source AND open a result.
    // Match the new result first, as the upstream pendingPage flow does.
    const candidates=(await driver.browser.user.openTabs()).filter(t=>newDestination(t,watch.before,driver.contract,watch.href,watch.searchValue));
    if(candidates.length>1){const error=new Error('CHROME_TAB_NOT_UNIQUE');error.safeReason=error.message;throw error;}
    if(candidates.length===1){
      const metadata=candidates[0];
      const tab=await driver.browser.user.claimTab(metadata);
      if(String(tab.id)!==String(metadata.id)||await tab.url()!==metadata.url){const error=new Error('CHROME_PAGE_CHANGED');error.safeReason=error.message;throw error;}
      // Fresh observed metadata identifies the destination but does not prove
      // ownership. Preserve this tab instead of claiming the right to close it.
      driver.tabs.set(String(tab.id),{tab,owned:false});driver.lifecycle?.track(driver,tab,false);
      driver.tab=tab;driver.history=[];driver.historyIndex=-1;
      return true;
    }
    const current=await driver.tab.url();
    if(current!==watch.source&&newDestination({id:'current-page',url:current},new Set(),driver.contract,watch.href,watch.searchValue))return false;
    if(Date.now()>=deadline)return false;
    await pause(250);
  }while(true);
}
