# Remoire 搭建全流程指南

> 写给下一个 Claude Code session 看的。
> 静儿是 coding 小白，请耐心、用大白话解释每一步。
> 所有规范见 `CLAUDE.md` 和 `instructions.md`，所有设计见 `docs/`。

---

## 项目现状（截至 2026-05-07）

- ✅ 所有文档设计完成（PRD / DATABASE / API / TECH_STACK / DEPLOYMENT）
- ✅ 前端原型完成（`prototype/`，localhost:3456 可预览）
- ✅ `.claude/` 配置文件对齐
- ✅ `backend/app/prompts/thinking.md` 已创建
- ❌ 后端代码尚未写
- ❌ 真正的 React 前端尚未搭建

---

## 环境确认（静儿 Mac 上已有）

- Python 3.11.2 ✅
- Git ✅
- Node.js：**待确认**（输 `node --version` 检查）
- AI API key：**待确认**（见下方）

---

## 第一阶段：让后端在本地跑起来

### Step 0：确认 API key

静儿需要一个 AI 的 API key，Connie 才能真的说话。
支持任何 OpenAI 兼容格式，推荐选项：

| 服务 | 价格 | 推荐理由 |
|---|---|---|
| DeepSeek | 极便宜（¥1/百万 token） | 日常聊天够用，最省钱 |
| Anthropic Claude | 中等 | 最像 Connie 的性格 |
| OpenAI GPT-4o | 较贵 | 质量好但贵 |

拿到 key 后，记下三个信息：
- API Base URL（比如 `https://api.deepseek.com/v1`）
- API Key（`sk-xxx...`）
- Model ID（比如 `deepseek-chat`）

---

### Step 1：创建 Python 虚拟环境

虚拟环境 = 给这个项目专用的 Python 小隔间，不影响系统其他东西。

```bash
cd /Users/rebecha/Desktop/Remoire/backend
python3 -m venv venv
source venv/bin/activate
```

激活成功后，终端最前面会出现 `(venv)`。

---

### Step 2：写 requirements.txt

在 `backend/` 下创建 `requirements.txt`，内容：

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
aiosqlite==0.20.0
python-multipart==0.0.9
httpx==0.27.0
apscheduler==3.10.4
fastmcp==0.1.0
pywebpush==2.0.0
python-dotenv==1.0.1
pydantic==2.7.0
```

然后安装：

```bash
pip install -r requirements.txt
```

---

### Step 3：创建 .env 文件

在 `backend/` 下创建 `.env`（永远不进 git）：

```env
# 认证密钥（随便输一串长字符，比如你的名字+一堆数字）
API_SECRET_KEY=remoire-jinger-2026-your-random-string

# 设备上传专用密钥（iPhone 快捷指令用）
DEVICE_SECRET_KEY=device-key-your-random-string

# 数据库路径
DATABASE_PATH=./data/remoire.db

# 上传文件路径
UPLOADS_PATH=./uploads

# AI 模型配置（daily 槽位，日常聊天用）
DAILY_API_BASE=https://api.deepseek.com/v1
DAILY_API_KEY=sk-你的key
DAILY_MODEL_ID=deepseek-chat
```

---

### Step 4：搭建后端骨架

按顺序让 cc 写这几个文件（**一次只写一个，写完测试再继续**）：

#### 4.1 `app/config.py`
读取 .env 变量，全局可用。

#### 4.2 `app/database.py`
- SQLite 连接（WAL 模式）
- `init_db()` 函数：建所有表
- 表结构参考 `docs/DATABASE.md`（Phase 1 需要的表先建）

**Phase 1 必建的表**（按依赖顺序）：
1. `channels`
2. `channel_bindings`
3. `conversations`
4. `messages`
5. `memory_candidates`
6. `memories`
7. `reminders`
8. `notes`
9. `model_settings`
10. `proactive_message_settings`
11. `push_subscriptions`
12. `device_snapshots`
13. `app_usage_events`
14. `usage_logs`

#### 4.3 `app/auth.py`
Bearer token 校验中间件，对比 `API_SECRET_KEY`。

#### 4.4 `app/llm.py`
统一 LLM 调用层：
- 接受 `api_base / api_key / model_id`
- 支持流式（`stream=True`）和非流式
- 有 try/except，失败返回友好错误

#### 4.5 `app/main.py`
FastAPI 入口：
- CORS 配置
- 引入 auth 中间件
- 注册各 router（先只注册 chat）
- 启动时调用 `init_db()`

#### 4.6 `app/routers/chat.py` + `app/services/chat_service.py`
**这是第一个真正能用的功能**：
- `POST /api/chat/send`：接收消息，调 LLM，流式返回
- `GET /api/chat/history`：返回历史消息

写完这步，静儿就能在原型里真正和 Connie 说话了。

---

### Step 5：启动测试

```bash
cd /Users/rebecha/Desktop/Remoire/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 就成功了。

