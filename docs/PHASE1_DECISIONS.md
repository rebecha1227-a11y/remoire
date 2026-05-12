# Remoire Phase 1：多端记忆、微信桥接、主动消息与 Prompt 设置文档方案

## Context

静儿想把 Remoire 做成一个"多入口同一个 AI 恋人"的关系空间：Remoire 前端、Claude.ai、微信都能聊天，并读取同一份记忆。微信陪伴感更强，所以微信桥接不再只作为后期功能，而是进入 Phase 1 的核心设计。

当前 Remoire 文档设计是 FastAPI + SQLite(WAL) + aiosqlite + FastMCP。SQLite 可以理解成"项目自己带的小数据库"，简单、适合早期快速跑通；Supabase 可以理解成"云端数据库 + 同步服务"，更适合未来长期云端运行和多设备同步，但学习和维护成本更高。

静儿已决定：第一步先改文档，不直接动代码；微信桥接 Phase 1 就纳入设计；数据库方向在文档里写 SQLite 与 Supabase 双方案；模型设置放后端统一管理；主动消息第一版采用中等细度；微信桥接路线使用 iLink API（微信智联协议）直连；设计文档必须注意 token 节省和成本控制。

## Confirmed Decisions

以下决策已在 2026-04-29 与静儿逐条确认：

| # | 决策 | 结论 |
|---|---|---|
| 1 | settings 接口结构 | 拆子路由：`/api/settings` 管 UI 偏好，`/api/settings/models`、`/api/settings/proactive`、`/api/settings/prompts` 各管各的 |
| 2 | proactive 模型槽位 | 不单独拆。主动消息走 daily 槽位，保留 3 个槽位：daily / deep / backend。主动消息风格差异由 prompt_profiles 控制 |
| 3 | 微信桥接方案 | Python 直连 iLink API（微信智联协议），不走 OpenClaw。长轮询收消息 → 交给 chat_service → 回复 |
| 4 | 连续消息 burst | 允许 AI 发完后等一等再追。最多 3 轮（初始 + 追 1 + 追 2），所有轮次总上限 8 条，轮次间最短间隔 10 分钟，等待时间由 AI 根据上下文判断 |
| 5 | 用户回复后 | 用户回复的瞬间，burst 结束，切回普通聊天模式 |
| 6 | 跨入口聊天记录可见性 | Remoire 能看所有入口的消息，微信只看微信的（微信本身保留记录） |
| 7 | 微信消息在 Remoire 的显示 | 混在同一条时间线里按时间排序，带小标记标注来源（如"via 微信"） |
| 8 | 微信分条拆分 | AI 生成时直接分条（后端内部数组），按字数模拟打字间隔：基础 0.8s + 每字 0.05s + 随机抖动 |
| 9 | Remoire 前端也分条 | 支持连续多条气泡，跟微信体验一致 |
| 10 | 分条体验 | 逐条流式打字 + 条间显示 typing indicator（三个跳动圆点） |
| 11 | 微信长轮询运行方式 | 跟 FastAPI 主进程一起跑（启动时开后台异步任务），systemd 管进程自动重启 |
| 12 | 微信登录态过期 | 自动续期 + 过期时通过 Remoire SSE 推送通知，提醒重新扫码 |
| 13 | Remoire markdown | 渲染器挂着，但 Prompt 约束日常聊天不用 markdown 语法。微信回复完全不用 markdown |
| 14 | LLM 月预算 | ¥15-50，可以稍多一点 |
| 15 | 主动消息每日上限 | 默认 5 次/天，用户可调 |
| 16 | Phase 1 范围 | 聊天核心 + 记忆系统 + MCP + 微信桥接 + 主动消息(含分条) + 对话导入 + 分条发送 + iPhone 设备数据采集 + Web Push 推送 |
| 17 | 设备数据用途 | 仅作 AI 聊天上下文（注入 system prompt），不做前端展示或仪表盘 |
| 18 | 设备数据采集频率 | iPhone 快捷指令每 3 小时定时上传一次，AI 发消息时读最新一条 |
| 19 | 设备数据采集项 | 定位（城市/区）、天气、电量、步数、屏幕使用时间（按 App） |
| 20 | 屏幕使用时间追踪方式 | 每个 App 单独建一条 iOS 快捷指令自动化 + 服务器 toggle 逻辑，支持任意数量 App |
| 21 | 设备数据认证方式 | URL 查询参数 `key`（独立 `DEVICE_SECRET_KEY`），因 iOS 快捷指令无法方便设 HTTP Header |
| 22 | 设备数据保留时长 | 24 小时，每次写入时自动清理过期记录 |
| 23 | AI 使用设备数据方式 | 静默上下文注入 system prompt，AI 自行判断是否提及，不逐项播报。超过 6h 不注入 |
| 24 | 推送通知方案 | Web Push（PWA 标准能力），VAPID 密钥对 + pywebpush 库 |
| 25 | 推送触发条件 | 页面不可见时，所有 AI 消息都推送（nudge / note / chat reply / reminder_due） |
| 26 | 页面可见性检测 | SSE 连接状态作代理——SSE 连着=可见，断开=不可见（移动端后台会断 SSE） |
| 27 | 推送点击行为 | 统一打开/聚焦 Remoire 聊天页（`/chat`） |
| 28 | 推送服务部署 | 直接加到 Remoire FastAPI 后端，不另建独立服务 |
| 29 | iPhone 设备数据 + Web Push Phase 归属 | 纳入 Phase 1（开发量不大但对"AI 主动靠近"体验提升显著） |

