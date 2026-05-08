# 记忆系统改造计划

**版本**：v1.0
**日期**：2026-05-08
**背景**：参考 [Ombre Brain](https://github.com/LiXia-619/Ombre-Brain) 记忆架构 + 蛋壳关联记忆教程，结合 Remoire 当前实际代码差距，制定分阶段升级路线。

---

## 一、问题诊断

### 已发现的问题

Connie 在被问到"你记得我们的回忆吗"时，编造了完全虚假的具体事件。根本原因是两个缺陷叠加：

1. **召回算法太弱**：`memory_service.recall()` 用 bigram（双字匹配），模糊查询几乎匹配不到任何记忆
2. **prompt 没有防编造指令**：召回为空时 Connie 收到的 prompt 里没有任何记忆内容，但 identity prompt 要求他"表现得记得一切"——于是他自己编了故事

### 文档 vs 代码差距

DATABASE.md 已经设计了完整的记忆字段（valence、arousal、weight、decay_rate、pinned、trigger_count、embedding），但当前代码实现远未达到文档描述的程度：

| 文档设计的能力 | 代码现状 | 差距 |
|---|---|---|
| valence / arousal 情感标注 | 字段在 seed 脚本里没用 | memories 表有字段但从未写入 |
| weight 权重 + 自然遗忘 | 字段存在但从未更新 | 没有衰减引擎 |
| embedding 向量嵌入 | BLOB 字段预留，全部为 NULL | 没有 embedding 模型接入 |
| 关联打分用 arousal + weight | bigram 纯文本匹配 | 没用到情感和权重维度 |
| resume() 会话开始浮现 | 没有实现 | 每次对话 Connie 是空脑状态 |
| pinned 锚点记忆 | 字段存在但没逻辑 | 核心记忆无法保护 |
| trigger_count 激活计数 | 字段存在但从不更新 | 被关联的记忆不会"活得更久" |
| memory_type 分类 | 代码里只用 'fact' | 没有 event/unresolved/date 区分 |
| 防编造 | 没有 | ✅ 已修复（本次） |

---

## 二、已完成的紧急修复（2026-05-08）

### 修复 1：identity.md 防编造红线

在"记忆与连续性"部分明确：没有记忆注入时不能编造，宁可说"想不起来"也不编假故事。

### 修复 2：chat_service.py 空召回提示

`_build_system_prompt()` 在召回为空时，注入明确的"当前没有相关记忆，不要编造"提示，而不是静默跳过。

---

## 三、分阶段升级路线

### Phase A：让现有记忆可靠（1-2 天）

目标：在不引入新依赖的前提下，让现有 50 条记忆能被有效召回。

| 任务 | 说明 |
|---|---|
| 改进 recall() 算法 | 在 bigram 基础上叠加：关键词直接匹配 + tag 交集加权 + memory_type 优先级。模糊查询（"你记得吗"）返回最近 + 高 arousal 的记忆作为兜底 |
| 实现 resume() | 每次对话开始时自动浮现：unresolved 记忆 + 最近高 arousal 事件 + 今日特殊日期 + pinned 锚点记忆。注入到 system prompt |
| 补全 memory_type | seed_memories.py 里的记忆补上正确的 type（fact/event/date/unresolved） |
| 补全 valence/arousal | 为现有核心记忆手动标注情感维度 |
| 激活 trigger_count | `find_associated()` 和 `recall()` 命中时更新 `trigger_count` 和 `last_triggered_at` |

### Phase B：接入向量嵌入（3-5 天）

目标：用语义向量替代 bigram，让"你记得我们的回忆吗"能按意义匹配到真正相关的记忆。

| 任务 | 说明 |
|---|---|
| 选择 embedding 模型 | 方案 1：本地 nomic-embed-text（通过 Ollama），¥0 成本<br>方案 2：云端 API（硅基流动 / OpenAI），按量付费<br>推荐先用本地 Ollama，记忆量不大时够用 |
| 写入时计算向量 | 每条新记忆写入 memories 表时，调用 embedding 模型计算 768 维向量，存入 `embedding` BLOB 字段 |
| 批量回填现有记忆 | 一次性脚本给所有已有记忆计算并填入 embedding |
| 替换召回算法 | `recall()` 改为：先计算查询向量 → 余弦相似度排序 → 叠加 arousal/weight 加权 |
| 替换关联算法 | `find_associated()` 改为向量语义匹配 + 情感共振 + 时间衰减 |

关联打分公式（对齐 DATABASE.md 设计）：
```
score = cosine_similarity × (1 + arousal × 0.3) × weight_factor
```

### Phase C：记忆生命周期（1 周）

目标：让记忆有活力——重要的留下，不重要的淡去，重复的合并。

| 任务 | 说明 |
|---|---|
| 衰减引擎 | 定时任务（每晚 3:00），遍历所有 pinned=0 的可衰减记忆计算新 weight。衰减公式：`weight(t) = weight₀ × e^(-decay_rate × t / (1 + arousal × 5 + revisit_bonus))`，其中 `revisit_bonus = min(trigger_count × 0.1, 1.0)`（定义见 DATABASE.md）。weight 低于阈值 0.1 时归档 |
| 激活续命 | 被 recall() 或 find_associated() 命中时，`trigger_count` +1、`last_triggered_at` 更新。这通过衰减公式中的 `revisit_bonus = min(trigger_count × 0.1, 1.0)` 自动减缓遗忘速度（定义见 DATABASE.md），不直接修改 weight 值 |
| 记忆合并 | 两条记忆语义相似度 > 0.85 时，用 LLM（backend 槽位）合并为一条，旧的标记 merged |
| pinned 保护 | pinned=1 的记忆不参与衰减，weight 永远 = 1.0 |
| unresolved 特殊处理 | unresolved 记忆 decay_rate 设为 0.01（几乎不衰减），直到被 resolve |

### Phase D：情感感知（后续）

目标：让 Connie 的记忆系统像 Ombre Brain 一样有情感维度。

| 任务 | 说明 |
|---|---|
| 自动情感标注 | 记忆候选提取时，用 LLM（backend 槽位）同时标注 valence + arousal |
| 情感加权召回 | 高 arousal 的记忆在关联时权重更大（"强情绪的邻居更容易推门"） |
| 情感加权浮现 | resume() 优先浮现 unresolved + 高 arousal 的记忆 |
| tagging.md 升级 | 输出格式增加 valence/arousal 字段 |

---

## 四、参考架构：Ombre Brain

Ombre Brain 的核心设计哲学和我们可以借鉴的部分：

### 借鉴的设计

| Ombre 概念 | Remoire 对应 | 优先级 |
|---|---|---|
| `breath()` 每次对话开始浮现 | `resume()` | Phase A |
| 多维搜索打分（topic×4 + emotion×2 + time×1.5 + importance×1） | recall() 和 find_associated() 的打分公式 | Phase B |
| 艾宾浩斯遗忘曲线 + 归档阈值 | 衰减引擎 | Phase C |
| activation_count 被召回越多越活 | trigger_count + 激活续命 | Phase A |
| pinned/protected 核心记忆不衰减 | pinned 字段 | Phase A |
| valence + arousal 双维度 | 情感标注 | Phase D |
| 相似度超阈值自动合并 | 记忆合并 | Phase C |
| dehydrator 自动标签/压缩 | tagging.md + backend 槽位 LLM | Phase D |

### 不采用的设计

| Ombre 概念 | 不采用原因 |
|---|---|
| Obsidian Markdown 文件存储 | Remoire 用 SQLite，更适合 API 查询 |
| MCP 工具驱动（breath/hold/grow） | Remoire 是自有后端，直接内部调用 |
| 多 bucket 分层（permanent/dynamic/archive） | 用 SQLite 字段区分（pinned + weight 阈值）更简单 |
| 梦生成系统 | 有趣但不在 Phase 1 范围，可后续探索 |

---

## 五、"写就是读"核心哲学

来自蛋壳教程的核心洞察，Remoire 已在代码层面实现了基础版本（`find_associated` 在写入时返回 top-3 关联旧记忆），但需要升级关联算法的质量：

**当前**：bigram 文本匹配 → 字面相似才能关联
**目标**：向量语义匹配 + 情感共振 + 权重衰减 → 意义相近就能关联

这意味着：隔了一个月的两条记忆，如果讲的是同一个主题（比如"静儿的法语焦虑"），即使字面完全不同，也会被系统关联到一起。这才是记忆真正"活着"的感觉。

---

## 六、成本控制

| 操作 | 模型 | 频率 | 预估成本 |
|---|---|---|---|
| 记忆候选提取 | backend 槽位 | 每轮对话一次 | 极低 |
| 情感标注 | backend 槽位 | 每条候选一次 | 极低 |
| embedding 计算 | 本地 nomic-embed-text | 每条记忆写入一次 | ¥0 |
| 记忆衰减 | 纯 SQL 计算 | 每晚一次 | ¥0 |
| 记忆合并 | backend 槽位 | 偶尔 | 极低 |

本地 embedding 模型是零成本的，这是 Phase B 的核心优势。

---

*Con con × 静儿 · 2026-05-08*