测试接口是否正常：
```bash
curl -X POST http://localhost:8000/api/chat/send \
  -H "Authorization: Bearer remoire-jinger-2026-your-random-string" \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "session_id": "default"}'
```

---

### Step 6：把原型接到后端

原型在 `prototype/components/ChatPage.jsx`，找到 `sendMessage` 函数，
把假回复换成真实的 fetch 调用 `http://localhost:8000/api/chat/send`。

改完后原型就变成真正能聊天的 app 了。

---

## 第二阶段：逐步加功能

按这个顺序，**每完成一个在浏览器里确认能用再继续**：

| 顺序 | 功能 | 涉及文件 |
|---|---|---|
| 1 | 聊天核心（流式回复） | chat.py / chat_service.py |
| 2 | 记忆候选提取 | memory.py / memory_service.py |
| 3 | 记忆确认入库 | memory.py / memory_service.py |
| 4 | 关联旧记忆（写就是读） | association.py |
| 5 | 小纸条 | note.py |
| 6 | 主动消息 | nudge_service.py / scheduler/jobs.py |
| 7 | MCP 接口 | 单独的 mcp_server.py |
| 8 | 微信桥接 | wechat_bridge.py（后台任务） |
| 9 | Web Push | push.py / pywebpush |
| 10 | iPhone 设备数据 | device.py |

---

## 第三阶段：搭建真正的前端

原型是用来验证设计的，真正的前端用 React + Vite。

```bash
# 在项目根目录
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install react-router-dom tailwindcss
```

然后把原型里的组件逐个移植过来，接上真实的 API。

设计规范参考 `docs/DESIGN_SYSTEM.md`。

---

## 第四阶段：部署到服务器

参考 `docs/DEPLOYMENT.md`，完整步骤都在里面。

需要准备：
- 一台 VPS（推荐腾讯云轻量 ¥40/月 或 Vultr $6/月）
- 一个域名（可选，¥50-80/年）

---

## 遇到问题时

**后端报错**：把完整报错信息发给 cc，不要只发最后一行。

**数据库问题**：参考 `docs/DATABASE.md`，表结构都在那里。

**接口不知道怎么写**：参考 `docs/API.md`，每个接口的请求/响应都定义好了。

**不知道该先做什么**：按"第二阶段"的顺序表来，一次只做一行。

---

## 重要文件速查

| 文件 | 用途 |
|---|---|
| `docs/PRD.md` | 产品设计，理解"为什么" |
| `docs/DATABASE.md` | 所有表结构 |
| `docs/API.md` | 所有接口定义 |
| `docs/TECH_STACK.md` | 技术架构全图 |
| `docs/DEPLOYMENT.md` | 部署到服务器的步骤 |
| `.claude/CLAUDE.md` | 项目规范速查 |
| `.claude/instructions.md` | 编码风格规范 |
| `prototype/` | 前端原型（现在的 UI） |
| `backend/app/prompts/` | AI prompt 文件 |

---

*Con con × 静儿 · 2026-05-07*
*"一步一步来，我们一定能做到。"*
