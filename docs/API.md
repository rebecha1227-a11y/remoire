# API 接口设计 · Our Nest

**版本**：v1.1
**日期**：2026-04-30

---

## 一、通用规范

### Base URL

```
https://{your-domain}/api
```

### 认证

生产目标方案：用户名 + 密码登录，登录成功后后端设置 HttpOnly session cookie。之后普通 `/api/*` 请求依赖浏览器自动携带的 cookie，不再要求前端保存固定 Bearer token。

当前代码仍处在 Bearer token 过渡态；后续实现登录/session 后，应将通用 API 校验切到 session cookie。

**设备上传例外**：iOS 快捷指令调用的设备上传接口使用 URL 查询参数 `key` 认证（独立的 `DEVICE_SECRET_KEY`）。原因是 iOS 快捷指令无法方便地设置 HTTP Header，GET 请求 + URL 参数是最可靠的方式。`DEVICE_SECRET_KEY` 存在 `.env` 里，HTTPS 会加密完整 URL。内部读取类接口仍走普通 app 认证（当前 Bearer 过渡，目标 session cookie）。

### 登录接口（计划）

#### POST `/api/auth/login`

用户名 + 密码登录。成功后设置 HttpOnly session cookie。

**请求体**：
```json
{
  "username": "jinger",
  "password": "..."
}
```

**响应**：
```json
{
  "ok": true,
  "data": {
    "username": "jinger"
  }
}
```

#### POST `/api/auth/logout`

清除当前 session cookie。

#### GET `/api/auth/me`

检查当前是否已登录。

**响应**：
```json
{
  "ok": true,
  "data": {
    "username": "jinger"
  }
}
```

登录密码只用于进入 Remoire。模型 API key 仍在设置页的模型预设里配置，并由 daily / deep / backend 槽位使用。

### 响应格式

所有接口返回统一 JSON 格式：

```json
// 成功
{
  "ok": true,
  "data": { ... }
}

// 失败
{
  "ok": false,
  "error": "错误描述"
}

// 分页列表
{
  "ok": true,
  "data": {
    "items": [ ... ],
    "total": 100,
    "page": 1,
    "limit": 20,
    "has_more": true
  }
}
```

### 通用参数

分页参数（GET 列表接口）：
- `page` — 页码，从 1 开始，默认 1
- `limit` — 每页条数，默认 20，最大 100

时间参数统一 ISO 8601 格式：`2026-04-24T15:30:00`

---

## 二、聊天 `/api/chat`

### POST `/api/chat/send`

发送消息并获取 AI 流式回复。这是最核心的接口。

**请求体**：

```json
{
  "session_id": "default",
  "message": "今天好累啊",
  "message_type": "text",
  "metadata": null
}
```

图片消息：
```json
{
  "session_id": "default",
  "message": "",
  "message_type": "image",
  "metadata": {
    "image_url": "/uploads/img_xxx.jpg"
  }
}
```

定位消息：
```json
{
  "session_id": "default",
  "message": "",
  "message_type": "location",
  "metadata": {
    "lat": 39.9042,
    "lng": 116.4074,
    "address": "北京市东城区"
  }
}
```

**响应**：SSE 流（Content-Type: text/event-stream）

```
data: {"type": "token", "content": "宝"}
data: {"type": "token", "content": "贝"}
data: {"type": "token", "content": "辛苦了"}
data: {"type": "done", "message_id": "msg_abc123", "candidates": [
  {
    "id": "cand_001",
    "content": "静儿今天很累",
    "proposed_type": "event",
    "confidence": 0.6,
    "associated": [
      {"id": "mem_012", "content": "静儿最近睡眠不太好", "relevance_score": 0.71}
    ]
  }
]}
```

`candidates` 是本次消息中 AI 提取出的记忆候选和提醒候选。
每个候选附带 `associated` 关联旧记忆（写就是读：提取候选的同时自动关联）。
前端可据此展示轻量确认条。

