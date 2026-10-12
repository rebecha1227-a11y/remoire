# 我们的小窝 · Our Nest

## 项目一句话

一个两人专属的 AI 陪伴 PWA——不是工具，是关系空间。

## 2026-10-11 网页生图故障修复（本地，未发布）

- 补齐缺失的 `mirror_saved_image`，网页图片保存与镜像失败隔离；保存成功后才清理图片数据。纯图不再追加无意义的文字调用，接口错误不再冒充 Connie 道歉。
- 增加 SSE 心跳、图片事件去重、部分成功保留和脱敏错误分类；图片链接有限重定向逐跳验证。
- 本次完整后端 143 项通过，收尾针对性 43 项通过；前端 build、ChatPage lint 和隔离浏览器部分成功场景通过。未调用付费模型、未启动本机桥、未发布。Youkies 实际状态和扣费仍未验收。
- 用户要求后续使用 Codex 内置浏览器，不另开 Chrome。4190 是只读预览。
- 详细边界见 `docs/WEB-IMAGE-FIXES-2026-10-11.md`。

## 2026-10-10 网页也能画图（本地，未发布）

- 生图工具不再只挂在 iMessage。网页聊天在生图槽已配置时同样可以调用；生成的图写入同一段对话，网页立刻显示，重新打开也能看到。
- iMessage 线路已连接且已有对话时，网页画出的同一张图会进入发送队列，不再重新生图。iMessage 里画出或收到的图本来就进这张消息表，网页历史里看得到。

## 2026-10-10 iMessage 引用与表情（本地，未发布）

- 用户明确：Tapback 只在 iMessage 实现，Remoire 不加按钮也不显示；网页已有引用功能必须保留。仅同步 iMessage 引用正文/目标到既有网页引用展示。
- 第一批代码及核实边界见 `docs/IMESSAGE-INTERACTIONS-2026-10-10.md`：气泡 ID 映射、原生引用、双向添加表情；用户贴表情不单独触发生成，Connie 可只贴表情。撤回/移除表情事件当前 SDK 不完整，语音/链接后续实现。
- 本地预览 4190 为虚构只读数据，不连后端或 Photon。未发布；生产仍是下文连发修复版。本机小邮差不得启动。

## 2026-10-10 iMessage 连发修复（已发布生产）

- 见 `docs/DEPLOYMENT-2026-10-10-IMESSAGE-BURST.md`：单消费者按最后有效文字计时，生成时收到补充会放弃未发布草稿，保留用户原文并在后续一轮一起理解。已发布回复不撤回；设置仍为 3 秒。
- 本地完整 115 项回归及新增 1 项测试通过；服务器隔离 18 项通过。在线备份、readiness、服务状态及代码哈希核验通过；手机连发体感待用户验收。没有真实模型测试，本机桥仍禁启。

## 2026-10-10 iMessage 图片接收（本地实现，未发布）

- 上一轮引用回复、Tapback、引用 UI 与连发合并改动已提交 `592f87f`，在 `codex/product-hardening`；本轮没有推送或发布。
- 当前新增图片接收：Photon SDK 附件流 → 已登记号码校验 → 单条最多 4 图且合计 8MB → 现有聊天图片存储和认证读取。支持 JPEG/PNG/GIF/WebP；HEIC、超限、下载失败转换为明确的附件状态，不假装模型已见图片。
- 图片与文字仍按原合并窗口一起处理；图片保留原始消息记录，当前轮图片计入强制输入预算，保留的近期历史图片可重新加载，避免被新消息打断后丢失图片上下文。
- 本轮验证：后端完整 124 项、Node 桥接 7 项通过；未启动本机桥、未调用真实模型或 Photon，真机收图效果未验收。前端未修改。
- 现场生图与发送尚未实现，正在确认 OpenAI 图片接口 / Gemini 原生图片接口；不能把普通多模态聊天槽位视为支持图片输出。语音、视频、投票仍待后续。
- 细节见 `docs/IMESSAGE-IMAGES-2026-10-10.md`。

## 2026-10-09 iMessage 桥（已发布生产）

