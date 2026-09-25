"""Bounded loopback-only static fixture for tab resource tests."""
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

REPORT=Path(__file__).resolve().parents[1]/'reports/tab-cleanup-20260924'
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path not in ('/a','/b','/c','/d'):
            self.send_response(404);self.end_headers();return
        page=self.path[1:]
        data=f'<!doctype html><meta charset="utf-8"><title>Jev temporary tab test {page}</title><h1>Jev temporary tab test {page}</h1><div role="status" aria-label="Fixture status">Ready {page}</div>'.encode()
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);origin='http://127.0.0.1:'+str(server.server_port)
    pages=['a','b','c','d'];steps=[]
    for i,page in enumerate(pages):
        if i:steps.append({'id':'open_'+page,'op':'new_tab','intent':'Open disposable page '+page,'input_ref':page,'after':[{'kind':'url','equals':origin+'/'+page}]})
        steps.append({'id':'read_'+page,'op':'read','intent':'Verify fixture '+page,'target':{'role':'status','name':'Fixture status'},'after':[{'kind':'url','equals':origin+'/'+page}]})
    contract={'goal':'Validate automatic mid-task and terminal cleanup of disposable local pages','target':{'driver':'browser','connection':'official_chrome','url':origin+'/a'},'scope':{'origins':[origin],'actions':['read','new_tab']},'inputs':{p:{'value':origin+'/'+p} for p in pages},'steps':steps,'success':[{'kind':'url','equals':origin+'/d'}],'budget':{'steps':20,'jev_calls':0,'seconds':120}}
    (REPORT/'live-contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),'utf-8')
    print(origin,flush=True);server.serve_forever()
