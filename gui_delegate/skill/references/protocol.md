# 常用任务契约与结果

本页描述 Jev 控制器的当前契约格式和实现限制，不是整个 GUI 任务的范围限制。优先委派，先做支持的恢复或分段；确认当前执行器无法表达或执行所需部分时，才按 SKILL.md 局部接手。

使用本地 JSON 契约，避免将同一完整对象在多个工具调用间重复传递。原生 MCP run_task 优先 `{"contract_path":"C:/absolute/contract.json"}`，兼容旧顶层内联字段。Chrome 始终走 [chrome.md](chrome.md) 的会话网关。两种入口都保留严格 schema、权限、预算、实时观察与后置校验，不接受任意代码/选择器/坐标。

必要字段：goal、target、scope、steps、success。省略有默认值的字段；不要展开 model_dump 后的空字段或全部默认值来构造新任务。完整 schema 在清单 gui_delegate.schemas/contract.json，仅查询实际用到的定义。

- target：browser 用 connection:"official_chrome"、url；已有标签加 tab_id。windows 用 hwnd、process_id、executable、window_title 的真实当前身份。不能凭标题猜窗口；没有身份证据则先补证据。
- scope：actions 为本任务操作白名单；origins 为协议+主机+端口；programs/read_roots/write_roots 按任务授权填入。网页不能扩大范围。
- inputs：`{引用名:{value:用户提供值}}`，文件另加 kind:"path"；pending:true 表示需 Astra/用户补文本，captured:true 表示本地观察产物，初始 value:""。秘密禁止发 Jev；契约不得含密码/验证码/密钥。
- steps：1–120 个 `{id,intent,op,target?,input_ref?,after:[Predicate]}`。op 从实际能力白名单选择；控件 target 为 `{role,name?,automation_id?,frame_url?,group?,semantic?:false}`。准确匹配由代码完成；semantic:true 才需要从实时候选作语义判断。将可能给 Jev 的非秘密标签放 jev_label_allowlist；不是每步由 Astra 挑候选。
- after 与最终 success 都是可验证谓词；常用 `{kind:exists|absent|value|text|checked,target,equals?或input_ref?}`；url 用 equals 完整 URL，file 用 path input_ref。填写必须校验实际值，点击必须校验真实效果。read/wait 也须有已观察的控件和可验证条件。
- 本地低风险变更加 effect:"local"；submit/send/publish/pay/delete/overwrite/account 等副作用只有明确具体用户授权才允许；按需查详细协议 Authorization，不猜测授权。Enter/Space 可能提交，须相应授权。
- 可选 budget 按已知子流程合理设置，不通过降低质量阈值节省调用；默认 steps:40、jev_calls:8、seconds:180、reobservations:3、no_progress:3。stop_conditions 默认空。`optional_if` 只在有证据的已满足条件下跳过该步，不是通用规划语言。

最小两步示例（只展示字段；换成已授权目标及真实标签）：

```json
{"goal":"填写并核对草稿，不提交","language":"zh","target":{"driver":"browser","connection":"official_chrome","url":"http://127.0.0.1:8000/"},"scope":{"origins":["http://127.0.0.1:8000"],"actions":["fill","check"]},"inputs":{"note":{"value":"用户提供的文本"}},"steps":[{"id":"fill","intent":"填写草稿","op":"fill","target":{"role":"textbox","name":"备注"},"input_ref":"note","effect":"local","after":[{"kind":"value","target":{"role":"textbox","name":"备注"},"input_ref":"note"}]},{"id":"check","intent":"勾选草稿选项","op":"check","target":{"role":"checkbox","name":"草稿"},"effect":"local","after":[{"kind":"checked","target":{"role":"checkbox","name":"草稿"},"equals":true}]}],"success":[{"kind":"value","target":{"role":"textbox","name":"备注"},"input_ref":"note"},{"kind":"checked","target":{"role":"checkbox","name":"草稿"},"equals":true}]}
```

浏览器入口在校验时绑定真实标签身份；独立 Python Contract 校验已有 Chrome 契约需要明确 tab_id。参考模板 gui_delegate/examples.py 是合成测试，不表示真实网站天然具有这些控件。

结果保留 status、completed、remaining、evidence_refs、usage、escalation_reason、resume_token、verification。completed + 所有 verification.passed:true 即完成，不再读源码/解密全部观察。usage 包括真实 Jev 请求/token/重试、动作/观察次数、Astra 决策补足次数；拿不到的 Astra token 为 unavailable。零 Jev 调用是确定性委派，不冒充模型判断。

resume_task 用 resume_token；继续暂停任务加 continue_task:true；补文本用 input_updates:{原pending引用:新值}；局部选择用 decision_override:{step_id,control_id,observation_fingerprint}，只能选 escalation_context 中当前候选。二者一次只用一个。用户接管须实际释放后 user_released_control:true。running 时长等待而非高频轮询，已完成任务不用 resume。cancel_task 核实在途动作后停止，不重放提交。

仅需要高级功能或恢复时查 [protocol-advanced.md](protocol-advanced.md)：命名 surfaces/复制传值/拖放/本地剪贴板、Authorization、Preferred GUI recovery、Official Chrome 0.3 additions。阈值和模型策略已持久化；常规使用不读校准历史。没有结构化观测/未知长期流程/缺文本等仍可能升级，正确升级不等于 GUI 独立支持。