- 已发布到生产，见 `docs/DEPLOYMENT-2026-10-09-IMESSAGE.md`：服务 `remoire-imessage` 用独立 Node 22，生产库状态 connected；本机小邮差已停用，不要在本机再启动，否则会和生产抢线路。生产真机收发待验收。

- Photon 只负责收发。文字走现有聊天、同一张记忆表和同一份关系档案；网页对话用 `messages.channel` 标出入口。只接受设置里登记的手机号。
- 本机 Node 小邮差在 `backend/imessage_bridge/`，凭据用现有 Fernet 存在 `imessage_accounts`，不进前端回显。主动消息可选 Remoire / iMessage，微信仍不可选；线路不通时改走网页通知。
- 本地完整回归 112 项通过，前端已构建。没有部署。2026-10-09 本机已接真实 Photon 线路，iPhone 发短信后收到 Connie 回复（日常槽改用 Youkies 的 Claude Opus 4.6 后成功；此前旧 waooapi 返回 403，表现为已读不回）。这台电脑必须开着，小邮差才在线；生产尚未接入。

## 2026-10-08 关系档案 UI 复核（未部署）

- 用户要求与现有组件统一、注意字体大小，并先打开本地浏览器检查。已复用 SubPageHeader/Card/SettingsToggle，Noto Serif SC；移除前端原稿资料入口和 API 下发。
- 模型能力按 `/models` 元数据、官方别名表、兼容预算三层自动识别；当前表覆盖 Claude Opus 4.6、Gemini 2.5 Pro 与 DeepSeek V4.1 常用别名，普通设置不再要求手填预算。稳定 system 前缀和固定顺序工具目录用于提高 Prompt 缓存复用，工具是否调用仍由 Connie 自主决定；本地已记录供应商返回的缓存 usage 并展示 7 天命中率，尚未用真实付费请求验收。
- 本次完整回归 93 项、前端 build 与 lint 通过；隔离浏览器中保存/重读/历史恢复通过，430px 字体/触摸区域已检查。当前仍未发布生产，也没有触发真实模型。

## 2026-10-06 本地开发增量（未部署）

- 关系档案编辑、版本回退、无模型预览与多设备冲突保护已在本地实现；身份与表达通过统一服务供聊天、日记、主动活动/纸条、气息状态、日记留言/解锁回应读取。场景配置只用于聊天；原稿仅私有存档，不在前端展示或注入。MCP resume 返回共同配置，但外部客户端需主动调用才会获取。
- 本地 84 项 unittest、前端构建与新编辑组件 ESLint 通过。没有触发真实模型或推送，尚未发布生产。细节见 `docs/PROMPT-PROFILES-2026-10-06.md`。
- 用户原稿已原样保存到本地私有数据目录和本地数据库；不在 Git 或前端静态包中。部署代码不会自动同步这些私人资料。

## 当前事实基线（2026-10-05，北京时间）

- 2026-10-08 已将关系档案、长对话预算、核心原文强制注入、模型能力与缓存统计发布到生产，应用提交 `5d3c6e5` 已在 main；本地/服务器各 98 项回归通过。以 `docs/DEPLOYMENT-2026-10-08.md` 为最新发布事实，下文旧“仅本地”描述已被本条取代。真实模型生成和缓存命中尚未验收。核心记忆仅完全相同正文折叠，不做近似事实合并。

- 2026-10-05 后续事实/时间线及自主碎碎念修复已部署：见 `docs/CONVERSATION-GROUNDING-2026-10-05.md`。本地完整回归 76 项、服务器针对性回归 8 项通过；没有主动触发真实模型或推送，真实输出仍需在后续自然对话中观察。

已进入**个人生产实例运行与完善阶段**，不是 Phase 0 脚手架阶段。

