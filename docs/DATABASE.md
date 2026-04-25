# 数据库 Schema · Our Nest

**版本**：v1.0
**日期**：2026-04-24
**引擎**：SQLite (WAL mode)

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

## 二、表结构总览

```
conversations          聊天消息（核心）
memory_candidates      记忆候选（等待确认）
memories               正式记忆（已确认）
special_dates          特殊日期（纪念日等）
reminders              提醒 / 待办 / 共同事件
diaries                日记
diary_unlock_logs      日记解锁记录
notes                  小纸条
model_configs          模型配置
books                  共读书目（P1）
reading_notes          共读批注（P1）
play_spaces            平行空间（P1）
signals                轻量生活信号（P1）
```

---

## 三、表结构详细

### 1. conversations — 聊天消息

所有聊天记录的存储。每条消息一行，用户消息和 AI 回复分别存储。

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,                          -- UUID v4
    session_id TEXT NOT NULL DEFAULT 'default',    -- 会话 ID，首发只有一个 default
    role TEXT NOT NULL,                            -- 'user' / 'assistant' / 'system'
    content TEXT NOT NULL,                         -- 消息文本内容
    message_type TEXT DEFAULT 'text',              -- 'text' / 'image' / 'voice' / 'location' / 'system_card'
    metadata_json TEXT,                            -- JSON，存附件信息：
                                                   --   图片：{"image_url": "...", "thumbnail_url": "..."}
                                                   --   语音：{"audio_url": "...", "duration_sec": 12}
                                                   --   定位：{"lat": 39.9, "lng": 116.4, "address": "..."}
                                                   --   系统卡：{"card_type": "memory_saved", "ref_id": "..."}
    is_proactive BOOLEAN DEFAULT 0,                -- 是否为 AI 主动发送的消息（区别于回复）
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

设计说明：
- `session_id` 首发阶段固定为 `'default'`，所有消息在同一个流里
- 后续如果要支持多会话（比如平行空间独立对话），通过 session_id 区分
- `metadata_json` 用 JSON 存灵活数据，不为每种消息类型建子表
- `is_proactive` 用于前端区分主动消息的视觉样式（更轻、更像自言自语）

### 2. memory_candidates — 记忆候选

从聊天中提取出来但还没被用户确认的记忆。是记忆系统的"缓冲区"。

```sql
CREATE TABLE IF NOT EXISTS memory_candidates (
    id TEXT PRIMARY KEY,                          -- UUID v4
    content TEXT NOT NULL,                         -- 候选记忆的文本内容
    source_type TEXT NOT NULL,                     -- 'chat' / 'import' / 'manual'
    source_id TEXT,                                -- 关联的消息 ID 或导入批次 ID
    proposed_memory_type TEXT,                     -- AI 建议的类型：
                                                   --   'fact' / 'event' / 'unresolved' /
                                                   --   'reminder' / 'date' / 'ignore'
    proposed_valence REAL DEFAULT 0.0,             -- 情感效价 -1.0(痛苦) ~ 1.0(愉悦)
    proposed_arousal REAL DEFAULT 0.0,             -- 情感强度 0.0(平静) ~ 1.0(激烈)
    proposed_tags TEXT,                            -- JSON array: ["法语", "考试", "deadline"]
    proposed_unresolved BOOLEAN DEFAULT 0,         -- AI 是否认为这是一件未完成的事
    confidence REAL DEFAULT 0.0,                   -- AI 的置信度 0.0 ~ 1.0
    status TEXT DEFAULT 'pending',                 -- 'pending' 待确认
                                                   -- 'accepted' 已确认为正式记忆
                                                   -- 'rejected' 已拒绝
                                                   -- 'merged' 已合并到其他记忆
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

入库规则：
- `confidence < 0.45` → 仅保留候选，不主动推给用户确认
- `confidence 0.45 ~ 0.75` → 推给用户确认
- `confidence > 0.75` 且是 fact / date / unresolved → 可自动入正式记忆

### 3. memories — 正式记忆

用户确认过的、或高置信度自动入库的长期记忆。这是小窝的灵魂。

```sql
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,                          -- UUID v4
    content TEXT NOT NULL,                         -- 记忆内容
    memory_type TEXT NOT NULL,                     -- 'fact' 人物事实（生日、偏好、目标）
                                                   -- 'event' 关系事件（重要对话、纪念片段）
                                                   -- 'unresolved' 未完成的事
                                                   -- 'reminder' 需要提醒的内容
                                                   -- 'date' 特殊日期
    valence REAL DEFAULT 0.0,                      -- 情感效价
    arousal REAL DEFAULT 0.0,                      -- 情感强度
    decay_rate REAL DEFAULT 0.05,                  -- 遗忘速率（越小越持久）
    weight REAL DEFAULT 1.0,                       -- 当前权重（衰减后会降低）
    unresolved BOOLEAN DEFAULT 0,                  -- 是否未解决
    tags TEXT,                                     -- JSON array
    source_type TEXT,                              -- 来源类型
    source_id TEXT,                                -- 来源 ID
    pinned BOOLEAN DEFAULT 0,                      -- 是否被用户手动固定（锚点记忆）
    last_triggered_at DATETIME,                    -- 上次被浮现/使用的时间
    trigger_count INTEGER DEFAULT 0,               -- 被关联浮现的总次数
    embedding BLOB,                                -- 向量嵌入（预留字段）
                                                   -- 首发阶段为 NULL，用关键词+tag匹配
                                                   -- 记忆 > 300 条后填入向量数据
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

