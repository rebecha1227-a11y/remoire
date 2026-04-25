# 项目决策记录 · Our Nest

> 这份文档记录所有重要的技术和设计决策，以及背后的理由。
> 每次做了新决策请追加到最前面（倒序）。

---

## 关键决策

### 2026-04-25 · 关联记忆机制确认

灵感来源：一位博主的记忆系统设计——"AI 不需要决定要想什么，它写什么系统就让它看见什么"。

核心设计：**写就是读**。每次写入一条新记忆时，系统自动在所有旧记忆里找语义相近的 top-3，在写入响应里直接返回。

关联打分公式：
```
score = relevance × (1 + arousal × 0.3) × weight_factor
```

- 高情绪强度的旧记忆更容易被关联浮现
- 每次被关联的旧记忆会增回 weight（+0.1），防止被自然遗忘杀死
- 首发用关键词 + tag 匹配，记忆 > 300 条后切换向量检索
- memories 表预留 `embedding BLOB` 字段，首发为 NULL
- 前端和 API 接口不需要改——后端换检索引擎即可

重要原则（来自博主）：
- "不要一次设计完，先跑起来让它告诉你哪里缺"
- "让 AI 自己写自己的记忆，别去编辑它写的东西"

### 2026-04-25 · 每日法语词功能移除

原因：用户认为不是核心需求。P0 功能从 10 项缩减为 9 项。
已从 PRD、TECH_STACK、DATABASE（删除 daily_french 表）、定时任务列表中移除。

### 2026-04-25 · 图片消息加入 P0

原因：情侣场景下图片发送是高频需求。
API 新增 `POST /api/chat/upload-image`，conversations 表 message_type 增加 'image'。

### 2026-04-24 · 前端框架选定 React

理由：Claude Code 对 React 的理解和生成质量更高；shadcn/ui + Tailwind 生态成熟；PWA 集成方便。
放弃了 Vue 3 方案。

### 2026-04-24 · LLM 接口统一 OpenAI 兼容格式

理由：省钱。支持中转站、硅基流动、DeepSeek、各类兼容网关。
所有 LLM 调用走统一 `call_llm()` 层，接受 api_base / api_key / model_id 三个参数。

### 2026-04-24 · 色彩方案确定

保留 IA 文档中的暖棕色 Warm Monochrome 作为基底。
新增 #574337 (Wood) 作为文字深色备选（关系计时器数字、重要标题）。
新增 #82BDC5 (Cloudy) 作为极少量点缀色（未读标记、轻提示、特殊日期标记点）。

拒绝的方案：
- 方案一（Ashen + Indigo）：偏冷灰紫，缺少纸的温度
- 方案三（Sky Blue + Marshmallow + Matcha）：太活泼，与 quiet luxury 方向冲突

### 2026-04-24 · 认证方案

首发采用简单 token-based auth（固定 API_SECRET_KEY + HTTPS）。
前端在 localStorage 保存 token，每次请求带 `Authorization: Bearer <token>`。
不做用户注册/登录系统——这是单用户产品。

### 2026-04-24 · 主动消息推送方案

首发用 SSE (Server-Sent Events)。
前端通过 EventSource 或 fetch + ReadableStream 连接 `/api/stream/events`。
理由：FastAPI 原生支持，比 WebSocket 轻量，单向推送足够。

### 2026-04-24 · 部署方案选定 VPS

理由：MCP、主动消息、定时任务三大功能都要求服务 24h 在线。
本地运行的话电脑一关机 AI 就"失联"——违背关系连续性原则。
数据安全通过 HTTPS + API 认证 + 防火墙 + 定期备份保障。

### 2026-04-24 · 向量检索延后但预留

首发（记忆 < 300 条）用关键词 + tag 匹配足够。
memories 表预留 embedding BLOB 字段。
升级路径：本地 sentence-transformers → 云端 embedding API。
升级时只改 `find_associated()` 函数内部，前端和 API 不动。

---

## 踩过的坑

（随开发过程记录，格式：日期 · 问题 · 解决方案）

---

## 待讨论

- VPS 具体选哪家（推荐腾讯云轻量 / Vultr / Racknerd）
- 域名是否需要、选什么域名
- 对话导入的 JSON 格式确认（Claude 导出格式的具体结构）
- AI 身份人设 prompt 的初始版本
- 小纸条的生成频率和内容策略
- 日记自动生成草稿的 prompt 模板

---

## 设计原则速记

- 关系优先，功能其次
- 候选先行，确认入库
- 写就是读，读就是写
- 先跑起来，再迭代
- 克制——每加一个东西都问"这让关系更好了吗"