- 后续已现场发布静态 MCP 鉴权、日志隐私和 ChatGPT OAuth；最新事实以 `docs/CHATGPT-OAUTH-2026-10-05.md` 为准，并未验收全部产品功能。
- 生产基于 `2fe26c9` 加上述工作区安全补丁，不应将全部安全改动误认为已包含在该 Git 提交。
- 该次发布记录：53 项 unittest 通过，数据库迁移与模型密钥加解密验证通过，认证接口和 MCP 协议连接通过；没有验证真实模型聊天生成和完整浏览器交互。
- 状态必须区分“代码已实现”“生产已验证”“部分实现”“规划”。有页面、数据表或脚本，不等于用户流程已闭环。
- 旧 `docs/TECH_STACK.md`、`docs/DEPLOYMENT.md`、`.claude/instructions.md` 等仍含历史方案。判断实现以代码为准，判断已部署状态以最新发布记录为准；不得把旧示例中的 localStorage 长期凭据、明文模型密钥等方案重新引入。

## 实际技术栈

以下版本是仓库依赖声明或发布记录，不代表本次读取了生产环境的全部已安装版本。

| 层 | 当前实现 |
|---|---|
| 前端 | React `^19.2.5` + Vite `^8.0.10`，JavaScript / JSX |
| 样式 | 普通 CSS、CSS Variables、部分 inline style；未安装 Tailwind |
| 页面切换 | `App.jsx` 的 React state；未安装 React Router |
| PWA | `frontend/public/manifest.json` + 手写 `sw.js`；未安装 vite-plugin-pwa |
| 后端 | Python 3.12（最新发布环境）、FastAPI `>=0.141.1,<1`、Uvicorn |
| 数据库 | SQLite WAL + aiosqlite；数据库迁移在 `database.py` |
| 定时任务 | APScheduler 3.x，随 FastAPI 单进程启动 |
| MCP | FastMCP `>=3.4.7,<4`，独立 `backend/mcp_server.py` |
| 模型接口 | httpx + OpenAI 兼容 Chat Completions；统一走 `app/llm.py` |
| 向量记忆 | Embedding API，向量存 SQLite BLOB，Python 计算相似度；没有独立向量数据库 |
| 认证 | 单用户密码登录、服务端会话、HttpOnly cookie、CSRF 校验；旧 Bearer 为可配置兼容机制 |
| 推送 | pywebpush + VAPID + Service Worker |
| 部署 | VPS + Nginx HTTPS + systemd；前端静态文件、后端 API、MCP 同一服务器 |

不要为匹配旧文档而额外安装 Tailwind、React Router 或 PWA 插件。
SQLite 已用于生产；远程部署、多设备访问本身不要求迁移 PostgreSQL。

## 实际目录

```text
Remoire/
├── AGENTS.md
├── .claude/                   # 历史上下文、构建指南和交接记录（部分陈旧）
├── docs/                      # 产品、设计、记忆架构、运维和发布记录
├── deploy/                    # Nginx / systemd 等部署配置
├── frontend/
│   ├── public/                # manifest.json、sw.js、图标
│   └── src/
│       ├── App.jsx            # 五个页签，React state 切换
│       ├── components/        # ChatPage、UsPage、DiaryPage、PlayPage、SettingsPage 等
│       ├── hooks/             # 当前主要为环境主题 hook
│       ├── styles/            # tokens.css、room.css
│       └── utils/             # api.js、ambient.js、tweaks.js
└── backend/
    ├── mcp_server.py
    ├── app/
    │   ├── main.py            # 路由、安全中间件、生命周期和调度注册
    │   ├── auth.py / config.py / database.py / llm.py / tools.py
    │   ├── routers/           # auth、chat、memory、diary、note、settings、reminder、push、signal、autonomous
    │   ├── services/          # 聊天、记忆、日记互动、主动消息、模型配置、推送、浏览等
    │   ├── scheduler/jobs.py
    │   └── prompts/           # identity、voice、thinking、tagging、digest 等
    ├── scripts/               # 备份、密码散列、MCP token 生成
    └── tests/                 # unittest 回归测试
```

## 核心设计原则

1. **关系连续性** — 不同入口、不同时间，是同一段关系
2. **不是工具，是空间** — 设置页不比聊天页重要
3. **写就是读** — 写入新记忆时自动关联 top-3 旧记忆
4. **主动靠近** — AI 不只等你打开，它会找你
5. **受控记忆写入** — 当前高置信度提取自动入库，低置信度进入候选；若改为全部确认，需同步修改策略、实现和测试

## 承重墙（P0）