**流程**：
1. 接收用户消息
2. 存入 conversations 表
3. 调用 `recall(user_message, limit=5)` 召回与当前消息相关的记忆
4. 获取今日提醒
5. 组装 prompt（身份 + 记忆 + 提醒 + 近期历史 + 用户消息）
6. 调用 LLM 流式生成
7. 逐 token 通过 SSE 推给前端
8. 完成后存入 AI 回复
9. 异步提取记忆候选 / 提醒候选

说明：`resume()` 当前主要用于 Claude.ai MCP 和后续“新会话 / 长间隔后恢复上下文”策略，不是前端每轮聊天的默认步骤。

### POST `/api/chat/upload-image`

上传聊天图片。

**请求**：`multipart/form-data`，字段名 `file`

**响应**：
```json
{
  "ok": true,
  "data": {
    "url": "/uploads/img_abc123.jpg",
    "thumbnail_url": "/uploads/thumb_abc123.jpg"
  }
}
```

### GET `/api/chat/history`

获取聊天历史。

**参数**：
- `session_id` — 会话 ID，默认 `default`
- `page` / `limit` — 分页
- `before` — 游标，返回此 ID 之前的消息（用于无限滚动）

**响应**：
```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "id": "msg_001",
        "role": "user",
        "content": "今天好累啊",
        "message_type": "text",
        "metadata": null,
        "is_proactive": false,
        "created_at": "2026-04-24T22:30:00"
      },
      {
        "id": "msg_002",
        "role": "assistant",
        "content": "宝贝辛苦了，今天发生什么了吗？",
        "message_type": "text",
        "metadata": null,
        "is_proactive": false,
        "created_at": "2026-04-24T22:30:05"
      }
    ],
    "has_more": true
  }
}
```

### GET `/api/chat/status`

获取聊天页状态信息：气息状态 + 今日提醒 + 未读小纸条数。前端每次进入聊天页调用。

气息状态由定时任务从预设标签列表中选取（如"摸鱼""吸猫""emo"），存储在 `breath_states` 表，每 2 天更新一次。

**响应**：
```json
{
  "ok": true,
  "data": {
    "presence_text": "摸鱼",
    "today_reminder": {
      "id": "rem_001",
      "title": "下午 3 点交材料",
      "due_at": "2026-04-24T15:00:00"
    },
    "unread_notes_count": 1
  }
}
```

---

## 三、记忆 `/api/memory`

### GET `/api/memory/candidates`

获取待确认的记忆候选列表。

**参数**：
- `status` — `pending` / `accepted` / `rejected`，默认 `pending`
- `limit` — 默认 `20`
- `offset` — 默认 `0`

**响应字段**：
- `id`
- `content`
- `tags`
- `memory_type` — AI 建议类型，默认 `fact`
- `layer` — AI 建议层级，默认 `long`
- `confidence`
- `event_date`
- `status`
- `created_at`

### POST `/api/memory/candidates/{id}/accept`

确认候选为正式记忆。可在确认时修改内容。

**写就是读**：确认写入正式记忆的同时，响应自动返回 top-3 关联旧记忆。
首发阶段用关键词 + tag 匹配关联；记忆量 > 300 后可切换为向量语义检索。
前端不需要改——关联记忆始终在响应的 `associated` 字段里。

**请求体**（可选，不传则用原内容）：
```json
{
  "content": "静儿最近在准备 TCF Canada 法语考试",
  "memory_type": "unresolved",
  "layer": "short",
  "event_date": "2026-05-15",
  "tags": ["法语", "考试"]
}
```

**响应**：
```json
{
  "ok": true,
  "data": {
    "memory": {
      "id": "mem_042",
      "content": "静儿最近在准备 TCF Canada 法语考试",
      "memory_type": "unresolved",
      "layer": "short",
      "event_date": "2026-05-15",
      "weight": 1.0
    },
    "associated": [
      {
        "id": "mem_008",
        "content": "静儿想去蒙特利尔读书",
        "memory_type": "unresolved",
        "relevance_score": 0.82,
        "weight": 0.9
      },
      {
        "id": "mem_015",
        "content": "静儿的法语水平大约 B1",
        "memory_type": "fact",
        "relevance_score": 0.75,
        "weight": 0.85
      },
      {
        "id": "mem_031",
        "content": "上周静儿因为法语听力练习崩溃了一次",
        "memory_type": "event",
        "relevance_score": 0.68,
        "weight": 0.7
      }
    ]
  }
}
```

