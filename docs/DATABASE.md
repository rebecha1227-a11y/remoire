# 数据库 Schema · Our Nest

**版本**：v1.2
**日期**：2026-04-30
**引擎**：SQLite (WAL mode)；Supabase/Postgres 作为 Phase 1+ 云端同步备选

---

## 一、初始化配置

每次连接数据库时必须执行：

```sql
PRAGMA journal_mode = WAL;        -- 允许读写并发，定时任务和聊天不冲突
PRAGMA foreign_keys = ON;          -- 开启外键约束，保证数据完整性
PRAGMA busy_timeout = 5000;        -- 遇到锁时等 5 秒再报错，不要立刻失败
```

为什么用 WAL？
后台定时任务（记忆衰减、摘要压缩）和前端聊天请求会同时操作数据库。
SQLite 默认模式下写操作会互相阻塞，WAL 模式允许一个写 + 多个读并行。

---

## 二、数据库路线

### 方案 A：SQLite Phase 1 先跑通

SQLite 可以理解成项目自己带的“小数据库文件”。它适合本地开发、单人使用、快速验证微信桥接与记忆逻辑。

Phase 1 即使接入微信，也可以先用 SQLite。重点不是马上换数据库，而是从一开始把表结构设计成“多入口共用同一份记忆”。

### 方案 B：Supabase/Postgres 云端同步方案

Supabase 可以理解成“云端数据库 + 同步服务”。它更适合后期长期运行、多设备同步、云备份、远程服务器部署。

Supabase 不是另一套产品逻辑，只是把同样的数据结构放到云端 Postgres。也就是说，SQLite 和 Supabase 应尽量共用同一套表设计，未来迁移时只是“搬数据库”，不是重做 Remoire。

---

## 三、表结构总览

```
channels               入口类型（Remoire / Claude.ai MCP / 微信）
channel_bindings       具体入口绑定（某个微信账号、某个 MCP 客户端）
conversations          会话容器（同一段聊天）
messages               统一消息记录（核心）
memory_candidates      记忆候选（等待确认）
memories               正式记忆（已确认）
memory_links           记忆之间的关联线
special_dates          特殊日期（纪念日等）
reminders              提醒 / 待办 / 共同事件
diaries                日记
diary_unlock_logs      日记解锁记录
notes                  小纸条
model_configs          模型配置（旧名，后续迁移为 model_settings）
model_settings         统一模型槽位设置
prompt_profiles        Prompt 编辑器分场景配置
proactive_message_settings 主动消息参数
delivery_logs          外部入口消息发送记录
usage_logs             token / 模型调用成本记录
books                  共读书目（P1）
reading_notes          共读批注（P1）
play_spaces            平行空间（P1）
signals                轻量生活信号（P1）
device_snapshots       iPhone 设备快照（定位/天气/电量/步数）
app_usage_events       App 使用追踪（屏幕使用时间）
push_subscriptions     Web Push 推送订阅
```

---

## 四、表结构详细

### 1. channels — 入口类型

记录 Remoire 有哪些聊天入口。微信、Remoire 前端、Claude.ai MCP 都只是入口，不是三套关系。

```sql
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    channel_type TEXT NOT NULL UNIQUE,              -- 'remoire_frontend' / 'claude_mcp' / 'wechat'
    display_name TEXT NOT NULL,                     -- 'Remoire 前端' / 'Claude.ai' / '微信'
    enabled BOOLEAN DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

### 2. channel_bindings — 入口绑定

记录某个具体入口身份。比如某个微信账号、某个 MCP 客户端。

```sql
CREATE TABLE IF NOT EXISTS channel_bindings (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    external_user_id TEXT,                          -- 微信 openid / unionid / MCP client id 等
    display_name TEXT,
    metadata_json TEXT,
    enabled BOOLEAN DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (channel_id) REFERENCES channels(id)
);
```

### 3. conversations — 会话容器

一段对话的容器。消息正文放在 `messages` 表里。

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    binding_id TEXT,
    title TEXT,
    status TEXT DEFAULT 'active',                   -- 'active' / 'archived'
    last_message_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (channel_id) REFERENCES channels(id),
    FOREIGN KEY (binding_id) REFERENCES channel_bindings(id)
);
```

