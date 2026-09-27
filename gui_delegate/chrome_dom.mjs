/** Fixed read-only observation code. It never evaluates caller/model strings. */
import {createHash} from 'node:crypto';
export function stop(reason){const e=new Error(reason);e.safeReason=reason;throw e;}
export const digest=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
export const quoted=value=>JSON.stringify(value);
export function readControls(root){
  // The host's read-only DOM may expose an empty value on every element and
  // omit isContentEditable. Read the declared/inherited HTML state first.
  const editable=el=>{
    for(let current=el;current;current=current.parentElement){
      const state=current.getAttribute?.('contenteditable')??null;
      if(state!==null){const value=state.toLowerCase();
        if(['','true','plaintext-only'].includes(value))return true;
        if(value==='false')return false;
      }
    }
    return el.isContentEditable===true;
  };
  const controlValue=el=>editable(el)?(el.innerText??el.textContent??'').replace(/\r\n?/g,'\n'):
    ['INPUT','TEXTAREA','SELECT'].includes(el.tagName)&&'value'in el?String(el.value):null;
  const doc=root?.ownerDocument||document;
  const neighborhood=el=>{
    let text='',parent=el.parentElement;
    for(let depth=0;parent&&depth<4;depth++,parent=parent.parentElement){
      if(/^(BODY|HTML|NAV|HEADER|FOOTER|FORM)$/.test(parent.tagName))break;
      if(parent.querySelector?.('input,textarea,[contenteditable="true"],[role="textbox"]'))break;
      const visible=(parent.innerText||'').trim().replace(/\s+/g,' ');
      if(visible.length>300||(parent.querySelectorAll?.('a,button,[role="button"]')?.length||0)>8)break;
      if(visible)text=visible;
    }
    return text;
  };
  // Anonymous frames are common on real sites. Derive a locator from the
  // observed DOM instead of requiring the site to assign an id/name/src.
  // A descendant boundary crosses an observed open shadow root; ordinary
  // light-DOM ancestors use direct-child segments.
  const framePath=el=>{
    let path='',current=el;
    while(current&&current.nodeType===1){
      const parent=current.parentElement,tree=current.getRootNode();
      let index=1;
      for(let sibling=current.previousElementSibling;sibling;sibling=sibling.previousElementSibling)
        if(sibling.tagName===current.tagName)index++;
      const part=current.tagName.toLowerCase()+':nth-of-type('+index+')';
      path=part+(path?' > '+path:'');
      if(parent){current=parent;continue;}
      if(tree.host){
        const inner=path;current=tree.host;path='';
        const outer=framePath(current);return outer?outer+' '+inner:'';
      }
      break;
    }
    return path;
  };
  const roots=[root||doc],elements=[];
  const selector='a,button,input,textarea,select,summary,h1,h2,h3,h4,h5,h6,[role],[aria-label],table,tr,td,th,iframe,canvas,video,img,[tabindex],[contenteditable]';
  let scanned=0;
  while(roots.length){
    const current=roots.shift();
    for(const el of current.querySelectorAll('*')){
      if(++scanned>30000)return {overflow:true,controls:[]};
      if(el.shadowRoot)roots.push(el.shadowRoot);
      if(!el.matches(selector))continue;
      const rect=el.getBoundingClientRect(),style=getComputedStyle(el);
      if(!rect.width||!rect.height||style.visibility==='hidden'||style.display==='none'||el.closest('[hidden],[inert],[aria-hidden="true"]'))continue;
      elements.push(el);
      if(elements.length>2400)return {overflow:true,controls:[]};
    }
  }
  const controls=elements.map(el=>{
    const tag=el.tagName.toLowerCase(),type=(el.getAttribute('type')||'').toLowerCase();
    let role=el.getAttribute('role')||({a:'link',button:'button',summary:'button',textarea:'textbox',select:'combobox',h1:'heading',h2:'heading',h3:'heading',h4:'heading',h5:'heading',h6:'heading',table:'table',tr:'row',td:'cell',th:'columnheader',iframe:'iframe',canvas:'canvas',video:'video',img:'image'})[tag];
    if(!role)role=tag==='input'?({search:'searchbox',checkbox:'checkbox',radio:'radio',range:'slider',file:'file',button:'button',submit:'button'})[type]||'textbox':editable(el)?'textbox':'generic';
    const refs=(el.getAttribute('aria-labelledby')||'').split(' ').filter(Boolean).map(id=>el.getRootNode().getElementById?.(id)?.textContent||'').join(' ');
    const name=el.getAttribute('aria-label')||refs||(el.labels&&Array.from(el.labels).map(x=>x.textContent).join(' '))||el.getAttribute('alt')||el.getAttribute('title')||el.getAttribute('placeholder')||(['input','textarea','select'].includes(tag)?'':el.innerText||el.textContent)||'';
    const rect=el.getBoundingClientRect(),style=getComputedStyle(el);
    const password=type==='password'||/one-time-code|current-password|new-password/.test(el.getAttribute('autocomplete')||'');
    const container=el.closest('article,section,li,tr,[role=group],[role=dialog],[role=region],[role=listitem]');
    const heading=container?.querySelector?.('h1,h2,h3,h4,h5,h6,[role=heading],legend');
    const landmark=el.closest('nav,[role=navigation],header,footer,aside,[role=menu]');
    const context=(container?.getAttribute('aria-label')||heading?.textContent||landmark?.getAttribute('aria-label')||'').trim().slice(0,160);
    const formContext=el.form?[el.form.getAttribute('role'),el.form.getAttribute('aria-label'),el.form.getAttribute('id'),el.form.getAttribute('class')].filter(Boolean).join(' ').slice(0,300):'';
    const searchLike=/(^|[\s_-])search(?:form|box)?([\s_-]|$)/i.test(formContext)||type==='search'||role==='searchbox'||!!el.closest('[role=search]')||/^(q|query|keyword|search|search_query)$/i.test(el.getAttribute('name')||'')||/(^|[-_])(search|query)([-_]|$)/i.test(el.id||'')||/search|搜索|搜尋|検索/i.test(name);
    const publicSearch=['textbox','searchbox'].includes(role)&&searchLike&&(!el.form||((el.form.getAttribute('method')||'get').toLowerCase()==='get'&&!el.form.querySelector('input[type=password]')));
    return {role,name:name.trim().slice(0,300),automation_id:el.id||'',
      enabled:!el.disabled&&el.getAttribute('aria-disabled')!=='true',visible:!!(rect.width&&rect.height)&&style.visibility!=='hidden'&&style.display!=='none',password,
      value:password?null:controlValue(el),
      checked:'checked'in el?el.checked:(el.hasAttribute('aria-checked')?el.getAttribute('aria-checked')==='true':null),
      attributes:{tag,type,group:el.closest('[role=group]')?.getAttribute('aria-label')||'',
        dom_path:framePath(el),context,neighborhood:role==='link'?neighborhood(el):'',readonly:String(!!el.readOnly),selected:el.getAttribute('aria-selected')||'',expanded:el.getAttribute('aria-expanded')||'',
        public_search:String(publicSearch),form_action:el.form?.action||'',form_context:formContext,
        submit:String(!!el.form&&(type==='submit'||(tag==='button'&&!el.hasAttribute('type')))),href:el.href||'',
        text:password?'':(el.innerText||el.textContent||'').trim().slice(0,1000),
        src:tag==='iframe'?el.src||'':'',srcdoc:String(tag==='iframe'&&el.hasAttribute('srcdoc')),
        ...(tag==='iframe'?{raw_src:el.getAttribute('src')||'',frame_path:framePath(el)}:{}),
        name_attr:el.getAttribute('name')||'',download:el.getAttribute('download')||'',target:el.getAttribute('target')||'',
        min:el.getAttribute('min')||'0',max:el.getAttribute('max')||'100',step:el.getAttribute('step')||'1',
        files:type==='file'?JSON.stringify(Array.from(el.files||[]).map(x=>({name:x.name,size:x.size}))):'',
        scrollTop:String(el.scrollTop),scrollLeft:String(el.scrollLeft),scrollHeight:String(el.scrollHeight),
        clientHeight:String(el.clientHeight),contenteditable:String(editable(el))}};
  });
  return {overflow:false,controls,url:doc.URL};
}

