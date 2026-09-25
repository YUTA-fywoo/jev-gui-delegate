# 用户 Chrome 的任务级委派

当前默认：用户已经连接的 Chrome 官方插件（Browser Use API）。不复制配置、Cookie，不访问插件私有接口，不开调试端口。只有当前 Codex 浏览器工具会话能持有官方 Browser/Tab 句柄；自建 MCP 不冒充有这个能力。

## 入口与最小调用

1. 从 `jev-integration.json.gui_delegate.official_chrome` 取得模块路径、状态和支持范围。需首次选择时遵循 `cua_repl` 的浏览器选择规则，通过只读清单确认 Chrome；用户点名或已选择的 Chrome 绑定优先，勿每轮重新选择。可用的只读准备调用包括： `await cua.getState();`、`await cua.listBrowsers();`、`await cua.rewriteDocumentation();`、`let chrome = await cua.getBrowser({id:"实际清单 ID"});`。准备只取绑定所需身份，不逐轮展开完整界面；后续观察优先由执行器完成。
2. 按 protocol/schema 准备契约，`target` 增加 `connection:"official_chrome"`、`driver:"browser"`、精确 `url`。URL 与标签 ID 来自用户指定或官方清单；不能猜测个人标签。规划需要结构时优先提交局部 read/export 观察契约；执行中由控制器读取和验证。仅当执行器无法提供必要信息时，Astra 补充局部观察或判断，然后恢复委派。
3. 将契约保存为本地绝对路径 JSON。委派时在 `mcp__cua_repl.js` 推荐使用下面的标准调用（`chromeConnection` 是已经选定的 Chrome 对象，替换为实际绑定名；模块地址使用清单中的实际路径）。示例中的 request 使用 JSON 字面量，网关输出精简结果。保留标准入口以便维护；接手时可直接使用当前官方工具，无需绕行旧适配器。

```js
let jevStrictGateway = await import("file:///C:/jev/jev-bridge/gui_delegate/chrome_gateway.mjs?release=0.4.3");
```

上面是首次初始化单独调用；后续每次只调用已绑定的入口（不要重新导入）：

```js
await jevStrictGateway.dispatch({browser:chromeConnection,request:{"operation":"run_task","contract_path":"C:/absolute/path/contract.json"}},nodeRepl);
```

提供 `target.tab_id` 时，控制器核验后认领当前清单中的该标签，不导航/刷新它；省略则在同一个用户 Chrome 新建目标页。URL 和标签 ID 必须来自用户或观察证据，不猜个人标签。不接受任意页面代码或选择器。

恢复/取消/诊断保持同一标准调用，request 换成 `{"operation":"resume_task","arguments":{"resume_token":"实际 token","continue_task":true}}` 等。固定 let 变量 jevStrictGateway 保留同一模块实例和当前管道；不要仅反复动态导入（本宿主跨工具调用不保证复用模块缓存）。运行中清理和终结清理由执行器自动执行，不再依赖额外关闭调用。兼容入口 `close_created_tab` 可在已终结任务上再次检查清理，arguments 仅含 resume_token；不会强行关闭受保护页面，也不会重试结果不明的关闭。观察导出是合法确定性操作，但不能把反复单步导出称为 Jev 内部决策。

源代码里的 `tests/chrome_contract.py` 和 `fixtures/chrome-workflow.html` 给出完整合成例子；测试网页服务需临时启动，报告中旧端口不是长期服务。正式任务使用当前目标 URL 和用户的真实授权。

## 内部执行与恢复

JS 适配器通过匿名标准输入/输出管道启动现有 Python worker。权限、单执行锁、确定性候选、Jev 调用、后置验证、加密检查点都复用原控制器。JS 仅执行本地白名单指令，网页/模型不能提交代码、选择器或任意快捷键。stdout 是协议，完整状态只留本机。Jev 使用同一凭据管理器条目，输入值不发给 Jev。

- `run_task` 通常一次完成；每 35 秒在安全检查点暂停，返回 `CHROME_SEGMENT_COMPLETE`。同一活跃会话中通过标准网关 `resume_task` 继续；这是分段，不是逐步决策。
- 待文本/模糊语义等问题使用原 `input_updates/decision_override` 协议，再通过**同一模块实例**恢复。
- `CHROME_SESSION_INTERRUPTED` 或实际用户接管后，不自动重抢；得到用户释放后才以 `user_released_control:true` 恢复。官方插件权限、停止按钮和标签所有权继续有效。
- 标准网关的 `cancel_task` 和 `diagnose_task` 可用；原 MCP 的取消与诊断也能访问同一任务记录。暂停的标签会标记待接管。
- 会话结束/REPL 重置后，旧 JS 管道不能冒充已恢复；返回 `CHROME_SESSION_REBIND_REQUIRED`，先核对真实结果后另建剩余任务，尤其不得重放不确定提交。独立 CLI/MCP 对官方 Chrome 返回 `CHROME_CODEX_SESSION_REQUIRED`，不是偷偷切换 Edge。
- `gui-stop.cmd` 为全局急停；`jev-chrome-rollback.cmd` 停用新的 Chrome 委派，`jev-chrome-restore.cmd` 恢复。停用不关闭 Chrome、不移除插件、不取消已经运行的任务；运行中任务使用 cancel/急停。

