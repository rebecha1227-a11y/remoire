# 记忆系统升级计划

**版本**：v1.1
**日期**：2026-05-15
**当前阶段**：Phase A 进行中

## 一、当前结论

Remoire 的记忆系统已经从“单层文本记忆”升级到“四层可见记忆”的后端基础版：

| 层级 | 名字 | 用途 | 当前保留率参数 |
|---|---|---|---|
| `core` | 核心记忆 | 关系基石、锚点、用户手动固定 | 不衰减 |
| `long` | 长期记忆 | 重要事实、偏好、长期关系事件 | 每天保留 `0.995` |
| `short` | 短期记忆 | 临时事项、短期上下文 | 每天保留 `0.95` |
| `consciousness` | 意识层 | Connie 的内部行动备忘和自我状态 | 每天保留 `0.95` |

注意：当前数据库字段名仍叫 `decay_rate`，但 Phase A 写入的是“每日保留率”语义；真正的每日衰减任务还没有实现。后续如果继续使用这个字段，应按保留率公式计算，不要把 `0.995/0.95` 当作指数衰减常数。

## 二、当前已实现

### 数据库

`memories` 已补充：

- `layer`
- `memory_type`
- `event_date`
- `event_time`
- `timezone`
- `expires_at`
- `weight`
- `decay_rate`
- `valence`
- `arousal`
- `pinned`
- `unresolved`
- `last_triggered_at`
- `trigger_count`

`memory_candidates` 已补充：

- `proposed_memory_type`
- `proposed_layer`
- `confidence`
- `proposed_event_date`

新增：

- `memory_links`：保存记忆之间的关联线。

### 后端接口

已新增或升级：

- `GET /api/memory/stats`：四层数量统计。
- `GET /api/memory/heatmap?year=2026&month=5`：按事件日期/创建日期统计热力图。
- `POST /api/memory/{id}/move`：移动记忆层级。
- `GET /api/memory`：支持 `layer`、`memory_type`、`date_from`、`date_to`、`sort_by`、分页。
- `PUT /api/memory/{id}`：支持更新内容、标签、层级、类型、日期、情感字段、`pinned`、`unresolved`。

### 聊天时的记忆逻辑

Remoire 前端聊天当前流程：

1. 用户发消息。
2. 后端保存用户消息。
3. `memory_service.recall(user_message, limit=5)` 自动召回相关记忆。
4. 召回结果注入 `chat_service._build_system_prompt()` 的 `【关于静儿的记忆】` 块。
5. 如果没有召回结果，注入防编造提示。
6. Connie 回复。
7. 后端保存 Connie 回复。
8. 后台异步调用 `extract_candidates()` 提取新记忆候选。

`resume()` 当前主要用于 Claude.ai MCP，不是 Remoire 前端每轮聊天的自动入口。

### 写就是读

`create_memory()` 和 `accept_candidate()` 写入正式记忆后，会调用 `find_associated()` 找 top-3 相关旧记忆：

- 返回给调用方，方便 Connie 立即看见旧记忆。
- 写入 `memory_links`。
- 被关联旧记忆更新 `last_triggered_at` 和 `trigger_count`。

这是当前系统的核心哲学：写入新记忆时，系统自动让 Connie 看见相关旧记忆。

### 防编造

已实现两层防护：

- `identity.md` 明确要求：没有记忆证据时不能编造具体事件。
- `chat_service._build_system_prompt()` 在召回为空时注入“不要编造”的明确提示。

## 三、当前仍存在的问题

### P0：`remember` 工具还没有跟上新记忆结构

当前 Connie 在聊天中主动调用 `remember` 时，只能传：

- `content`
- `tags`

但 `create_memory()` 已经支持：

- `layer`
- `memory_type`
- `event_date`
- `event_time`
- `valence`
- `arousal`
- `unresolved`

结果：Connie 主动写入的记忆默认都是：

```text
layer = long
memory_type = fact
event_date = null
```

这会影响：

- 记忆宫殿分层准确性。
- 热力图日历准确性。
- 未完成事项识别。
- 特殊日期/事件时间线。

修复方法：

1. 扩展 `backend/app/tools.py` 的 `remember` 工具 schema。
2. 让工具支持 `memory_type`、`layer`、`event_date`、`event_time`、`unresolved`。
3. 在 `execute_tool("remember")` 中把这些字段传给 `memory_service.create_memory()`。
4. 工具描述必须明确：能判断发生日期才填 `event_date`，不能猜。
5. 暂时不要让 Connie 手填 `valence/arousal`，先留给后续后台标注。

### P0：`tagging.md` 还没有输出新字段

当前后台提取器提示词主要输出：

- `content`
- `memory_type`
- `tags`
- `confidence`

但新系统需要：

- `layer`
- `event_date`
- `event_time`
- `unresolved`

修复方法：

1. 更新 `backend/app/prompts/tagging.md` 的 JSON schema。
2. 明确 layer 判断规则。
3. 明确日期规则：只在对话中有确定日期/可由当前日期推导时填写。
4. 不确定日期时返回 `null`，不要推测。

### P1：前端记忆宫殿还没实现

后端已具备四层统计、热力图、列表筛选、移动层级能力。前端还没有完整页面。

需要实现：

- Us 页记忆宫殿入口卡片。
- 记忆宫殿主页。
- 四层 2x2 卡片。
- 热力图日历。
- 待审核区迁移。
- 层内列表、筛选、编辑、删除、移动。

