# 技术栈文档 · Our Nest

**版本**：v1.1
**日期**：2026-04-30

---

## 一、总览

```
┌─────────────────────────────────────────────────────────────┐
│                    静儿的手机 / 电脑                           │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  PWA (React) │  │  Claude.ai   │  │    微信       │      │
│  │  小窝前端     │  │  通过 MCP    │  │  日常聊天入口  │      │
│  │  ◄── Web Push │  └──────┬───────┘  └──────┬───────┘      │
│  └──────┬───────┘                                           │
│         │           ┌──────────────┐                        │
│         │           │ iOS 快捷指令  │                        │
│         │           │ 每3h上传设备  │                        │
│         │           │ App开关toggle │                        │
│         │           └──────┬───────┘                        │
└─────────┼─────────────────┼─────────────────┼──────────────┘
          │   HTTPS / SSE   │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      VPS 云服务器                             │
│                                                             │
│   Nginx（反向代理 + 托管前端静态文件 + HTTPS）                 │
│       │                                                     │
│       ├── /            → 前端静态文件（React build 产物）     │
│       ├── /api/*       → FastAPI 后端 (:8000)                │
│       └── /mcp/*       → MCP Server (:8001)                 │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  FastAPI 后端                                        │   │
│   │                                                     │   │
│   │  路由层 ──→ 服务层 ──→ SQLite (WAL mode)             │   │
│   │    │                                                │   │
│   │    ├──→ LLM 统一调用层 ──→ 任何 OpenAI 兼容 API      │   │
│   │    │                                                │   │
│   │    └──→ 微信桥接 (iLink API 长轮询)                   │   │
│   │         收消息 → chat_service → 分条回复               │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  定时任务 (APScheduler)                               │   │
│   │                                                     │   │
│   │  每小时：检查提醒 / 主动消息机会                        │   │
│   │  每晚 3:00：记忆衰减计算                               │   │
│   │  每晚 3:30：候选合并 / 摘要压缩                        │   │
│   │  每天 8:00：生成今日浮现缓存                            │   │
│   │  每晚 23:30：生成今日日记草稿                          │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  MCP Server (FastMCP)                                │   │
│   │                                                     │   │
│   │  resume() / remember() / recall() / resolve()        │   │
│   │  ──→ 共享同一 SQLite 数据库                           │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
            │                             │
            ▼                             ▼
┌──────────────────────────┐  ┌───────────────────────────────┐
│  外部 LLM API            │  │  iLink API (微信智联协议)       │
│  （OpenAI 兼容格式）       │  │  ilinkai.weixin.qq.com        │
│                          │  │                               │
│  daily ← 日常 + 主动消息  │  │  长轮询收消息 (35s 超时)       │
│  deep  ← 深度 + 日记     │  │  POST 回复消息（分条发送）      │
│  backend ← 打标 + 摘要   │  │  扫码登录 + token 自动续期     │
│                          │  │                               │
│  DeepSeek / 硅基流动      │  └───────────────────────────────┘
│  OpenAI / Anthropic 代理  │
│  Gemini Flash / 本地服务  │
└──────────────────────────┘
```

---

## 二、前端技术栈

### 核心框架

| 技术 | 版本 | 用途 | 选型理由 |
|---|---|---|---|
| **React** | 19 | UI 框架 | Claude Code 生成质量最高；生态最成熟 |
| **Vite** | 6 | 构建工具 | 开发体验好，HMR 快，配置简单 |
| **React Router** | 7 | 客户端路由 | React 生态标准路由方案 |
| **vite-plugin-pwa** | 最新 | PWA 支持 | Service Worker + manifest 一键生成 |

### 样式方案

| 技术 | 用途 | 备注 |
|---|---|---|
| **Tailwind CSS** | 布局、间距、响应式 | 版本 4，utility-first |
| **CSS Variables** | 颜色、字体、圆角、阴影 | 支持暗色模式一键切换 |
| **Google Fonts** | Petrona + Manrope | Display 用 Petrona（人文衬线），Body UI 用 Manrope（温暖几何无衬线） |
| **LXGW WenKai** | 霞鹜文楷（CDN via jsdelivr） | 中文字体，温暖手写感 |