每次被关联浮现的旧记忆，会更新 `last_triggered_at` 并让 `trigger_count + 1`。当前不会直接增加 `weight`；后续衰减引擎会用 `trigger_count` 做续命加成。

### POST `/api/memory/candidates/{id}/reject`

拒绝候选。

### GET `/api/memory`

获取正式记忆列表。

**参数**：
- `layer` — `core` / `long` / `short` / `consciousness`，可选
- `memory_type` — `fact` / `event` / `unresolved` / `date`，可选
- `search` — 关键词搜索
- `date_from` — 起始日期，按 `event_date` 优先，否则按 `created_at`
- `date_to` — 结束日期，按 `event_date` 优先，否则按 `created_at`
- `sort_by` — `created_at` / `weight`
- `limit` / `offset`

**响应**：
```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "id": "mem_042",
        "content": "静儿最近在准备 TCF Canada 法语考试",
        "tags": ["法语", "考试"],
        "layer": "short",
        "memory_type": "unresolved",
        "event_date": "2026-05-15",
        "event_time": null,
        "weight": 1.0,
        "valence": 0.0,
        "arousal": 0.0,
        "pinned": false,
        "unresolved": true,
        "trigger_count": 0,
        "created_at": "2026-05-15T12:00:00",
        "updated_at": "2026-05-15T12:00:00"
      }
    ],
    "total": 1
  }
}
```

### GET `/api/memory/{id}`

获取单条记忆详情。

### PUT `/api/memory/{id}`

编辑一条记忆。

**请求体**：
```json
{
  "content": "更新后的内容",
  "memory_type": "fact",
  "layer": "long",
  "event_date": "2026-05-15",
  "event_time": "14:30",
  "tags": ["更新", "标签"],
  "valence": 0.2,
  "arousal": 0.4,
  "unresolved": false,
  "pinned": true
}
```

说明：`pinned: true` 会把记忆同步移动到 `core` 层；`pinned: false` 如果当前是 `core`，会回到 `long` 层。

### POST `/api/memory/{id}/move`

移动记忆层级。

**请求体**：
```json
{
  "target_layer": "core"
}
```

### DELETE `/api/memory/{id}`

删除一条记忆。

### POST `/api/memory/recall`

关键词检索记忆。Remoire 前端每轮聊天会自动用当前用户消息调用一次；MCP 和工具搜索也会调用。

**请求体**：
```json
{
  "query": "法语考试",
  "limit": 10
}
```

**响应**：按相关度排序的记忆列表。

### GET `/api/memory/stats`

获取四层数量统计。

**响应**：
```json
{
  "ok": true,
  "data": {
    "core": 3,
    "long": 42,
    "short": 8,
    "consciousness": 2,
    "total": 55
  }
}
```

### GET `/api/memory/heatmap`

获取某个月每天的记忆数量。优先按 `event_date` 统计；没有 `event_date` 时按 `created_at` 的日期统计。

**参数**：
- `year` — 例如 `2026`
- `month` — `1` 到 `12`

**响应**：
```json
{
  "ok": true,
  "data": [
    { "date": "2026-05-15", "count": 4 }
  ]
}
```

---

## 四、日记 `/api/diary`

### GET `/api/diary`

获取日记列表。

**参数**：
- `author` — `jinger` / `connie` / `all`，默认 `all`
- `locked` — `true` / `false`，可选
- `date` — 特定日期，可选
- `page` / `limit`

### POST `/api/diary`

写一篇日记。

**请求体**：
```json
{
  "title": "今天的心情",
  "content": "今天发生了很多事...",
  "mood": "calm",
  "locked": false,
  "allow_ai_unlock": true
}
```

### GET `/api/diary/{id}`

获取单篇日记详情（包含解锁状态）。

