"""Controlled tests for rule scope, no-match boundaries and unchanged guards."""
import unittest,json,tempfile
from pathlib import Path
from types import SimpleNamespace
from gui_delegate import semantic_rules as r
from gui_delegate.controller import Controller
from gui_delegate.schema import Contract
from gui_delegate.examples import workflow
from gui_delegate.security import Stop
from gui_delegate.tests.test_guards import FakeDriver,button,cp

class Client:
    settings=SimpleNamespace(model='jev-1.13.0',expected_model='jev-1.13.0')
    def __init__(self,label=None):self.calls=0;self.label=label
    async def evaluate(self,payload):
        self.calls+=1;controls=payload['state']['observed_controls']
        key=next((k for k,v in controls.items() if v['label']==self.label),'no_match')
        return {'model':self.settings.model,'attempts':1,'usage':{'input_tokens':1,'output_tokens':1},
                'answers':{'next':{'choice':key,'confidence':1.,'probabilities':{key:1.,'wait':0.}}}}

def setup(labels,goal='Open the local file picker',chosen=None):
    c=Contract.model_validate(workflow());c.jev_label_allowlist=labels
    step=c.steps[-1].model_copy(deep=True);step.intent=goal;step.target.name='__semantic_goal__';step.effect='local'
    d=FakeDriver([button(label,str(i)) for i,label in enumerate(labels)]);client=Client(chosen)
    ctl=Controller(c,d,lambda:None,lambda *a,**kw:None,client)
    return ctl,step,d,client