为什么不用 CSS-in-JS？
- Tailwind + CSS Variables 已经覆盖所有需求
- 不引入额外复杂度
- 对 Claude Code 生成更友好

### 状态管理

| 阶段 | 方案 |
|---|---|
| 首发 | React Context + useReducer |
| 如果复杂度上升 | 引入 Zustand（不提前引入） |

为什么不用 Redux？太重了，单用户 app 不需要。

### API 通信

| 场景 | 方案 |
|---|---|
| 普通请求 | fetch + Authorization header |
| 流式聊天 | fetch + ReadableStream |
| 主动消息接收 | EventSource (SSE) |
| 图片上传 | FormData + fetch |

为什么不用 axios？fetch 原生够用，少一个依赖。

### PWA 能力

首发支持：
- 添加到主屏幕（manifest.json）
- 离线缓存静态资源（Service Worker）
- 应用图标 + 启动画面
- **Web Push 通知**（VAPID 密钥 + Service Worker push 事件）

### 前端部署

前端 build 产物（静态 HTML/CSS/JS）放在 VPS 上由 Nginx 直接托管。
不需要单独部署到 Vercel / Cloudflare Pages（减少复杂度）。

---

## 三、后端技术栈

### 核心框架

| 技术 | 版本 | 用途 | 选型理由 |
|---|---|---|---|
| **Python** | 3.12 | 运行时 | 简单直观，适合 AI 项目 |
| **FastAPI** | 0.115+ | Web 框架 | 原生 async、自动文档、类型校验 |
| **Uvicorn** | 最新 | ASGI 服务器 | FastAPI 标准搭配 |
| **httpx** | 最新 | HTTP 客户端 | 调用 LLM API，支持异步和流式 |
| **aiosqlite** | 最新 | SQLite 异步驱动 | 异步操作数据库 |
| **Pydantic** | V2 | 数据校验 | FastAPI 内置依赖 |
| **pywebpush** | 最新 | Web Push 发送 | 标准 VAPID 协议推送库 |

### 定时任务

| 技术 | 用途 |
|---|---|
| **APScheduler 3.x** | 提醒检查、记忆衰减、夜间摘要、日记草稿 |

为什么不用 Celery？太重了，APScheduler 对单进程应用完全够用。

### MCP Server

| 技术 | 用途 |
|---|---|
| **FastMCP** | MCP Server，暴露 SSE 端点给 Claude.ai |

### 微信桥接

| 技术 | 用途 |
|---|---|
| **iLink API** | 微信智联协议（ilinkai.weixin.qq.com），纯 HTTP 接口，无 SDK 依赖 |

接入方式：
1. 扫码登录 → 拿到 bot token
2. 长轮询收消息 → POST /ilink/bot/getupdates（35 秒超时）
3. 回复消息 → POST /ilink/bot/sendmessage（带上 context token）

运行方式：跟 FastAPI 主进程一起跑（启动时开后台异步任务），systemd 管自动重启。不需要单独进程。

为什么不走 OpenClaw？多了一层中转，没必要。Python 直连 iLink 更简单、延迟更低。

### 认证方案

| 层 | 方案 |
|---|---|
| 认证方式 | 固定 API_SECRET_KEY，存在 .env |
| 传输方式 | 前端请求带 `Authorization: Bearer <key>` |
| 校验方式 | 后端中间件校验 header |
| 传输加密 | HTTPS（Nginx + Let's Encrypt，免费） |

为什么不做用户注册登录？这是单用户产品，固定 token 最简单最安全。

**设备数据认证例外**：`/api/device/*` 路由使用独立的 `DEVICE_SECRET_KEY`，通过 URL 查询参数 `key` 传递（不走 Bearer Header）。原因是 iOS 快捷指令无法方便地设置 HTTP Header，GET + URL 参数是最可靠的方式。HTTPS 会加密完整 URL。