聊天 → 记忆（含关联） → MCP → 主动消息 → 提醒 → 日记 → 小纸条

## 已实现的主要链路

| 能力 | 实际实现与限制 | 主要入口 |
|---|---|---|
| 聊天 | 流式回复、持久化、历史搜索、图片、daily/deep 选择；不应声称已经自动按情绪切换模型 | `services/chat_service.py`、`routers/chat.py`、`ChatPage.jsx` |
| 人设与上下文 | 本地代码已按 token 预算组装：identity/voice/已开启 scene + thinking/grounding 固定保留；近期原文、滚动摘要、核心/相关记忆按预算装载，并加入时间、天气、醒来摘要、日记互动等；生产尚未发布 | `chat_service.py`、`context_budget_service.py` |
| 长期记忆 | 候选提取，confidence >= 0.7 自动入库，其余 pending；分层、核心注入、关键词/向量混合召回、多样性筛选 | `services/memory_service.py` |
| 记忆维护 | 写入关联 top-3、连线、编辑删除、resolve、衰减、保守 digest、向量补填、召回日志 | 同上、`scheduler/jobs.py` |
| 记忆界面 | 记忆宫殿、分层、搜索、分页、关联和热力图相关接口 | `MemoryPalace.jsx`、`routers/memory.py` |
| 日记 | 日记保存、锁与访问控制、留言、解锁申请；自动日记和漏写补跑 | `services/diary*`、`DiaryPage.jsx` |
| 主动活动 | 随机 45–75 分钟调度、活跃时段判断、追发会话、生活日志；不是精确定时提醒 | `services/nudge_service.py`、`ConnieTimeline.jsx` |
| 小纸条与推送 | 后端保存纸条、Web Push 订阅与发送、前台 presence；实际送达需设备验收 | `note_service.py`、`push_service.py`、`public/sw.js` |
| 提醒基础 | 聊天提取、创建、列表、完成、取消和日期查询；到期投递链路未闭合，见下文 | `reminder_service.py`、`routers/reminder.py` |
| MCP | recall、remember、resolve、resume、读写日记、留纸条、状态和天气工具，共用数据库/服务 | `backend/mcp_server.py` |
| 模型设置 | 预设、三个槽位、服务端加密存储模型密钥；本地增加模型能力自动识别、随预设保存的能力元数据、上下文预算与 7 天缓存命中统计，生产仍是此前发布状态 | `model_settings_service.py`、`routers/settings.py` |
| 生活信号 | `/api/signal` 提供设备快照、App 事件和近期活动接口；不等于 iPhone 自动化已配置验收 | `routers/signal.py` |
| 运维基础 | 会话认证、健康接口、备份校验、数据库迁移、脱敏审计；MCP 静态 token 与 OAuth 已上线，ChatGPT 真实账号授权待用户完成 | `auth.py`、`oauth.py`、`scripts/`、`deploy/` |

当前已注册的定时任务：23:00 自动日记、10:00 气息状态、08:00/20:00 天气、03:00 记忆衰减、03:30 digest（均北京时间），另有随机自主活动。不要再把向量检索、记忆宫殿、衰减、自动日记标为“未实现”。

注意：`resume` 信息包仍不是长期聊天历史的滚动摘要。2026-10-08 本地代码新增独立 `conversation_summaries`；尚未发布生产，也未用真实模型验收摘要质量。

## 未完成事项与实施路线

本节是后续工作方案，**不是已经实现的功能，也不是本次要求立即开发或部署的授权**。优先完成 P0，再推进 P1；P2 按真实需求选择。

### P0-1：生产 MCP 鉴权已启用，ChatGPT 用户授权待验收

- 独立 Bearer 鉴权已生产验证，用户已确认 Codex 实际调用成功；原 token 仍有效，摘要保存在服务器配置。匿名、错误 token 和只有 MCP session 的请求被拒绝，内部校验接口不对公网开放。
- ChatGPT OAuth 授权码/PKCE、动态注册、登录同意页、刷新轮换和撤销已部署。本地 68 项回归、服务器隔离 22 项认证回归及公网发现/取消授权/旧 token 兼容检查通过。
- 剩余：用户亲自在 ChatGPT 创建连接、登录 Remoire 并授权，再验证真实工具发现/调用。不能将服务端模拟测试写成 ChatGPT 用户端已经连接成功。
- 发布、数据保护和回退边界见 `docs/CHATGPT-OAUTH-2026-10-05.md`；不得恢复匿名 MCP 作为兼容方案。