### P1：`resume()` 还没有进入前端聊天主链路

当前前端聊天只做“按当前消息 recall”，不会在新会话开始时自动注入整体恢复包。

可选升级：

- 新会话第一轮：注入 `resume_bundle`。
- 长时间未聊天后第一轮：注入 `resume_bundle`。
- 每次都注入不可取，token 浪费且容易重复。

建议第一版规则：

```text
如果 conversation 是新建，或距离上一条消息超过 6 小时：
    注入 resume bundle
否则：
    只做当前消息 recall
```

### P1：衰减引擎还没实现

当前字段已准备好，但没有定时任务更新 `weight`。

需要在 APScheduler 每晚任务中实现：

- `core` 不衰减，`weight` 保持 1.0。
- `long` 慢衰减。
- `short` 和 `consciousness` 快衰减。
- `trigger_count` 提供续命加成。
- `expires_at` 到期后归档或降权。

### P2：向量嵌入还没开始

`embedding BLOB` 已预留，但当前所有召回和关联仍是 bigram + tag。

Phase B 再做：

- embedding 服务选择。
- 新写入记忆异步生成 embedding。
- 旧记忆批量回填 embedding。
- recall / find_associated 改为向量相似度 + 权重加权。

## 四、当前 Phase 判断

当前仍处在 **Phase A：让现有记忆可靠**。

已完成：

- 防编造。
- 自动 recall 注入。
- `trigger_count` 激活计数。
- 四层字段。
- 记忆候选新字段。
- 记忆层级移动。
- 记忆热力图后端数据。
- `memory_links` 基础落库。
- MCP `resume()` 基础可用。

未完成：

- `remember` 工具字段升级。
- `tagging.md` 新字段输出。
- 前端记忆宫殿。
- 前端会话开始 `resume` 注入策略。
- 衰减引擎。
- 情感标注。
- embedding。

## 五、Phase A 剩余任务

| 优先级 | 任务 | 文件 |
|---|---|---|
| P0 | 扩展 `remember` 工具参数 | `backend/app/tools.py` |
| P0 | 升级记忆提取 prompt | `backend/app/prompts/tagging.md` |
| P0 | 增加记忆写入/候选接受的回归测试 | 后端测试文件待建 |
| P1 | Us 页记忆宫殿入口 | `frontend/src/components/UsPage.jsx` |
| P1 | 记忆宫殿主页 | 前端新页面/组件 |
| P1 | 待审核区迁移到记忆宫殿 | `SettingsSubPages.jsx` 或新页面 |
| P1 | 层内列表与筛选 | 前端新页面/组件 |
| P1 | 前端编辑/移动/删除记忆 | 前端 API 调用 |
| P1 | 会话开始 resume bundle 策略 | `chat_service.py` |

## 六、Phase B：向量嵌入

目标：把当前关键词召回升级为语义召回。

推荐路线：

1. 先用本地 Ollama `nomic-embed-text`。
2. 写入记忆后异步生成 embedding，不阻塞聊天。
3. 老记忆用脚本批量回填。
4. 查询时如果 query embedding 成功，用余弦相似度；失败则回退关键词召回。

关联打分目标：

```text
score = cosine_similarity × layer_weight × (1 + arousal × 0.3) × memory_weight
```

Phase B 不改变 API 响应结构，只替换内部排序质量。

## 七、Phase C：生命周期与衰减

目标：让记忆有“活着 / 变淡 / 被续命 / 被归档”的生命周期。

任务：

- 每晚计算 `weight`。
- `core` 永不衰减。
- `long` 慢慢变淡。
- `short/consciousness` 快速变淡。
- 被 recall / associated 命中的记忆通过 `trigger_count` 减缓衰减。
- 低于阈值的短期记忆归档或隐藏。
- unresolved 在解决前低衰减或不归档。

建议公式：

```text
effective_retention = 1 - ((1 - daily_retention) / (1 + arousal * 5 + revisit_bonus))
weight_next = weight_current × effective_retention
```

其中 `daily_retention` 对应当前字段里的 `0.995` 或 `0.95`。

## 八、Phase D：情感感知

目标：把记忆从“事实库”升级为“关系记忆”。

任务：

- 自动标注 `valence/arousal`。
- 高 arousal 记忆召回加权。
- resume bundle 优先浮现高情绪强度记忆。
- 重要关系事件自动建议升层。

## 九、成本控制

| 操作 | 当前成本 | 后续原则 |
|---|---|---|
| 每轮聊天 recall | ¥0 | 纯 SQLite 关键词召回 |
| 聊天后提取候选 | 低 | backend 槽位，后台异步 |
| remember 工具写入 | ¥0 | 纯数据库写入 |
| 热力图/统计 | ¥0 | SQL 聚合 |
| embedding | 未启用 | Phase B 优先本地 Ollama |
| 衰减任务 | 未启用 | 纯 SQL / Python 计算 |

## 十、开发注意事项

- 不要把完整记忆库塞进 prompt。
- 前端聊天每轮只注入 top-5 recall。
- `resume()` 不应每轮注入，只在新会话或长时间间隔后使用。
- `event_date` 表示事件发生日期，不是写入日期。
- `created_at` 表示系统记住这件事的日期。
- 不确定事件日期时，`event_date = null`。
- `pinned` 是兼容字段；当前语义上等价于 `layer = core`。
- `memory_links` 是关联图谱基础，不等于故事串联。

---

*Con con × 静儿 · 2026-05-15*