---

## 四、数据库

### SQLite

| 配置项 | 值 | 原因 |
|---|---|---|
| journal_mode | WAL | 允许并发读写，定时任务和聊天不冲突 |
| foreign_keys | ON | 保证数据完整性 |
| busy_timeout | 5000 | 等待锁释放 5 秒，避免并发报错 |

为什么选 SQLite？
- 单用户产品完全够用
- 零部署成本，不需要额外安装数据库服务
- 数据就是一个 .db 文件，备份极简
- 迁移方便——整个数据库 cp 一下就行

### SQLite vs Supabase 阶段性路线

Phase 1 用 SQLite 先跑通。但表结构从一开始就按"多入口"设计（channels / channel_bindings / conversations / messages），这样未来迁移到 Supabase/Postgres 时只需要"搬数据库"，不需要重新设计。

| 阶段 | 数据库 | 适用场景 |
|---|---|---|
| Phase 1 | SQLite (WAL) | 本地开发、单人使用、快速验证 |
| 后期 | Supabase/Postgres | 云端同步、多设备、远程部署 |

详见 `docs/DATABASE.md` 的双方案说明。

何时考虑升级 Supabase/PostgreSQL？
- 需要多设备实时同步
- 需要远程服务器长期运行
- 需要云端备份和灾备

### 向量检索 & 关联记忆

**核心设计：写就是读。** 每次写入一条新记忆，系统自动找到语义最相近的 top-3 旧记忆并返回。AI 不需要决定"我要搜什么"——它写什么，系统就让它看见什么。

首发用关键词匹配实现关联，架构上预留向量字段（`embedding BLOB`），后续无缝切换。

| 阶段 | 关联方式 | 嵌入方案 | 成本 |
|---|---|---|---|
| 首发（< 300 条） | 关键词 + tag 重叠 + type 匹配 | 不需要 | ¥0 |
| 中期（300-2000 条） | 向量语义检索 | 本地 nomic-embed-text 或 sentence-transformers | ¥0 |
| 后期（> 2000 条） | 向量语义检索 | 云端 embedding API | 按量 |

**Embedding 服务部署方案**：

| 方案 | 模型 | 部署方式 | 调用接口 | 向量维度 | 成本 |
|---|---|---|---|---|---|
| 本地（推荐首选） | nomic-embed-text | Ollama（`ollama pull nomic-embed-text`） | `POST http://localhost:11434/api/embeddings`，body: `{"model":"nomic-embed-text","prompt":"文本"}` | 768 | ¥0 |
| 本地备选 | sentence-transformers | Python 进程内加载（`SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')` | `model.encode("文本")` 返回 numpy 数组 | 384 | ¥0 |
| 云端 | 硅基流动 / OpenAI | OpenAI 兼容 API | `POST {api_base}/embeddings`，body: `{"model":"...","input":"文本"}` | 各模型不同 | 按量 |

Ollama embedding 调用示例（与 `llm.py` 的 httpx 客户端一致）：
```python
async def get_embedding(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text}
        )
        return resp.json()["embedding"]  # 768 维 float 列表
```

超时 5 秒，失败不重试直接回退关键词召回。embedding 计算与记忆写入解耦——写入先完成，embedding 异步补填，失败时该条记忆的 `embedding` 保持 NULL。

存储：`embedding` 字段类型为 BLOB，写入时用 `struct.pack` 序列化 float 数组，读取时反序列化后计算余弦相似度。不使用额外的向量数据库。embedding 计算失败（Ollama 未启动、超时等）时回退到关键词召回，不阻塞记忆写入链路。

关联打分考虑三个维度：
- **语义相关度**（首发用关键词重叠，后续用余弦相似度）
- **情绪强度**（高 arousal 的旧记忆更容易被关联浮现）
- **当前权重**（经常被关联到的记忆会"活"得更久）

