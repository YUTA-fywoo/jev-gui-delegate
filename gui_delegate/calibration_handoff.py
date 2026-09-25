"""Preserve measurements, publish a scoped calibration report, and package source."""
import argparse,hashlib,json,re,sys,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from jev_client import ROOT
from manage import backup,codex_home
from .daily_calibration import BASE,read,write,accepted,evaluate
from . import decision_policy as dp

def safe_write(path,text):
    if path.exists() and path.read_text('utf-8')==text:return
    if path.exists():backup(path)
    path.write_text(text,'utf-8')

def report():
    policy=dp.load();assert policy and read('deployment')['active']
    validation=read('validation');confirmation=read('confirmation-summary')
    rows=read('holdout-rows');fresh=read('confirmation-rows');train=read('train-rows')
    def threshold(r):
        p=next((p for p in policy.profiles if (p.driver,p.language)==(r['driver'],r['language'])),None)
        return p.thresholds.model_dump() if p else dp.DEFAULT
    selected=[r for r in rows if accepted(r,threshold(r))]
    assert all(r['action_verified'] and not r['wrong_action'] for r in selected)
    assert not any(r['wrong_action'] for r in fresh)
    failures=[{'case':r['id'],'goal':r['goal'],'selected':r['raw_selected'],'probability':r['answer']['probabilities'][r['answer']['choice']],
        'confidence':r['answer']['confidence'],'final_policy_would_reject':not accepted(r,threshold(r))} for r in rows if r['wrong_action']]
    assert all(r['final_policy_would_reject'] for r in failures)
    scopes={}
    for driver in ('browser','windows'):
        for language in ('en','zh','ja'):
            cohort=[r for r in rows if (r['driver'],r['language'])==(driver,language)]
            new=[r for r in fresh if (r['driver'],r['language'])==(driver,language)]
            scopes[driver+':'+language]={'holdout_original':evaluate(cohort,dp.DEFAULT),'holdout_released':evaluate(cohort,threshold(cohort[0])),
                'confirmation_actions_verified':sum(r['action_verified'] for r in new),'confirmation_positive':sum(r['expected'] is not None for r in new),
                'confirmation_wrong_actions':sum(r['wrong_action'] for r in new),'thresholds':threshold(cohort[0])}
    samples=train+rows+fresh
    summary={'status':'DEPLOYED_SCOPED_SYNTHETIC_POLICY','policy_id':policy.id,'model':policy.model,
        'production_calibrated':False,'automatic_background_calibration':False,
        'evaluation_requests':len(samples),'main_evaluation_usage':{k:sum(r['usage'][k] for r in samples) for k in ('jev_requests','http_attempts','input_tokens','output_tokens','failed_retries')},
        'stages':{'train_samples':len(train),'holdout_samples':len(rows),'fresh_confirmation_samples':len(fresh)},
        'candidate_holdout_actions':sum(r['usage']['actions'] for r in rows),'candidate_holdout_wrong_actions':len(failures),
        'released_policy_holdout_reanalysis':{'accepted':len(selected),'correct':len(selected),'positive':sum(r['expected'] is not None for r in rows),
          'note':'Same frozen API answers re-evaluated under the released subset; each retained action was actually verified. Not another live rerun.'},
        'confirmation':confirmation,'cohorts':scopes,'rejected_candidate_failures':failures,
        'invalid_or_failed_responses':sum(r['answer'] is None for r in samples),
        'confirmation_exits':dict(Counter(r['reason'] for r in fresh if r['reason'])),
        'mcp_policy':read('mcp-policy'),'development_overhead':{'included_in_main_evaluation_usage':False,'astra_tokens':'unavailable','money':'unavailable',
          'note':'Fixture debugging and diagnostic API calls are separate. The 828-request total covers the three frozen datasets only.'},
        'actual_money':'unavailable','threshold_runtime_extra_jev_requests':0,
        'rollback_test':{'deploy':True,'idempotent_deploy':True,'rollback':True,'restore':True,'evidence':'Actual deploy/rollback/restore commands and fresh MCP workers verified in this task.'},
        'limitations':validation['limitations']+['Only harmless click-to-outcome fixtures, not the real application behavior suggested by their labels.',
          'No guarantee for arbitrary daily apps, sessions, side effects, physical IME, multi-monitor or unstructured graphics.',
          'Normal use does not silently change thresholds or upload task history; further calibration is a deliberate bounded evaluation.']}
    write('release-summary',summary)
    table=[]
    for key,v in scopes.items():
        before=v['holdout_original'];after=v['holdout_released'];p=v['thresholds']['probability']
        table.append(f"| {key} | {p:.2f} | {before['correct_accepted']}/{before['positive_samples']} → {after['correct_accepted']}/{after['positive_samples']} | {v['confirmation_actions_verified']}/{v['confirmation_positive']} |")
    text=f'''# Jev 日常 GUI 校准：限定范围的已部署结果

已在本机保存并启用 `{policy.id}`，固定 Jev `{policy.model}`。主模型、登录和提供商未改。只把英文网页、中文 Windows 的低风险按钮选择概率门槛从 0.97 调到 0.95；confidence 0.90、首选与次选概率差 0.15 保持不变。其他场景保持原门槛。该数值不是动作成功率。

适用条件由代码检查：模型和选择协议匹配、语言/驱动匹配、click、none/local 风险、2–6 个真实按钮候选。其他动作、混合语言、分组选择、较大候选集仍用原门槛。高影响语义动作仍升级；权限、状态新鲜度、后置验证、预算、取消保持生效。精确控件匹配继续走确定性代码。

## 实际验证与失败

- 训练 144 例、按意图族隔离的验收 540 例、额外冻结的新意图确认 144 例，共 **828 次真实 Jev 请求**。三阶段合计 {summary['main_evaluation_usage']['input_tokens']:,} 输入 / {summary['main_evaluation_usage']['output_tokens']:,} 输出 tokens，0 次失败重试。一次性校准开销单列，不计入日常任务节省。
- 候选配置在验收阶段实际执行 211 次，其中 **6 次错误**：文件选择误选文件夹、日文使用指南误选“关于应用”。只改变合成窗口的结果文本，真实后置检查报错，没有操作生产任务。原始失败保留在 `holdout-rows.json`。涉及的放宽配置未部署，最终配置对这 6 个原始响应全部拒绝。
- 最终配置在同一验收响应上的保留集合为 **{len(selected)}/216 个正例自动完成、0 个错误接受**；这些动作均已实际执行验证。这是同批响应重算，不能冒称额外独立实验。
- 冻结最终配置后，新 144 例中 **65 次实际动作通过、0 次错误动作**；96 个正例中有 31 个未自动完成，48 个无匹配反例全部无错误动作。未执行不计为独立完成。确认运行耗时 {confirmation['elapsed_seconds']:.3f} 秒，不包括开发与部署。
- 三阶段有 **{summary['invalid_or_failed_responses']} 次无效/失败响应**被阻止，均未执行动作；保留原始校验，未自动归一化概率来提高通过率。`train-summary/holdout-summary` 的旧 `status=PASS` 仅表示采集完成，不表示任务全对；以本报告的错误计数为准。
- 新建真实 stdio MCP 子进程和工作进程已分别完成英文网页、中文原生窗口任务，确认凭据、固定版本和持久化策略均实际加载。

| 范围 | 最终 probability 门槛 | 独立验收正例自动完成：原值 → 最终值 | 新确认实际完成/正例 |
|---|---:|---:|---:|
'''+ '\n'.join(table)+f'''

模型输入仅为批准的合成标签、子目标和候选信息；未上传真实桌面、用户文件、秘密或输入值。对模型能看见的证据完全相同的按钮，现在直接请求局部接管，不靠内部 ID 猜测。

## 能说明什么

这次达成“在有证据支持的范围减少不必要接管”，没有把门槛一律调高。英文网页的正例覆盖 31/36 → 34/36，中文 Windows 30/36 → 33/36。新的确认集自动完成率只有 65/96，说明日常任务的语义覆盖仍有不足。

**尚未证明日常所有 GUI 基本不会出错。** 这些是有真值的合成控件选择，不是真实邮件、文件管理、支付等业务完整任务。翻译与变体彼此相关，不能把 828 例当成 828 个独立生产场景；小样本零错误也不是零风险。未完成真实应用、账号状态、业务副作用、物理输入法、多显示器等生产校准。日文门槛没有放宽；后续应按获授权的具体应用补充任务级独立验收。

官方 confidence 概念依据：[TypeSafe confidence](https://docs.typesafe.ai/confidence)。模型已知的语义边界依据：[Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)。上述本机数字只来自保存的实测数据。

## 保留、速度与撤销

策略保存在 `gui_delegate/decision-policy.json`，清单位于实际 CODEX_HOME 的 `jev-integration.json`。新任务工作进程读取这些文件，因此后续对话会复用；本次仅更新文件和控制器，不需要重启电脑。MCP 工具目录已存在的会话可直接调用，缺少 task 工具的旧会话需新开，或使用同一 CLI。

日常运行仅做本地策略匹配和文件完整性校验，**没有增加额外 Jev 请求**；本次没有重新进行 Astra 对照测速，不能给出新速度或费用节省比例。运行时不会自动改阈值，也未设置后台校准任务。其他电脑仍需配置本机环境、凭据和路径，并做驱动与任务回归；本机合成证据不能当成另一台电脑已验证的证据。

仅撤销这次数值策略和版本固定：`C:\\jev\\jev-bridge\\jev-calibration-rollback.cmd`；恢复：`jev-calibration-restore.cmd`。已实际验证重复部署、撤销和恢复；遇到较新的用户配置改动会停止，保留用户内容。源码中的选择协议和歧义修复保留；原始备份在 CODEX_HOME/backups/jev-bridge。

最短验证：`C:\\jev\\jev-bridge\\gui-demo.cmd`，运行 15 步合成网页任务并真实核对结果。可直接对 Codex 说“用 Jev 委派运行本机的合成 GUI 验收任务”。

主要证据：`plan.json`、`selection.json`、三阶段 `*-rows.json`、`validation.json`、`confirmation-plan.json`、`mcp-policy.json`、`release-summary.json`。历史 72 例保留，不混入这次 828 例。
'''
    safe_write(BASE/'REPORT.md',text)
    calibration=ROOT/'gui_delegate/CALIBRATION.md'
    safe_write(calibration,'# 当前校准结果\n\n当前已部署的 828 例评估、两处适度放宽、失败记录、持续使用和回滚说明见 [本次报告](reports/daily-calibration-20260923/REPORT.md)。`production_calibrated=false`；未宣称所有日常 GUI 基本不会出错。\n\n历史 72 例仍保存在 `reports/calibration.json`、`calibration-cases.json` 和 `calibration-rows.json`，不与当前独立验收混合。\n')
    manifest=codex_home()/'jev-integration.json';backup(manifest);d=json.loads(manifest.read_text('utf-8'))
    d['updated_at']=datetime.now(timezone.utc).isoformat()
    d['gui_delegate'].update(calibration_release_summary=str(BASE/'release-summary.json'),
        calibration_rollback=str(ROOT/'jev-calibration-rollback.cmd'),calibration_restore=str(ROOT/'jev-calibration-restore.cmd'),
        calibration_new_session_required=False,calibration_tests={'real_requests':len(samples),'candidate_wrong_actions':6,'confirmation_wrong_actions':0,'mcp_policy':'PASS'})
    d['todo']=[x for x in d.get('todo',[]) if not x.startswith('Calibrate by application')]
    d['todo'].insert(0,'Two scoped button profiles are synthetically evaluated, not production calibrated. Further authorized per-application regression is required; Japanese thresholds remain unchanged.')
    safe_write(manifest,json.dumps(d,ensure_ascii=False,indent=2))
    print(json.dumps({'report':str(BASE/'REPORT.md'),'requests':len(samples),'profiles':len(policy.profiles),'confirmation_actions':65},ensure_ascii=True))

