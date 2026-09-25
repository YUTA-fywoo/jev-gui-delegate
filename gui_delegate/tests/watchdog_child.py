import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from gui_delegate import worker
from gui_delegate.schema import Control
from gui_delegate.drivers import observation
class HangingOwnedTestDriver:
    def open(self):pass
    def observe(self):return observation(1,'fixture',[Control(id='one',role='button',name='Wait target',visible=True,enabled=True)])
    def act(self,*args):time.sleep(60)
    def close(self):pass
worker.create_driver=lambda c:HangingOwnedTestDriver()
worker.work(sys.argv[1])
