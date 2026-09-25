"""Bounded before/after experiments on owned synthetic DOM/UIA widgets only."""
import argparse,hashlib,json,time
from collections import Counter
from jev_client import ROOT,load_settings
from .daily_calibration import Fixture,Capture,BASE as PRIOR
from .controller import Controller
from .schema import Checkpoint
from .security import Stop
from . import decision_policy as dp,semantic_rules as rules

BASE=ROOT/'gui_delegate/reports/semantic-kind-repair-20260923'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name,value):
    BASE.mkdir(parents=True,exist_ok=True)
    (BASE/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf-8')
def read(name):return json.loads((BASE/(name+'.json')).read_text('utf-8'))
def emit(value):print(json.dumps(value,ensure_ascii=True),flush=True)

def freeze():
    from .kind_repair_cases import cases
    assert not BASE.exists(),'Do not overwrite frozen evidence'
    data=cases();assert len(data)==132
    for c in data:
        expected=c['family'] if c['family'] not in ('properties','release_notes') else None
        assert rules.intent_kind(c['goal'])==expected,(c['id'],rules.intent_kind(c['goal']))
    write('cases',data)
    write('plan',{'case_sha256':sha(BASE/'cases.json'),'rules_sha256':rules.fingerprint(),
      'baseline_controller_sha256':sha(ROOT/'gui_delegate/controller.py'),'policy_sha256':sha(dp.PATH),
      'protocol_sha256':dp.PROTOCOL_HASH,'model':load_settings().expected_model,'planned_per_arm':len(data),
      'limits_per_arm':{'seconds':900,'requests':150,'input_tokens':200000},
      'scope':'Synthetic local buttons and verified outcome labels; not actual external file pickers/help apps.',
      'holdout_note':'Prospective combinations in the known confusion families, not independent production apps or a threshold retuning set.',
      'acceptance':['no wrong dispatched action','all targeted positive cases complete','all targeted negatives stop before dispatch',
                    'unchanged thresholds, model, question protocol and permissions','unrelated compatibility cases are not blocked by new rules']})
    emit(read('plan'))

def summarize(rows,elapsed):
    pos=[r for r in rows if r['expected'] is not None];neg=[r for r in rows if r['expected'] is None]
    return {'samples':len(rows),'positive':len(pos),'positive_completed':sum(r['action_verified'] for r in pos),
      'negative':len(neg),'negative_stopped':sum(r['usage']['actions']==0 for r in neg),
      'real_actions':sum(r['usage']['actions'] for r in rows),'wrong_actions':sum(r['wrong_action'] for r in rows),
      'elapsed_seconds':round(elapsed,3),'reasons':dict(Counter(r['reason'] for r in rows if r['reason'])),
      'usage':{k:sum(r['usage'].get(k,0) for r in rows) for k in ('jev_requests','http_attempts','input_tokens','output_tokens','failed_retries','semantic_alias_decisions')},
      'by_scope':{d+':'+l:{'samples':len(c:=[r for r in rows if r['driver']==d and r['language']==l]),
         'positive_completed':sum(r['action_verified'] for r in c),'wrong_actions':sum(r['wrong_action'] for r in c)}
         for d in ('browser','windows') for l in ('en','zh','ja')}}

def run(arm):
    plan=read('plan');assert sha(BASE/'cases.json')==plan['case_sha256'] and rules.fingerprint()==plan['rules_sha256']
    assert sha(dp.PATH)==plan['policy_sha256'] and dp.PROTOCOL_HASH==plan['protocol_sha256']
    if arm=='before':assert sha(ROOT/'gui_delegate/controller.py')==plan['baseline_controller_sha256']
    assert not (BASE/(arm+'-rows.json')).exists(),'Measured evidence retained; no implicit reruns'
    write(arm+'-source',{'controller_sha256':sha(ROOT/'gui_delegate/controller.py'),'rules_sha256':rules.fingerprint()})
    rows=[];fixture=Fixture();begin=time.monotonic();limits=plan['limits_per_arm']
    try:
        for case in read('cases'):
            if time.monotonic()-begin>limits['seconds'] or sum(r['usage']['input_tokens'] for r in rows)>limits['input_tokens']:break
            if sum(r['usage']['jev_requests'] for r in rows)>=limits['requests']:break
            c,driver=fixture.prepare(case);client=Capture();events=[]
            ctl=Controller(c,driver,lambda:None,lambda event,**kw:events.append((event,kw)),client)
            observed=ctl.observe();labels=[x.name for x in observed.controls if x.role.lower()=='button' and x.visible and x.enabled]
            status='completed';reason=None;start=time.monotonic()
            checkpoint=Checkpoint(task_id='kind-repair',contract_hash=case['id'],next_step=0,completed=[],phase='idle')
            try:ctl.perform(c.steps[0],checkpoint)
            except Stop as exc:status=exc.status;reason=exc.reason
            response=client.response
            if response:assert response['model']==plan['model']
            if not response and client.unvalidated:
                for key in ('input_tokens','output_tokens'):ctl.usage[key]+=client.unvalidated['usage'][key]
            chosen=next((x.name for x in observed.controls if x.id==checkpoint.pending_control_id),None)
            row={**case,'status':status,'reason':reason,'usage':ctl.usage,'observed_labels':labels,
              'answer':response['answers']['next'] if response else None,'selected':chosen,'action_verified':status=='completed',
              'wrong_action':ctl.usage['actions']>0 and chosen!=case['expected'],'elapsed_ms':round((time.monotonic()-start)*1000),
              'invalid_response_diagnostic':client.unvalidated if not response else None}
            rows.append(row);write(arm+'-rows',rows)
            if len(rows)%12==0:emit({'arm':arm,**summarize(rows,time.monotonic()-begin)})
    finally:fixture.close()
    result=summarize(rows,time.monotonic()-begin);result['collection_complete']=len(rows)==plan['planned_per_arm']
    write(arm+'-summary',result);emit(result)

def replay():
    """Actual UIA/DOM with previously recorded model answers; NOT new API success."""
    from types import SimpleNamespace
    old=json.loads((PRIOR/'holdout-rows.json').read_text('utf-8'));bad=[r for r in old if r['wrong_action']]
    assert len(bad)==6
    class Recorded:
        settings=SimpleNamespace(model='jev-1.13.0',expected_model='jev-1.13.0')
        async def evaluate(self,payload):
            assert [x['label'] for x in payload['state']['observed_controls'].values()]==row['observed_labels']
            return {'answers':{'next':row['answer']},'model':self.settings.model,'attempts':0,'usage':{'input_tokens':0,'output_tokens':0}}
    fixture=Fixture();results=[]
    try:
        for row in bad:
            c,driver=fixture.prepare(row);ctl=Controller(c,driver,lambda:None,lambda *a,**kw:None,Recorded())
            reason=None
            try:ctl.perform(c.steps[0],Checkpoint(task_id='replay',contract_hash=row['id'],next_step=0,completed=[],phase='idle'))
            except Stop as exc:reason=exc.reason
            assert reason=='SEMANTIC_KIND_CONFLICT' and ctl.usage['actions']==0,(row['id'],reason)
            results.append({'id':row['id'],'reason':reason,'actions':0,'live_api_requests':0})
    finally:fixture.close()
    from .schema import Control
    # Replay the rule invariant against every previously correctly dispatched choice.
    correct=[r for r in old if r['action_verified']]
    conflicts=[]
    for r in correct:
        control=Control(id='recorded',role='button',name=r['raw_selected'],visible=True,enabled=True)
        if rules.conflict(rules.intent_kind(r['goal']),control):conflicts.append(r['id'])
    assert not conflicts
    report={'status':'PASS','recorded_failures_in_real_widgets':results,'prior_correct_recorded_choices_checked':len(correct),
      'new_conflicts_with_prior_correct_choices':conflicts,'live_api_requests':0,'note':'Recorded-answer regression; distinct from live before/after collection.'}
    write('recorded-regression',report);emit(report)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','before','after','replay']);a=p.parse_args()
    if a.command=='freeze':freeze()
    elif a.command=='replay':replay()
    else:run(a.command)
