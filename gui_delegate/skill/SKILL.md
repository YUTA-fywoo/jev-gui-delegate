---
name: jev-gui-delegate
description: 所有网页和原生桌面 GUI 优先委派 Jev，减少 Astra token；可恢复问题先恢复委派，确认当前执行器做不到的部分才由 Astra 接手。普通问答、代码编辑及非 GUI 工作优先可靠 API/CLI。
---

所有 GUI 都优先交给 Jev，不按网站、应用、控件类型或任务长度预先排除。目标是减少 Astra 的界面读取、判断和逐步操作，同时保持执行质量。尽量一次委派完整子流程：确定性动作由本地控制器执行，语义选择用 Jev。Astra 只承担当前执行器无法承担的规划、内容生成、判断或操作。

- 首次只读实际 CODEX_HOME/jev-integration.json 的 gui_delegate 必要路径；本机为 %USERPROFILE%/.codex。常用契约见 [protocol.md](references/protocol.md)；其他资料、完整 schema 和日志按当前问题读取，不重复加载整套文档。
- 网页优先通过 [chrome.md](references/chrome.md) 的 chrome_gateway.mjs 复用用户 Chrome 官方插件；原生 Windows 优先 jev-bridge.run_task({contract_path:绝对路径})，MCP 未加载时用清单中的同一 Python CLI。绑定只取必要的标签／窗口身份，已有有效绑定直接复用。
- 规划需要界面信息时，优先执行器的局部 read/export 和精简结果，不让 Astra 每步读屏或挑选 Jev 能判断的候选。执行器无法提供必要观察时，Astra 才补最小范围观察；补完继续委派。
- 缺文本用 input_updates，局部语义不明可用现有候选和 decision_override；Astra 只补执行器缺少的内容／判断，点击填写仍交回执行器。低置信、控件失配、连接或临时错误本身不等于无能力：先利用现有重观察／恢复，或做有依据的修复。失败原因未变化时不重复同一请求，不为维持委派死循环。
- 只有当前能力说明或实际诊断表明确实无法完成所需部分（含合理修复后仍不可用），才用当前官方 GUI 工具局部接手；无需故意制造失败或取得 executor_capability_gap、grant、bind-fallback、调用绑定或 120 秒令牌。核对上一步真实状态后只完成受阻部分，后续可执行步骤立即回到 Jev。
- running / CHROME_SEGMENT_COMPLETE 沿原入口等待和接续，不额外观察或重规划。契约步数、调用预算和标签数是单次实现参数；按任务合理设置、分段并复用进度，不据此改用 Astra 或降低阈值。未知分支只规划下一段，已适配但未实测不自动排除委派。
- completed 且实际成功条件验证通过，Astra 核对精简结果即可交付；不例行再截图、读页面或解密全部证据。只有验证不足、结果不明、新疑点或用户明确审计时追加必要核验。不重放结果不明的动作。
- 不为节省 token 降低 Jev 模型／置信阈值、截掉候选、跳过新鲜身份检查或真实后置验证。确定性动作不强行调用模型；控制器执行、真实 Jev 请求和 Astra 补充／接手分别记录，零 Jev 请求如实报告。

本技能与 prefer_jev 非拦截 Hook 不增加审批手续；现有用户授权、系统／工具权限、用户接管和急停仍有效，不自动抢回控制。取消用 cancel_task；急停为 C:/jev/jev-bridge/gui-stop.cmd 或 Ctrl+Alt+F12。控制器按实际状态清理临时标签，保留个人、编辑、交付、接管或结果不明的页面。

当前策略见 gui_delegate/routing-policy.json。已启动 MCP 可能缓存旧 routing 描述，重连后刷新；不因旧描述恢复已取消的令牌手续。模型、控制器和宿主的能力缺口须分开说明，不把无法封装某项操作说成 Jev 模型质量差，也不声称所有 GUI 已独立支持。
