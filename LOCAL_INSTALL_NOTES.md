# Jev 本机接入

此目录是本机自建 `jev-bridge` MCP 服务，不是 TypeSafe 发布的 MCP 插件。Codex 原有 Astra 主模型、登录、提供商与其他 MCP 配置保持不变。第二阶段已增加有边界的 GUI 连续执行器和用户级 skill，详见 [GUI 交付](gui_delegate/README.md) 与 [支持矩阵](gui_delegate/SUPPORT.md)。它是已实测的有限范围原型，不是任意 GUI 的全面接管。

## 最短用法

运行 `C:\jev\jev-bridge\verify.cmd`：用目录内合成数据分别直接调用 Jev 和通过实际注册的 MCP 子进程调用 Jev，并更新验收报告。每条路径只提交一次包含 Choice、Noul、Score 的请求；网络问题最多重试两次。没有密钥会报告 `BLOCKED`，不会伪造成功。

`health.cmd` 仅检查本地就绪状态，不发起付费请求。`verify.cmd --all` 还会运行故障、注册/回滚、Codex 发现和独立 GUI 测试。原生测试只操作新建测试窗口；Chrome 测试必须在当前 Codex 浏览器工具会话中运行。

## 密钥

`set-key.cmd` 打开本机掩码输入窗口，保存到当前用户 Windows 凭据管理器，目标名为 `Codex/jev-bridge/TYPESAFE_API_KEY`。不要把密钥发到聊天或保存到项目文件。

客户端仅读取进程 `TYPESAFE_API_KEY` 和上述命名凭据，前者优先。MCP 配置转发该环境变量，并可直接读取当前 Windows 用户凭据，因此不依赖启动 Codex 时的旧环境。`.env.example` 无真实值，程序不会自动加载 `.env`。真实 MCP 认证是否完成以报告中的 `mcp_authenticated_jev` 为准。

## 文件与配置

- `jev_client.py`：官方 `typesafe-sdk` 异步客户端封装，严格验证输入、全部答案与 usage。
- `server.py` / `start.cmd`：stdio MCP，保留 `health`、`capabilities`、`evaluate`，GUI 安装启用时增加 `run_task`、`resume_task`、`cancel_task`、`diagnose_task`；stdout 只传协议。
- `cli.py` / `example.json`：最小调用与合成测试数据。示例：`.venv\Scripts\python.exe cli.py smoke`。
- `settings.json`：请求模型、模型版本预期、超时和重试限制，无密钥。
- `requirements.lock`：全部依赖锁定版本及实际安装轮子的 SHA-256，适用于原生 Windows x64 / Python 3.12。
- `reports/`：直接请求、MCP、GUI、故障、Codex 发现和回滚测试结果；`sources.json` 记录来源。
- `logs/usage.sqlite3`：允许列表式日志，只保存随机请求编号、时间、状态、尝试次数、模型版本和 usage，不保存 state、questions、answers、HTTP 头或异常正文。
- `%USERPROFILE%\.codex\jev-integration.json`：下一阶段读取的无秘密交接清单；若设置 `CODEX_HOME`，程序使用它。

运行时使用本机 Codex 自带 Python 3.12.14 创建的隔离 `.venv`，不改变系统 Python。该基础 Python 的目录若被未来的 Codex 更新移除，应使用受支持的 Python 3.12 重建虚拟环境并运行 `install.py`。

## 限制与版本管理

单次最多 32 个问题、JSON 最多 64 KiB、嵌套最多 16 层；这些是本地保守限制，不等于厂商 token 配额。HTTP 操作超时 10 秒，总截止时间 40 秒；仅 SDK 负责重试，最多 3 次 HTTP 尝试，重试预算 25 秒，遵守 Retry-After。无效输入、缺失密钥、401/403/422 不重试。网络超时可能已产生服务端用量，本地只汇总已收到的 usage，未声称获知全部账单。