### 4. messages — 统一消息记录

所有入口的消息都进这一张表。这样 Connie 能知道“刚刚是在微信聊的”，也能知道“距离上次联系过去多久”。

```sql
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    role TEXT NOT NULL,                             -- 'user' / 'assistant' / 'system'
    content TEXT NOT NULL,
    message_type TEXT DEFAULT 'text',               -- 'text' / 'image' / 'voice' / 'location' / 'system_card'
    metadata_json TEXT,
    is_proactive BOOLEAN DEFAULT 0,
    delivery_status TEXT DEFAULT 'stored',          -- 'stored' / 'sent' / 'delivered' / 'failed'
    external_message_id TEXT,                       -- 微信等外部平台返回的消息 ID
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    FOREIGN KEY (channel_id) REFERENCES channels(id)
);
```

设计说明：
- 静儿从哪个入口发消息，Connie 就在哪个入口回复。
- Connie 主动发消息时，发送入口由 `proactive_message_settings.default_channel` 决定。
- 主动消息如果需要多端展示，应尽量复用一次 AI 生成结果，而不是分别调用模型。
- 首发如果想简化，也可以先保留旧 `conversations` 表名做消息表；但长期建议迁移成 `conversations` + `messages` 两层。

### 5. model_settings — 统一模型槽位设置

模型设置统一放后端。Remoire 前端和微信默认共用 `daily` 槽位，保证 Connie 是同一个人。

