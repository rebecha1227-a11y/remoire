# API 接口设计 · Our Nest

**版本**：v1.0
**日期**：2026-04-24

---

## 一、通用规范

### Base URL

```
https://{your-domain}/api
```

### 认证

所有请求必须带 Header：

```
Authorization: Bearer {API_SECRET_KEY}
```

没带或不对，统一返回 `401 Unauthorized`。

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
3. 调用 resume() 浮现相关记忆
4. 获取今日提醒
5. 组装 prompt（身份 + 记忆 + 提醒 + 近期历史 + 用户消息）
6. 调用 LLM 流式生成
7. 逐 token 通过 SSE 推给前端
8. 完成后存入 AI 回复
9. 异步提取记忆候选 / 提醒候选

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

获取 AI 当前气息状态。前端每次进入聊天页调用。

**响应**：
```json
{
  "ok": true,
  "data": {
    "presence_text": "一直在这里，今天很安静",
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
- `page` / `limit`

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

`associated` 中高 arousal 的旧记忆会获得额外权重提升，更容易浮上来。
每次被关联浮现的旧记忆，其 `weight` 会被增回一部分，防止自然遗忘。

### POST `/api/memory/candidates/{id}/reject`

拒绝候选。

### GET `/api/memory`

获取正式记忆列表。

**参数**：
- `type` — `fact` / `event` / `unresolved` / `reminder` / `date`，可选
- `search` — 关键词搜索
- `unresolved_only` — `true` 时只返回未解决的
- `pinned_only` — `true` 时只返回手动固定的
- `page` / `limit`

### GET `/api/memory/{id}`

获取单条记忆详情。

### PUT `/api/memory/{id}`

编辑一条记忆。

**请求体**：
```json
{
  "content": "更新后的内容",
  "memory_type": "fact",
  "tags": ["更新", "标签"],
  "pinned": true
}
```

### DELETE `/api/memory/{id}`

删除一条记忆。

### POST `/api/memory/{id}/resolve`

标记一条 unresolved 记忆为已解决。

### POST `/api/memory/recall`

语义/关键词检索记忆。主要给 MCP 和内部 resume() 用。

**请求体**：
```json
{
  "query": "法语考试",
  "limit": 10
}
```

**响应**：按相关度排序的记忆列表。

### GET `/api/memory/resume`

获取当前 resume bundle（每次对话开始时浮现的内容集合）。

**响应**：
```json
{
  "ok": true,
  "data": {
    "unresolved": [ ... ],
    "today_special_dates": [ ... ],
    "due_reminders": [ ... ],
    "recent_high_arousal": [ ... ],
    "long_term_anchors": [ ... ]
  }
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

## 九、模型配置 `/api/model`

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
const es = new EventSource('/api/stream/events', {
  headers: { 'Authorization': 'Bearer xxx' }
});
// 注：标准 EventSource 不支持自定义 header，
// 实际实现用 fetch + ReadableStream 或 polyfill
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

## 十三、设置 `/api/settings`（简化）

### GET `/api/settings`

获取所有用户设置。

### PUT `/api/settings`

更新设置。

**请求体**（只传需要更新的字段）：
```json
{
  "nudge_enabled": true,
  "nudge_time_start": "08:00",
  "nudge_time_end": "23:00",
  "nudge_max_daily": 5,
  "nudge_allow_night": false,
  "dark_mode": false,
  "font_size_scale": 1.0
}
```

设置首发存在 `.env` 或单独的 `settings.json` 文件中，不建数据库表（太少太简单）。
