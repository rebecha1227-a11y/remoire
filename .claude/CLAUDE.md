# 我们的小窝 · Remoire

## 项目一句话

一个两人专属的 AI 陪伴 PWA——不是工具，是关系空间。

## 技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 前端 | React + Vite | React 19, Vite 6 |
| 样式 | Tailwind CSS + CSS Variables | Tailwind 4 |
| 前端路由 | React Router | v7 |
| PWA | vite-plugin-pwa | 最新 |
| 后端 | Python + FastAPI | Python 3.12, FastAPI 0.115+ |
| 数据库 | SQLite (WAL mode) | — |
| 异步 DB | aiosqlite | 最新 |
| 定时任务 | APScheduler | 3.x |
| MCP | FastMCP | 最新 |
| HTTP 客户端 | httpx | 最新 |
| LLM 接口 | 任何 OpenAI 兼容格式 | — |

## 目录结构

```
our-nest/
├── .claude/                  # Claude Code 上下文（你正在读的）
│   ├── CLAUDE.md
│   ├── instructions.md
│   └── memories.md
├── docs/                     # 项目文档
│   ├── PRD.md               │ API.md
│   ├── TECH_STACK.md        │ DATABASE.md
│   ├── DESIGN_SYSTEM.md     │ DEPLOYMENT.md
│   └── design-prompts/       # 各页面设计 Prompt
├── frontend/                 # React 前端
│   └── src/
│       ├── components/       # ChatBubble, Card, Badge, NavBar...
│       ├── pages/            # ChatPage, UsPage, DiaryPage, PlayPage, SettingsPage
│       ├── hooks/            # useSSE, useChat, useMemory...
│       ├── stores/           # React Context
│       ├── styles/           # globals.css (CSS Variables)
│       ├── utils/            # api.js, format.js
│       └── App.jsx
├── backend/                  # FastAPI 后端
│   └── app/
│       ├── main.py           # FastAPI 入口 + CORS + auth middleware
│       ├── auth.py           # Bearer token 校验
│       ├── config.py         # 环境变量
│       ├── database.py       # SQLite + WAL + init
│       ├── llm.py            # 统一 LLM 调用（OpenAI 兼容）
│       ├── identity.py       # AI 人设 profile
│       ├── routers/          # chat, memory, diary, reminder, calendar,
│       │                     # import_, model, note, stream, settings, play, signal
│       ├── services/         # memory_service, association, reminder_service,
│       │                     # diary_service, nudge_service, digest_service
│       ├── scheduler/jobs.py # APScheduler 定时任务
│       └── prompts/          # identity.md, tagging.md, nudge.md
```

## 核心设计原则

1. **关系连续性** — 不同入口、不同时间，是同一段关系
2. **不是工具，是空间** — 设置页不比聊天页重要
3. **写就是读** — 写入新记忆时自动关联 top-3 旧记忆
4. **主动靠近** — AI 不只等你打开，它会找你
5. **候选先行** — 记忆先进候选，确认后才进正式库

## 承重墙（P0）

聊天 → 记忆（含关联） → MCP → 主动消息 → 提醒 → 日记 → 小纸条

## 当前阶段

Phase 1 — 文档设计完成，准备开发

## Phase 1 范围

聊天核心 + 记忆系统 + MCP + 微信桥接(iLink) + 主动消息(含 burst) + 对话导入 + 分条发送

## Phase 1 关键原则

- **多入口统一后端**：微信、Remoire 前端、Claude.ai 都只是入口，记忆/Prompt/模型配置归后端统一管理
- **微信桥接用 iLink API 直连**：Python 长轮询，跟 FastAPI 主进程一起跑，不走 OpenClaw
- **模型 3 个槽位**：daily（日常+主动消息）/ deep / backend，主动消息不单独设槽位
- **数据库双路线**：Phase 1 用 SQLite，表结构按多入口设计，未来可迁移 Supabase
- **成本控制**：一个入口发 → 一个入口回；主动消息默认单端；记忆召回 top-3~5；LLM 月预算 ¥15-50
- **分条发送**：微信和 Remoire 都支持 AI 连续发多条，逐条流式 + typing indicator

## DO

- 所有 LLM 调用走 `app/llm.py` 的 `call_llm()`，兼容 OpenAI 格式
- SQLite 开 WAL：`PRAGMA journal_mode=WAL`
- CSS Variables 管理颜色，暗色模式通过 `[data-theme="dark"]` 切换变量
- 字体：Display 用 **Petrona**（Google Fonts，人文衬线），Body UI 用 **Manrope**（Google Fonts，温暖几何无衬线），中文用 **LXGW WenKai 霞鹜文楷**（开源温暖手写感）。组件里硬编码改用 `var(--font-display)` / `var(--font-body)`
- 移动端优先，430px 设计基准
- API 统一格式：`{ "ok": bool, "data": ..., "error": ... }`
- 阴影用 `rgba(40,33,28,...)` 暖棕色
- 图标用 lucide-react，outline，stroke-width 1.5
- memories 表预留 `embedding BLOB` 字段
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
| remember() | 记住——生成记忆候选 |
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
| 部署 | docs/DEPLOYMENT.md |
| Phase 1 设计决策 | docs/PHASE1_DECISIONS.md |
