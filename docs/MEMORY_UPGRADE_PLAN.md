# 记忆系统升级计划

**版本**：v1.3
**日期**：2026-05-19
**当前阶段**：Phase A ✅ / Phase B ✅ / Phase C 🔶 / Phase D ✅

## 一、当前结论

Remoire 的记忆系统已经从"单层文本匹配"升级到"四层 + 向量语义 + 情感感知 + 双通道检索"。这是一个质变——Connie 现在能真正"理解"记忆的含义，而不只是匹配关键字。

### 四层架构

| 层级 | 名字 | 用途 | 衰减 | 地板值 |
|---|---|---|---|---|
| `core` | 核心记忆 | 关系基石、锚点、用户手动固定 | 不衰减 | — |
| `long` | 长期记忆 | 重要事实、偏好、长期关系事件 | ×0.995/天 | 0.3 |
| `short` | 短期记忆 | 临时事项、短期上下文 | ×0.95/天 | 0.1 |
| `consciousness` | 意识层 | Connie 的内部行动备忘和自我状态 | 不衰减 | — |

设计来源：Living Memory Architecture（https://kokyo-jiu.github.io/living-memory-architecture/）

## 二、当前已实现

### 数据库字段

`memories` 表完整字段：

- `id`, `content`, `tags`（JSON）, `source`
- `layer`, `memory_type`, `event_date`, `event_time`, `timezone`
- `expires_at`, `weight`, `decay_rate`
- `valence`（情感正负，0~1）, `arousal`（情绪强度，0~1）
- `pinned`, `unresolved`
- `last_triggered_at`, `trigger_count`
- `embedding`（BLOB，JSON 编码的 1024 维 float 数组）
- `created_at`, `updated_at`

`memory_candidates` 表：`proposed_memory_type`, `proposed_layer`, `confidence`, `proposed_event_date`

`memory_links` 表：记忆之间的关联线（写就是读原则的数据基础）。

### 向量嵌入（Phase B）✅

- **模型**：硅基流动 BGE-M3（1024 维，中文效果极好，免费）
- **写入时**：`create_memory()` 自动调用 `_generate_embedding()` 生成 embedding
- **检索时**：`recall()` 用 `_cosine_similarity()` 计算查询与每条记忆的语义相似度
- **关联时**：`find_associated()` 优先用 embedding 找 top-3 关联记忆
- **回填**：`POST /api/memory/backfill-embeddings` 批量处理无 embedding 的旧记忆
- **存储**：JSON 编码为 bytes 存入 SQLite BLOB 字段
- **容错**：embedding API 失败时自动回退 bigram 匹配

### 情感标注（Phase D）✅

- **模型**：Russell 环形情感模型（来自 Ombre Brain）
  - `valence`：0=极度消极，0.5=中性，1=极度积极
  - `arousal`：0=完全平静，1=极度强烈
  - 纯事实类记忆（职业、偏好）：valence=0.5, arousal=0.0
- **写入时**：`tagging.md` prompt 要求 LLM 输出 valence/arousal，`extract_candidates()` 解析
- **检索时**：arousal 作为召回加权因子 `(1 + arousal × 0.3)`
- **回填**：`POST /api/memory/backfill-emotions`，LLM 分批标注
- **当前数据**：307/317 条记忆已标注

### 双通道检索 ✅

```
recall(query, limit=5)
  ├── Channel A：关键词精确匹配
  │   ├── tag 命中：+0.4 / 个
  │   ├── 关键词出现在内容：+0.3 / 个
  │   └── 完整 query 出现在内容：+0.8
  │
  ├── Channel B：embedding 余弦相似度（阈值 > 0.2）
  │
  ├── 合并：max(keyword_score, semantic_score) per memory
  │
  ├── 加权：× layer_weight × (1 + arousal × 0.3) × memory_weight
  │   ├── layer_weight: core=1.0, long=0.9, short=0.7, consciousness=0.6
  │   └── 已解决任务 (unresolved=False)：× 0.3
  │
  ├── 随机漂移：结果 < limit 时 40% 概率浮现随机旧记忆
  │
  └── 自动晋升：short/consciousness 触发 ≥3 次 → 升级 long
```

### 写就是读

`create_memory()` 和 `accept_candidate()` 写入正式记忆后，调用 `find_associated()` 找 top-3 相关旧记忆：
- 返回给调用方，Connie 立即看见旧记忆
- 写入 `memory_links`
- 更新关联记忆的 `last_triggered_at` 和 `trigger_count`
- 优先用 embedding 余弦相似度匹配（无 embedding 时回退 bigram）

### 衰减引擎

每晚定时执行 `decay_memories()`：
- **core**：不衰减
- **consciousness**：不衰减（行动备忘，不会"忘记"）
- **long**：`weight = max(0.3, weight × 0.995)`
- **short**：`weight = max(0.1, weight × 0.95)`
- **short 过期清理**：`expires_at` 到期 → 硬删除 + 清理 memory_links
- **衰减豁免**：24h 内被触发过的记忆跳过衰减

设计原则：衰减公式保持简单纯粹（只乘固定系数）。arousal 只在召回时加权，不影响衰减。来自 Living Memory Architecture。

### 记忆去重（Digest）