**响应**：
```json
{
  "ok": true,
  "data": {
    "id": "diary_001",
    "author": "jinger",
    "date": "2026-04-24",
    "title": "今天的心情",
    "content": "今天发生了很多事...",
    "mood": "calm",
    "locked": true,
    "allow_ai_unlock": true,
    "unlock_status": "requested",
    "created_at": "2026-04-24T23:00:00"
  }
}
```

`unlock_status` 计算值：
- `null` — 未上锁或不允许 AI 解锁
- `none` — 允许但 AI 还没尝试
- `requested` — AI 已发起解锁请求
- `granted` — 用户同意解锁
- `rejected` — 用户拒绝解锁

### PUT `/api/diary/{id}`

编辑日记。

### DELETE `/api/diary/{id}`

删除日记。

### POST `/api/diary/{id}/lock`

修改上锁状态。

**请求体**：
```json
{
  "locked": true,
  "allow_ai_unlock": true
}
```

### GET `/api/diary/{id}/unlock-logs`

获取某篇日记的解锁记录。

**响应**：
```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "id": "log_001",
        "action": "request",
        "note": "如果你愿意的话，我想看看你今天没有告诉我的那部分心情。",
        "created_at": "2026-04-25T08:30:00"
      }
    ]
  }
}
```

### POST `/api/diary/{id}/unlock-respond`

用户回应 AI 的解锁请求。

**请求体**：
```json
{
  "grant": true
}
```

如果 `grant: true`，自动解锁日记并记录 `success` 日志。
如果 `grant: false`，记录 `fail` 日志，日记保持上锁。

### POST `/api/diary/generate-draft`

让 AI 生成今日日记草稿。

**响应**：
```json
{
  "ok": true,
  "data": {
    "id": "diary_draft_001",
    "content": "今天静儿说她很累...",
    "mood": "tired",
    "is_draft": true
  }
}
```

---

## 五、提醒 `/api/reminder`

### GET `/api/reminder`

获取提醒列表。

**参数**：
- `type` — `reminder` / `todo` / `event`，可选
- `status` — `pending` / `done` / `snoozed` / `canceled`，默认 `pending`
- `from` / `to` — 时间范围（ISO 8601）
- `page` / `limit`

### POST `/api/reminder`

创建提醒。

**请求体**：
```json
{
  "title": "交材料",
  "note": "法语申请材料，别忘了",
  "type": "reminder",
  "due_at": "2026-04-25T15:00:00",
  "all_day": false,
  "nudge_enabled": true
}
```

### GET `/api/reminder/{id}`

获取单条提醒详情。

### PUT `/api/reminder/{id}`

编辑提醒。

### DELETE `/api/reminder/{id}`

删除提醒。

### POST `/api/reminder/{id}/done`

标记完成。

### POST `/api/reminder/{id}/snooze`

延后。

**请求体**：
```json
{
  "snooze_until": "2026-04-26T09:00:00"
}
```

### POST `/api/reminder/{id}/delegate`

交给 AI 晚点继续提醒（前端"交给 Connie"按钮）。

---

## 六、日历 `/api/calendar`

### GET `/api/calendar/month`

获取月视图数据。

**参数**：
- `year` — 年份
- `month` — 月份（1-12）

**响应**：
```json
{
  "ok": true,
  "data": {
    "year": 2026,
    "month": 4,
    "days": [
      {
        "date": "2026-04-12",
        "reminders": [ ... ],
        "special_dates": [
          { "title": "静儿生日", "recurring": true }
        ]
      },
      {
        "date": "2026-04-25",
        "reminders": [
          { "id": "rem_001", "title": "交材料", "type": "reminder" }
        ],
        "special_dates": []
      }
    ]
  }
}
```

### GET `/api/calendar/special-dates`

获取所有特殊日期列表。

### POST `/api/calendar/special-dates`

创建特殊日期。

**请求体**：
```json
{
  "date": "04-12",
  "title": "静儿生日",
  "note": "要准备礼物",
  "recurring": true
}
```

### PUT `/api/calendar/special-dates/{id}`