衰减参数参考：

| 记忆类型 | 推荐 decay_rate | 含义 |
|---|---|---|
| 普通事实 fact | 0.06 | 比较快淡掉（"今天中午吃了什么"） |
| 关系事件 event | 0.04 | 慢慢淡掉但不会很快消失 |
| 特殊日期 date | 0.015 | 非常持久（"静儿生日是4月12日"） |
| 未完成 unresolved | 0.01 | 几乎不衰减，直到被 resolve |

衰减公式：
```
weight(t) = weight₀ × e^(-decay_rate × t / (1 + arousal × 5 + revisit_bonus))
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
- `trigger_count` +1
- `weight` 获得 revisit_bonus（+0.1，上限不超过初始值）

这意味着：经常被新记忆关联到的旧记忆会持续"活着"，不会被自然遗忘杀死。

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

### 4. special_dates — 特殊日期

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

### 5. reminders — 提醒 / 待办 / 共同事件

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

### 6. diaries — 日记

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

### 7. diary_unlock_logs — 日记解锁记录

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

### 8. notes — 小纸条

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

### 9. model_configs — 模型配置

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

### 10. books — 共读书目（P1）

```sql
CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    cover_url TEXT,                                -- 封面图 URL（可选）
    added_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

### 11. reading_notes — 共读批注（P1）

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

### 12. play_spaces — 平行空间（P1）

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

### 13. signals — 轻量生活信号（P1）

```sql
CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,                            -- 'location' / 'weather' / 'activity'
    data_json TEXT NOT NULL,                       -- JSON，信号数据
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

---

## 四、索引

```sql
-- 聊天：按会话和时间查询
CREATE INDEX IF NOT EXISTS idx_conv_session
    ON conversations(session_id, created_at);

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
```

---

## 五、迁移策略

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

## 六、备份策略

```bash
# 每天凌晨 4 点自动备份（cron）
0 4 * * * cp /opt/our-nest/backend/data/our-nest.db /root/backups/our-nest-$(date +\%Y\%m\%d).db

# 保留最近 30 天备份，自动清理旧的
0 5 * * * find /root/backups -name "our-nest-*.db" -mtime +30 -delete
```

手动备份到本地电脑：
```bash
scp root@你的VPS:/opt/our-nest/backend/data/our-nest.db ~/Downloads/
```

---

## 七、注意事项

1. **所有主键用 UUID v4 字符串**，不用自增整数。原因是 MCP 端和小窝端都可能创建记忆，UUID 避免冲突。

2. **时间统一用 ISO 8601 格式存储**：`2026-04-24T15:30:00`。SQLite 没有原生时间类型，TEXT 列存 ISO 字符串，用 `datetime()` 函数比较。

3. **JSON 字段用 TEXT 类型存储**，读取时在应用层 `json.loads()` 解析。SQLite 的 JSON 函数可以用但不强制。

4. **不要在高频写入路径上做事务嵌套**。聊天消息存储 + 候选记忆提取应该是两个独立的 INSERT，不要包在同一个事务里——万一打标失败不应该影响消息存储。

5. **`model_configs` 表的 `api_key` 字段**：首发明文存储，后续可改为 AES 加密。.db 文件本身通过文件权限保护（chmod 600）。