export function probe(el){
  // The host's read-only DOM may expose an empty value on every element and
  // omit isContentEditable. Read the declared/inherited HTML state first.
  const editable=el=>{
    for(let current=el;current;current=current.parentElement){
      const state=current.getAttribute?.('contenteditable')??null;
      if(state!==null){const value=state.toLowerCase();
        if(['','true','plaintext-only'].includes(value))return true;
        if(value==='false')return false;
      }
    }
    return el.isContentEditable===true;
  };
  const controlValue=el=>editable(el)?(el.innerText??el.textContent??'').replace(/\r\n?/g,'\n'):
    ['INPUT','TEXTAREA','SELECT'].includes(el.tagName)&&'value'in el?String(el.value):null;
  const neighborhood=el=>{
    let text='',parent=el.parentElement;
    for(let depth=0;parent&&depth<4;depth++,parent=parent.parentElement){
      if(/^(BODY|HTML|NAV|HEADER|FOOTER|FORM)$/.test(parent.tagName))break;
      if(parent.querySelector?.('input,textarea,[contenteditable="true"],[role="textbox"]'))break;
      const visible=(parent.innerText||'').trim().replace(/\s+/g,' ');
      if(visible.length>300||(parent.querySelectorAll?.('a,button,[role="button"]')?.length||0)>8)break;
      if(visible)text=visible;
    }
    return text;
  };
  const tag=el.tagName.toLowerCase(),type=(el.getAttribute('type')||'').toLowerCase();
  const refs=(el.getAttribute('aria-labelledby')||'').split(' ').filter(Boolean).map(id=>el.getRootNode().getElementById?.(id)?.textContent||'').join(' ');
  const name=el.getAttribute('aria-label')||refs||(el.labels&&Array.from(el.labels).map(x=>x.textContent).join(' '))||el.getAttribute('alt')||el.getAttribute('title')||el.getAttribute('placeholder')||(['input','textarea','select'].includes(tag)?'':el.innerText||el.textContent)||'';
  let role=el.getAttribute('role')||({a:'link',button:'button',summary:'button',textarea:'textbox',select:'combobox',h1:'heading',h2:'heading',h3:'heading',h4:'heading',h5:'heading',h6:'heading',table:'table',tr:'row',td:'cell',th:'columnheader',iframe:'iframe',canvas:'canvas',video:'video',img:'image'})[tag];
  if(!role)role=tag==='input'?({search:'searchbox',checkbox:'checkbox',radio:'radio',range:'slider',file:'file',button:'button',submit:'button'})[type]||'textbox':editable(el)?'textbox':'generic';
  const container=el.closest('article,section,li,tr,[role=group],[role=dialog],[role=region],[role=listitem]');
  const heading=container?.querySelector?.('h1,h2,h3,h4,h5,h6,[role=heading],legend');
  const landmark=el.closest('nav,[role=navigation],header,footer,aside,[role=menu]');
  const context=(container?.getAttribute('aria-label')||heading?.textContent||landmark?.getAttribute('aria-label')||'').trim().slice(0,160);
  return {tag,id:el.id||'',type,role,name:name.trim().slice(0,300),context,neighborhood:role==='link'?neighborhood(el):'',
    password:(el.getAttribute('type')||'').toLowerCase()==='password'||/one-time-code|current-password|new-password/.test(el.getAttribute('autocomplete')||''),
    href:el.href||'',submit:String(!!el.form&&((el.getAttribute('type')||'').toLowerCase()==='submit'||(el.tagName.toLowerCase()==='button'&&!el.hasAttribute('type')))),
    value:controlValue(el),
    checked:'checked'in el?el.checked:(el.hasAttribute('aria-checked')?el.getAttribute('aria-checked')==='true':null)};
}

