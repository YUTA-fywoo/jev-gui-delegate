const {app,BrowserWindow,session}=require('electron');
const path=require('path');
app.setPath('userData',path.join(__dirname,'private-profile'));
app.commandLine.appendSwitch('force-renderer-accessibility');
app.enableSandbox();
app.whenReady().then(()=>{
  session.defaultSession.webRequest.onBeforeRequest((details,callback)=>callback({cancel:!details.url.startsWith('file:')}));
  const w=new BrowserWindow({width:720,height:460,show:false,title:'Jev Isolated Electron Fixture',webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true}});
  w.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  w.loadFile(path.join(__dirname,'page.html'));
  w.once('ready-to-show',()=>{w.showInactive();console.log(JSON.stringify({pid:process.pid,hwnd:Number(w.getNativeWindowHandle().readBigUInt64LE())}));});
  setTimeout(()=>app.quit(),120000).unref();
});
app.on('window-all-closed',()=>app.quit());