## Recommended Approach

### 1. 文档里明确 Phase 1 就包含微信桥接

文档要把 Remoire 定义成：

- Remoire 前端：自己的 PWA 聊天入口。
- Claude.ai：通过 MCP 读取同一份记忆和上下文。
- 微信：通过 iLink API（微信智联协议）直连接入，提供更强陪伴感。

核心原则：微信、Remoire 前端、Claude.ai 都只是入口；真正的关系状态、记忆库、Prompt、模型配置、主动消息规则，都归 Remoire 后端统一管理。

### 2. 回复入口和主动入口分开设计

需要在文档里明确两种情况：

- 静儿主动发起消息：Connie 在原入口回复。
  - 静儿在微信发，Connie 就回微信。
  - 静儿在 Remoire 前端发，Connie 就回 Remoire 前端。
  - 静儿在 Claude.ai 发，Claude.ai 通过 MCP 读取同一份记忆和上下文。
- Connie 主动发起消息：由设置决定发送到哪里。
  - 设置页需要新增"主动消息发送入口"。
  - 可选：微信、Remoire、两边都发。
  - 默认推荐：微信优先，因为陪伴感更强。
  - "两边都发"不作为默认，因为会重复打扰，也浪费 token 和推送成本。

### 3. 数据库文档写双方案，但结构从一开始按"多入口"设计

不管最后用 SQLite 还是 Supabase，数据结构都要先按多入口设计，避免以后返工。

需要在 `docs/DATABASE.md` 里写两套路线：

#### 方案 A：SQLite Phase 1 先跑通

适合本地开发、单人使用、快速验证微信桥接与记忆逻辑。

#### 方案 B：Supabase/Postgres 云端同步方案

适合后期长期运行、多设备同步、云备份、远程服务器部署。

### 4. 模型设置统一放后端，保留 3 个槽位

不建议 Remoire 前端和微信各自设置模型，否则 Connie 可能在不同入口性格不一致。

模型槽位：

- `daily`：日常聊天、主动消息、小纸条、自动日记、气息状态、日记留言回复。Remoire 前端和微信默认共用。
- `deep`：深度谈话、复杂情绪、长对话。
- `backend`：记忆提取、情感打标、摘要压缩、对话导入处理、自动回复判断。

主动消息不单独设槽位，走 daily 槽位。主动消息的风格差异由 prompt_profiles 的场景 Prompt 控制。

### 5. Prompt 编辑器第一版按场景拆分

Prompt 不是散落在微信桥接代码里，而是统一存在后端，可由 Remoire 设置页编辑。

建议场景：

