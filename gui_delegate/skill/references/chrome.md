# 用户 Chrome：优先委派入口

网页 GUI 优先使用用户已连接的官方 Chrome Browser Use API 和本地 Jev 控制器。首次遵循 cua_repl 的浏览器选择规则，复用已有绑定。本地 MCP 无法单独持有官方浏览器会话。

按 [protocol.md](protocol.md) 写本地契约。target 使用 driver:browser、connection:official_chrome 和当前 URL；已有标签加观察得到的 tab_id，认领但不刷新。不填 tab_id 则在用户 Chrome 新建页。规划所需结构优先通过委派局部 read/export 获取；仅当执行器无法提供必要信息时补充最小范围直接观察。

首次初始化（本机路径；其他安装以清单为准）：

```js
let jevStrictGateway = await import("file:///C:/jev/jev-bridge/gui_delegate/chrome_gateway.mjs?release=0.4.3");
```

推荐保留如下标准入口；变量名中的 Strict 是现有接口名称，不代表仍启用强制拦截：

```js
await jevStrictGateway.dispatch({browser:chromeConnection,request:{"operation":"run_task","contract_path":"C:/absolute/path/contract.json"}},nodeRepl);
```

恢复／取消／诊断可替换 request 的 operation 为 resume_task/cancel_task/diagnose_task，arguments 带 resume_token。继续暂停任务加 continue_task:true；补文本用 input_updates，补局部选择用 decision_override。恢复时保留同一模块与会话，避免重放结果不明的提交。

超过 35 秒返回 CHROME_SEGMENT_COMPLETE 时，通过同一网关 resume_task 接续原任务，无需重新读取页面或重规划。优先一次委派完整子流程；连接错误、低置信和控件失配先诊断并恢复。确认当前执行器无法完成所需部分后，Astra 才局部接手，后续仍回到 Jev；无需能力缺口令牌、精确调用绑定或 120 秒时限。

控制器会在验证后清理安全的自建临时页，保留个人页、编辑过的页面、交付／接管页以及结果不明的页面。单契约最多 8 个同时自建标签属于实现限制，优先按页面批次分段并利用已有清理完成更多页面的任务；不把标签数限制当作接手理由。用户停止或接管后不抢回控制。

接手仍使用当前官方浏览器接口，核对实际页面状态后接续剩余工作。已适配但未实测的操作仍可在授权范围内委派并验证；确实未封装且无受支持等价路径的部分才需接手。能力表描述的是执行器和宿主现状，不是 GUI 任务禁区。

按需参阅：[能力矩阵](chrome-capabilities.md)、[功能细节](chrome-details.md)、[协议与恢复](protocol-advanced.md)。
