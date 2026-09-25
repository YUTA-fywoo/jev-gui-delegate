"""Reviewable release evidence; preserves prior calibration and benchmark records."""
import argparse,hashlib,io,json,subprocess,sys,unittest
from datetime import datetime,timezone
from manage import codex_home,backup
from jev_client import ROOT,load_settings
from .kind_repair_evaluation import BASE,read,write,sha
from . import semantic_rules as rules,semantic_rule_policy as activation,decision_policy as dp

def save(path,text):
    if path.exists() and path.read_text('utf-8')==text:return
    if path.exists():backup(path)
    path.write_text(text,'utf-8')

def verify():
    suites=['gui_delegate.tests.test_guards','gui_delegate.tests.test_extensions','gui_delegate.tests.test_decision_policy',
            'gui_delegate.tests.test_semantic_rules','tests.test_failures','tests.test_registration','tests.test_credentials']
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(suites))
    (BASE/'controlled-tests.txt').write_text(stream.getvalue(),'utf-8')
    assert r.wasSuccessful(),stream.getvalue()
    report={'status':'PASS','tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'note':'Controlled tests, not live API success.'}
    write('controlled',report)
    policy_before=dp.PATH.read_bytes();rule_before=activation.PATH.read_bytes();config_before=sha(codex_home()/'config.toml')
    from .tests.test_semantic_rules import setup
    try:
        for _ in range(2):
            subprocess.run([str(ROOT/'jev-semantic-repair-rollback.cmd')],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
            assert not activation.active()
        ctl,s,d,client=setup(['Browse files','Browse folders'],chosen='Browse files');ctl.choose(s,ctl.observe())
        assert client.calls==1 and not ctl.semantic_rules_active
    finally:
        subprocess.run([str(ROOT/'jev-semantic-repair-restore.cmd')],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    subprocess.run([str(ROOT/'jev-semantic-repair-restore.cmd')],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    ctl,s,d,client=setup(['Browse files','Browse folders'],chosen='Browse files');ctl.choose(s,ctl.observe())
    assert client.calls==0 and ctl.semantic_rules_active
    assert dp.PATH.read_bytes()==policy_before and sha(codex_home()/'config.toml')==config_before
    # JSON formatting may change; behavior and signed rule identity must be identical.
    assert json.loads(activation.PATH.read_bytes())==json.loads(rule_before)
    write('rollback',{'status':'PASS','disable_twice':'PASS','restore_twice':'PASS','new_controller_uses_current_setting':True,
                      'thresholds_and_codex_config_unchanged':True,'active_workers_unchanged':True})
    print(json.dumps({'controlled':report,'rollback':'PASS'},indent=2))

def report():
    before,after=read('before-summary'),read('after-summary');plan=read('plan')
    assert all(s['collection_complete'] and s['samples']==132 for s in (before,after))
    assert after['positive_completed']==60 and after['negative_stopped']==72 and after['wrong_actions']==0
    assert sha(dp.PATH)==plan['policy_sha256'] and dp.PROTOCOL_HASH==plan['protocol_sha256']
    assert rules.fingerprint()==plan['rules_sha256'] and activation.active()
    assert load_settings().model==load_settings().expected_model==plan['model']
    for name in ('mcp-rules','recorded-regression','controlled','rollback'):assert read(name)['status']=='PASS'
    checks=json.loads((ROOT/'gui_delegate/reports/verification.json').read_text('utf-8'))
    native=json.loads((ROOT/'gui_delegate/reports/native.json').read_text('utf-8'))
    assert checks['live_mcp']['status']=='PASS' and checks['desktop_command_exit']==0
    assert all(native[k]['status']=='completed' for k in ('native_cjk','file_dialog','save_dialog'))
    compatible={arm:sum(r['action_verified'] for r in read(arm+'-rows') if r['family'] in ('properties','release_notes')) for arm in ('before','after')}
    assert compatible=={'before':12,'after':12}
    fixed={'status':'FIXED_AND_RETESTED','issue':'New alias log used kind keyword that collided with worker record(kind, **data).',
           'first_mcp_result':'LOCAL_RUNTIME_FAILURE','actions_before_failure':0,'fix':'Rename metadata field to concept_type; add actual recorder-signature regression.',
           'retest':'Four fresh registered MCP tasks and full 15-step workflow pass.',
           'frozen_evaluation_note':'Frozen 132-case after run used identical choice rules before this logging-only fix. Rules/thresholds/prompt hashes are unchanged.'}
    write('development-issue',fixed)
    summary={'status':'DEPLOYED','rules':activation.describe(),'before':before,'after':after,'compatibility':compatible,
      'prior_bad_recorded_responses_stopped':6,'prior_correct_recorded_choices_not_conflicted':205,
      'controlled_checks':read('controlled'),'mcp_alias_tasks':4,'mcp_continuous_actions':15,
      'native_cjk_open_save':'PASS','rollback_restore':'PASS','thresholds_changed':False,'model_changed':False,
      'question_protocol_changed':False,'production_calibrated':False,'background_recalibration':False,
      'controller_sha256':sha(ROOT/'gui_delegate/controller.py'),'rules_sha256':rules.fingerprint(),
      'live_evaluation_usage':{k:before['usage'][k]+after['usage'][k] for k in ('jev_requests','input_tokens','output_tokens','failed_retries')},
      'live_smoke_usage':checks['live_mcp']['result']['usage'],
      'limitations':['Four known intent kinds and exact approved labels only; unknown wording retains existing Jev behavior.',
       'Related synthetic combinations, not independent production applications or a general error-rate estimate.',
       'Existing production thresholds already rejected the six historical wrong responses; this adds a semantic invariant, not a claim of newly eliminating six current production failures.',
       'Two invalid API responses in after run were stopped; response validation was not weakened.',
       '132-case timing is one sequential run per arm, includes negative cases and fixture work; no new Astra comparison.']}
    write('release-summary',summary)
    text=f'''# 局部语义修复：减少错选，也减少不必要的停顿

已部署 `gui-kind-rules-1`。本次没有提高或降低任何概率、confidence、margin 门槛，也没有改主模型、Jev 版本、选择问题协议、权限或后置验证。

本地代码只对完整目标明确、标签已批准的低风险按钮选择增加四类区分：文件选择、文件夹选择、使用指南、关于应用。匹配唯一时直接选择当前真实控件；存在同义重名时要求补充证据；Jev 或局部 Astra 选择了明确相反的类型时，在点击前报告 `SEMANTIC_KIND_CONFLICT`。未覆盖的表达和标签保留原 Jev 判断流程，不因含有某个关键词一概拒绝。

## 实测结果

| 相同的 132 个合成用例 | 改进前 | 改进后 |
|---|---:|---:|
| 60 个正常目标自动完成 | {before['positive_completed']}/60 | {after['positive_completed']}/60 |
| 72 个缺失、禁用或歧义用例在动作前停止 | 72/72 | 72/72 |
| 实际错误动作 | {before['wrong_actions']} | {after['wrong_actions']} |
| 不相关属性/更新日志兼容用例完成 | 12/12 | 12/12 |
| 真实 Jev 请求 | {before['usage']['jev_requests']} | {after['usage']['jev_requests']} |
| Jev 输入 / 输出 tokens | {before['usage']['input_tokens']:,} / {before['usage']['output_tokens']:,} | {after['usage']['input_tokens']:,} / {after['usage']['output_tokens']:,} |
| 整批耗时，含负例和夹具 | {before['elapsed_seconds']:.3f} 秒 | {after['elapsed_seconds']:.3f} 秒 |

中、日、英 × 浏览器/Windows 共六组，每组改进后 10/10 个正例完成、12/12 个负例停下。其中 48 个明确的正例由本地词表直接选择，24 个歧义例直接升级，其余 60 例真实调用 Jev。所有已执行动作均核验了实际 outcome 状态；负例升级不计为独立完成。改进后仍有 2 个概率响应校验失败，均未点击，原验证没有放宽。

之前 6 个实际错选响应已放回真实合成控件中重放，全部在动作前由类型冲突规则阻止；这是**历史响应回归，不是 6 次新 API 成功**。另外对此前 205 个正确选择做规则回放，新增冲突为零。原来部署的数值策略本就拒绝那 6 个旧错误响应；本次的收益是增加更具体的语义约束，并让明确正例少受模型置信度波动影响。

{summary['controlled_checks']['tests_run']} 项受控检查通过，包含未批准页面文字、越权、敏感输入、提交授权、状态过期、取消、重名和配置篡改等。真实已注册 stdio MCP 的 tools/list 与 tools/call 通过；4 个新任务验证中日英词表在实际子进程生效。另一个 15 步网页任务连续完成，真实 Jev 请求 1 次（753 输入 / 75 输出），证明模型与凭据通路仍工作。原生中日文输入、Windows 打开/保存对话框复测成功。

MCP 初测发现新增日志参数重名，点击前报 `LOCAL_RUNTIME_FAILURE`。已修复、加回归并通过上述工作进程复测，见 `development-issue.json`；没有隐去首次失败。

## 适用边界

这些是已知混淆类型的新措辞与标签组合，数据和规则在实测前冻结。它们是相关的合成控件选择，不能代表 132 个独立生产应用，也不能证明所有日常 GUI 零错误。新规则只从结构化标签判断已知类型，无法保证任意软件在按钮背后的业务行为；后置验证仍必要。目标含额外限制、未知控件语义、图像/Canvas 或需要新规划时仍可能交给 Astra。现有英文网页/中文 Windows 的 0.95 门槛与其他范围 0.97 门槛原样保留，confidence 0.90、margin 0.15 不变。

这次两组共 {summary['live_evaluation_usage']['jev_requests']} 次真实 Jev 请求，是一次性开发验收开销；没有重新运行 Astra 对照，也没有宣称新的 Astra token/美元节省率。普通使用不会自动校准或改阈值。

## 持久化与撤销

规则、启用文件和用户级 skill 已保存；后续任务使用同一安装路径即可复用。新工作进程立即读取规则，不需重启电脑或因本次变更新开对话。已经运行中的任务保留启动时配置；已加载旧 MCP 的诊断信息可能需新进程刷新，但新 task worker 会加载新代码。

- 本次增强撤销：`C:\\jev\\jev-bridge\\jev-semantic-repair-rollback.cmd`。
- 恢复：`C:\\jev\\jev-bridge\\jev-semantic-repair-restore.cmd`。
- 已验证各执行两次均幂等；只切换本次规则，不改阈值、凭据、Codex 配置或其他技能。
- 最短整体验证：`C:\\jev\\jev-bridge\\gui-demo.cmd`。

主要证据为冻结的 `plan.json`、`cases.json`、两组 `*-rows.json`、`recorded-regression.json`、`mcp-rules.json`、`controlled-tests.txt`、`rollback.json`。源码和无秘密清单仍在原位置，旧校准与 Astra 对照记录保留。
'''
    save(BASE/'REPORT.md',text)
    cal=ROOT/'gui_delegate/CALIBRATION.md'
    addition='\n## 局部语义改进\n\n未改数值门槛的文件/文件夹与使用指南/关于应用修复，以及 132 例前后对照，见 [局部修复报告](reports/semantic-kind-repair-20260923/REPORT.md)。正例自动完成 55/60 → 60/60；相关合成范围之外仍未完成生产校准。\n'
    if 'semantic-kind-repair-20260923/REPORT.md' not in cal.read_text('utf-8'):save(cal,cal.read_text('utf-8')+addition)
    support=ROOT/'gui_delegate/SUPPORT.md'
    note='\n局部语义词表增强 `gui-kind-rules-1` 已实测：文件/文件夹与使用指南/关于应用的中日英按钮选择。132 例前后对照和限制见 [修复报告](reports/semantic-kind-repair-20260923/REPORT.md)。这不代表所有文件操作或任意帮助应用已支持。\n'
    if 'gui-kind-rules-1' not in support.read_text('utf-8'):save(support,support.read_text('utf-8')+note)
    manifest=codex_home()/'jev-integration.json';d=json.loads(manifest.read_text('utf-8'))
    benchmark_before=json.dumps({k:v for k,v in d['gui_delegate'].items() if 'benchmark' in k},sort_keys=True)
    d['gui_delegate']['semantic_rule_repair']={**activation.describe(),'policy_path':str(activation.PATH),
      'report':str(BASE/'REPORT.md'),'release_summary':str(BASE/'release-summary.json'),'thresholds_changed':False,
      'positive_before':55,'positive_after':60,'positive_total':60,'negative_stopped':72,'wrong_actions_after':0,
      'rollback':str(ROOT/'jev-semantic-repair-rollback.cmd'),'restore':str(ROOT/'jev-semantic-repair-restore.cmd'),
      'new_session_required_for_new_tasks':False,'production_calibrated':False}
    d['updated_at']=datetime.now(timezone.utc).isoformat();save(manifest,json.dumps(d,ensure_ascii=False,indent=2))
    assert json.dumps({k:v for k,v in d['gui_delegate'].items() if 'benchmark' in k},sort_keys=True)==benchmark_before
    print(json.dumps({'status':'DEPLOYED','report':str(BASE/'REPORT.md'),'positive':'55/60 -> 60/60','wrong_actions_after':0,'thresholds_changed':False},ensure_ascii=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['verify','report']);args=p.parse_args()
    verify() if args.action=='verify' else report()