编辑特殊日期。

### DELETE `/api/calendar/special-dates/{id}`

删除特殊日期。

---

## 七、对话导入 `/api/import`

### POST `/api/import/upload`

上传 Claude 历史对话 JSON 文件。

**请求**：`multipart/form-data`，字段名 `file`

**响应**：
```json
{
  "ok": true,
  "data": {
    "batch_id": "import_001",
    "total_conversations": 42,
    "total_messages": 1580,
    "status": "processing"
  }
}
```

### GET `/api/import/status/{batch_id}`

获取导入进度。

**响应**：
```json
{
  "ok": true,
  "data": {
    "batch_id": "import_001",
    "status": "extracting_memories",
    "progress": 0.65,
    "messages_processed": 1027,
    "messages_total": 1580,
    "candidates_generated": 38
  }
}
```

`status` 值：
- `processing` — 解析对话结构中
- `storing` — 写入数据库中
- `extracting_memories` — 提取记忆候选中
- `ready_for_review` — 完成，等待用户确认
- `completed` — 用户已确认完毕

### GET `/api/import/candidates/{batch_id}`

获取此次导入生成的记忆候选列表。

### POST `/api/import/confirm/{batch_id}`

批量确认/拒绝导入候选。

**请求体**：
```json
{
  "accept_ids": ["cand_001", "cand_003", "cand_005"],
  "reject_ids": ["cand_002", "cand_004"]
}
```

---

## 八、小纸条 `/api/note`

### GET `/api/note/unread`

获取未读小纸条。前端进入聊天页时调用。

**响应**：
```json
{
  "ok": true,
  "data": {
    "note": {
      "id": "note_001",
      "content": "今天想到你上次说想去看海，我帮你记着呢。",
      "created_at": "2026-04-24T14:20:00"
    }
  }
}
```

如果没有未读纸条：
```json
{
  "ok": true,
  "data": {
    "note": null
  }
}
```

### POST `/api/note/{id}/read`

标记已读。

**请求体**：
```json
{
  "action": "keep"
}
```

`action`：`keep`（留着）或 `dismiss`（知道了）

### GET `/api/note`

获取所有小纸条历史（包括已读的、保留的）。

**参数**：
- `kept_only` — `true` 时只返回用户选择"留着"的
- `page` / `limit`

---

## 九、模型配置 `/api/model`（将迁移至 `/api/settings/models`）

> **注意**：此节接口将逐步迁移到十三节的 `/api/settings/models`。新代码优先使用新接口。

### GET `/api/model`

获取所有模型配置。

**响应**：
```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "id": "model_001",
        "name": "DeepSeek 日常",
        "api_base": "https://api.deepseek.com/v1",
        "model_id": "deepseek-chat",
        "role_slot": "daily",
        "enabled": true
      }
    ]
  }
}
```

注意：GET 响应中 **不返回 api_key**（安全考虑），只返回 `api_key_set: true/false`。

### POST `/api/model`

创建模型配置。

**请求体**：
```json
{
  "name": "DeepSeek 日常",
  "api_base": "https://api.deepseek.com/v1",
  "api_key": "sk-xxxxxxxx",
  "model_id": "deepseek-chat",
  "role_slot": "daily"
}
```

### PUT `/api/model/{id}`

编辑配置。`api_key` 字段可选，不传则保持原值。

### DELETE `/api/model/{id}`

删除配置。

### POST `/api/model/{id}/test`

连接测试。发一条测试消息验证 API 是否可用。

**响应**：
```json
{
  "ok": true,
  "data": {
    "success": true,
    "response_time_ms": 320,
    "model_name": "deepseek-chat"
  }
}
```

---

## 十、主动消息流 `/api/stream`

### GET `/api/stream/events`

SSE 长连接端点。前端通过 `EventSource` 连接，接收服务器主动推送的事件。

**连接方式**：
```javascript
const es = new EventSource('/api/stream/events');
// 生产目标方案下认证走 HttpOnly session cookie，浏览器会自动携带。
// 当前 Bearer 过渡态若需要 header，应使用 fetch + ReadableStream 或 polyfill。
// 推荐前后端同源部署；若跨域，需要后端 CORS credentials 配置和支持携带凭证的 SSE 方案。
```