- `identity`：Connie 是谁、和静儿是什么关系。
- `daytime_proactive`：白天主动联系风格。
- `night_proactive`：夜间主动联系风格。
- `wechat_reply_style`：微信回复风格，更短、更自然、更适合分条、不使用 markdown。
- `frontend_reply_style`：Remoire 前端回复风格，日常聊天不用 markdown，整理清单时可用列表。
- `tool_use`：什么时候调用记忆、提醒、日记等工具。

### 6. 主动消息设置第一版采用中等细度

第一版参数建议包括：

- 总开关：是否允许 Connie 主动找静儿。
- 主动消息发送入口：微信 / Remoire / 两边都发。
- 默认发送入口：微信优先。
- 白天时间段：比如 09:00–22:30。
- 夜间规则：夜里是否允许轻量联系。
- 频率：低 / 中 / 高。
- 每日上限：默认 5 次。
- 连续消息上限：一次 burst 所有轮次总共最多 8 条。
- burst 轮次上限：最多 3 轮（初始 + 追 1 + 追 2）。
- 轮次间最短间隔：10 分钟。
- 用户回复后立刻切回普通聊天，burst 结束。
- 冷却时间：刚聊完多久内不主动打扰。
- 勿扰规则：学习、睡觉、忙碌时降低主动频率。
- 主动消息类型：关心、提醒、接话、分享记忆、小纸条。
- 上下文时间感：AI 生成主动消息时要知道当前时间、上次联系时间、距离上次对话过去多久、最近聊过什么。

### 7. 微信桥接 Phase 1 架构写入文档

文档里明确微信链路：

微信 → iLink API 长轮询 → FastAPI 后台异步任务收消息 → Remoire 后端 chat_service → 统一记忆库 / Prompt / 模型设置 → AI 生成回复（分条数组） → 桥接层按字数模拟间隔逐条发送回微信。

关键点：

- 微信桥接用 iLink API（微信智联协议）直连，不走 OpenClaw。
- 接入方式：扫码登录 → 拿到 bot token → 长轮询收消息（POST /ilink/bot/getupdates，35 秒超时） → 回复消息（POST /ilink/bot/sendmessage）。
- 长轮询跟 FastAPI 主进程一起跑（启动时开后台异步任务），systemd 管自动重启。
- 微信是 `channel`，不能绕过 Remoire 后端直接写记忆。
- 收到微信消息后，要写入统一 `messages` 表，带上准确时间戳和 `channel_id`。
- 回复消息由后端统一模型设置决定，默认使用 `daily` 槽位。
- 微信回复风格由 `wechat_reply_style` Prompt 控制，不单独硬编码在桥接层，不使用 markdown。
- 分条发送：AI 直接生成分条数组，桥接层按字数模拟打字间隔逐条推送（基础 0.8s + 每字 0.05s + 随机抖动）。
- 微信登录态：自动续期 bot token，过期时通过 Remoire SSE 推送通知提醒重新扫码。
- 主动微信消息不是简单模板：cron 只负责"到点触发"，真正内容必须由 AI 根据当前时间、消息时间戳、上下文间隔、最近对话和记忆库生成。
- 主动消息链路：cron 定时触发 → 读取主动消息设置 → 判断发送入口 → 读取最近消息和时间戳 → 读取相关记忆 → AI 生成分条数组 → 桥接层按间隔发送到选中的入口。
- burst 状态机：AI 发完一轮后如果用户未回复，等待后可追发，最多 3 轮，总上限 8 条。用户回复后立刻切回普通聊天。

### 8. 跨入口聊天记录可见性

- Remoire 前端能看到所有入口的消息（包括微信里的），按时间线混合排列。
- 来自微信的消息带小标记标注来源（如"via 微信"）。
- 微信端只看微信里的消息（微信平台本身保留记录）。
- Remoire 前端分条发送时，逐条流式打字 + 条间显示 typing indicator。

### 9. 成本控制和 token 节省必须写进文档

多入口最容易浪费 token，所以要明确成本原则：