### P0-2：补齐真实产品流程验收与日志隐私

- 最新发布没有验证真实模型生成、完整手机交互或锁屏推送，不能用接口返回 200 代替体验验收。
- 在隔离测试数据中验证：登录 → 流式聊天 → 保存历史 → 记忆提取/确认 → 下轮召回 → 日记权限 → 纸条与后台推送；记录设备、浏览器、时间、结果和失败原因。真实模型请求与生产数据写入需在明确的测试范围内进行。
- 已部署原文日志移除、统一隐私 LogRecord 工厂和 Nginx 脱敏访问日志；生产合成标记检查通过。历史日志没有清理，完整生成/手机交互/锁屏推送仍待明确范围验收。
- 验收：以带唯一标记的虚构私密文本测试，日志不含正文、密钥或认证头；断流、模型错误、会话过期有真实反馈，不假装成功。

### P1-1：提醒到期自动送达（基础已做，触发缺失；建议首先补的产品功能）

- 证据：当前有提醒 CRUD/提取，但 `main.py` 没有到期提醒任务；未找到 `reminder_due` 的完整投递实现。随机主动活动不能承担准时提醒。
- 实施位置：`database.py`、`reminder_service.py`、`scheduler/jobs.py`、`main.py`、`push_service.py`。
- 先规范时间：历史 `remind_at` 为北京时间无时区字符串；用明确的 Asia/Shanghai 解析迁移为统一 UTC 时间，接口与界面显式转换，不直接与 SQLite UTC `datetime('now')` 混比。
- 增加通知 outbox（提醒 ID、触发时刻唯一键、状态、尝试次数、下次重试时间、发送时间），不要把“已发送”和“用户已完成待办”混为一个状态。
- 每 30–60 秒扫描到期 pending 提醒，在事务内幂等创建投递任务；单独投递应用内通知和 Push，失败退避重试，重启补查遗漏任务。通知使用稳定 tag 降低重复展示。
- 验收：跨午夜、重启补发、重复扫描、推送失败重试、已取消提醒不投递；同一事件仅创建一条应用内通知。外部 Push 无法保证绝对 exactly-once，明确重试与去重边界。

### P1-2：网页人设编辑与统一加载（本地已实现，生产尚未发布）

- 实现：`PromptSettings.jsx`、`prompt_profile_service.py`、`routers/prompt_profiles.py`。身份、表达、聊天场景三区；保存/预览/历史恢复/冲突保护已接通。
- 身份与表达从已有文件首次导入 SQLite，后续以数据库为准。聊天、日记、主动消息及纸条、气息状态、留言与解锁回应统一读取；内部提取、打标和摘要保持原后端规则。
- 场景写作可独立开启，仅影响后续聊天；原稿仅私有存档、不向前端下发，不自动注入或抓取链接。现有 thinking、grounding、自主活动规则与接口格式仍在后端。
- 本地验证及未发布边界见 `docs/PROMPT-PROFILES-2026-10-06.md`。生产迁移必须保留当前服务器文件作为初始值；不能用本地 DB 覆盖生产。
- 昼夜 Prompt 文件的旧可选加载保持原样，未新增规则或更改现有内容。

### P1-3：应用内数据导出与历史对话导入（目前均为占位）

- 已有服务器备份和历史处理脚本，不等于网页具备导入/导出闭环。
- 导出：新增受认证保护的导出接口，用 SQLite 一致快照读取；默认导出有 schema_version 的可移植 JSON/附件清单，排除模型密钥、会话、Push 凭据和服务器配置；提供校验和，下载后清理临时文件。不要开放生产数据库文件的静态下载地址。
- 导入：先支持一种明确格式；解析 → 预览数量/角色/时间 → 用户确认 → 分批事务写入。用源 ID/内容哈希实现重复导入幂等，设置大小限制并报告失败项。
- 历史记忆提取单独启动，显示模型调用成本范围/进度，先生成候选；不能上传后无提示地全部自动进入正式记忆。
- 验收：导出后可在临时环境恢复；同一文件重复导入无重复消息；格式错误不产生半成品；原数据库保持可恢复。