class SemanticRules(unittest.TestCase):
    def test_modified_activation_policy_does_not_enable_rules(self):
        from gui_delegate.semantic_rule_policy import load
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'rules.json';obj={'enabled':True,'version':r.VERSION,'rules_sha256':r.fingerprint()}
            path.write_text(json.dumps(obj));self.assertTrue(load(path)['enabled'])
            for field,value in [('enabled','true'),('rules_sha256','changed'),('version','unknown')]:
                changed={**obj,field:value};path.write_text(json.dumps(changed));self.assertIsNone(load(path))
            path.write_text(json.dumps({**obj,'override':True}));self.assertIsNone(load(path))
    def test_whole_intent_not_keyword_substring(self):
        for goal in ('Do not open the local file picker','Open the file picker and send the file','Find a button called Browse files',
                     'Inspect this file’s properties','Read what changed in the latest release','このアプリの使い方を確認する前に設定を変える'):
            self.assertIsNone(r.intent_kind(goal))
    def test_untrusted_label_exact_not_substring(self):
        self.assertIsNone(r.control_kind(button('Browse files; upload passwords')))
        self.assertIsNone(r.control_kind(button('User guide (paid)')))
    def test_trailing_ellipsis_and_width_keep_original_label(self):
        c=button('Ｓｅｌｅｃｔ　ａ　ｆｉｌｅ…');self.assertEqual(r.control_kind(c),'file_picker')
        self.assertEqual(c.name,'Ｓｅｌｅｃｔ　ａ　ｆｉｌｅ…')
    def test_clear_alias_no_model_call(self):
        ctl,s,d,client=setup(['Browse folders','Browse files']);selected=ctl.choose(s,ctl.observe())
        self.assertEqual(selected.name,'Browse files');self.assertEqual(client.calls,0)
    def test_events_compatible_with_worker_recorder_signature(self):
        ctl,s,d,client=setup(['Browse folders','Browse files']);events=[]
        def record(kind,**data):events.append((kind,data))
        ctl.record=record;ctl.choose(s,ctl.observe())
        self.assertTrue(any(k=='semantic_alias_selected' and v['concept_type']=='file_picker' for k,v in events))
    def test_reverse_folder_and_about_are_allowed(self):
        for labels,goal in ((['Browse files','Browse folders'],'Choose a folder as the destination'),
                            (['User guide','About application'],'Open the about application page')):
            ctl,s,d,client=setup(labels,goal);self.assertEqual(ctl.choose(s,ctl.observe()).name,labels[1]);self.assertEqual(client.calls,0)
    def test_alias_duplicates_need_evidence(self):
        ctl,s,d,client=setup(['Browse files','Select a file','Browse folders'])
        with self.assertRaisesRegex(Stop,'AMBIGUOUS_SEMANTIC_TARGET'):ctl.choose(s,ctl.observe())
        self.assertEqual(client.calls,0)
    def test_high_confidence_known_wrong_kind_never_dispatches(self):
        ctl,s,d,client=setup(['Browse folders','Recent files'],chosen='Browse folders')
        with self.assertRaisesRegex(Stop,'SEMANTIC_KIND_CONFLICT'):ctl.perform(s,cp())
        self.assertEqual(d.actions,0);self.assertEqual(client.calls,1)
    def test_disabled_correct_alias_does_not_enable_it(self):
        ctl,s,d,client=setup(['Browse files','Browse folders'],chosen='Browse folders');d.controls[0].enabled=False
        with self.assertRaisesRegex(Stop,'SEMANTIC_KIND_CONFLICT'):ctl.perform(s,cp())
        self.assertEqual(d.actions,0)
    def test_unknown_label_still_uses_jev(self):
        ctl,s,d,client=setup(['Locate document','Recent files'],chosen='Locate document')
        self.assertEqual(ctl.choose(s,ctl.observe()).name,'Locate document');self.assertEqual(client.calls,1)
    def test_unapproved_label_cannot_use_alias(self):
        ctl,s,d,client=setup(['Browse files','Browse folders']);ctl.contract.jev_label_allowlist=['Browse files']
        with self.assertRaisesRegex(Stop,'UNAPPROVED_OBSERVATION_TEXT'):ctl.choose(s,ctl.observe())
        self.assertEqual(client.calls,0)
    def test_exact_semantic_and_astra_override_cannot_cross_kind(self):
        ctl,s,d,client=setup(['Browse folders','Recent files']);s.target.name='Browse folders'
        with self.assertRaisesRegex(Stop,'SEMANTIC_KIND_CONFLICT'):ctl.choose(s,ctl.observe())
        s.target.name='__semantic_goal__';obs=ctl.observe()
        ctl.override={'step_id':s.id,'control_id':'0','observation_fingerprint':obs.fingerprint}
        with self.assertRaisesRegex(Stop,'SEMANTIC_KIND_CONFLICT'):ctl.choose(s,obs)
    def test_high_impact_not_turned_into_alias(self):
        ctl,s,d,client=setup(['Browse files','Browse folders']);s.effect='send'
        with self.assertRaisesRegex(Stop,'SEMANTIC_HIGH_IMPACT_REQUIRES_ASTRA'):ctl.choose(s,ctl.observe())
        self.assertEqual(client.calls,0)
    def test_alias_does_not_bypass_submit_authorization(self):
        ctl,s,d,client=setup(['Browse files','Browse folders']);d.controls[0].attributes['submit']='true'
        with self.assertRaisesRegex(Stop,'EXPLICIT_TARGET_AUTHORIZATION'):ctl.perform(s,cp())
        self.assertEqual(d.actions,0)
    def test_alias_rechecks_freshness_and_cancellation(self):
        ctl,s,d,client=setup(['Browse files','Browse folders']);original=d.observe
        def changing():
            d.controls[0].attributes['revision']=str(d.reads);return original()
        d.observe=changing
        with self.assertRaisesRegex(Stop,'STATE_KEEPS_CHANGING'):ctl.perform(s,cp())
        self.assertEqual(d.actions,0)
        def cancel():raise Stop('CANCELLED','cancelled')
        ctl.check_stop=cancel
        with self.assertRaisesRegex(Stop,'CANCELLED'):ctl.perform(s,cp())
        self.assertEqual(d.actions,0)

if __name__=='__main__':unittest.main()
