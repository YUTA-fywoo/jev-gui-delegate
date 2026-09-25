/** Fixed read-only observation code. It never evaluates caller/model strings. */
import {createHash} from 'node:crypto';
export function stop(reason){const e=new Error(reason);e.safeReason=reason;throw e;}
export const digest=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
export const quoted=value=>JSON.stringify(value);
export function readControls(root){
  const doc=root?.ownerDocument||document;
  const roots=[root||doc],elements=[];
  const selector='a,button,input,textarea,select,summary,[role],[aria-label],table,tr,td,th,iframe,canvas,video,img,[tabindex],[contenteditable]';
  while(roots.length){
    const current=roots.shift();
    for(const el of current.querySelectorAll('*')){
      if(el.shadowRoot)roots.push(el.shadowRoot);
      if(el.matches(selector))elements.push(el);
      if(elements.length>600)return {overflow:true,controls:[]};
    }
  }
  const controls=elements.map(el=>{
    const tag=el.tagName.toLowerCase(),type=(el.getAttribute('type')||'').toLowerCase();
    let role=el.getAttribute('role')||({a:'link',button:'button',summary:'button',textarea:'textbox',select:'combobox',table:'table',tr:'row',td:'cell',th:'columnheader',iframe:'iframe',canvas:'canvas',video:'video',img:'image'})[tag];
    if(!role)role=tag==='input'?({checkbox:'checkbox',radio:'radio',range:'slider',file:'file',button:'button',submit:'button'})[type]||'textbox':el.isContentEditable?'textbox':'generic';
    const refs=(el.getAttribute('aria-labelledby')||'').split(' ').filter(Boolean).map(id=>el.getRootNode().getElementById?.(id)?.textContent||'').join(' ');
    const name=el.getAttribute('aria-label')||refs||(el.labels&&Array.from(el.labels).map(x=>x.textContent).join(' '))||el.getAttribute('alt')||el.getAttribute('title')||(['input','textarea','select'].includes(tag)?'':el.innerText||el.textContent)||'';
    const rect=el.getBoundingClientRect(),style=getComputedStyle(el);
    const password=type==='password'||/one-time-code|current-password|new-password/.test(el.getAttribute('autocomplete')||'');
    return {role,name:name.trim().slice(0,300),automation_id:el.id||'',
      enabled:!el.disabled&&el.getAttribute('aria-disabled')!=='true',visible:!!(rect.width&&rect.height)&&style.visibility!=='hidden'&&style.display!=='none',password,
      value:password?null:('value'in el?String(el.value):el.isContentEditable?el.textContent:null),
      checked:'checked'in el?el.checked:(el.hasAttribute('aria-checked')?el.getAttribute('aria-checked')==='true':null),
      attributes:{tag,type,group:el.closest('[role=group]')?.getAttribute('aria-label')||'',
        submit:String(!!el.form&&(type==='submit'||(tag==='button'&&!el.hasAttribute('type')))),href:el.href||'',
        text:password?'':(el.innerText||el.textContent||'').trim().slice(0,1000),
        src:tag==='iframe'?el.src||'':'',srcdoc:String(tag==='iframe'&&el.hasAttribute('srcdoc')),
        name_attr:el.getAttribute('name')||'',download:el.getAttribute('download')||'',target:el.getAttribute('target')||'',
        min:el.getAttribute('min')||'0',max:el.getAttribute('max')||'100',step:el.getAttribute('step')||'1',
        files:type==='file'?JSON.stringify(Array.from(el.files||[]).map(x=>({name:x.name,size:x.size}))):'',
        scrollTop:String(el.scrollTop),scrollLeft:String(el.scrollLeft),scrollHeight:String(el.scrollHeight),
        clientHeight:String(el.clientHeight),contenteditable:String(el.isContentEditable)}};
  });
  return {overflow:false,controls,url:doc.URL};
}

export function probe(el){
  const tag=el.tagName.toLowerCase(),type=(el.getAttribute('type')||'').toLowerCase();
  const refs=(el.getAttribute('aria-labelledby')||'').split(' ').filter(Boolean).map(id=>el.getRootNode().getElementById?.(id)?.textContent||'').join(' ');
  const name=el.getAttribute('aria-label')||refs||(el.labels&&Array.from(el.labels).map(x=>x.textContent).join(' '))||el.getAttribute('alt')||el.getAttribute('title')||(['input','textarea','select'].includes(tag)?'':el.innerText||el.textContent)||'';
  let role=el.getAttribute('role')||({a:'link',button:'button',summary:'button',textarea:'textbox',select:'combobox',table:'table',tr:'row',td:'cell',th:'columnheader',iframe:'iframe',canvas:'canvas',video:'video',img:'image'})[tag];
  if(!role)role=tag==='input'?({checkbox:'checkbox',radio:'radio',range:'slider',file:'file',button:'button',submit:'button'})[type]||'textbox':el.isContentEditable?'textbox':'generic';
  return {tag,id:el.id||'',type,role,name:name.trim().slice(0,300),
    password:(el.getAttribute('type')||'').toLowerCase()==='password'||/one-time-code|current-password|new-password/.test(el.getAttribute('autocomplete')||''),
    href:el.href||'',submit:String(!!el.form&&((el.getAttribute('type')||'').toLowerCase()==='submit'||(el.tagName.toLowerCase()==='button'&&!el.hasAttribute('type')))),
    value:'value'in el?String(el.value):el.isContentEditable?el.textContent:null,
    checked:'checked'in el?el.checked:(el.hasAttribute('aria-checked')?el.getAttribute('aria-checked')==='true':null)};
}

export function geometry(el){
  const r=el.getBoundingClientRect(),w=el.ownerDocument.defaultView;
  const x=r.x+r.width/2,y=r.y+r.height/2,top=el.getRootNode().elementFromPoint(x,y);
  return {x,y,width:r.width,height:r.height,viewportWidth:w.innerWidth,viewportHeight:w.innerHeight,
    scale:w.visualViewport?.scale||1,ratio:w.devicePixelRatio,occluded:!(top===el||el.contains(top)),
    visible:x>=0&&y>=0&&x<w.innerWidth&&y<w.innerHeight};
}

export function frameSelector(c){
  if(c.automation_id)return 'iframe[id='+quoted(c.automation_id)+']';
  if(c.attributes.name_attr)return 'iframe[name='+quoted(c.attributes.name_attr)+']';
  if(c.attributes.src)return 'iframe[src='+quoted(c.attributes.src)+']';
  stop('CHROME_FRAME_IDENTITY_UNAVAILABLE');
}
