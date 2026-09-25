"""Install only independently validated improvements; reversible local threshold release."""
import argparse,hashlib,json
from pathlib import Path
from jev_client import ROOT,load_settings
from manage import backup,pin_model,codex_home
from . import decision_policy as dp
from .daily_calibration import BASE,read

STATE=BASE/'deployment.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')

def deploy():
    candidate=dp.Policy.model_validate(read('validated-policy'));validation=read('validation')
    confirmation=read('confirmation-summary');plan=read('confirmation-plan');rows=read('confirmation-rows')
    assert confirmation['samples']==plan['samples']==len(rows) and confirmation['wrong_actions']==0
    assert plan['policy_frozen_before_confirmation'] and not plan['threshold_selection_allowed']
    assert plan['policy_sha256']==sha(BASE/'confirmation-policy.json')
    assert candidate.model_dump()==read('confirmation-policy'),'Release policy differs from the frozen confirmation policy.'
    assert candidate.profiles,'No heldout improvement qualified for release.'
    assert candidate.protocol_sha256==dp.PROTOCOL_HASH and candidate.evidence_sha256==sha(Path(candidate.evidence_report))
    assert validation['selection_frozen_before_holdout']
    for profile in candidate.profiles:
        v=validation['cohorts'][profile.driver+':'+profile.language]
        assert v['deploy'] and v['new']['wrong_accepted']==0 and v['wrong_actions']==0
        assert v['new']['correct_accepted']>v['old']['correct_accepted']
        assert v['real_verified_actions']==v['new']['accepted']
    if STATE.exists():
        state=read('deployment')
        if state['active']:
            assert dp.PATH.exists() and sha(dp.PATH)==state['policy_sha256'],'Local policy edits retained.'
            assert sha(ROOT/'settings.json')==state['settings_sha256'],'Local Jev settings edits retained.'
            return {'status':'INSTALLED','changed':False}
    settings=ROOT/'settings.json'
    state={'active':True,'policy_path':str(dp.PATH),'policy_backup':str(backup(dp.PATH)) if dp.PATH.exists() else None,
      'settings_backup':str(backup(settings)),'prior_settings':load_settings().model_dump(),
      'source_validation':str(BASE/'validation.json'),'automatic_background_calibration':False}
    # Pin only Jev, never change Codex's main model/provider/login.
    pin_model(candidate.model)
    write(dp.PATH,candidate.model_dump());assert dp.load() is not None
    state.update(policy_sha256=sha(dp.PATH),settings_sha256=sha(settings));write(STATE,state)
    manifest=codex_home()/'jev-integration.json';backup(manifest);d=json.loads(manifest.read_text('utf-8'))
    d['api']['settings']=load_settings().model_dump()
    d['gui_delegate'].update(decision_policy=str(dp.PATH),decision_policy_id=candidate.id,
      calibration_latest=str(BASE/'validation.json'),calibration_report_latest=str(BASE/'REPORT.md'),
      threshold_status='SCOPED_SYNTHETIC_HOLDOUT_EVALUATED',production_calibrated=False,thresholds_calibrated=False,
      calibration_model=candidate.model,calibration_rollback='python -m gui_delegate.deploy_calibration rollback',
      automatic_background_calibration=False)
    write(manifest,d)
    return {'status':'INSTALLED','changed':True,'model':candidate.model,'profiles':[p.model_dump() for p in candidate.profiles]}

def rollback():
    state=read('deployment')
    if not state['active']:return {'status':'ROLLED_BACK','changed':False}
    settings=ROOT/'settings.json'
    assert sha(dp.PATH)==state['policy_sha256'] and sha(settings)==state['settings_sha256'],'Newer user edits retained; automatic rollback stopped.'
    backup(dp.PATH);backup(settings)
    if state['policy_backup']:dp.PATH.write_bytes(Path(state['policy_backup']).read_bytes())
    else:
        assert dp.PATH.resolve().parent==(ROOT/'gui_delegate').resolve();dp.PATH.unlink()
    settings.write_bytes(Path(state['settings_backup']).read_bytes());state['active']=False;write(STATE,state)
    manifest=codex_home()/'jev-integration.json';backup(manifest);d=json.loads(manifest.read_text('utf-8'))
    d['api']['settings']=load_settings().model_dump();d['gui_delegate'].update(threshold_status='ENGINEERING_DEFAULT',decision_policy_id=None)
    write(manifest,d)
    return {'status':'ROLLED_BACK','changed':True,'reports_retained':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['deploy','rollback']);a=p.parse_args()
    print(json.dumps(deploy() if a.action=='deploy' else rollback(),ensure_ascii=True,indent=2))