- 不因为有微信和 Remoire 两个入口就生成两次回复。
- 静儿从哪个入口发消息，就只在那个入口回复。
- Connie 主动消息默认只发到一个入口，推荐微信优先。
- "两边都发"只有静儿手动开启时才使用。
- 同一条主动消息如果要多端展示，应尽量复用一次 AI 生成结果，而不是分别调用模型。
- 记忆召回只取最相关的少量内容，比如 top-3 到 top-5，避免每次塞太多历史。
- 长聊天先用摘要，再加最近几条原文，避免把完整聊天记录都发给模型。
- 后端记录 `usage_logs`，方便以后看哪些功能最费 token。
- 主动消息要有频率（默认 5 次/天）、冷却时间、每日上限，避免过度调用模型。
- LLM 月预算 ¥15-50，可稍多。

### 10. API 文档新增规划

建议在 `docs/API.md` 里新增：

- `GET /api/settings/models`：读取统一模型设置（3 个槽位）。
- `PUT /api/settings/models`：保存统一模型设置。
- `GET /api/settings/proactive`：读取主动消息设置（含 burst 参数）。
- `PUT /api/settings/proactive`：保存主动消息设置。
- `GET /api/settings/prompts`：读取 Prompt 分场景配置。
- `PUT /api/settings/prompts/{scene}`：保存某个场景 Prompt。
- `POST /api/settings/prompts/preview`：预览当前配置合成后的最终 Prompt。
- `POST /api/channels/{channel}/messages`：统一写入来自某个入口的消息。
- `POST /api/channels/wechat/inbound`：iLink 收到微信消息后进入 Remoire。
- `GET /api/channels/wechat/status`：获取微信连接状态（是否在线、token 是否过期）。
- `POST /api/channels/wechat/login`：触发微信扫码登录流程。

原有的 `GET/PUT /api/settings` 保留，只管 UI 偏好（深色模式、字体大小等）。
原有的 `/api/model` 接口逐步迁移到 `/api/settings/models`。

### 11. Phase 1 范围

Phase 1 必须完成：
1. 聊天核心（Remoire 前端能聊天）
2. 记忆系统（聊天自动提取 + 确认）
3. MCP（Claude.ai 共享记忆）
4. 微信桥接（iLink 直连）
5. 主动消息（含连续多条 + burst 状态机）
6. 对话导入（Claude 历史）
7. 分条发送（微信 + Remoire 都支持）

Phase 2 再做：
- 提醒 + 共同日历
- 日记系统（含上锁/解锁）
- 小纸条
- Prompt 编辑器 UI（后端先支持，前端设置页后面做）

## Critical Files To Modify

- `docs/PRD.md`：更新 Phase 1 范围、模型槽位改 3 个、微信桥接改 iLink 直连、主动消息 burst 规则、跨入口可见性、分条发送、markdown 约束。
- `docs/DATABASE.md`：model_settings 删 proactive 槽位、proactive_message_settings 加 burst 字段。
- `docs/API.md`：新增 settings 子路由、channels 接口、微信状态/登录接口。
- `docs/TECH_STACK.md`：更新字体（Petrona + Manrope + LXGW WenKai）、架构图加微信桥接层、模型槽位改 3 个、加 SQLite vs Supabase 说明。
- `.claude/CLAUDE.md`：补 Phase 1 原则（微信桥接、统一模型配置、双 DB 路线、iLink 直连）。

## Verification

文档阶段验证方式：

1. 读一遍 `docs/PRD.md`，确认产品方向能解释"Remoire 前端 / Claude.ai / 微信是多个入口，不是多个 AI"，Phase 1 包含微信桥接和对话导入。
2. 读一遍 `docs/DATABASE.md`，确认 SQLite 和 Supabase 两套路线共用同一套多入口数据结构，模型槽位只有 3 个，包含 burst 参数和 usage 记录。
3. 读一遍 `docs/API.md`，确认 settings 子路由、channels 接口、微信状态接口都有。
4. 读一遍 `docs/TECH_STACK.md`，确认架构图包含微信桥接层，字体已更新，有 SQLite vs Supabase 说明。
5. 不需要跑代码；这一步只改设计文档。
