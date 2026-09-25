import hashlib,json,tempfile,unittest
from pathlib import Path
from gui_delegate import decision_policy as p
from gui_delegate.schema import Contract
from gui_delegate.examples import workflow
from gui_delegate.tests.test_guards import button

def policy():
    return p.Policy.model_validate({'version':1,'id':'unit','model':'jev-1.13.0','protocol_sha256':p.PROTOCOL_HASH,
      'status':'synthetic_holdout_validated','production_calibrated':False,'evidence_report':'unused','evidence_sha256':'unused',
      'profiles':[{'driver':'browser','language':'en','thresholds':{'probability':.90,'confidence':.75,'margin':.10},'max_candidates':6}]})

class DecisionPolicy(unittest.TestCase):
    def setUp(self):
        c=workflow();c['language']='en';self.c=Contract.model_validate(c);self.step=self.c.steps[-1]
        self.controls=[button(),button('Preview','two')]
    def test_evaluated_low_risk_cohort_gets_profile(self):
        t,source=p.resolve(policy(),self.c,self.step,self.controls,'jev-1.13.0')
        self.assertEqual(t['probability'],.9);self.assertEqual(source,'unit:browser:en')
    def test_wrong_model_falls_back(self):
        t,source=p.resolve(policy(),self.c,self.step,self.controls,'jev-1.14.0');self.assertEqual(t,p.DEFAULT)
    def test_unevaluated_language_falls_back(self):
        self.c.language='mixed';self.assertEqual(p.resolve(policy(),self.c,self.step,self.controls,'jev-1.13.0')[0],p.DEFAULT)
    def test_risk_cannot_use_relaxed_threshold(self):
        self.step.effect='send';self.assertEqual(p.resolve(policy(),self.c,self.step,self.controls,'jev-1.13.0')[0],p.DEFAULT)
    def test_larger_candidate_set_falls_back(self):
        self.assertEqual(p.resolve(policy(),self.c,self.step,self.controls*4,'jev-1.13.0')[0],p.DEFAULT)
    def test_same_visible_evidence_not_disambiguated_by_hidden_ids(self):
        a=button();b=button(ident='other');a.frame_url='one';b.frame_url='two'
        self.assertTrue(p.indistinguishable(a,[a,b]))
    def test_no_match_does_not_become_action(self):
        self.assertFalse(p.passes({'choice':'no_match','confidence':1.,'probabilities':{'no_match':1.,'c0':0.}},p.DEFAULT))
    def test_evidence_and_prompt_hash_bind_policy(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);ev=d/'evidence.json';ev.write_text('{}');obj=policy().model_dump();obj.update(evidence_report=str(ev),evidence_sha256=hashlib.sha256(ev.read_bytes()).hexdigest())
            file=d/'policy.json';file.write_text(json.dumps(obj));self.assertIsNotNone(p.load(file))
            ev.write_text('{"changed":true}');self.assertIsNone(p.load(file))
            ev.write_text('{}');obj['protocol_sha256']='changed';file.write_text(json.dumps(obj));self.assertIsNone(p.load(file))
    def test_invalid_profile_cannot_disable_gate(self):
        obj=policy().model_dump();obj['profiles'][0]['thresholds']['probability']=0.
        with self.assertRaises(ValueError):p.Policy.model_validate(obj)

if __name__=='__main__':unittest.main()
