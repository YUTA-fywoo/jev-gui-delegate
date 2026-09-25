# Jev GUI Delegate 0.4.0

本机已安装可运行的有限范围原型：Astra 下发一次任务契约，本地控制器连续观察、产生候选、按需调用 Jev、检查权限、执行并核对真实结果。完成、出现缺口或达到预算后返回简短结果。没有在执行器内部调用 Astra 或其他生成式模型。

用户 skill 位于 `%USERPROFILE%/.agents/skills/jev-gui-delegate`。默认项目路径为 `C:/jev/jev-bridge/.venv`，依赖官方 TypeSafe skill 和 `jev-bridge`。下文“本机”及已验证状态指原开发环境；公开副本的安装与复核入口见根目录 README。

## 使用

新开一个 Codex 会话，直接说：**用 Jev 委派运行本机的合成 GUI 验收任务。** 新会话已实际验证自然语言路由、skill 发现和七个 MCP 工具。本次长会话的工具参数 schema 可能仍是旧版；新会话会取得跨窗口等新增参数，不需要重装或重启电脑。

`gui-demo.cmd` 输出 Chrome 会话所需的契约模板与入口，不冒充已执行。`verify-gui.cmd --live` 运行受控检查和实际注册 MCP 检查；`--desktop` 增加原生测试窗口。真实 Chrome GUI 按 `skill/references/chrome.md` 在当前官方插件会话一次委派。

自定义任务先看 `skill/references/protocol.md`、`schemas/contract.json` 和 `examples/workflow.json`。网页主路径是当前 Chrome 会话的 `chrome_delegate.run_task`；原生窗口使用 MCP，未加载 MCP 时执行 `.venv\Scripts\python.exe -m gui_delegate.cli run contract.json`。`resume` 可用 `--request-json repair.json` 传入待补文本或当前候选选择。不要把敏感值放在命令参数；完成后删除仅用于交接的本地修复文件。

## 代码与数据

`schema.py` 定义严格输入/观察/动作/检查点/结果；`controller.py` 实现内部循环；`chrome_driver.mjs` 提供官方 Chrome DOM，`drivers.py` 提供 UIA；`security.py` 约束程序、域名、路径、动作；`worker.py` 提供独占锁、超时与取消；`service.py` 是 CLI 与 MCP 共用入口。没有把模型文本交给 eval 或 shell。

实时控件树、任务输入、跨窗口捕获值和检查点只保存在 ACL 限制的 `private/`，由当前 Windows 用户 DPAPI 加密。默认无截图。`copy` 将观测到的非秘密值保存为本地引用；显式 `paste` 临时写入剪贴板、读回核对并在进入 GUI 驱动前恢复，再用控件语义接口填写。支持可完整备份的 HGLOBAL 格式；图片句柄等无法可靠备份时在修改前拒绝。普通事件日志只保留标量、ID、哈希和用量。运行 `python -m gui_delegate.cli cleanup` 清理超过七天且不活跃的任务；未建立后台定时任务。

密钥仍只取 `TYPESAFE_API_KEY` 或 Windows Credential Manager 的 `Codex/jev-bridge/TYPESAFE_API_KEY`。完整界面、输入值、密码/验证码/秘密均不提交 Jev；标签需明确允许列表。当前固定 Jev 为 `jev-1.13.0`。828 个真实合成评估用例支持两处适度放宽，已保存至 `decision-policy.json` 供后续对话复用；其他范围保留原值，`production_calibrated=false`。模型/协议/范围不匹配时不沿用旧策略。普通使用不重新校准、不自动修改阈值；本次没有增加每次决策的 Jev 请求数。结果、失败与局限见 [CALIBRATION.md](CALIBRATION.md)。

0.2 新增有证据的网页拖放、分组语义检索、命名窗口/页面间本地值传递、原生滑块与滚动、跨源合成 iframe，以及隔离 Electron UIA 验收。原生坐标拖放、任意应用启动/长程规划、官方 Chrome 未封装的操作仍需局部接管。完整实际范围见 [SUPPORT.md](SUPPORT.md)。

Electron 仅作隔离测试夹具，锁定 44.4.4，不是第二套模型或 Jev 环境。源码包不带 node_modules；需要重建时运行 `python -m gui_delegate.setup_electron_fixture`。该脚本从官方 npm 锁安装，禁用远程生命周期脚本，验证已审查的本地安装器、校验和文件及最终二进制哈希后才接受结果。它保留浏览器沙箱，不使用个人资料。

## 急停和撤销

- `gui-stop.cmd` 设置全局 STOP；`cancel_task` 取消特定任务。已发出的动作只做结果核查，绝不自动重复提交。若驱动挂死，会报告最终状态未验证并结束自己创建的进程树。
- Ctrl+Alt+F12 监听代码已实现；实际按键触发尚未人工验收。STOP 文件和取消路径已实测。
- 用户键鼠活动会暂停原生桌面任务；Chrome 使用官方会话所有权；恢复须用户明确交还控制。物理接管尚未实测，受控恢复授权检查已测。
- 剪贴板中途被用户改变时保留新内容并暂停，不抢回。异常恢复入口 `python -m gui_delegate.cli restore-clipboard` 仅在当前序号仍匹配时恢复加密副本，否则保留副本并要求人工处理，不覆盖较新的内容。
- `gui-uninstall.cmd` 急停并撤销本 skill、路由段、窄 Hook 与四个任务工具；保留原有 Jev 判断接口、源码、环境和凭据。`gui-restore.cmd` 重装并清除 STOP。修改前备份在实际 CODEX_HOME 的 `backups/jev-bridge`；用户后续改动发生冲突会保留并报错。
- 仅撤销此次阈值策略及 Jev 版本固定：`jev-calibration-rollback.cmd`；重新启用：`jev-calibration-restore.cmd`。语义歧义检查修复、源码和测试证据保留。这两项操作及重复执行均已实际验证。

重复安装、撤销、恢复和无关配置保留已实测。Hook 通过 Codex 正常审阅完成信任；未绕过审批、关闭安全设置或修改二进制。若未来 Hook 定义改变，必须重新正常审阅。安装路径目前限本机已验证的无空格项目路径；压缩包是可恢复的完整源码，不宣称任意宿主即插即用。

验收看 `reports/acceptance.json`，逐项范围看 [SUPPORT.md](SUPPORT.md)，实际成本对照看 [BENCHMARK.md](BENCHMARK.md)（0.1 历史实测，未重测 0.2 费用）。

已知测试事故：首次剪贴板探测在 CloseClipboard 前记录序号，误判变化后未确认恢复原内容；进程已退出，不能声称那次原内容已恢复。已修正序号时机，并在修改前持久化 DPAPI 恢复副本；之后实际逐字节恢复及故障检查通过。此修复不能倒推抹去首次影响。


最新清理：[0.4 报告](reports/edge-retirement-20260923/REPORT.md)。已移除 Edge 运行路径和专用输入监视器。29 个旧测试/发布入口归档为历史材料；现有校准策略、统计分析、Windows 校准与 Chrome 任务接口保留。旧 Edge 批量浏览器采样器已退役，新浏览器采样须经官方 Chrome 会话；不会偷偷重启 Edge。