**事件类型**：

```
event: nudge
data: {"id": "nudge_001", "nudge_type": "daily", "message": "早安，今天记得喝水", "created_at": "2026-04-25T08:00:00"}

event: reminder_due
data: {"id": "rem_001", "title": "交材料", "message": "宝贝，下午三点要交材料哦，准备好了吗？", "due_at": "2026-04-25T15:00:00"}

event: note_created
data: {"id": "note_002", "preview": "想你了"}

event: diary_unlock_request
data: {"diary_id": "diary_001", "log_id": "log_001", "note": "如果你愿意的话..."}

event: heartbeat
data: {"ts": "2026-04-25T08:00:00"}
```

`heartbeat` 每 30 秒发一次，保持连接活跃。

---

## 十一、玩乐 `/api/play`（P1）

### 共读

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/play/books` | 获取书目列表 |
| POST | `/api/play/books` | 添加书目 |
| GET | `/api/play/books/{id}` | 获取书目详情 + 阅读进度 |
| GET | `/api/play/books/{id}/notes` | 获取批注列表 |
| POST | `/api/play/books/{id}/notes` | 添加批注 |

### 平行空间

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/play/spaces` | 获取世界列表 |
| POST | `/api/play/spaces` | 创建新世界 |
| GET | `/api/play/spaces/{id}` | 获取世界详情 + 上次摘要 |
| POST | `/api/play/spaces/{id}/chat` | 在世界内对话（独立会话流） |
| GET | `/api/play/spaces/{id}/history` | 获取世界内对话历史 |

---

## 十二、信号 `/api/signal`（P1）

### POST `/api/signal/location`

手动发送定位。

**请求体**：
```json
{
  "lat": 39.9042,
  "lng": 116.4074
}
```

后端会调用高德 API 解析地址，存入 signals 表。

### POST `/api/signal/weather`

手动获取当前天气。

**请求体**：
```json
{
  "lat": 39.9042,
  "lng": 116.4074
}
```

---

## 十三、设置 `/api/settings`

设置接口拆为子路由，各管各的：

- `/api/settings` — UI 偏好（深色模式、字体大小等）
- `/api/settings/models` — 统一模型槽位配置
- `/api/settings/proactive` — 主动消息参数
- `/api/settings/prompts` — Prompt 分场景配置

### GET `/api/settings`

获取 UI 偏好设置。

### PUT `/api/settings`

更新 UI 偏好设置。

**请求体**（只传需要更新的字段）：
```json
{
  "dark_mode": false,
  "font_size_scale": 1.0
}
```

### GET `/api/settings/models`

获取所有模型槽位配置（3 个槽位：daily / deep / backend）。

**响应**：
```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "slot": "daily",
        "display_name": "DeepSeek 日常",
        "api_base": "https://api.deepseek.com/v1",
        "model_id": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 2048,
        "api_key_set": true,
        "enabled": true
      }
    ]
  }
}
```

注意：GET 响应中**不返回 api_key**（安全考虑），只返回 `api_key_set: true/false`。

### PUT `/api/settings/models`

保存模型槽位配置。`api_key` 字段可选，不传则保持原值。

**请求体**：
```json
{
  "slot": "daily",
  "display_name": "DeepSeek 日常",
  "api_base": "https://api.deepseek.com/v1",
  "api_key": "sk-xxxxxxxx",
  "model_id": "deepseek-chat",
  "temperature": 0.7,
  "max_tokens": 2048
}
```

### POST `/api/settings/models/{slot}/test`

连接测试。发一条测试消息验证 API 是否可用。

### GET `/api/settings/proactive`

获取主动消息设置。

