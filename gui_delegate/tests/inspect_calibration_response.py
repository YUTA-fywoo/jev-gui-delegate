"""Inspect only one pre-authored synthetic failing request; never log authentication."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import jev_client
from gui_delegate.daily_calibration import Fixture,Capture,read,write
from gui_delegate.controller import Controller
from gui_delegate.security import Stop

original=jev_client.validate_response;diagnostic={}
def inspect(response,request):
    diagnostic.update(model=response.model,usage=response.usage.model_dump(),answers={k:v.model_dump(mode='json') for k,v in response.answers.items()})
    return original(response,request)
jev_client.validate_response=inspect
case=next(c for c in read('cases') if c['id']=='train-expand-ja-windows-missing')
f=Fixture()
try:
    c,d=f.prepare(case);ctl=Controller(c,d,lambda:None,lambda *a,**kw:None,Capture())
    try:ctl.choose(c.steps[0],ctl.observe());diagnostic['status']='VALID'
    except Stop as exc:diagnostic['status']=exc.reason
finally:f.close()
write('development-response-diagnostic',diagnostic)
print(json.dumps(diagnostic,ensure_ascii=True))
