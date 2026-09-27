# 安装 Jev GUI Delegate 0.7.0

适用于 Windows x64、Python 3.12、Node.js，以及能提供官方 Chrome 会话的 Codex 桌面环境。需要自己的 TypeSafe API 密钥。

1. 解压完整安装包到长期保留的目录。
2. 双击 `install-skill.cmd`。它安装锁定依赖、注册 MCP、生成本机运行配置，并安装 `jev-gui-delegate` skill。路径可以包含空格。
3. 双击 `set-key.cmd`，在本地掩码窗口设置自己的 TypeSafe 密钥。已有命名凭据可继续使用。
4. 在 Codex 连接官方 Chrome 插件并打开新对话。例如：“使用 Jev 访问 GitHub，打开 github/spec-kit 的最新发布，告诉我版本和主要变化。”

`health.cmd` 检查本地就绪状态，不调用远程模型。`verify.cmd` 会调用 TypeSafe 服务做实际验证。skill 的浏览器操作还需要当前对话中的官方浏览器会话，MCP 本身不能创建这个宿主会话。

更新已有安装时，应保留原安装目录中的 `.venv`、本机配置和 `gui_delegate/install-state.json`，然后在原目录运行安装入口。安装器只更新它能确认归属的内容；发现用户改过的 skill、同名 MCP 冲突或安装身份变化会报告冲突。不要在另一个目录安装同名服务来覆盖旧注册。

安装包不含密钥、Cookie、登录状态、个人日志、依赖环境或原作者的校准状态。首次安装需要联网下载锁定依赖。安装与真实网站的验证范围见 [VALIDATION.md](VALIDATION.md)；并未在一台全新的物理电脑上完成端到端安装验收。

当前使用 Jev `1.13.0`。低置信、验证码、登录、缺少语义信息的控件等仍可能需要补充或用户操作，不能保证所有网页自动完成。
