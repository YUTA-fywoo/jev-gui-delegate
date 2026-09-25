"""Bounded localhost synthetic pages; no directories or arbitrary local files."""
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from jev_client import ROOT

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path.split('?')[0] not in ('/workflow','/other'):
            self.send_response(404);self.end_headers();return
        data=(ROOT/'gui_delegate/fixtures/chrome-workflow.html').read_bytes()
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)

if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    url='http://127.0.0.1:'+str(server.server_port)
    p=ROOT/'gui_delegate/reports/current-verification/fixture.json'
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({'origin':url,'url':url+'/workflow'}),'utf-8')
    print(url,flush=True)
    server.serve_forever()