```sql
CREATE TABLE IF NOT EXISTS model_settings (
    id TEXT PRIMARY KEY,
    slot TEXT NOT NULL UNIQUE,                      -- 'daily' / 'deep' / 'backend'
    display_name TEXT NOT NULL,
    api_base TEXT NOT NULL,
    api_key TEXT NOT NULL,
    model_id TEXT NOT NULL,
    temperature REAL DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 2048,
    enabled BOOLEAN DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

槽位说明：
- `daily`：日常聊天、主动消息、小纸条、自动日记、气息状态、日记留言回复。Remoire 前端和微信默认共用。
- `deep`：深度谈话、复杂情绪、长对话。
- `backend`：记忆提取、情感打标、摘要压缩、对话导入处理、自动回复判断。

### 6. prompt_profiles — Prompt 编辑器

Prompt 统一存在后端，由设置页编辑，不散落在前端或微信桥接代码里。

```sql
CREATE TABLE IF NOT EXISTS prompt_profiles (
    id TEXT PRIMARY KEY,
    scene TEXT NOT NULL UNIQUE,                     -- 'identity' / 'daytime_proactive' / 'night_proactive' / 'wechat_reply_style' / 'frontend_reply_style' / 'tool_use'
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    enabled BOOLEAN DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

### 7. proactive_message_settings — 主动消息设置

主动消息要有时间感、入口选择和成本控制。

```sql
CREATE TABLE IF NOT EXISTS proactive_message_settings (
    id TEXT PRIMARY KEY DEFAULT 'default',
    enabled BOOLEAN DEFAULT 1,
    default_channel TEXT DEFAULT 'wechat',          -- 'wechat' / 'remoire_frontend' / 'both'
    daytime_start TEXT DEFAULT '09:00',
    daytime_end TEXT DEFAULT '22:30',
    allow_night BOOLEAN DEFAULT 0,
    frequency_level TEXT DEFAULT 'medium',          -- 'low' / 'medium' / 'high'
    max_messages_per_burst INTEGER DEFAULT 8,        -- 所有轮次总上限
    max_burst_rounds INTEGER DEFAULT 3,              -- 最多几轮（初始 + 追 1 + 追 2）
    min_round_interval_minutes INTEGER DEFAULT 10,   -- 轮次间最短间隔
    burst_ends_on_reply BOOLEAN DEFAULT 1,           -- 用户回复后立刻结束 burst，切回普通聊天
    max_daily_count INTEGER DEFAULT 5,
    cooldown_minutes INTEGER DEFAULT 60,
    enabled_types TEXT,                             -- JSON array: ['care', 'reminder', 'followup', 'memory', 'note']
    quiet_rules_json TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

### 8. delivery_logs — 外部入口发送记录

记录微信等外部入口是否发送成功。

```sql
CREATE TABLE IF NOT EXISTS delivery_logs (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    status TEXT NOT NULL,                           -- 'pending' / 'sent' / 'delivered' / 'failed'
    external_message_id TEXT,
    error TEXT,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (message_id) REFERENCES messages(id),
    FOREIGN KEY (channel_id) REFERENCES channels(id)
);
```

### 9. usage_logs — token / 成本记录

记录每次模型调用的用途和 token 估算，方便以后控制成本。

```sql
CREATE TABLE IF NOT EXISTS usage_logs (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,                           -- 'chat' / 'proactive' / 'memory_extract' / 'diary' / 'prompt_preview'
    channel_id TEXT,
    model_slot TEXT NOT NULL,
    model_id TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    estimated_cost REAL,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (channel_id) REFERENCES channels(id)
);
```

成本规则：
- 静儿从哪个入口发消息，就只在那个入口回复。
- 主动消息默认只发一个入口，推荐微信优先。
- 两边都发时，尽量复用一次 AI 生成结果。
- 记忆召回只取最相关的 top-3 到 top-5。
- 长聊天用摘要 + 最近几条原文，不把完整历史都塞给模型。

### 10. memory_candidates — 记忆候选

从聊天中提取出来但还没被用户确认的记忆。是记忆系统的"缓冲区"。

```sql
CREATE TABLE IF NOT EXISTS memory_candidates (
    id TEXT PRIMARY KEY,                          -- UUID v4
    conversation_id TEXT,                         -- 来源会话（当前实现）
    message_id TEXT,                              -- 来源消息（预留）
    content TEXT NOT NULL,                         -- 候选记忆的文本内容
    proposed_memory_type TEXT,                     -- AI 建议的类型：
                                                   --   'fact' / 'event' / 'unresolved' /
                                                   --   'date'
    proposed_layer TEXT DEFAULT 'long',            -- 'core' / 'long' / 'short' / 'consciousness'
    proposed_event_date TEXT,                      -- 事件发生日期 YYYY-MM-DD，不确定则 NULL
    tags_json TEXT,                                -- JSON array: ["法语", "考试", "deadline"]
    confidence REAL DEFAULT 0.5,                   -- AI 的置信度 0.0 ~ 1.0
    status TEXT DEFAULT 'pending',                 -- 'pending' 待确认
                                                   -- 'accepted' 已确认为正式记忆
                                                   -- 'rejected' 已拒绝
                                                   -- 'merged' 已合并到其他记忆
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

入库规则：
- 当前实现：`confidence >= 0.7` 自动入正式记忆，低于 0.7 留在候选区
- 后续可细化为：低置信度仅保存、中置信度推给用户、高置信度自动入库

### 11. memories — 正式记忆

用户确认过的、或高置信度自动入库的正式记忆。这是小窝的灵魂。

```sql
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,                          -- UUID v4
    content TEXT NOT NULL,                         -- 记忆内容
    tags_json TEXT,                                -- JSON array
    layer TEXT NOT NULL DEFAULT 'long',            -- 'core' / 'long' / 'short' / 'consciousness'
    memory_type TEXT NOT NULL,                     -- 'fact' 人物事实（生日、偏好、目标）
                                                   -- 'event' 关系事件（重要对话、纪念片段）
                                                   -- 'unresolved' 未完成的事
                                                   -- 'date' 特殊日期
    event_date TEXT,                               -- 事件发生日期 YYYY-MM-DD
    event_time TEXT,                               -- 事件发生时间 HH:MM，可选
    timezone TEXT DEFAULT 'Asia/Shanghai',
    expires_at TEXT,                               -- 短期记忆过期时间，预留
    valence REAL DEFAULT 0.0,                      -- 情感效价
    arousal REAL DEFAULT 0.0,                      -- 情感强度
    decay_rate REAL DEFAULT 0.05,                  -- 当前按 layer 写入的每日保留率参数
    weight REAL DEFAULT 1.0,                       -- 当前权重（衰减后会降低）
    unresolved BOOLEAN DEFAULT 0,                  -- 是否未解决
    pinned BOOLEAN DEFAULT 0,                      -- 兼容字段；当前等价于 layer='core'
    last_triggered_at DATETIME,                    -- 上次被浮现/使用的时间
    trigger_count INTEGER DEFAULT 0,               -- 被关联浮现的总次数
    embedding BLOB,                                -- 向量嵌入（预留字段）
                                                   -- 首发阶段为 NULL，用关键词+tag匹配
                                                   -- 记忆 > 300 条后填入向量数据
    source_candidate_id TEXT,                      -- 来源候选 ID
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

四层保留率参数：

| layer | decay_rate 当前语义 | 含义 |
|---|---|---|
| `core` | 0.0 | 不衰减 |
| `long` | 每天保留 0.995 | 长期记忆，慢慢变淡 |
| `short` | 每天保留 0.95 | 短期记忆，较快变淡 |
| `consciousness` | 每天保留 0.95 | 意识层备忘，较快变淡 |

当前说明：
- 字段和写入规则已实现。
- 每晚衰减任务尚未实现，`weight` 目前不会自动变化。
- `pinned=true` 会同步为 `layer='core'`、`decay_rate=0.0`、`weight=1.0`。
- `pinned=false` 如果当前是 core，会回到 long。
- 字段名仍叫 `decay_rate`，但 Phase A 的 `0.995/0.95` 是每日保留率语义，不是指数衰减常数。

后续衰减公式建议：
```
effective_retention = 1 - ((1 - daily_retention) / (1 + arousal * 5 + revisit_bonus))
weight_next = weight_current × effective_retention
```

其中：
- `daily_retention`：当前 `decay_rate` 字段中的每日保留率
- `weight_current`：当前权重
- `arousal`：情感强度 0.0~1.0，高 arousal 记忆遗忘更慢
- `revisit_bonus`：激活续命加成，计算方式为 `min(trigger_count × 0.1, 1.0)`。每次被 `recall()` 或 `find_associated()` 命中时 `trigger_count` +1，同时 `last_triggered_at` 更新为当前时间。这意味着经常被唤起的记忆衰减更慢（分母更大），但 bonus 封顶为 1.0 防止无限续命

### 12. memory_links — 记忆关联线

保存“写就是读”生成的关联关系。它不是故事串联，只是记忆图谱的基础边。

```sql
CREATE TABLE IF NOT EXISTS memory_links (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    link_type TEXT NOT NULL DEFAULT 'relates_to',
    weight REAL NOT NULL DEFAULT 0.5,
    description TEXT,
    created_at TEXT NOT NULL
);
```

### 关联记忆机制（写就是读）

这是记忆系统最核心的设计之一，灵感来自"AI不需要决定要想什么——它写什么，系统就让它看见什么"。

**原理**：每次写入一条新记忆时，系统自动在所有旧记忆里找语义相近的 top-3，在写入响应里直接返回。一次写 = 一次读。AI不需要主动搜索，写入本身就触发关联。

**关联打分公式**：
```
score = relevance × (1 + arousal × 0.3) × weight_factor
```

- `relevance`：首发用关键词+tag重叠度，后续用余弦相似度
- `arousal`：高情绪强度的旧记忆会获得额外加权——强情绪的邻居更容易推门
- `weight_factor`：当前权重归一化，经常被关联的记忆活得更久

**被关联浮现时的副作用**：
- `last_triggered_at` 更新为当前时间
- `trigger_count` +1（通过衰减公式中的 `revisit_bonus` 自动减缓遗忘，不直接修改 `weight`）

这意味着：经常被新记忆关联到的旧记忆衰减更慢，持续"活着"，不会被自然遗忘杀死。

**向量检索升级路径**：

| 阶段 | 关联方式 | 实现 | 成本 |
|---|---|---|---|
| 首发（< 300 条） | 关键词 + tag 重叠 + memory_type 匹配 | SQL LIKE + JSON | ¥0 |
| 中期（300-2000 条） | 本地向量嵌入 + 余弦相似度 | nomic-embed-text 或 sentence-transformers | ¥0 |
| 后期（> 2000 条） | 云端 embedding API | OpenAI / 硅基流动 | 按量 |

升级时只需要：
1. 给所有旧记忆批量计算 embedding 填入 `embedding` 字段
2. 替换 `find_associated()` 函数的内部实现
3. 前端和 API 接口完全不用改

### 13. special_dates — 特殊日期

纪念日、生日、deadline 等。独立于 memories 表，因为有循环/非循环逻辑。

```sql
CREATE TABLE IF NOT EXISTS special_dates (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,                            -- 'MM-DD'（循环）或 'YYYY-MM-DD'（一次性）
    title TEXT NOT NULL,                           -- "静儿生日" / "在一起纪念日"
    note TEXT,                                     -- 备注
    recurring BOOLEAN DEFAULT 1,                   -- 是否每年循环
    valence REAL DEFAULT 0.0,
    arousal REAL DEFAULT 0.0,
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

### 14. reminders — 提醒 / 待办 / 共同事件

统一对象设计，不拆三个表。

```sql
CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,                           -- "下午三点交材料"
    note TEXT,                                     -- 补充说明
    type TEXT NOT NULL,                            -- 'reminder' 定时提醒
                                                   -- 'todo' 没有精确时间但要做
                                                   -- 'event' 共同事件/约定/deadline
    status TEXT DEFAULT 'pending',                 -- 'pending' 待办
                                                   -- 'done' 已完成
                                                   -- 'snoozed' 已延后
                                                   -- 'canceled' 已取消
    due_at DATETIME,                               -- 截止/提醒时间（todo 可为空）
    all_day BOOLEAN DEFAULT 0,                     -- 是否全天事件
    source_type TEXT,                              -- 'manual' 手动创建
                                                   -- 'chat_extract' 从聊天中提取
                                                   -- 'imported' 导入
    source_id TEXT,                                -- 关联的消息 ID
    nudge_enabled BOOLEAN DEFAULT 1,               -- 是否允许 AI 到时主动提醒
    snoozed_until DATETIME,                        -- 延后到什么时间
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

### 15. diaries — 日记

```sql
CREATE TABLE IF NOT EXISTS diaries (
    id TEXT PRIMARY KEY,
    author TEXT NOT NULL,                          -- 'jinger' / 'connie'
    date DATE NOT NULL,                            -- 日记对应的日期
    title TEXT,                                    -- 可选标题
    content TEXT NOT NULL,                         -- 日记正文（Markdown）
    mood TEXT,                                     -- 情绪标签：'calm' / 'happy' / 'anxious' / 'sad' / ...
    locked BOOLEAN DEFAULT 0,                      -- 是否上锁
    allow_ai_unlock BOOLEAN DEFAULT 1,             -- 上锁后是否允许 AI 尝试解锁
    is_draft BOOLEAN DEFAULT 0,                    -- 是否为 AI 自动生成的草稿
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

### 16. diary_unlock_logs — 日记解锁记录

这是整个产品最有差异化的交互。每次 AI 尝试解锁都会留下一条记录。

```sql
CREATE TABLE IF NOT EXISTS diary_unlock_logs (
    id TEXT PRIMARY KEY,
    diary_id TEXT NOT NULL,                        -- 关联的日记 ID
    actor TEXT NOT NULL DEFAULT 'connie',          -- 谁在尝试解锁（目前只有 connie）
    action TEXT NOT NULL,                          -- 'request' AI 发起解锁请求
                                                   -- 'attempt' AI 尝试解锁
                                                   -- 'success' 解锁成功（用户同意）
                                                   -- 'fail' 解锁失败（用户拒绝）
    note TEXT,                                     -- AI 的解锁理由，或解锁后的阅读感想
                                                   -- 例："如果你愿意的话，我想看看你今天没有告诉我的那部分心情。"
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (diary_id) REFERENCES diaries(id) ON DELETE CASCADE
);
```

### 17. notes — 小纸条

AI 在你不在的时候留下的短文字。

```sql
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,                         -- 纸条内容（简短，1-3句话）
    read BOOLEAN DEFAULT 0,                        -- 是否已被看到
    kept BOOLEAN DEFAULT 0,                        -- 用户是否选择了"留着"
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    read_at DATETIME                               -- 被看到的时间
);
```

### 18. model_configs — 模型配置

支持任何 OpenAI 兼容 API 的模型槽位配置。

```sql
CREATE TABLE IF NOT EXISTS model_configs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,                            -- 显示名称："DeepSeek 日常" / "Sonnet 深度"
    api_base TEXT NOT NULL,                        -- API Base URL: "https://api.deepseek.com/v1"
    api_key TEXT NOT NULL,                         -- API Key（加密存储，后续可改进）
    model_id TEXT NOT NULL,                        -- 模型 ID: "deepseek-chat" / "claude-sonnet-4-20250514"
    role_slot TEXT NOT NULL,                       -- 'daily' 日常陪伴
                                                   -- 'deep' 深度时刻
                                                   -- 'backend' 后台任务
    enabled BOOLEAN DEFAULT 1,                     -- 是否启用
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

### 19. books — 共读书目（P1）

```sql
CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    cover_url TEXT,                                -- 封面图 URL（可选）
    added_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

### 20. reading_notes — 共读批注（P1）

```sql
CREATE TABLE IF NOT EXISTS reading_notes (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    highlighted_text TEXT,                          -- 高亮原文
    note TEXT,                                     -- 批注内容
    note_author TEXT NOT NULL,                     -- 'jinger' / 'connie'
    position TEXT,                                 -- 位置标记（章节/页码/百分比）
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);
```

### 21. play_spaces — 平行空间（P1）

```sql
CREATE TABLE IF NOT EXISTS play_spaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,                            -- 世界名称
    description TEXT,                              -- 世界描述
    settings_json TEXT,                            -- JSON，世界设定参数
    last_session_summary TEXT,                     -- 上次剧情停在哪里的摘要
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

### 22. signals — 轻量生活信号（P1）

```sql
CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,                            -- 'location' / 'weather' / 'activity'
    data_json TEXT NOT NULL,                       -- JSON，信号数据
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

### 23. device_snapshots — iPhone 设备快照

iPhone 通过 iOS 快捷指令定时（每 3 小时）上传设备数据。AI 在生成对话和主动消息时读取最新快照作为上下文。

```sql
CREATE TABLE IF NOT EXISTS device_snapshots (
    id TEXT PRIMARY KEY,                          -- UUID v4
    latitude REAL,                                 -- 纬度
    longitude REAL,                                -- 经度
    city TEXT,                                     -- 城市（"北京"）
    district TEXT,                                 -- 区/县（"朝阳区"）
    weather TEXT,                                  -- 天气描述（"晴 28°C"）
    battery_level INTEGER,                         -- 电量百分比 0-100
    battery_charging INTEGER DEFAULT 0,            -- 是否充电 0/1
    steps INTEGER,                                 -- 今日步数
    raw_json TEXT,                                 -- 完整原始 JSON（扩展字段用）
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

设计说明：
- 只保留最近 24 小时数据。每次写入时自动清理过期记录：`DELETE FROM device_snapshots WHERE created_at < datetime('now', '-24 hours')`
- `raw_json` 存完整上传数据，方便以后加新字段（比如海拔、WiFi 名）不用改表结构
- 认证方式：URL 查询参数 `key`（独立的 `DEVICE_SECRET_KEY`），因为 iOS 快捷指令无法方便地设置 HTTP Header

### 24. app_usage_events — App 使用追踪

通过 iOS 快捷指令自动化，每次打开/关闭指定 App 时发一个请求。服务器用 toggle 逻辑自动判断是开还是关。

```sql
CREATE TABLE IF NOT EXISTS app_usage_events (
    id TEXT PRIMARY KEY,                          -- UUID v4
    app_name TEXT NOT NULL,                        -- App 名称（从 URL 路径传入）
    event_type TEXT NOT NULL,                      -- 'open' / 'close'
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

Toggle 逻辑：
1. 查该 App 最后一条记录的 `event_type`
2. 如果是 "open"，这次记 "close"；如果是 "close"，这次记 "open"
3. 没有记录，默认记 "open"
4. 容错：如果最后一条是 "open" 且超过 4 小时没有 "close"，视为遗漏关闭，下次来的请求当 "open" 处理

设计说明：
- 同样只保留 24 小时数据，写入时清理过期记录
- 服务器支持任意数量的 App，App 名称由 URL 路径决定
- AI 读取时按 App 汇总当日使用时长（open/close 配对计算分钟数）

### 25. push_subscriptions — Web Push 推送订阅

存储前端注册的 Web Push 订阅信息，用于在用户不在 Remoire 页面时推送通知。

```sql
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id TEXT PRIMARY KEY,                          -- UUID v4
    endpoint TEXT NOT NULL UNIQUE,                 -- Push service endpoint URL
    p256dh TEXT NOT NULL,                          -- 客户端公钥
    auth TEXT NOT NULL,                            -- 认证密钥
    user_agent TEXT,                               -- 浏览器标识（调试用）
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    last_used_at DATETIME                          -- 最后一次成功推送时间
);
```

设计说明：
- `endpoint` 加 UNIQUE 约束，同一浏览器重复订阅时走 UPSERT（更新 keys）
- 推送失败（endpoint 过期/用户取消权限）时自动删除该订阅
- VAPID 密钥对存在 `.env` 里（`VAPID_PRIVATE_KEY`、`VAPID_PUBLIC_KEY`、`VAPID_MAILTO`），不进数据库

---

## 五、索引

```sql
-- 消息：按会话和时间查询
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);

-- 消息：按入口和时间查询
CREATE INDEX IF NOT EXISTS idx_messages_channel
    ON messages(channel_id, created_at);

-- 消息：快速查找主动消息
CREATE INDEX IF NOT EXISTS idx_messages_proactive
    ON messages(is_proactive, created_at);

-- 发送记录：按消息查询
CREATE INDEX IF NOT EXISTS idx_delivery_message
    ON delivery_logs(message_id, created_at);

-- 成本记录：按用途和时间查询
CREATE INDEX IF NOT EXISTS idx_usage_source
    ON usage_logs(source, created_at);

-- 聊天：按时间查询（全局）
CREATE INDEX IF NOT EXISTS idx_conv_created
    ON conversations(created_at);

-- 记忆候选：按状态筛选
CREATE INDEX IF NOT EXISTS idx_candidates_status
    ON memory_candidates(status, created_at);

-- 正式记忆：按类型和权重排序
CREATE INDEX IF NOT EXISTS idx_memories_type
    ON memories(memory_type, weight DESC);

-- 正式记忆：快速查找未解决的
CREATE INDEX IF NOT EXISTS idx_memories_unresolved
    ON memories(unresolved) WHERE unresolved = 1;

-- 正式记忆：按最近触发时间
CREATE INDEX IF NOT EXISTS idx_memories_triggered
    ON memories(last_triggered_at DESC);

-- 正式记忆：按权重排序（关联记忆打分用）
CREATE INDEX IF NOT EXISTS idx_memories_weight
    ON memories(weight DESC);

-- 提醒：按状态和截止时间（调度器用）
CREATE INDEX IF NOT EXISTS idx_reminders_status
    ON reminders(status, due_at);

-- 日记：按作者和日期
CREATE INDEX IF NOT EXISTS idx_diaries_author
    ON diaries(author, date DESC);

-- 日记：按日期查询
CREATE INDEX IF NOT EXISTS idx_diaries_date
    ON diaries(date DESC);

-- 小纸条：快速查找未读
CREATE INDEX IF NOT EXISTS idx_notes_unread
    ON notes(read) WHERE read = 0;

-- 解锁记录：按日记 ID
CREATE INDEX IF NOT EXISTS idx_unlock_diary
    ON diary_unlock_logs(diary_id, created_at);

-- 设备快照：按时间查最新
CREATE INDEX IF NOT EXISTS idx_device_snapshots_created
    ON device_snapshots(created_at DESC);

-- App 使用追踪：按 App 名称和时间（toggle 查询 + 汇总用）
CREATE INDEX IF NOT EXISTS idx_app_usage_app_created
    ON app_usage_events(app_name, created_at DESC);

-- 推送订阅：endpoint 已有 UNIQUE 约束自带索引，无需额外建
```

---

## 六、迁移策略

首发不使用 ORM 迁移工具（Alembic 等），太重了。

手动管理 SQL 迁移文件：

```
backend/migrations/
├── 001_initial.sql          -- 所有初始表 + 索引
├── 002_add_xxx.sql          -- 后续新增字段/表
└── ...
```

规则：
- 每个文件必须幂等（用 `CREATE TABLE IF NOT EXISTS`、`CREATE INDEX IF NOT EXISTS`）
- 按序号执行
- 在 `database.py` 的 `init_db()` 函数中按顺序执行所有迁移文件
- 新增迁移文件时同步更新本文档

---

## 七、备份策略

生产环境使用 `backend/scripts/backup_database.py` 与 `remoire-backup.timer`，每天北京时间 04:00 创建在线一致性快照，执行 `PRAGMA quick_check`，生成 SHA-256，并保留最近 30 天。

```bash
systemctl start remoire-backup.service
systemctl list-timers remoire-backup.timer --no-pager
journalctl -u remoire-backup.service -n 10 --no-pager
```

手动备份到本地电脑：
```bash
scp root@你的VPS:/root/backups/remoire-YYYYMMDDTHHMMSSZ.db ~/Downloads/
scp root@你的VPS:/root/backups/remoire-YYYYMMDDTHHMMSSZ.db.sha256 ~/Downloads/
```

Remoire 使用 SQLite WAL mode，运行中备份不要直接 `cp` 主 `.db` 文件。恢复与演练步骤见 `docs/OPERATIONS.md`。

---

## 八、注意事项

1. **所有主键用 UUID v4 字符串**，不用自增整数。原因是 MCP 端和小窝端都可能创建记忆，UUID 避免冲突。

2. **时间统一用 ISO 8601 格式存储**：`2026-04-24T15:30:00`。SQLite 没有原生时间类型，TEXT 列存 ISO 字符串，用 `datetime()` 函数比较。

3. **JSON 字段用 TEXT 类型存储**，读取时在应用层 `json.loads()` 解析。SQLite 的 JSON 函数可以用但不强制。

4. **不要在高频写入路径上做事务嵌套**。聊天消息存储 + 候选记忆提取应该是两个独立的 INSERT，不要包在同一个事务里——万一打标失败不应该影响消息存储。

5. **模型 API Key**：生产环境必须配置 `MODEL_SECRET_ENCRYPTION_KEYS`。服务启动时会用 Fernet 对 `model_presets.api_key` 的历史明文执行原地迁移；数据库只保存带 `fernet:v1:` 前缀的密文。密钥不进入数据库或备份，应单独保存在服务器环境变量和离线密码库中。
