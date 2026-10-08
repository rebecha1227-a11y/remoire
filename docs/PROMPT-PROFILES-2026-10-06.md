# 关系档案编辑与统一配置 · 2026-10-06

## 状态

本地实现，尚未部署生产。不能将本文作为生产验收记录。没有调用真实模型、发送推送或修改生产数据库。

## 用户入口与生效范围

设置 → 关系档案：身份与关系、表达偏好、场景写作。原稿不作为前端功能展示，也不通过配置 API 下发。

- 身份与表达保存到服务器 SQLite；下一次生成读取新版本，已经开始的生成继续使用已读取的内容。各区分别保存，未保存草稿仅在当前页面内存中。
- 聊天、自动日记、日记留言、解锁回应、气息状态、自主活动及其纸条/日记/主动消息共用 `prompt_profile_service.load_shared()`。无模型参与的固定兜底文字和无聊天记录时随机选取的气息状态不受 prompt 编辑控制。
- 场景写作初始为空且关闭；勾选并保存才会在后续聊天加载。它是此实例的聊天设置，影响各设备的后续聊天，不是某个气泡的显示开关，也不保证模型输出固定长度。关闭停止加载该配置，不会删除已发送的历史上下文。
- 原稿仅私有存档（用户已要求移除原稿资料页签）；不作为身份、表达或场景 prompt 注入，不自动抓取参考链接，不自动提取为记忆。本次用户正文保存在本地 `backend/data/prompt-originals/2026-10-06-original.md` 和本地数据库 original 配置内，保留原文、标点及 Markdown 转义，没有合并进生成配置。链接正文尚未读取。
- MCP 两个服务的 `resume()` 返回共同配置；外部客户端需调用该工具，不能承诺外部客户端即时更新其 system prompt。手动提交的日记或纸条不会被服务端重新改写。
- 现有 thinking、grounding、自主活动规则和各入口的任务/格式要求仍在后端；记忆提取、打标、digest、是否写日记等内部判断保持原来的流程。
- 2026-10-08 的聊天预算器把 identity、voice、已开启 scene、thinking、grounding 作为固定层。thinking 保持独立文件，语义上属于 Connie 的思考方式；grounding 保持独立事实边界，二者没有合并进 voice 正文。
- `nudge.md` 现在会在允许主动发消息的自主活动中与 `autonomous.md` 一起装载；消息被时段、冷却等规则阻止时不装载主动消息规则。tagging、reminder_extract、digest 继续由各自服务读取。

## 存储与保护

- 首次从运行服务器的 identity.md/voice.md 原样初始化。数据库已有配置（包括空正文）优先，重启不会覆盖。文件此后只作为新实例初值。
- `prompt_profiles` 保存当前版本，`prompt_profile_versions` 保存不可变历史。事务内比较 expected_version，多设备旧版本写入返回 409；回退生成新版本。
- 正文最多 60000 字符，不做 trim。前端按纯文本显示，不将正文作为 HTML 渲染。接口复用会话认证/CSRF，响应不缓存。
- 查看历史、预览均不调用模型。预览仅展示已保存的共同配置及已开启的聊天场景配置，不代表含记忆等动态上下文的完整 system prompt。
- 原稿文件、数据库及导入前在线备份都位于 Git 忽略的数据目录；不放入前端 bundle 或静态资源。

## 本地验证

- `cd backend && venv/bin/python -m unittest discover -s tests`：84 项通过，含 8 项新配置测试。使用隔离测试数据库和模拟模型调用。
- `cd frontend && npm run build`：通过。
- `npx eslint src/components/PromptSettings.jsx`：通过。
- 2026-10-08 再次运行完整回归：84 项通过；前端构建和 PromptSettings.jsx/settingsShared.jsx ESLint 通过。
- 2026-10-08 长对话预算完成后再次运行完整回归：88 项通过；前端 build 与全量 lint 通过。没有调用真实模型。
- 本地浏览器：独立临时数据库、示例文字，不加载主服务 scheduler。登录 → 设置 → 关系档案 → 编辑保存 → 重新读取 → 历史版本 → 恢复已验证，恢复生成版本 4，示例正文还原。
- 430 CSS px 实测无横向溢出；正文 Noto Serif SC 16px；返回、三页签、工具栏和保存按钮均高 44px。另在浏览器实际报告的 585/645/1536 CSS px 检查无横向溢出（浏览器缩放导致实际 CSS 宽度与请求 viewport 不一致，不记作 390px 真机验收）。
- 截图：output/playwright/profiles-mobile.png、profiles-scene-mobile.png。用户检查用预览 http://127.0.0.1:4187；本地临时账号 connie，暗号 synthetic-ui-only，仅作用于测试服务。未做真实手机软键盘、真实模型生成或生产验证。

## 后续生产发布

1. 先读最新生产发布记录，确认实际环境；在线备份生产 SQLite，不复制正在运行的 WAL 主文件。
2. 发布代码与前端，保留生产现有 identity.md/voice.md 作为首次导入源；启动执行 init_db。不能用本地 DB 覆盖生产 DB。
3. 私人原稿不会随 Git 发布。需单独安全传输到服务器私有目录，然后执行 `scripts/import_prompt_original.py <原稿路径> --database <生产数据库路径>`。脚本先在线备份，仅接受空原稿首次导入或完全相同内容的重复导入，不覆盖不同原稿。
4. 重启单进程 API 和实际使用的 MCP 服务；不增加 scheduler worker。
5. 验证认证、CSRF、编辑/刷新/恢复及配置读取；真实模型生成与设备体验另按明确范围验收，另写生产结果。
