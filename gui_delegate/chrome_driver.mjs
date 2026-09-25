/** Whitelisted task operations over the installed official Chrome APIs. */
import path from 'node:path';
import {TaskTabs} from './chrome_tabs.mjs';
import {readControls,probe,geometry,frameSelector,quoted,digest,stop} from './chrome_dom.mjs';
const {permittedFile,writeArtifact,copyArtifact,writeScreenshot}=await import(new URL('./chrome_artifacts.mjs',import.meta.url).href+'?rev=2');

export const OPERATIONS=new Set(['read','wait','copy','click','fill','check','uncheck','select','context_click','key','paste','double_click','hover','scroll','range','drag','upload','download','switch_tab','close_tab','navigate','new_tab','back','forward','reload','screenshot','export','logs','assets','dialog_accept','dialog_dismiss','clipboard_write','clipboard_read','mark_deliverable','mark_handoff','viewport_set','viewport_reset']);
const KEYS=new Set(['Tab','Escape','ArrowDown','ArrowUp','ArrowLeft','ArrowRight','Home','End','PageDown','PageUp','Enter','Space','Control+A']);
const PAGE_OPS=new Set(['switch_tab','close_tab','navigate','new_tab','back','forward','reload','screenshot','export','logs','assets','dialog_accept','dialog_dismiss','clipboard_write','clipboard_read','mark_deliverable','mark_handoff','viewport_set','viewport_reset']);