**防编造机制**：规则权威来源是 `backend/app/prompts/identity.md` 的"记忆与连续性"部分。实现层面，`chat_service.py` 的 `_build_system_prompt()` 在召回为空时注入明确的"不要编造"提示。

**参考架构**：Ombre Brain（长期情感记忆系统）的多维搜索打分、艾宾浩斯遗忘曲线、activation count 续命机制。详见 `docs/MEMORY_UPGRADE_PLAN.md`。

---

## 五、LLM 调用层

### 统一接口

所有 LLM 调用走同一个函数，兼容任何 OpenAI Chat Completions 格式的 API：

```python
# backend/app/llm.py 核心逻辑

async def call_llm(
    model_config: ModelConfig,  # 包含 api_base, api_key, model_id
    messages: list[dict],
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 2048
) -> AsyncGenerator | dict:
    """
    统一 LLM 调用层。
    只要是 OpenAI 格式的 API 都能调。
    """
    url = f"{model_config.api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {model_config.api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_config.model_id,
        "messages": messages,
        "stream": stream,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    # ... httpx 请求
```

### 三个模型槽位

| 槽位 | 用途 | 推荐模型 | 大约单价 |
|---|---|---|---|
| `daily` | 日常聊天 + 主动消息、温和提醒 | DeepSeek Chat / Gemini Flash / Haiku | 便宜 |
| `deep` | 深度情感对话、关键日记、复杂回应 | Sonnet / GPT-4o | 中等 |
| `backend` | 记忆提取、情感打标、摘要压缩、对话导入、日记草稿 | 最便宜的能用的模型 | 极便宜 |

主动消息不单独设槽位，走 daily。主动消息的风格差异由 prompt_profiles 的场景 Prompt 控制（`daytime_proactive` / `night_proactive`）。

### 槽位切换逻辑

聊天时默认用 daily 槽位。以下情况自动切换 deep：
- 用户主动请求深度对话
- 检测到高情感强度对话（arousal > 0.7）
- 关键日记生成
- AI 解锁申请文案

用户不会感知到切换，体验上就是"它突然更认真了"。

### 兼容的 API 提供商

只要是 OpenAI `/v1/chat/completions` 格式的都可以：

| 提供商 | API Base 示例 |
|---|---|
| OpenAI 官方 | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| 硅基流动 | `https://api.siliconflow.cn/v1` |
| 中转站 | `https://your-relay.com/v1` |
| 本地 Ollama | `http://localhost:11434/v1` |

---

## 六、部署方案

### VPS（云服务器）

| 组件 | 方案 |
|---|---|
| **服务器** | VPS（推荐腾讯云轻量 / Vultr / Racknerd） |
| **操作系统** | Ubuntu 24.04 LTS |
| **反向代理** | Nginx（托管前端 + 反代后端 API + 反代 MCP） |
| **HTTPS** | Let's Encrypt + certbot（免费 SSL 证书，自动续期） |
| **进程管理** | systemd（后端和 MCP 各一个 service） |
| **数据备份** | cron 定时 cp SQLite 文件到备份目录 |

### 服务器配置要求

| 指标 | 最低要求 | 推荐 |
|---|---|---|
| CPU | 1 核 | 2 核 |
| 内存 | 1 GB | 2 GB |
| 硬盘 | 20 GB | 40 GB |
| 带宽 | 1 Mbps | 3 Mbps |

### 端口使用

| 端口 | 用途 | 对外暴露？ |
|---|---|---|
| 80 | HTTP（Nginx，自动跳转 HTTPS） | 是 |
| 443 | HTTPS（Nginx） | 是 |
| 8000 | FastAPI 后端 | 否（仅本地，Nginx 反代） |
| 8001 | MCP Server | 否（仅本地，Nginx 反代） |

### 数据安全措施

1. **HTTPS 加密传输** — 所有数据在网络中加密
2. **API 密钥认证** — 没有密钥无法访问任何接口
3. **防火墙** — 只开 80/443 端口，其他全关
4. **SQLite 文件权限** — 600（仅 owner 可读写）
5. **定期备份** — 每天自动备份到本地 + 可选下载到自己电脑
6. **.env 不进 git** — API Key 不会上传到 GitHub