export function geometry(el){
  const r=el.getBoundingClientRect(),w=el.ownerDocument.defaultView;
  const x=r.x+r.width/2,y=r.y+r.height/2,top=el.getRootNode().elementFromPoint(x,y);
  return {x,y,width:r.width,height:r.height,viewportWidth:w.innerWidth,viewportHeight:w.innerHeight,
    scale:w.visualViewport?.scale||1,ratio:w.devicePixelRatio,occluded:!(top===el||el.contains(top)),
    visible:x>=0&&y>=0&&x<w.innerWidth&&y<w.innerHeight};
}

export function frameSelectors(c){
  const selectors=[];
  if(c.automation_id)selectors.push('iframe[id='+quoted(c.automation_id)+']');
  if(c.attributes.name_attr)selectors.push('iframe[name='+quoted(c.attributes.name_attr)+']');
  const src=c.attributes.raw_src??c.attributes.src;
  if(src)selectors.push('iframe[src='+quoted(src)+']');
  if(c.attributes.frame_path)selectors.push(c.attributes.frame_path);
  if(!selectors.length)stop('CHROME_FRAME_IDENTITY_UNAVAILABLE');
  return [...new Set(selectors)];
}

export function frameIdentity(el){
  return {id:el.id||'',name:el.getAttribute('name')||'',
    src:el.getAttribute('src')||'',srcdoc:String(el.hasAttribute('srcdoc'))};
}
