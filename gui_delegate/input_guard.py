"""Native user-takeover guard; Chrome ownership is enforced by the official session."""
from .security import Stop,last_input_tick

def describe():
    return {'version':'native-and-official-session-2',
            'official_chrome':'official_browser_session','native_or_clipboard':'session',
            'legacy_isolated_browser':'removed','records_input_content':False}

def mode_for(contract):
    targets=[contract.target,*contract.targets.values()]
    if all(t.driver=='browser' and t.connection=='official_chrome' for t in targets):
        # Chrome paste is a tab-local value operation, not the Windows clipboard.
        return 'official_browser_session'
    return 'session'

class InputGuard:
    def __init__(self,contract):
        self.mode=mode_for(contract)
        self.baseline=last_input_tick() if self.mode=='session' else None
    def start(self):pass
    def check(self):
        if self.mode=='session' and last_input_tick()!=self.baseline:
            raise Stop('USER_TAKEOVER','paused')
    def release(self):
        # Caller must first validate user_released_control in the resume protocol.
        if self.mode=='session':self.baseline=last_input_tick()
    def close(self):pass