响应必须包含实际 `jev-x.y.z` 模型版本。第一次成功会记录别名对应版本；后续版本变化返回 `MODEL_VERSION_CHANGED`。完成校准后先运行 `.venv\Scripts\python.exe manage.py pin --model 实际版本`，该命令只允许已经真实观察到的版本，并备份配置。它不会把校准状态自动标为完成。若使用校准阈值，必须在固定版本、状态结构、问题和实际任务数据上验证，再显式设置 `calibrated`。

`evaluate` 不执行代码、按键或点击。第二阶段的 `run_task` 使用本地驱动执行经过约束的动作，将新鲜的最小语义状态交给 Jev，把不确定或失败情况交给 Astra。不能把概率当作操作授权。

## GUI 基础

网页通过用户 Chrome 的官方插件和当前 Codex Browser Use 会话执行。旧隔离 Edge 驱动已移除；不复制个人配置/cookie、不暴露调试端口。本地 Playwright 不再是运行依赖；已有轮子仅保留供历史恢复，没有自动卸载系统浏览器。

pywinauto 0.6.9 的 UIA 后端已在当前 Windows 交互会话测试读取原生窗口的 Edit/Button/Text 控件、设置文本、调用按钮，并验证真实键鼠输入。Windows 虚拟环境启动器与实际窗口进程 PID 不同，测试程序已正确处理。

系统 Windows PowerShell 的脚本执行限制保持不变；所有交付入口为 CMD/Python。没有安装 OCR、视觉模型或其他生成式模型。Canvas、图片内容、远程桌面、无辅助功能控件，以及提权/安全桌面尚未覆盖。

## 重装、卸载和回滚

`install.cmd` 可重复运行，按哈希锁定文件安装隔离依赖，复用已有官方 skill，并检查 MCP 同名冲突。官方 skill 仅通过 `npx skills@1.7.0 add typesafe-ai/skills --skill typesafe-ai --agent codex --global --yes` 安装，禁用安装器遥测和 npm 生命周期脚本，不安装 Claude 插件。

`uninstall.cmd` 只移除本次创建、且未被后来修改的 `jev-bridge` 配置。`uninstall.cmd --delete-credential --remove-skill` 还会删除本集成命名凭据与未修改的官方 skill；不移除无关依赖，也不递归删除项目。默认保留 skill 和凭据供重装复用。

配置每次修改前备份到实际 `CODEX_HOME\backups\jev-bridge`。回滚按配置项移除，保留安装后新增的无关设置；不整文件覆盖回旧配置。注册幂等性、备份、同名冲突与保留后来无关改动已有隔离测试。

## 官方核验来源

- [TypeSafe 官方 skill](https://github.com/typesafe-ai/skills)，安装时提交 `65a39f393687675ce170e6094757de20370365b9`。安装副本与官方正文一致，仅文件换行格式不同。
- [HTTP API](https://docs.typesafe.ai/api)、[Python SDK](https://docs.typesafe.ai/sdk/python)、[模型](https://docs.typesafe.ai/models)、[Coding agents](https://docs.typesafe.ai/introduction/coding-agents)。网页索引工具读取 llms.txt 失败后，已用本机 HTTPS 直接获取成功。
- [Codex Skills](https://developers.openai.com/codex/skills/)、[Codex MCP](https://developers.openai.com/codex/mcp/)，并核对本机 Codex 命令帮助和生成的协议 schema。
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)、[Playwright](https://playwright.dev/python/docs/browsers)、[pywinauto](https://pywinauto.readthedocs.io/en/latest/getting_started.html)。

新 Codex 进程已验证能发现 skill 和 MCP 工具；随后当前对话也已加载工具，并通过原生 MCP `evaluate` 完成真实云端调用，无需为本次接入另开对话。具体 PASS/BLOCKED 状态和已验证的对话 ID 以 `reports/acceptance.json` 及 `CODEX_HOME/jev-integration.json` 为准。