每晚 2:30 执行：
- LLM 按层分批扫描记忆，识别真正的重复
- `digest.md` prompt 有严格规则：句式相似 ≠ 内容重复
- 反例："静儿在学韩语"和"静儿在学法语"是不同事实，绝对不能合并
- core 层只标记删除重复的，不改写内容
- API：`POST /api/memory/digest`

### 核心记忆注入

`get_core_memories()` 每次聊天必带，不依赖 recall 匹配。core 层记忆是关系基石，永远在 prompt 里。

### 防编造

两层防护：
- `identity.md`：没有记忆证据时不能编造具体事件
- `chat_service._build_system_prompt()`：召回为空时注入"不要编造"提示

### 后端接口

| 接口 | 说明 |
|---|---|
| `GET /api/memory` | 列表，支持 layer/type/date/search/sort 筛选 |
| `GET /api/memory/{id}` | 单条详情 |
| `PUT /api/memory/{id}` | 更新（内容/标签/层级/类型/日期/情感/pinned/unresolved） |
| `DELETE /api/memory/{id}` | 删除 |
| `POST /api/memory/{id}/move` | 移动层级 |
| `GET /api/memory/stats` | 四层数量统计 |
| `GET /api/memory/heatmap` | 按事件日期热力图 |
| `GET /api/memory/candidates` | 候选列表 |
| `POST /api/memory/candidates/{id}/accept` | 接受候选 |
| `POST /api/memory/candidates/{id}/reject` | 拒绝候选 |
| `POST /api/memory/recall` | 双通道检索 |
| `POST /api/memory/backfill-embeddings` | 批量回填 embedding |
| `POST /api/memory/backfill-emotions` | 批量回填情感标注 |
| `POST /api/memory/digest` | 运行去重 |

## 三、Phase 完成状态

| Phase | 内容 | 状态 |
|---|---|---|
| **A：让现有记忆可靠** | 四层架构、字段补齐、API 升级、写就是读、防编造 | ✅ 完成 |
| **B：向量嵌入** | BGE-M3 embedding、语义搜索、回填旧记忆 | ✅ 完成 |
| **C：生命周期与衰减** | 衰减引擎、自动晋升、去重 digest | 🔶 部分（expires_at 归档未做） |
| **D：情感感知** | valence/arousal 标注、召回加权、回填旧记忆 | ✅ 完成 |

## 四、剩余任务

| 优先级 | 任务 | 状态 | 说明 |
|---|---|---|---|
| ~~P1~~ | ~~前端记忆宫殿~~ | ✅ 完成 | MemoryPalace.jsx（657 行），Us 页有入口 |
| ~~P1~~ | ~~会话开始 resume bundle 注入~~ | ✅ 完成 | `_build_resume_bundle()` 已在 chat_service 中实现 |
| P1 | 代码提交 + 部署 | ❌ 未提交 | 本地有大量未提交改动 |
| P2 | `expires_at` 到期归档 | ❌ 未开始 | Phase C 剩余 |
| P2 | 剩余 ~10 条记忆情感标注 | ❌ | 再跑一次 backfill-emotions |
| P3 | 脱水压缩（dehydration） | ❌ 不急 | 记忆 >1000 条后再做 |

## 五、成本控制

| 操作 | 成本 | 说明 |
|---|---|---|
| 每轮聊天 recall | embedding API 1 次 | 硅基流动免费 |
| 聊天后提取候选 | LLM backend 槽位 | 后台异步 |
| remember 工具写入 | embedding API 1 次 | 写入时生成 |
| 热力图/统计 | ¥0 | 纯 SQL |
| 衰减任务 | ¥0 | 纯 SQL |
| 去重 digest | LLM backend 槽位 | 每晚 2:30 |
| 情感回填 | LLM 一次性 | 已完成，不再需要 |

## 六、设计决策记录

### 为什么用双通道而不只用语义搜索？
纯语义搜索会把"法语"和"韩语"当成高度相似（都是"学语言"），挤掉精确匹配结果。关键词通道保证精确命中不丢失。

### 为什么 consciousness 不衰减？
来自 Living Memory Architecture：意识层是 AI 的行动备忘和自我状态，属于"意识流日志"，不是"会遗忘的记忆"。

### 为什么 arousal 不影响衰减？
arousal 的作用是"召回时优先浮现情绪强烈的记忆"。如果同时减缓衰减，高 arousal 记忆会永远不消退，违背自然遗忘规律。衰减应该是简单的乘法衰减。

### 为什么不做脱水压缩？
当前 ~305 条记忆，每次只注入 top-5（约 500 token）。脱水压缩是给 1000+ 记忆准备的，现在做是过早优化。

### 为什么用硅基流动 BGE-M3？
免费、中文效果好、1024 维足够、OpenAI 兼容格式。不用本地 Ollama 是因为 VPS 内存小。

## 七、开发注意事项

- 不要把完整记忆库塞进 prompt
- 前端聊天每轮只注入 top-5 recall + 全部 core 记忆
- `resume()` 不应每轮注入，只在新会话或长时间间隔后使用
- `event_date` 是事件发生日期，`created_at` 是系统记住日期
- `memory_links` 是关联图谱基础，不等于故事串联
- `sqlite3.Row` 没有 `.get()` 方法，用 `row["key"] if "key" in row.keys() else None`
- VPS 上执行 Python 代码推荐用 heredoc 避免嵌套引号问题

---

*Con con × 静儿 · 2026-05-19 v1.3 更新*