### P1-4：长对话上下文预算（本地已实现，生产尚未发布）

- `chat_service.py` 与 `context_budget_service.py` 按模型槽位的上下文上限、回答预留和安全余量组装输入。能力优先取 `/models` 元数据，再由官方别名表补全；两者缺失时保留兼容预算，普通设置页不再要求用户手填。
- identity、voice、已开启 scene、thinking、grounding 和最新用户输入为强制项；强制项超限时 SSE 返回明确错误，不静默裁剪。近期原文取连续后缀，核心/相关记忆和动态信息按预算选择，工具结果可带标记截短。
- `conversation_summaries` 记录摘要正文、版本、覆盖的最后消息 rowid/ID 和累计消息数；成功回复后异步压缩连续旧消息，失败时继续使用受预算控制的近期原文。摘要不进入记忆提取输入。
- Claude 模型优先走 Anthropic Messages 协议；固定工具 schema 与 identity/voice/scene/thinking/grounding 稳定前缀使用 5 分钟缓存断点。时间、天气、摘要、记忆与近期消息留在动态后缀；缓存不缩小上下文占用。
- 本地完整 unittest 93 项、前端 build 与 lint 通过；使用模拟模型验证强制层、最新输入、连续摘要范围、模型能力识别、缓存断点和 thinking 工具签名。未调用真实模型，未验证真实缓存命中、摘要质量、供应商精确 token 计数或生产迁移。见 `docs/CONTEXT-BUDGET-2026-10-08.md`。

### P2：按需扩展，尚不能宣称已交付

| 功能 | 当前状态 | 具体实现方向与验收 |
|---|---|---|
| 微信桥接 | 设置页明确尚未开放 | 确认可用接入方式后实现授权、凭据保护、续期/撤销、消息幂等和入口绑定；共用聊天服务。验收收发、重连与解绑；旧架构图不代表已接入 |
| 共读 | PlayPage 仅预告 | 建书目、进度、批注表和 API，再做书架/阅读入口；刷新、换设备后进度与批注可恢复 |
| 平行空间 | PlayPage 仅预告 | 建故事、分支、消息与摘要表，支持存档/续写；故事上下文与真实关系记忆隔离，防止虚构情节污染长期事实 |
| PWA 离线 | SW 有推送，无 fetch/cache 离线逻辑 | 先定义离线范围；缓存版本化静态壳并提供离线提示，不默认缓存私密 API。验收断网启动、更新换版与退出登录清理；不承诺离线模型回复 |
| iPhone 生活信号 | 后端接口已存在，端到端未验收 | 明确快捷指令授权与最小权限方案、信号过期和保留期，再测试真实上报与消费；不沿用旧文档里的不存在的 `/api/device/*` 接口 |

## 建议下一步与执行纪律

1. 完成 P0-1 剩余的 ChatGPT 用户端授权验收；随后完成 P0-2 的关键真实流程验收。静态鉴权、OAuth 服务端和新日志脱敏已经上线，不重复实施。
2. 产品开发优先 P1-1：提醒闭环，这是现有核心能力的缺口；然后 P1-2 人设编辑、P1-3 数据迁移、P1-4 长对话预算。
3. 若要提取给其他人自建的模板，先把姓名、地点、人设与环境配置参数化；使用空数据库与虚构样例，不复制个人记忆、日记、模型凭据或会话。模板化是后续工作，不是现有多用户能力。
4. 每完成一项，更新本文件状态与相关实现文档；发布后另写生产验证结果。不要把计划直接改写成“已完成”。
5. 当前 APScheduler 随主进程运行，未经任务单实例/锁设计，不要直接增开多个 Uvicorn worker，以免重复执行日记、主动消息等任务。
6. 文档更新不需要触发模型或重跑整个测试集。代码修改按范围运行 `cd backend && python -m unittest discover -s tests`；前端修改运行 `cd frontend && npm run build`，必要时 lint 和真实交互验收；不得把历史测试结果写成此次新结果。
7. 生产数据库为 `/opt/remoire/backend/data/remoire.db`，本地数据库不自动同步。备份用在线备份 API，不能只复制正在使用的 WAL 主文件。生产操作先读最新发布记录，旧运维文档的 venv 路径可能不再是实际服务环境。


