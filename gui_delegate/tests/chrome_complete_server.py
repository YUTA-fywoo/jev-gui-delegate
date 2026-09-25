"""Own loopback fixtures only; never serves arbitrary files or directories."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import json,threading,uuid
from jev_client import ROOT

REPORT=ROOT/'gui_delegate/reports/chrome-complete-20260923'
NAME='jev-synthetic-'+uuid.uuid4().hex[:12]+'.txt'
DATA='Jev Chrome synthetic download\n中文 / 日本語\n'.encode()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,data,kind='text/html; charset=utf-8',attachment=False):
        if isinstance(data,str):data=data.encode()
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
        if attachment:self.send_header('Content-Disposition','attachment; filename="'+NAME+'"')
        self.end_headers();self.wfile.write(data)
    def do_GET(self):
        route=self.path.split('?')[0]
        if route=='/download':self.send(DATA,'text/plain; charset=utf-8',True);return
        if route=='/image.svg':self.send('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect width="40" height="40" fill="green"/></svg>','image/svg+xml');return
        if route=='/frame':
            self.send('<!doctype html><meta charset="utf-8"><label>框架输入<input id="frameInput" aria-label="框架输入"></label><button type="button" id="frameButton" onclick="document.getElementById(\'frameStatus\').textContent=\'Frame done\'">Frame action</button><span role="status" aria-label="Frame state" id="frameStatus">Frame pending</span>');return
        if route=='/destination':self.send('<!doctype html><meta charset="utf-8"><h1>Known destination</h1><span role="status" aria-label="Destination">Arrived</span>');return
        if route=='/features':
            template=(ROOT/'gui_delegate/fixtures/chrome-features.html').read_text('utf-8')
            self.send(template.replace('__FRAME_ORIGIN__',FRAME).replace('__DOWNLOAD_NAME__',NAME));return
        if route=='/workflow':self.send((ROOT/'gui_delegate/fixtures/chrome-workflow.html').read_bytes());return
        self.send_response(404);self.end_headers()
    def do_POST(self):
        if self.path!='/upload':self.send_response(404);self.end_headers();return
        size=int(self.headers.get('Content-Length','0'))
        if size>100000:self.send_response(413);self.end_headers();return
        body=self.rfile.read(size);self.send(json.dumps({'received':len(body),'contains_synthetic_text':b'SYNTHETIC UPLOAD' in body}),'application/json')

if __name__=='__main__':
    REPORT.mkdir(parents=True,exist_ok=True)
    frame=ThreadingHTTPServer(('127.0.0.1',0),Handler);FRAME='http://127.0.0.1:'+str(frame.server_port)
    threading.Thread(target=frame.serve_forever,daemon=True).start()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);origin='http://127.0.0.1:'+str(server.server_port)
    (REPORT/'fixture.json').write_text(json.dumps({'origin':origin,'url':origin+'/features','frame_origin':FRAME,'download_name':NAME,'download_sha256':__import__('hashlib').sha256(DATA).hexdigest()}),'utf-8')
    print(origin,flush=True);server.serve_forever()