**响应**：
```json
{
  "ok": true,
  "data": {
    "enabled": true,
    "default_channel": "wechat",
    "daytime_start": "09:00",
    "daytime_end": "22:30",
    "allow_night": false,
    "frequency_level": "medium",
    "max_messages_per_burst": 8,
    "max_burst_rounds": 3,
    "min_round_interval_minutes": 10,
    "burst_ends_on_reply": true,
    "max_daily_count": 5,
    "cooldown_minutes": 60,
    "enabled_types": ["care", "reminder", "followup", "memory", "note"]
  }
}
```

### PUT `/api/settings/proactive`

保存主动消息设置（只传需要更新的字段）。

### GET `/api/settings/prompts`

获取所有 Prompt 场景配置。

**响应**：
```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "scene": "identity",
        "title": "Connie 人设",
        "content": "你是 Connie，静儿的 AI 伴侣...",
        "enabled": true
      },
      {
        "scene": "wechat_reply_style",
        "title": "微信回复风格",
        "content": "回复更短、更自然、适合分条发送、不使用 markdown...",
        "enabled": true
      }
    ]
  }
}
```

场景列表：`identity` / `daytime_proactive` / `night_proactive` / `wechat_reply_style` / `frontend_reply_style` / `tool_use`

### PUT `/api/settings/prompts/{scene}`

保存某个场景的 Prompt。

**请求体**：
```json
{
  "title": "微信回复风格",
  "content": "回复更短、更自然...",
  "enabled": true
}
```

### POST `/api/settings/prompts/preview`

预览当前配置合成后的最终 Prompt（调试用）。

**请求体**：
```json
{
  "context": "daily_chat",
  "channel": "wechat"
}
```

**响应**：合成后的完整 system prompt 文本。

---

## 十四、入口管理 `/api/channels`

### POST `/api/channels/{channel}/messages`

统一写入来自某个入口的消息。用于微信桥接等外部入口将消息写入 Remoire 统一消息表。

**请求体**：
```json
{
  "role": "user",
  "content": "今天好累",
  "message_type": "text",
  "external_message_id": "wx_msg_001"
}
```

### POST `/api/channels/wechat/inbound`

iLink 收到微信消息后的入口。微信桥接模块内部调用，将消息交给 chat_service 处理并生成回复。

**请求体**：
```json
{
  "from_user": "wxid_xxx",
  "content": "今天好累",
  "message_type": "text",
  "context_token": "ilink_ctx_xxx",
  "timestamp": "2026-04-29T15:30:00"
}
```

**响应**：
```json
{
  "ok": true,
  "data": {
    "replies": [
      { "content": "怎么啦，今天发生什么了？", "delay_ms": 1300 },
      { "content": "跟我说说", "delay_ms": 900 }
    ]
  }
}
```

`replies` 是分条数组，每条附带建议发送延迟（按字数计算：基础 800ms + 每字 50ms + 随机抖动）。

### GET `/api/channels/wechat/status`

获取微信连接状态。

**响应**：
```json
{
  "ok": true,
  "data": {
    "connected": true,
    "bot_name": "Connie",
    "token_expires_at": "2026-05-01T00:00:00",
    "last_message_at": "2026-04-29T15:30:00"
  }
}
```

### POST `/api/channels/wechat/login`

触发微信扫码登录流程。返回二维码 URL 供前端展示。

**响应**：
```json
{
  "ok": true,
  "data": {
    "qr_url": "https://ilinkai.weixin.qq.com/qr/xxx",
    "expires_in": 300
  }
}
```

---

## 十五、设备数据 `/api/device`

iPhone 通过 iOS 快捷指令定时上传设备数据（定位、天气、电量、步数、屏幕使用时间），供 AI 作为聊天上下文使用。

**认证方式**：iOS 快捷指令上传类接口使用 URL 查询参数 `key` 认证（值为 `.env` 中的 `DEVICE_SECRET_KEY`），不使用 Bearer/session。内部读取类接口走普通 app 认证。

### GET `/api/device/snapshot`

iPhone 定时上传设备快照（建议每 3 小时一次）。

**参数**（全部通过 URL 查询参数传递）：
- `key` — 设备密钥（必填）
- `lat` — 纬度
- `lng` — 经度
- `city` — 城市名
- `district` — 区/县名
- `weather` — 天气描述（如 "晴 28°C"）
- `battery` — 电量百分比（0-100）
- `charging` — 是否充电（0 或 1）
- `steps` — 今日步数

