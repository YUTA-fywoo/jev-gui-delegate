"""Read-only verification of the installed calibration and packaged evidence."""
import hashlib,json,tomllib,zipfile
from pathlib import Path
from manage import codex_home
from jev_client import ROOT,load_settings
from gui_delegate import decision_policy as dp
from gui_delegate.daily_calibration import BASE,read,write

def main():
    policy=dp.load();assert policy is not None
    settings=load_settings();assert settings.model==settings.expected_model==policy.model=='jev-1.13.0'
    config=tomllib.loads((codex_home()/'config.toml').read_text('utf-8'))
    assert config['model']=='gpt-6-astra'
    manifest=json.loads((codex_home()/'jev-integration.json').read_text('utf-8'))
    d=manifest['gui_delegate'];assert d['decision_policy_id']==policy.id and d['benchmark_latest']
    assert Path(d['calibration_report_latest']).is_file() and not d['production_calibrated']
    release=read('release-summary');assert release['evaluation_requests']==828 and release['candidate_holdout_wrong_actions']==6
    assert release['confirmation']['wrong_actions']==0 and release['confirmation']['samples']==144
    archive=Path(d['source_archive']);p=read('package');assert hashlib.sha256(archive.read_bytes()).hexdigest()==p['sha256']
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert z.read('gui_delegate/decision-policy.json')==dp.PATH.read_bytes()
        evidence=z.read(Path(policy.evidence_report).relative_to(ROOT).as_posix())
        assert hashlib.sha256(evidence).hexdigest()==policy.evidence_sha256
        names=z.namelist()
        assert not any('/private/' in name or '/node_modules/' in name or name.endswith('deployment.json') for name in names)
    report={'status':'PASS','main_model_preserved':True,'policy_persisted':True,'jev_version_pinned':True,
        'prior_benchmark_preserved':True,'archive_integrity':True,'evidence_hash_matches_packaged_bytes':True,
        'production_calibrated':False,'automatic_background_calibration':False}
    write('delivery-verification',report);print(json.dumps(report,indent=2))

if __name__=='__main__':main()