## 已接入与实测边界

当前保留的 Chrome 能力在用户 Chrome 中实际通过：表单、菜单、表格、分页、多步界面、中文日文多行；允许域的跨源 iframe、开放 Shadow DOM；滚动、滑块、双击、悬停和页内拖放；单/多文件选择、合成文件实际上传、下载事件与本地文件完成校验；新建/切换/关闭本任务标签、前进/后退/重载、命名多页面与本地传值；截图、日志、页面资源、结构化页面导出、会话文本剪贴板和临时视口尺寸/恢复。

固定 CDP 鼠标输入也通过官方插件、限定标签页执行，坐标仅从刚观察的控件计算；不接受任务或 Jev 的任意坐标/命令。iframe 内的坐标手势尚未接入，语义填表/点击已验证。剪贴板为官方浏览器会话剪贴板；`paste` 使用当前控件 fill，不写 Windows 系统剪贴板。

当前宿主的 JS 原生 alert/confirm/prompt 关闭接口出现焦点初始化超时。包含 `dialog_accept/dialog_dismiss` 的任务会在打开任何标签或发出动作前返回 `CHROME_JS_DIALOG_HOST_BLOCKED`，留有本地诊断任务记录，不签发额外路由授权；Astra 仅可在官方接口实际可用且不重复挂起时处理；否则让用户处理弹窗。不要重复调用或自动开启新测试弹窗。网页内部的 HTML 对话框仍可按普通 DOM 操作。普通 `content.export()` 实测被 Chrome 后端拒绝；可明确选择 `export_format:"dom_snapshot"` 保存结构化页面，不能声称它等于完整网页/PDF 导出。

Google Workspace 导出、YouTube 字幕导出仅完成适配，未以真实账户验收。富格式剪贴板、历史检索、开发调试命令、截图后的视觉推理仍由当前 Astra 按实际官方 API、用户范围和插件权限处理。Jev 不理解图像，也不能执行任意 JS/CDP。不要为这些操作安装另一个付费模型、扩大权限或修改插件。

完整能力映射、明确的未测项和删除状态见 [chrome-capabilities.md](chrome-capabilities.md)。旧隔离 Edge 驱动已移除；Windows UIA、Jev 客户端、阈值和历史证据保留。低置信、失配或临时错误先按当前证据修复并恢复委派；不能不加诊断就判为能力缺失。确认无受支持路径或合理修复仍无法继续时，Astra 才接手该部分，随后回到 Jev；无需能力缺口令牌或接管时限。实际宿主或系统权限问题仍按当前工具规则处理；接手是否成功以验证结果为准。

指定标签 API 不注入全局鼠标键盘；用户与自动化同时编辑同一页面仍可能冲突，真人并行点击、官方停止按钮与跨对话检查点恢复未作本次实测。授权域检查不等于拦截页面所有第三方子资源。页面资源打包只接收已观察且属于允许域的资源；CDN 需列入任务授权范围。登录、验证码、系统权限仍交给用户。

最新证据：`C:/jev/jev-bridge/gui_delegate/reports/chrome-complete-20260923/REPORT.md`。配置/源码更新后新任务即可使用；新 Codex 会话能重新加载用户 skill 和 MCP 的新增 schema。会话重置后不能恢复旧 JS 管道，需要重新观察再规划剩余任务，不能重放结果不明的提交。

## 标签生命周期

每次真实后置验证和检查点保存后，清理后续步骤及最终成功条件不再需要的本任务临时页；命名页面在最后一次使用后即可关闭。需要后续 `switch_tab`、显式 `close_tab`、标签数量断言的页面会保留，最终成功验证之前不关闭验证所需页面。运行期每任务新建页同时最多 8 个，达到上限返回 `CHROME_TASK_TAB_LIMIT`。优先利用安全清理、页面复用或按批次规划；不以创建重复任务无界堆积标签，也不因此直接接手全部任务。

执行器记录明确创建的页面身份；不根据网址、标题或网页指令认领个人标签。关闭前重新读取并比较页面状态。个人页、`mark_deliverable`、`mark_handoff`、敏感控件、编辑过的表单、用户接管/状态变化、弹窗和关闭结果不明的页保留。自动打开但无法证明归属的弹出页也不盲目关闭。主任务无法判断仍需不需要时应规划剩余步骤，不能让 Jev 任意猜测关闭目标。

正常完成、已核对状态的取消和失败会清理安全临时页；急停、用户接管或动作结果不明时停止清理。进程/宿主直接退出后无法保证自动收尾，必须报告未清理项，不能声称已关闭。暂停保留恢复所需页。

`usage` 增加 `tabs_created`、`tabs_closed_during_run`、`tabs_closed_at_end`、`tabs_closed_explicitly`、`tabs_peak_owned`、`tabs_retained`、`tabs_cleanup_deferred`；网关 `tab_cleanup.retained` 给出标签 ID 和保留原因。清理使用确定性代码，不新增 Jev 请求；只对待关闭页面进行额外状态核验。