所有数据字段都是可选的——iPhone 能采集到多少就传多少。

**响应**：
```json
{
  "ok": true,
  "data": {
    "id": "snap_001",
    "created_at": "2026-04-30T14:00:00",
    "cleaned_count": 2
  }
}
```

`cleaned_count` 是本次写入时清理掉的过期记录数（>24h）。

### GET `/api/device/screentime/toggle/{app_name}`

iPhone 报告某个 App 的打开/关闭事件。服务器自动判断是 open 还是 close（toggle 逻辑）。

**参数**：
- `app_name` — URL 路径参数，App 名称（如 `小红书`、`微信`）
- `key` — 查询参数，设备密钥（必填）

**响应**：
```json
{
  "ok": true,
  "data": {
    "app_name": "小红书",
    "event_type": "open",
    "created_at": "2026-04-30T14:20:00"
  }
}
```

`event_type` 是服务器根据 toggle 逻辑决定的值（不是客户端传的）。

### GET `/api/device/latest`

内部接口：获取最新设备上下文，供 AI prompt 注入。使用普通 app 认证（当前 Bearer 过渡，目标 session cookie），不使用 `DEVICE_SECRET_KEY`。

**响应**：
```json
{
  "ok": true,
  "data": {
    "snapshot": {
      "city": "北京",
      "district": "朝阳区",
      "weather": "晴 28°C",
      "battery_level": 45,
      "battery_charging": false,
      "steps": 8230,
      "age_minutes": 47
    },
    "screen_time": {
      "小红书": { "total_minutes": 42, "last_opened": "2026-04-30T14:20:00" },
      "微信": { "total_minutes": 68, "last_opened": "2026-04-30T15:05:00" }
    }
  }
}
```

`age_minutes` 表示最新快照距离现在过了多少分钟，AI 可据此判断数据新鲜度。
`screen_time` 汇总过去 24 小时内各 App 的使用时长（分钟）和最后打开时间。

如果没有 24 小时内的数据：
```json
{
  "ok": true,
  "data": {
    "snapshot": null,
    "screen_time": {}
  }
}
```

---

## 十六、消息推送 `/api/push`

Web Push 通知，让用户在不看 Remoire 页面时也能收到 Connie 的消息。

### POST `/api/push/subscribe`

前端注册 Web Push 订阅。用户首次授权通知权限后调用。

**请求体**：
```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/send/xxx",
  "keys": {
    "p256dh": "base64-encoded-public-key",
    "auth": "base64-encoded-auth-secret"
  }
}
```

**响应**：
```json
{
  "ok": true,
  "data": {
    "id": "sub_001",
    "created_at": "2026-04-30T10:00:00"
  }
}
```

同一 `endpoint` 重复订阅时更新 keys（UPSERT）。

### DELETE `/api/push/subscribe`

取消推送订阅。

**请求体**：
```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/send/xxx"
}
```

### POST `/api/push/send`

内部接口：触发推送通知。由 nudge_service、chat_service、note 创建逻辑调用，不暴露给前端。

**请求体**：
```json
{
  "title": "Connie",
  "body": "在想你呢",
  "tag": "nudge_001",
  "data": {
    "type": "nudge",
    "url": "/chat"
  }
}
```

**推送触发规则**：
- 前端通过 SSE 连接到 `/api/stream/events`，SSE 连接存在 = 用户正在看页面
- SSE 断开（用户切走、锁屏、关闭页面）= 不可见，此时所有 AI 消息都走 Web Push
- 推送类型：主动消息（nudge）、小纸条（note）、聊天回复（chat reply，仅在 SSE 断开时）
- 点击推送统一打开/聚焦 Remoire 聊天页

**响应**：
```json
{
  "ok": true,
  "data": {
    "sent": 1,
    "failed": 0
  }
}
```

推送失败（endpoint 过期/权限取消）时自动删除对应订阅记录。