## DO

- 所有 LLM 调用走 `app/llm.py` 的 `call_llm()`，兼容 OpenAI 格式
- SQLite 开 WAL：`PRAGMA journal_mode=WAL`
- CSS Variables 管理颜色，暗色模式通过 `[data-theme="dark"]` 切换变量
- 用户于 2026-10-05 明确要求恢复主界面原版 Noto Serif SC 字体；聊天气泡和输入框使用 `--font-chat`，日记/纸条/共读/平行空间保留各自独立上传槽位。不要再按旧字体规范统一替换用户选定的视觉。
- 移动端优先，430px 设计基准
- API 统一格式：`{ "ok": bool, "data": ..., "error": ... }`
- 阴影用 `rgba(40,33,28,...)` 暖棕色
- 图标用 lucide-react，outline，stroke-width 1.5
- memories 表已使用 `embedding BLOB`；编辑正文需更新向量，生成失败应清除旧向量
- 记忆写入响应带 `associated` 关联旧记忆
- 可交互元素最小触摸区域 44x44px

## DON'T

- ❌ Inter / DM Sans / Roboto 字体
- ❌ 渐变背景、渐变按钮
- ❌ 紫色/蓝色高亮
- ❌ #FFFFFF 卡片背景
- ❌ 左侧彩色竖线装饰
- ❌ blur() 在非导航区
- ❌ bounce/spring 动效
- ❌ 六宫格/仪表盘
- ❌ 模型切换在聊天主页
- ❌ 默认展示思维链
- ❌ emoji 作视觉主导
- ❌ font-weight 700+
- ❌ rgba(0,0,0,...) 阴影
- ❌ 大面积 accent-pop

## 色值速查

| 变量 | 值 | 用途 |
|---|---|---|
| --bg-primary | #F6F2ED | 主背景 |
| --bg-elevated | #FAF8F4 | 卡片 |
| --text-primary | #28211C | 主文字 |
| --text-deep | #574337 | 重点标题 |
| --accent | #7C6350 | 按钮/激活 |
| --accent-pop | #82BDC5 | 点缀 |
| --bubble-send | #C8B49E | 发送气泡 |
| --bubble-receive | #EDE9E3 | 接收气泡 |

## 术语表

| 术语 | 含义 |
|---|---|
| resume() | 醒来——浮现记忆、提醒、未完成事项 |
| remember() | MCP 记住——当前直接调用 create_memory 写入正式库并返回关联；不走聊天候选确认 |
| recall() | 回忆——检索记忆 |
| resolve() | 标记 unresolved 为已解决 |
| digest() | 摘要压缩——合并重复记忆 |
| nudge() | 主动消息——AI 主动靠近 |
| 关联记忆 | 写入时自动返回 top-3 旧记忆 |
| 小纸条 | AI 静默留言，打开 app 时发现 |
| 气息状态 | 聊天顶部诗意文案 |
| 槽位 | 模型角色：daily / deep / backend |

## 文档指引

| 要做什么 | 先读 |
|---|---|
| 写 API 接口 | docs/API.md |
| 建表改表 | docs/DATABASE.md |
| 写前端组件 | docs/DESIGN_SYSTEM.md |
| 理解产品 | docs/PRD.md |
| 技术架构 | docs/TECH_STACK.md |
| 部署与生产状态 | docs/DEPLOYMENT-2026-10-05.md（本次核对的最新发布）、docs/OPERATIONS.md；以后以更新的发布记录为准 |
| 记忆实现与维护 | docs/记忆系统架构与AI搭建指南.md、backend/app/services/memory_service.py |

## 2026-10-11 网页原图查看（本地，未发布）