export class OfficialTabDriver{
  constructor(tab,contract,browser=null,lifecycle=null,owned=false){this.tab=tab;this.contract=contract;this.browser=browser;this.lifecycle=lifecycle;this.bindings=new Map();this.bound=false;this.tabs=new Map([[String(tab.id),{tab,owned}]]);this.history=[];this.historyIndex=-1;this.frames=new Map();this.receipts=new Map();lifecycle?.track(this,tab,owned);}
  async capability(id){const cap=await this.tab.capabilities.get(id);await cap.documentation();if(id==='cdp')return {send:(method,params)=>cap.send(method,params,{timeoutMs:3500})};return cap;}
  checkUrl(raw){
    let url;try{url=new URL(raw);}catch{stop('CHROME_PAGE_CHANGED');}
    if(!['http:','https:'].includes(url.protocol)||url.username||url.password||!this.contract.scope.origins.includes(url.origin))stop('CHROME_ORIGIN_DENIED');return raw;
  }
  async location(){const url=this.checkUrl(await this.tab.url());this.lastUrl=url;return url;}
  source(framePath){let source=this.tab.playwright;for(const selector of framePath)source=source.frameLocator(selector);return source;}
  locator(c){
    const source=this.source(c._framePath||[]);
    if(c.automation_id)return source.locator('[id='+quoted(c.automation_id)+']');
    return source.getByRole(c.role,{name:c.name,exact:true});
  }
  async fresh(c){
    if(!c||c._pageUrl!==await this.location())stop('CHROME_CONTROL_STALE');
    if(c.password)stop('CHROME_PASSWORD_CONTROL');
    if(!c.enabled||!c.visible)stop('CHROME_ELEMENT_NOT_ACTIONABLE');
    for(const frame of c._frames||[]){
      const loc=this.source(frame.parents).locator(frame.selector);
      if(await loc.count()!==1||await loc.getAttribute('src')!==frame.rawSrc)stop('CHROME_FRAME_CHANGED');
    }
    const loc=this.locator(c);
    if(await loc.count()!==1)stop('CHROME_AMBIGUOUS_CONTROL');
    const check=await loc.evaluate(probe);
    if(check.password)stop('CHROME_PASSWORD_CONTROL');
    if(check.role!==c.role||check.name!==c.name)stop('CHROME_CONTROL_STALE');
    if(check.tag!==c.attributes.tag||check.id!==c.automation_id||check.type!==c.attributes.type||check.value!==c.value||check.checked!==c.checked||check.href!==c.attributes.href||check.submit!==c.attributes.submit)stop('CHROME_CONTROL_STALE');
    if(!await loc.isVisible()||!await loc.isEnabled())stop('CHROME_ELEMENT_NOT_ACTIONABLE');
    return loc;
  }
  async point(c,loc){
    if((c._framePath||[]).length)stop('CHROME_FRAME_COORDINATES_REQUIRE_ASTRA');
    const a=await loc.evaluate(geometry),b=await loc.evaluate(geometry);
    if(JSON.stringify(a)!==JSON.stringify(b)||a.scale!==1||!a.visible||a.occluded||a.width<=0||a.height<=0)stop('CHROME_GEOMETRY_UNSAFE');
    return {x:a.x,y:a.y};
  }
  async observe(){
    const dialog=await this.tab.getJsDialog(),url=dialog?this.lastUrl:await this.location();
    if(this.history[this.historyIndex]!==url){this.history=this.history.slice(0,this.historyIndex+1);this.history.push(url);this.historyIndex++;}
    this.bindings.clear();this.frames.clear();
    const controls=[];
    if(dialog){
      controls.push({id:'official-dialog:'+dialog.type,role:'dialog',name:dialog.type,automation_id:'',frame_url:url,enabled:true,visible:true,password:false,value:null,checked:null,attributes:{text:dialog.type}});
    }else{
      const queue=[{path:[],frames:[],url}],count=new Map();
      while(queue.length){
        const frame=queue.shift();
        const source=this.source(frame.path);
        const data=frame.path.length?await source.locator('html').evaluate(readControls):await this.tab.playwright.evaluate(readControls);
        if(data.overflow||controls.length+data.controls.length>600)stop('CHROME_STATE_TOO_LARGE');
        let frameUrl=data.url||frame.url;
        if(frameUrl==='about:srcdoc'||frameUrl==='about:blank')frameUrl=frame.url;else this.checkUrl(frameUrl);
        for(const raw of data.controls){
          const key=digest([url,frame.path,frameUrl,raw.role,raw.name,raw.automation_id,raw.attributes.tag,raw.attributes.type]);
          const occurrence=count.get(key)||0;count.set(key,occurrence+1);
          const c={...raw,id:key+':'+occurrence,frame_url:frameUrl};
          this.bindings.set(c.id,{...c,_framePath:frame.path,_frames:frame.frames,_pageUrl:url});controls.push(c);
          if(raw.role==='iframe'&&raw.visible){
            if(frame.path.length>=4)stop('CHROME_FRAME_DEPTH_LIMIT');
            const nextUrl=raw.attributes.srcdoc==='true'||!raw.attributes.src?frameUrl:this.checkUrl(raw.attributes.src);
            const selector=frameSelector(raw),frameLoc=source.locator(selector);
            if(await frameLoc.count()!==1)stop('CHROME_FRAME_IDENTITY_UNAVAILABLE');
            queue.push({path:[...frame.path,selector],frames:[...frame.frames,{parents:frame.path,selector,rawSrc:await frameLoc.getAttribute('src')}],url:nextUrl});
          }
        }
      }
    }
    this.lifecycle?.observed(this,this.tab,{url,controls});
    for(const [name,value] of this.receipts)controls.push({id:'receipt:'+name,role:'status',name:'Jev artifact '+name,automation_id:'',frame_url:url,enabled:true,visible:true,password:false,value:null,checked:null,attributes:{text:JSON.stringify(value)}});
    return {url,controls,tab_count:this.tabs.size};
  }
  async dispatch(method,payload){
    if(method==='bind'){
      if(this.bound||payload.tab_id!==String(this.tab.id)||payload.tab_id!==this.contract.target.tab_id||payload.url!==this.contract.target.url||JSON.stringify(payload.origins)!==JSON.stringify(this.contract.scope.origins))stop('CHROME_IDENTITY_MISMATCH');
      if(await this.location()!==payload.url)stop('CHROME_PAGE_CHANGED');this.bound=true;return {bound:true,lifecycle_checkpoints:!!this.lifecycle};
    }
    if(!this.bound)stop('CHROME_IDENTITY_MISMATCH');
    if(method==='observe')return await this.observe();
    if(method!=='act'||!OPERATIONS.has(payload.operation)||!this.contract.scope.actions.includes(payload.operation))stop('CHROME_UNSUPPORTED_ACTION');
    const op=payload.operation,value=payload.value,options=payload.options||{};
    if(['fill','paste','select','check','uncheck','range','upload','key'].includes(op))this.lifecycle?.edited(this.tab);
    if(PAGE_OPS.has(op))return await this.pageAction(op,value,options,payload);
    if(await this.tab.getJsDialog())stop('CHROME_DIALOG_REQUIRES_REVIEW');
    const url=await this.location();
    const c=this.bindings.get(payload.control_id),loc=await this.fresh(c);
    if(await this.location()!==url)stop('CHROME_PAGE_CHANGED');
    if(['fill','paste','select','key','range','upload','download'].includes(op)&&typeof value!=='string')stop('CHROME_INPUT_NOT_ALLOWED');
    if(['fill','paste'].includes(op)){
      if(c.role!=='textbox')stop('CHROME_UNSUPPORTED_ACTION');await loc.fill(value,{timeoutMs:3500});
    }else if(['click','context_click','double_click'].includes(op)){
      if(c.attributes.href)this.checkUrl(c.attributes.href);
      try{if(op==='double_click')await loc.dblclick({timeoutMs:3500});else await loc.click({button:op==='context_click'?'right':'left',timeoutMs:3500});}
      catch(error){
        // A modal can cause the official mouse call to time out after it has
        // actually fired. Never click again: the controller checks fresh dialog
        // state against the original postcondition before accepting success.
        if(!await this.tab.getJsDialog())throw error;
      }
    }else if(op==='check'||op==='uncheck'){
      if(!['checkbox','switch'].includes(c.role))stop('CHROME_UNSUPPORTED_ACTION');await loc.setChecked(op==='check',{timeoutMs:3500});
    }else if(op==='select'){
      if(c.attributes.tag!=='select')stop('CHROME_UNSUPPORTED_ACTION');await loc.selectOption({label:value},{timeoutMs:3500});
    }else if(op==='key'){
      if(!KEYS.has(value))stop('CHROME_INPUT_NOT_ALLOWED');await loc.press(value,{timeoutMs:3500});
    }else if(op==='range'){
      const n=Number(value),min=Number(c.attributes.min),max=Number(c.attributes.max),delta=Number(c.attributes.step),steps=Math.round((n-min)/delta);
      if(c.attributes.type!=='range'||!Number.isFinite(n)||!Number.isFinite(delta)||delta<=0||n<min||n>max||Math.abs(min+steps*delta-n)>1e-8||steps>100)stop('CHROME_RANGE_DENIED');
      await loc.press('Home',{timeoutMs:3500});for(let i=0;i<steps;i++)await loc.press('ArrowRight',{timeoutMs:3500});
      if((await loc.evaluate(probe)).value!==value)stop('CHROME_RANGE_UNVERIFIED');
    }else if(op==='scroll'||op==='hover'){
      const point=await this.point(c,loc);
      if(op==='hover'){
        const cdp=await this.capability('cdp');
        await cdp.send('Input.dispatchMouseEvent',{type:'mouseMoved',x:point.x,y:point.y});
      }else{
        const cdp=await this.capability('cdp');
        await cdp.send('Input.dispatchMouseEvent',{type:'mouseWheel',x:point.x,y:point.y,deltaX:options.scroll_x??0,deltaY:options.scroll_y??400});
      }
    }else if(op==='drag'){
      const destination=this.bindings.get(payload.destination_control_id),destLoc=await this.fresh(destination);
      const a=await this.point(c,loc),b=await this.point(destination,destLoc);
      const cdp=await this.capability('cdp');
      await cdp.send('Input.dispatchMouseEvent',{type:'mouseMoved',x:a.x,y:a.y});
      await cdp.send('Input.dispatchMouseEvent',{type:'mousePressed',x:a.x,y:a.y,button:'left',buttons:1,clickCount:1});
      try{for(let i=1;i<=12;i++)await cdp.send('Input.dispatchMouseEvent',{type:'mouseMoved',x:a.x+(b.x-a.x)*i/12,y:a.y+(b.y-a.y)*i/12,button:'left',buttons:1});}
      finally{await cdp.send('Input.dispatchMouseEvent',{type:'mouseReleased',x:b.x,y:b.y,button:'left',buttons:0,clickCount:1});}
    }else if(op==='upload'){
      const files=[value,...(options.upload_files||[])].map(file=>permittedFile(file,this.contract.scope.read_roots,{exists:true}));
      if(files.length>20)stop('CHROME_INPUT_NOT_ALLOWED');
      const pending=this.tab.playwright.waitForEvent('filechooser',{timeoutMs:8000});pending.catch(()=>{});
      await loc.click({timeoutMs:3500});const chooser=await pending;
      if(files.length>1&&!chooser.isMultiple())stop('CHROME_UPLOAD_MULTIPLE_NOT_SUPPORTED');
      try{await chooser.setFiles(files,{timeoutMs:8000});}catch{stop('CHROME_UPLOAD_FILE_ACCESS_REQUIRED');}
    }else if(op==='download'){
      permittedFile(value,this.contract.scope.write_roots,{write:true});
      if(c.attributes.href)this.checkUrl(c.attributes.href);
      if(!options.expected_download_name||!options.download_directory)stop('CHROME_DOWNLOAD_DESTINATION_REQUIRED');
      if(c.attributes.download&&c.attributes.download!==options.expected_download_name)stop('CHROME_DOWNLOAD_NAME_CHANGED');
      const pending=this.tab.playwright.waitForEvent('download',{timeoutMs:8000});pending.catch(()=>{});
      await loc.click({timeoutMs:3500});await pending;
      return {dispatched:true,download_triggered:true};
    }else stop('CHROME_UNSUPPORTED_ACTION');
    return {dispatched:true};
  }
  async pageAction(op,value,options,payload){
    const dialog=await this.tab.getJsDialog(),url=dialog?this.lastUrl:await this.location();
    if(dialog&&!['dialog_accept','dialog_dismiss','screenshot'].includes(op))stop('CHROME_DIALOG_REQUIRES_REVIEW');
    let receipt;
    if(op==='navigate'){
      this.checkUrl(value);if(url!==value)await this.tab.goto(value);
      if(await this.location()!==value)stop('CHROME_NAVIGATION_UNVERIFIED');
    }else if(op==='new_tab'){
      this.checkUrl(value);if(!this.browser)stop('CHROME_BROWSER_BINDING_REQUIRED');
      this.lifecycle?.beforeCreate();const tab=await this.browser.tabs.new();this.tabs.set(String(tab.id),{tab,owned:true});this.lifecycle?.track(this,tab,true);await tab.goto(value);this.tab=tab;this.history=[];this.historyIndex=-1;
      if(await this.location()!==value)stop('CHROME_NAVIGATION_UNVERIFIED');
    }else if(op==='switch_tab'){
      const matches=[];for(const entry of this.tabs.values())if(await entry.tab.url()===value)matches.push(entry.tab);
      if(matches.length!==1)stop('CHROME_TAB_NOT_UNIQUE');this.tab=matches[0];this.history=[];this.historyIndex=-1;
    }else if(op==='close_tab'){
      if(this.tabs.size<2)stop('CHROME_LAST_TAB_CLOSE_REQUIRES_ASTRA');
      const item=this.tabs.get(String(this.tab.id));if(!item?.owned&&!options.allow_close_existing)stop('CHROME_EXISTING_TAB_CLOSE_REQUIRES_CONFIRMATION');
      const id=String(this.tab.id);await this.tab.close();this.lifecycle?.closed(this.tab,'tabs_closed_explicitly');this.tabs.delete(id);this.tab=this.tabs.values().next().value.tab;this.history=[];this.historyIndex=-1;
    }else if(op==='back'||op==='forward'){
      const n=this.historyIndex+(op==='back'?-1:1),target=this.history[n];
      if(!target)stop('CHROME_HISTORY_OUTSIDE_TASK');this.checkUrl(target);
      if(op==='back')await this.tab.back();else await this.tab.forward();
      if(await this.location()!==target)stop('CHROME_NAVIGATION_UNVERIFIED');this.historyIndex=n;
    }else if(op==='reload'){
      await this.tab.reload();await this.tab.playwright.waitForLoadState({state:'domcontentloaded',timeoutMs:8000});
      if(await this.location()!==url)stop('CHROME_NAVIGATION_UNVERIFIED');
    }else if(op==='screenshot'){
      receipt=writeScreenshot(value,await this.tab.screenshot({fullPage:options.full_page??false}),this.contract);
    }else if(op==='export'){
      const format=options.export_format||'page';let artifact;
      if(format==='dom_snapshot'){receipt=writeArtifact(value,await this.tab.playwright.domSnapshot(),this.contract);}
      else if(format==='page')artifact=await this.tab.content.export();
      else if(format==='youtube_transcript')artifact=await this.tab.content.exportYouTubeTranscript();
      else artifact=await this.tab.content.exportGsuite(format);
      if(artifact)receipt=copyArtifact(artifact,value,this.contract);
    }else if(op==='logs'){
      receipt=writeArtifact(value,JSON.stringify((await this.tab.dev.logs({limit:200})).map(log=>({...log,message:String(log.message).replace(/(?:apikey_|sk-)[A-Za-z0-9_-]+|Bearer\s+[^\s]+|(?:password|api[_ -]?key|cookie)\s*[:=]\s*[^\s]+/gi,'[REDACTED]')})),null,2),this.contract);
    }else if(op==='assets'){
      const capability=await this.capability('pageAssets'),inventory=await capability.list();
      const kinds=options.asset_kinds||['image'];
      const selected=inventory.assets.filter(asset=>kinds.includes(asset.kind));
      if(selected.length>100)stop('CHROME_ASSET_LIMIT');
      for(const asset of selected)this.checkUrl(asset.url);
      const bundled=selected.length?await capability.bundle({inventoryId:inventory.id,assetIds:selected.map(asset=>asset.id)}):{assets:[],summary:{requestedCount:0,downloadedCount:0,failedCount:0},failures:[]};
      const copied=[];
      for(const asset of bundled.assets){
        const destination=path.join(path.dirname(value),path.parse(value).name+'-'+copied.length+path.extname(asset.path));
        copied.push({...copyArtifact(asset.path,destination,this.contract),kind:asset.kind});
      }
      receipt=writeArtifact(value,JSON.stringify({assets:copied,summary:bundled.summary,failures:bundled.failures},null,2),this.contract);
    }else if(op==='clipboard_write'){
      await this.tab.clipboard.writeText(value);
      if(await this.tab.clipboard.readText()!==value)stop('CHROME_CLIPBOARD_UNVERIFIED');receipt={characters:value.length};
    }else if(op==='clipboard_read'){
      receipt=writeArtifact(value,await this.tab.clipboard.readText(),this.contract);
    }else if(op==='dialog_accept'||op==='dialog_dismiss'){
      stop('CHROME_JS_DIALOG_HOST_BLOCKED');
    }else if(op==='viewport_set'||op==='viewport_reset'){
      if(!this.browser)stop('CHROME_BROWSER_BINDING_REQUIRED');
      const viewport=await this.browser.capabilities.get('viewport');await viewport.documentation();
      if(op==='viewport_set'){
        this.viewportChanged=true;await viewport.set({width:options.viewport_width,height:options.viewport_height});
        const size=await this.tab.playwright.evaluate(()=>({width:window.innerWidth,height:window.innerHeight}));
        if(size.width!==options.viewport_width||size.height!==options.viewport_height)stop('CHROME_VIEWPORT_UNVERIFIED');
        this.viewportChanged=true;receipt=size;
      }else{await viewport.reset();this.viewportChanged=false;receipt={reset:true};}
    }else if(op==='mark_deliverable'){this.lifecycle?.preserve(this.tab,'deliverable');await this.tab.markDeliverable();}
    else if(op==='mark_handoff'){this.lifecycle?.preserve(this.tab,'handoff');await this.tab.markHandoff();}
    else stop('CHROME_UNSUPPORTED_ACTION');
    if(receipt)this.receipts.set(payload.step_id,receipt);
    return {dispatched:true,...(receipt?{artifact:receipt}:{})};
  }
}

