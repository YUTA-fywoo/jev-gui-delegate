"""Finite live calibration: frozen family split, real DOM/UIA, unchanged authority."""
import argparse,asyncio,html,itertools,json,math,subprocess,sys,time,hashlib,statistics
from pathlib import Path
from jev_client import ROOT,JevClient,load_settings
from .daily_cases import cases,dataset_hash
from .decision_policy import DEFAULT,PROTOCOL_HASH,Policy,passes
from .schema import Contract,Checkpoint
from .controller import Controller
from .drivers import Windows
from .security import Stop
from .calibration import wilson

BASE=ROOT/'gui_delegate/reports/daily-calibration-20260923'
MODEL='jev-1.13.0'
LIMIT={'requests':720,'input_tokens':900000,'seconds_per_phase':1200}

def write(name,data):
    BASE.mkdir(parents=True,exist_ok=True);(BASE/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
def read(name):return json.loads((BASE/(name+'.json')).read_text('utf-8'))
def emit(value):print(json.dumps(value,ensure_ascii=True),flush=True)

class Capture:
    def __init__(self):
        self.real=JevClient(settings=load_settings().model_copy(update={'model':MODEL,'expected_model':MODEL,'calibrated':False}))
        self.settings=self.real.settings;self.response=None;self.payload=None
        self.unvalidated=None
    async def evaluate(self,payload):
        self.payload=payload
        # Pass-through observation of the real SDK response; validator always runs.
        # This calibration process makes serial requests, never changes acceptance.
        import jev_client
        original=jev_client.validate_response
        def observe(response,request):
            self.unvalidated={'model':response.model,'usage':response.usage.model_dump(),
                'probability_sums':{k:sum(a.probabilities.values()) for k,a in response.answers.items()}}
            return original(response,request)
        jev_client.validate_response=observe
        try:self.response=await self.real.evaluate(payload);return self.response
        finally:jev_client.validate_response=original

class Fixture:
    def __init__(self):self.native=None;self.process=None
    def contract(self,case):
        if case['driver']=='windows' and self.process is None:
            import win32gui
            self.process=subprocess.Popen([sys.executable,str(ROOT/'gui_delegate/fixtures/calibration_native.py')],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
            self.pid,self.hwnd=map(int,self.process.stdout.readline().split())
        native=case['driver']=='windows';role='Button' if native else 'button'
        target={'driver':'windows','hwnd':self.hwnd,'process_id':self.pid,'executable':sys._base_executable,'window_title':'Jev Synthetic Calibration'} if native else {'driver':'browser','url':(ROOT/'gui_delegate/fixtures/calibration.html').as_uri()}
        after={'kind':'text','target':{'role':'Text','automation_id':'103'} if native else {'role':'status','name':'Outcome'},'equals':case['expected'] or 'NO_MATCH_EXPECTED'}
        return Contract.model_validate({'goal':'Synthetic daily GUI decision: '+case['goal'],'language':case['language'],'target':target,
          'scope':{'programs':[sys._base_executable] if native else [],'read_roots':[str(ROOT/'gui_delegate/fixtures')],'actions':['click']},
          'jev_label_allowlist':list(dict.fromkeys(case['labels'])),
          'steps':[{'id':'choose','intent':case['goal'],'op':'click','target':{'role':role,'name':'__semantic_goal__','semantic':True},'effect':'local','after':[after]}],
          'success':[after],'budget':{'jev_calls':1,'steps':1,'reobservations':0,'no_progress':1,'seconds':15}})
    def prepare(self,case):
        c=self.contract(case)
        if case['driver']=='browser':
            raise Stop('BROWSER_CALIBRATION_REQUIRES_OFFICIAL_CHROME_SESSION')
        import win32gui as g,win32con
        for i in range(12):
            hwnd=g.GetDlgItem(self.hwnd,200+i)
            if i<len(case['labels']):
                label=case['labels'][i];g.SetWindowText(hwnd,label);g.EnableWindow(hwnd,label not in case['disabled']);g.ShowWindow(hwnd,win32con.SW_SHOWNA)
            else:g.ShowWindow(hwnd,win32con.SW_HIDE)
        g.SetWindowText(g.GetDlgItem(self.hwnd,103),'Pending')
        if self.native is None:self.native=Windows(c);self.native.open()
        self.native.contract=c
        return c,self.native
    def close(self):
        if self.process:
            import win32gui,win32con
            if win32gui.IsWindow(self.hwnd):win32gui.PostMessage(self.hwnd,win32con.WM_CLOSE,0,0)
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=3)

def prepare():
    data=cases()
    families={split:{c['family'] for c in data if c['split']==split} for split in ('train','holdout')}
    assert not families['train']&families['holdout']
    write('cases',data);plan={'dataset_sha256':dataset_hash(data),'protocol_sha256':PROTOCOL_HASH,'model':MODEL,
      'train_samples':sum(c['split']=='train' for c in data),'holdout_samples':sum(c['split']=='holdout' for c in data),
      'train_families':sorted(families['train']),'holdout_families':sorted(families['holdout']),'budgets':LIMIT,
      'deployment_rules':['zero wrong accepted training choices','zero wrong accepted heldout choices per deployed cohort',
       'no higher error than original threshold on same responses','strictly greater correct heldout coverage',
       'real accepted actions verify','model/protocol/action/risk/candidate count remain bound'],
      'user_scope':'browser and Windows; synthetic nonsecret local state only; no user documents uploaded'}
    write('plan',plan);emit(plan)

def raw_selected(row):
    a=row.get('answer')
    if not a or not a['choice'].startswith('c') or not a['choice'][1:].isdigit():return None
    return row['observed_labels'][int(a['choice'][1:])]
def accepted(row,t):
    label=raw_selected(row)
    return bool(label is not None and row['observed_labels'].count(label)==1 and passes(row['answer'],t))
def evaluate(rows,t):
    chosen=[r for r in rows if accepted(r,t)];correct=sum(raw_selected(r)==r['expected'] for r in chosen)
    positive=sum(r['expected'] is not None for r in rows)
    return {'samples':len(rows),'positive_samples':positive,'accepted':len(chosen),'correct_accepted':correct,'wrong_accepted':len(chosen)-correct,
      'correct_positive_coverage':correct/positive if positive else 0,'accepted_correctness_wilson95':wilson(correct,len(chosen))}

def select():
    rows=read('train-rows');profiles=[];stats={}
    assert len(rows)==read('plan')['train_samples']
    grid=list(itertools.product((.80,.85,.90,.93,.95,.97,.99,.999),(.65,.75,.85,.90,.95,.99),(.10,.15,.25,.40,.60)))
    for driver,language in itertools.product(('browser','windows'),('en','zh','ja')):
        cohort=[r for r in rows if (r['driver'],r['language'])==(driver,language)];options=[]
        for p,c,m in grid:
            t={'probability':p,'confidence':c,'margin':m};s=evaluate(cohort,t)
            if s['accepted'] and not s['wrong_accepted']:
                distance=sum(abs(t[k]-DEFAULT[k]) for k in t)
                options.append((s['correct_accepted'],-distance,t,s))
        if options:
            _,_,t,s=max(options,key=lambda x:(x[0],x[1]))
            profiles.append({'driver':driver,'language':language,'thresholds':t,'max_candidates':6})
            stats[driver+':'+language]={'selected':t,'training':s,'old':evaluate(cohort,DEFAULT)}
        else:stats[driver+':'+language]={'selected':None,'reason':'no zero-error candidate; retain default'}
    frozen={'version':1,'id':'daily-gui-20260923','model':MODEL,'protocol_sha256':PROTOCOL_HASH,
      'status':'synthetic_holdout_validated','production_calibrated':False,'evidence_report':str(BASE/'validation.json'),'evidence_sha256':'pending',
      'profiles':profiles}
    write('candidate-policy',frozen);write('selection',{'grid_candidates':len(grid),'objective':'maximize correct automatic coverage with zero observed training error; closest to existing threshold breaks ties',
      'cohorts':stats,'candidate_sha256':hashlib.sha256((BASE/'candidate-policy.json').read_bytes()).hexdigest(),'holdout_used':False})
    emit(stats)

def run(phase,limit=None,resume=False):
    plan=read('confirmation-plan' if phase=='confirmation' else 'plan');dataset=read('confirmation-cases' if phase=='confirmation' else 'cases');assert dataset_hash(dataset)==plan['dataset_sha256'] and PROTOCOL_HASH==plan['protocol_sha256']
    target=[c for c in dataset if c['split']==phase]
    if limit is not None:target=target[:limit]
    path=BASE/(phase+'-rows.json')
    if path.exists() and not resume:raise RuntimeError('Existing measured evidence retained; use --resume only to continue unfinished cases')
    policy=Policy.model_validate(read('confirmation-policy' if phase=='confirmation' else 'candidate-policy')) if phase!='train' else None
    if phase=='holdout':assert hashlib.sha256((BASE/'candidate-policy.json').read_bytes()).hexdigest()==read('selection')['candidate_sha256']
    if phase=='confirmation':assert hashlib.sha256((BASE/'confirmation-policy.json').read_bytes()).hexdigest()==plan['policy_sha256']
    rows=read(phase+'-rows') if path.exists() else []
    assert [r['id'] for r in rows]==[c['id'] for c in target[:len(rows)]]
    seconds_limit=plan['budgets']['seconds'] if phase=='confirmation' else LIMIT['seconds_per_phase']
    token_limit=plan['budgets']['input_tokens'] if phase=='confirmation' else LIMIT['input_tokens']
    fixture=Fixture();started=time.monotonic()
    try:
        for case in target[len(rows):]:
            if time.monotonic()-started>seconds_limit:break
            if sum(r['usage']['input_tokens'] for r in rows)>token_limit:break
            c,driver=fixture.prepare(case);client=Capture();ctl=Controller(c,driver,lambda:None,lambda *a,**kw:None,client,policy=policy)
            status='decision_only';reason=None;begin=time.monotonic()
            try:
                if phase=='train':ctl.choose(c.steps[0],ctl.observe())
                else:ctl.perform(c.steps[0],Checkpoint(task_id='calibration',contract_hash=case['id'],next_step=0,completed=[],phase='idle'));status='completed'
            except Stop as exc:status=exc.status;reason=exc.reason
            response=client.response
            if response:assert response['model']==MODEL
            if not client.payload:raise RuntimeError('No API request issued: '+str(reason))
            if not response and client.unvalidated:
                for key in ('input_tokens','output_tokens'):ctl.usage[key]+=client.unvalidated['usage'][key]
            labels=[v['label'] for v in client.payload['state']['observed_controls'].values()]
            assert sorted(labels)==sorted(l for l in case['labels'] if l not in case['disabled'])
            row={**case,'answer':response['answers']['next'] if response else None,'observed_labels':labels,'model':response['model'] if response else None,
              'status':status,'reason':reason,'usage':ctl.usage,'action_verified':status=='completed','elapsed_ms':round((time.monotonic()-begin)*1000),
              'request_sha256':hashlib.sha256(json.dumps(client.payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
              'invalid_response_diagnostic':client.unvalidated if not response else None}
            row['raw_selected']=raw_selected(row);row['raw_correct']=bool(response) and row['raw_selected']==row['expected']
            row['wrong_action']=ctl.usage['actions']>0 and row['raw_selected']!=row['expected']
            rows.append(row);write(phase+'-rows',rows)
            if len(rows)%12==0:emit({'phase':phase,'completed':len(rows),'planned':len(target),'elapsed_seconds':round(time.monotonic()-started,1),'wrong_actions':sum(r['wrong_action'] for r in rows)})
            if not response and (reason not in ('JEV_INVALID_RESPONSE','JEV_NETWORK_TIMEOUT','JEV_NETWORK_ERROR','JEV_RATE_LIMITED') or
                (len(rows)>=5 and all(r['answer'] is None for r in rows[-5:]))):break
    finally:fixture.close()
    write(phase+'-summary',{'samples':len(rows),'planned':len(target),'status':'COLLECTION_COMPLETE' if len(rows)==len(target) else 'PARTIAL',
      'elapsed_seconds':round(time.monotonic()-started,3),'usage':{k:sum(r['usage'][k] for r in rows) for k in ('jev_requests','http_attempts','input_tokens','output_tokens','failed_retries')},
      'elapsed_note':'This process segment only; resumed runs include previous row usage but not prior process setup time.',
      'real_actions':sum(r['usage']['actions'] for r in rows),'wrong_actions':sum(r['wrong_action'] for r in rows),'api_invalid_or_failed':sum(r['answer'] is None for r in rows)})
    emit(read(phase+'-summary'))

def prepare_confirmation():
    from .confirmation_cases import cases as new_cases
    assert not (BASE/'confirmation-plan.json').exists(),'Frozen confirmation evidence retained.'
    dataset=new_cases();prior=read('cases')
    assert not {r['family'] for r in dataset}&{r['family'] for r in prior}
    policy=read('validated-policy')
    write('confirmation-policy',policy);write('confirmation-cases',dataset)
    write('confirmation-plan',{'dataset_sha256':dataset_hash(dataset),'protocol_sha256':PROTOCOL_HASH,'model':MODEL,
        'samples':len(dataset),'policy_sha256':hashlib.sha256((BASE/'confirmation-policy.json').read_bytes()).hexdigest(),
        'fresh_families':sorted({r['family'] for r in dataset}),'budgets':{'requests':144,'input_tokens':150000,'seconds':600},
        'policy_frozen_before_confirmation':True,'threshold_selection_allowed':False,
        'release_rule':'No wrong real action in fresh confirmation; then verify the persisted policy in fresh MCP workers.',
        'scope':'Owned synthetic local browser and Windows controls only; neither production apps nor physical mouse use.'})
    emit(read('confirmation-plan'))

def report():
    rows=read('holdout-rows');assert len(rows)==read('plan')['holdout_samples']
    policy=read('candidate-policy');cohorts={};deploy=[]
    for profile in policy['profiles']:
        key=profile['driver']+':'+profile['language'];subset=[r for r in rows if r['driver']==profile['driver'] and r['language']==profile['language']]
        old=evaluate(subset,DEFAULT);new=evaluate(subset,profile['thresholds'])
        verified=sum(r['action_verified'] for r in subset);wrong=sum(r['wrong_action'] for r in subset)
        valid=(new['wrong_accepted']==0 and wrong==0 and verified==new['accepted'] and new['correct_accepted']>old['correct_accepted'])
        cohorts[key]={'old':old,'new':new,'real_verified_actions':verified,'wrong_actions':wrong,'deploy':valid,'thresholds':profile['thresholds']}
        if valid:deploy.append(profile)
    result={'status':'EVALUATED','cohorts':cohorts,'deployable_profiles':deploy,'model':MODEL,'protocol_sha256':PROTOCOL_HASH,
      'train':read('train-summary'),'holdout':read('holdout-summary'),'dataset_sha256':read('plan')['dataset_sha256'],
      'production_calibrated':False,'claims_no_general_error_guarantee':True,'selection_frozen_before_holdout':True,
      'limitations':['Synthetic labels and safe outcome widgets, not arbitrary third-party app side effects.',
         'Train/holdout families disjoint, but translations and variants correlated; per-sample intervals are descriptive only.',
         'Threshold cannot eliminate confident semantic errors outside the evaluated domain.',
         'Risk/permission/freshness/duplicate-target checks and real postconditions remain mandatory.']}
    write('validation',result)
    final={**policy,'profiles':deploy,'evidence_sha256':hashlib.sha256((BASE/'validation.json').read_bytes()).hexdigest()}
    write('validated-policy',final);emit(result)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','train','select','holdout','report','prepare-confirmation','confirmation']);p.add_argument('--limit',type=int);p.add_argument('--resume',action='store_true');args=p.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='select':select()
    elif args.action=='report':report()
    elif args.action=='prepare-confirmation':prepare_confirmation()
    else:run(args.action,args.limit,args.resume)