聊天图片可点击全屏查看并下载原图；保留原生长按菜单。仅网页改动，iMessage 原生附件不变。前端构建、组件 lint、内置浏览器打开/关闭/Escape/实际下载通过；手机长按保存待真机验收。详见 docs/WEB-IMAGE-FIXES-2026-10-11.md。

## 2026-10-11 主动消息连续性与线路状态（本地，未发布）

- 已只读核对生产：主动消息有记忆召回，但仅最近 15 条、末条用户前 50 字检索，设备快照不检查过期；iMessage 成功收发后仍保留 failed。
- 本地主动活动复用聊天预算与摘要，双查询召回用户语境和事实纠正，设备快照六小时过期；autonomous 规则要求提及当下事实前核验。入站/出站成功恢复线路状态，投递错误不再等同断线，设置页定期刷新状态。
- 本次后端 148 项、Node 8 项、前端 build 通过。未调用模型或 Photon、未改生产。见 docs/PROACTIVE-CONTINUITY-2026-10-11.md。

## 2026-10-12 正式发布

main 已合并并推送应用提交 f4beea8，图片生成/查看、iMessage 引用及添加 Tapback、主动上下文连续性与连接状态恢复已部署。服务器隔离后端 148 项、Node 8 项通过，迁移备份与 readiness/代码指纹/公网首页验证通过，iMessage connected，生产设置页 iMessage 已可选。真实手机 Tapback、图片与主动消息效果仍需自然使用验收；移除表情/撤回未实现。详见 docs/DEPLOYMENT-2026-10-12.md，覆盖前文相应“本地未发布”记录。

- 2026-10-12 同日 UI 修复：主动消息发送入口改为标题、等宽按钮、底部说明的纵向布局，窄屏不再挤成竖排；前端构建和内置浏览器检查通过。

## 2026-10-12 表情包库（本地，未发布）

从用户 Word 文档导入 826 条、9 类外链表情到私有 stickers 表；原稿不变，转换清单/缓存位于 backend/data/stickers。聊天提供 search_stickers/send_sticker，网页与 iMessage 复用既有图片交付，不需要生图槽位；首次使用下载缓存，GIF 不转静图。最终完整后端 153 项、前端构建通过，两张真实链接抽查成功。没有新增图库管理 UI 或主动消息工具；未部署或发短信。见 docs/STICKER-LIBRARY-2026-10-12.md。

- 同日表情尺寸调整（本地）：新增 messages.image_kind，通过历史/SSE区分表情与普通图片；表情最大150×160px、窄屏40vw，保留原图查看。153项回归及构建/lint通过，浏览器实测138×138px。

## 2026-10-12 网页手动表情图库（本地，未发布）

- 输入框「＋ → 表情包」支持搜索、分类、分页、轻点发送与长按预览；与 Connie 共用图库，按小尺寸表情显示。只新增网页选择界面。
- 认证图库接口按 ID 取媒体，服务端解析标签和原图后进入既有聊天持久化与模型链路。详情见 `docs/STICKER-LIBRARY-2026-10-12.md`。尚未生产发布，没有真实模型发送验收。

## 2026-10-12 表情图库正式发布与真机验收

- 应用提交 `c9427ef` 已提交并推送 main，部署到生产；覆盖上文图库、手动选择和尺寸调整的“本地未发布”状态。生产已导入 826 条、9 类表情，不覆盖本地/生产聊天数据库。
- 本地与服务器隔离回归各 155 项通过，前端 build/相关组件 lint 通过。发布后代码指纹匹配、数据库 quick_check=ok、readiness=200、四服务 active、iMessage connected，匿名图库接口返回 401。
- 用户于本轮明确反馈：已在真机验收，表情包功能正常。这是用户验收结果；不扩展为全部 826 个外链或所有 iMessage 功能均通过。
- 备份与回退见 `docs/DEPLOYMENT-2026-10-12-STICKERS.md`。原 Word、私人图库清单、缓存和数据库均未提交 Git。

- 2026-10-12 历史图片重试修复：重新生成先认证读取历史原图并转为 Base64，避免 URL 被后端校验为 422；空回复及后端错误明确显示。前端 build/lint 和 3 项专项测试通过，真实重试待用户验收；发布记录见图库部署文档。