def package():
    assert dp.load() and read('mcp-policy')['status']=='PASS'
    verification=json.loads((ROOT/'gui_delegate/reports/verification.json').read_text('utf-8'))
    assert verification['controlled_checks']['status']=='PASS' and verification['live_mcp']['status']=='PASS'
    native=json.loads((ROOT/'gui_delegate/reports/native.json').read_text('utf-8'))
    assert all(native[k]['status']=='completed' for k in ('native_cjk','file_dialog','save_dialog'))
    from credentials import resolve_key
    key,_=resolve_key();secret=key.encode() if key else None
    suffixes={'.py','.js','.cmd','.md','.json','.html','.txt','.yaml','.toml','.lock'}
    excluded={'private','__pycache__','skills-installer','codex-schema','node_modules','private-profile','backups','.venv'}
    state_names={'install-state.json','registration.json','deployment.json'}
    files=[p for p in ROOT.iterdir() if p.is_file() and (p.suffix in suffixes or p.name in ('.env.example','.gitignore'))]
    for directory in ('tests','gui_delegate','reports','docs'):
        files += [p for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in suffixes and
            not any(part in excluded for part in p.relative_to(ROOT).parts) and p.name not in state_names and
            not p.name.startswith(('initial-','codex-hook-deny','codex-hook-shell','codex-hook-name'))]
    archive=ROOT.parent/'jev-gui-delegate-calibrated-source.zip'
    def scrub(v):
        if isinstance(v,dict):return {k:('[redacted task token]' if k in ('resume_token','token') else scrub(x)) for k,x in v.items()}
        if isinstance(v,list):return [scrub(x) for x in v]
        if isinstance(v,str):return re.sub(r'jev-fallback:[a-f0-9]{64}','jev-fallback:[redacted]',v)
        return v
    count=0
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(set(files)):
            if p.name in state_names:continue
            if p.name=='package.json' and 'fixtures' not in p.relative_to(ROOT).parts:continue
            raw=p.read_bytes()
            if secret and secret in raw:raise RuntimeError('Configured secret in a delivery file; packaging aborted')
            if p.suffix=='.json':
                data=json.loads(raw);clean=scrub(data)
                # Keep evidence bytes stable: the persisted policy binds their SHA256.
                if clean!=data:raw=json.dumps(clean,ensure_ascii=False,indent=2).encode()
            z.writestr(p.relative_to(ROOT).as_posix(),raw);count+=1
    result={'status':'PASS','source_files':count,'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'configured_secret_found':False,'session_tokens_redacted':True,'custom_file_metadata_added':False,
        'excluded':['venv','credential store','private DPAPI envelopes','raw session jsonl','browser profiles','node_modules','installation/rollback ownership state'],
        'portable_claim':False,'host_setup_and_regression_required':True}
    write('package',result)
    manifest=codex_home()/'jev-integration.json';backup(manifest);d=json.loads(manifest.read_text('utf-8'))
    d['gui_delegate'].update(source_archive=str(archive),calibration_package_report=str(BASE/'package.json'),
        calibration_verification={'controlled':verification['controlled_checks'],'mcp_15_steps':'PASS','native_cjk_open_save':'PASS'})
    safe_write(manifest,json.dumps(d,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=True,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['report','package']);args=p.parse_args()
    report() if args.action=='report' else package()