export class ChromeSurfaces{
  constructor(tab,contract,browser,options={}){this.contract=contract;this.browser=browser;this.current='main';this.lifecycle=new TaskTabs(contract,options);this.drivers=new Map([['main',new OfficialTabDriver(tab,contract,browser,this.lifecycle,options.rootCreated===true)]]);}
  get tab(){return this.drivers.get(this.current).tab;}
  async cleanup(options={}){
    for(const driver of this.drivers.values())if(driver.viewportChanged){
      await (await this.browser.capabilities.get('viewport')).reset();driver.viewportChanged=false;
    }
    return await this.lifecycle.sweep(this,options);
  }
  async dispatch(method,payload){
    if(method==='checkpoint'){
      this.lifecycle.checkpoint(payload.completed);
      await this.lifecycle.sweep(this);if(this.lifecycle.interrupted)stop('CHROME_SESSION_INTERRUPTED');return this.lifecycle.stats();
    }
    if(method==='activate'){
      const name=payload.surface;
      if(name!=='main'&&!Object.hasOwn(this.contract.targets||{},name))stop('CHROME_SURFACE_DENIED');
      if(!this.drivers.has(name)){
        if(!this.browser)stop('CHROME_BROWSER_BINDING_REQUIRED');
        const target=this.contract.targets[name];let tab;
        if(target.tab_id&&target.tab_id!=='new-tab-preflight'){
          const info=(await this.browser.user.openTabs()).find(x=>String(x.id)===target.tab_id);if(!info)stop('CHROME_TAB_CLOSED');
          tab=await this.browser.user.claimTab(info);
        }else{this.lifecycle.beforeCreate();tab=await this.browser.tabs.new();}
        const child={...this.contract,target:{...target,tab_id:String(tab.id)},targets:{}};
        const owned=!target.tab_id||target.tab_id==='new-tab-preflight';
        const driver=new OfficialTabDriver(tab,child,this.browser,this.lifecycle,owned);this.drivers.set(name,driver);
        if(owned)await tab.goto(target.url);
        await driver.dispatch('bind',{tab_id:String(tab.id),url:target.url,origins:this.contract.scope.origins});
      }
      this.current=name;return {surface:name};
    }
    return await this.drivers.get(this.current).dispatch(method,payload);
  }
}