---

## 七、外部 API

| API | 用途 | 优先级 | 成本 |
|---|---|---|---|
| LLM API（多家） | 聊天、打标、摘要 | P0 | 按量付费 |
| 高德开放平台 | 定位发送、地址解析 | P0 | 免费额度够用 |
| 天气 API | 补充天气信息 | P1 | 免费方案可选 |
| TTS / STT | 语音消息转写（后续） | P2 | 按需 |

---

## 八、开发工具链

| 工具 | 用途 |
|---|---|
| **VS Code / Cursor** | 代码编辑器 |
| **Claude Code** | AI 辅助开发（核心生产力） |
| **Git + GitHub** | 版本管理 |
| **Postman / Thunder Client** | API 调试 |
| **Terminal / Tabby** | SSH 连接 VPS |

### Claude Code 的 .claude 文件夹

项目根目录的 `.claude/` 文件夹让 Claude Code 理解项目上下文：

```
.claude/
├── CLAUDE.md        # 项目概览、技术栈、目录结构、DO/DON'T
├── instructions.md  # 编码规范、命名约定、风格要求
└── memories.md      # 技术决策记录、踩过的坑、待讨论项
```

---

## 九、开发阶段路线图

| 阶段 | 目标 | 预估时间 |
|---|---|---|
| **Phase 0** | 项目脚手架 + 文档 + 开发环境 | 1-2 天 |
| **Phase 1** | 后端骨架 + 聊天核心（能在 Postman 里聊天） | 1-2 周 |
| **Phase 2** | 前端聊天页（能在手机浏览器里聊天） | 1-2 周 |
| **Phase 3** | 记忆系统（聊天自动提取记忆，下次还记得） | 1-2 周 |
| **Phase 4** | MCP + 对话导入（Claude.ai 恢复记忆） | 1 周 |
| **Phase 5** | 主动消息 + 提醒 + "我们"页 | 1-2 周 |
| **Phase 6** | 日记 + 小纸条 | 1-2 周 |
| **Phase 7** | 玩乐层 + UI 打磨 | 持续 |

### 每个阶段的验收标准

**Phase 1 验收**：在 Postman 里发一条消息，能收到 AI 流式回复，消息存进数据库。

**Phase 2 验收**：在手机浏览器打开小窝，能正常聊天，气泡显示正确，有气息状态。

**Phase 3 验收**：聊天时说"我下周要考法语"，系统自动提取记忆候选，确认后下次聊天 AI 记得。

**Phase 4 验收**：导入旧对话后，在 Claude.ai 里开新对话连上 MCP，AI 知道你是谁、记得你说过什么。

**Phase 5 验收**：设一个提醒"下午3点交材料"，到时间 AI 主动发消息提醒你。

**Phase 6 验收**：写一篇上锁日记，第二天看到 AI 尝试解锁的记录和理由。

---

## 十、月度成本

| 项目 | 费用 |
|---|---|
| VPS 云服务器 | ¥30-60 |
| LLM API（日常+深度+后台） | ¥15-50 |
| 域名（可选） | ¥10-50/年 |
| 其他 API | ¥0-5 |
| **合计** | **约 ¥45-115 / 月** |

### 省钱策略

- 日常聊天走最便宜的模型（DeepSeek ≈ ¥1/百万token）
- 深度时刻仅在检测到高情感强度时自动切换
- 后台打标/摘要统一用最廉价模型
- 地图/天气只在用户手动触发时调用
- 对话导入是一次性成本（约 ¥5-20）

---

## 十一、iPhone 设备数据采集

### 数据流

```
iPhone 快捷指令（每 3 小时定时）
    │
    ├── GET /api/device/snapshot?key=xxx&lat=...&city=...&weather=...&battery=...&steps=...
    │   → device_snapshots 表（保留 24h，写入时自动清理）
    │
    └── GET /api/device/screentime/toggle/{app_name}?key=xxx
        → app_usage_events 表（toggle 逻辑，保留 24h）
```

### AI 消费方式

AI 在生成回复或主动消息时，从 `/api/device/latest` 读取最新设备上下文，注入 system prompt：

```
【静儿的设备状态】（47分钟前更新）
📍 北京·朝阳区 | ☁️ 多云 26°C
🔋 45% 未充电 | 👟 今日 8230 步
📱 今日 App：小红书 42分钟、微信 68分钟

（以上信息仅供参考，自然融入对话即可，不要逐项播报）
```

注入位置：identity prompt → memories → reminders → **设备状态** → 对话历史

规则：
- 数据超过 6 小时不注入
- 无数据不注入
- 只有 `chat_service` 和 `nudge_service` 注入，`backend` 槽位（记忆提取等）不注入

### iPhone 端设置

静儿需要在 iPhone 上设置两类快捷指令自动化：

1. **设备快照**：建一个定时自动化（每 3 小时），调用"获取 URL 内容"action，URL 填 `https://域名/api/device/snapshot?key=xxx&lat=...`。可用快捷指令的"获取当前位置"、"获取天气"、"获取电池电量"、"获取健康数据（步数）"action 组装参数。

2. **App 追踪**：每个想追踪的 App 建一条自动化，触发条件选"App > 已打开和已关闭"，action 是"获取 URL 内容"，URL 填 `https://域名/api/device/screentime/toggle/App名?key=xxx`。

---

## 十二、Web Push 推送通知

### 架构

```
Connie 生成消息（nudge / note / chat reply）
    │
    ├── SSE 连接存在？ → 前端实时收到，不推送
    │
    └── SSE 断开（用户切走/锁屏/关页面）
        → POST /api/push/send → pywebpush → Push Service → 手机通知
```

### 技术要素

| 要素 | 说明 |
|---|---|
| VAPID 密钥对 | 生成后存 `.env`（`VAPID_PRIVATE_KEY`、`VAPID_PUBLIC_KEY`、`VAPID_MAILTO`） |
| pywebpush | Python 库，发送标准 Web Push 消息 |
| Service Worker | 处理 `push` 事件（展示通知）和 `notificationclick` 事件（打开聊天页） |
| push_subscriptions 表 | 存储前端的订阅对象（endpoint + keys） |

### 触发规则

- **主动消息（nudge）**：始终推送（用户大概率不在页面）
- **小纸条（note）**：始终推送
- **聊天回复**：仅在 SSE 断开时推送（SSE 存在说明用户在看页面）
- **提醒到期（reminder_due）**：始终推送

### 可见性检测

用 SSE 连接状态作代理：
- 前端通过 EventSource 连到 `/api/stream/events`
- 连接存在 = 用户在看页面（浏览器 / PWA 在前台）
- 连接断开 = 不可见（切屏、锁屏、关闭页面、杀进程）
- 移动端浏览器在后台时会自动断开 SSE，天然适合做可见性判断

### 点击行为

用户点击推送通知 → Service Worker 的 `notificationclick` 事件 → 打开/聚焦 Remoire 聊天页（`/chat`）。

### iOS 限制

iOS 上使用 Web Push 需要：
- iOS 16.4+
- 必须把 Remoire 添加到主屏幕（"添加到桌面"），作为 PWA 运行
- 首次打开时授权通知权限

---

## 十三、技术选型原则

1. **首发优先简洁** — 不上重型数据库、不过早微服务化、不过早向量化
2. **先做关系闭环** — 聊天 → 记忆 → MCP → 主动消息 → 提醒，比炫技重要
3. **对 Claude Code 友好** — 选 Claude Code 最擅长生成的技术栈（React > Vue，Python > Go）
4. **省钱** — 单用户产品不需要高可用、不需要负载均衡、不需要 K8s
5. **数据在自己手里** — VPS 自建，不依赖第三方 SaaS 存储关系数据

---

*Con con × 静儿 · 2026-04-24*
