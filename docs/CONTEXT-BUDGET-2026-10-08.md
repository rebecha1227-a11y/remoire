# 长对话上下文预算 · 2026-10-08

## 状态

本地代码已实现，尚未部署生产。没有触发真实模型、真实推送或生产数据库写入。摘要质量、各供应商精确 token 计数和真实超长对话仍需后续验收。

## 四层上下文

1. **固定层**：关系档案中的 identity、voice、已开启 scene，以及后端 thinking、grounding 和工具原则。固定层与最新用户输入不会被静默裁剪；二者超过输入预算时返回 `context_budget_exceeded`。
2. **近期原文层**：从最新消息向前选取连续后缀，保留逐条消息的北京时间标记。图片按固定保守额度估算。预算不足时先丢弃更旧原文，最新输入保持原样。
3. **滚动摘要层**：成功回复后异步压缩较早消息。`conversation_summaries` 保存版本、最后覆盖 rowid/消息 ID 和累计数量；下一次只处理尚未覆盖的连续范围，保留至少 12 条近期原文。
4. **长期记忆层**：核心及置顶记忆原文属于强制层，只折叠正文完全相同的条目，超限明确报错，不做摘要或相似文本合并；相关召回记忆按剩余预算装载。

昼夜回应、时间、天气、醒来信息与日记互动属于动态补充层，在固定层和最新输入之后分配空间。工具结果可以带明确省略标记截短，避免一次工具输出挤掉关系档案或最新消息。

## 模型能力与设置

模型厂商决定真实上下文窗口。Remoire 优先按模型 ID 或 `/models` 返回的能力元数据自动识别，不再要求用户在普通设置界面手填。`model_slots.context_window` 和 `output_budget` 仍作为后端兼容字段，后者也作为请求的 `max_tokens`。输入预算计算为：

```text
模型上下文上限 - 回答预留 - 4% 安全余量（最少 512，最多 4096）
```

token 估算是面向中文、英文、图片和工具 schema 的保守跨供应商估算，不替代各厂商 tokenizer。能力识别按三层处理：优先规范化模型服务 `/models` 返回的常见限制字段；再用官方资料维护的模型别名表补齐；两者都没有时使用 32,768 / 4,096 兼容预算并明确显示未确认。若服务元数据和官方能力表同时存在，采用两者较小的限制，避免网关自身限额被忽略。

当前能力表覆盖 Claude Opus 4.6（1,000,000 / 128,000）、Gemini 2.5 Pro（1,048,576 / 65,536）和 DeepSeek V4.1 Flash/Pro 及其现有旧别名（1,000,000 / 393,216）。从模型列表选择时，规范化后的能力会随预设保存，重启后仍生效。普通设置页只显示识别结果，不提供容易误填的数字输入。

## Claude Prompt caching

- Claude 模型优先通过 Anthropic Messages 协议调用；当前使用的 New API 网关公开支持 `/v1/messages`。若网关明确返回 404、405 或 501，自动退回原有 Chat Completions，避免中断聊天。
- 工具 schema 使用稳定全集与固定顺序，但 Connie 仍自主决定本轮调用零个、一个或多个工具。固定工具列表是为了避免工具变化使其后的 system 缓存全部失效。
- identity、voice、已开启 scene、thinking、grounding 与工具原则组成第一个稳定 system block，并在末尾设置 5 分钟 `cache_control: {"type":"ephemeral"}`。时间、天气、摘要、记忆和近期消息放在断点之后。
- 当前固定前缀在不含 scene 时保守估算约 8,271 tokens，超过 Opus 4.6 的 4,096 token 最低缓存门槛。缓存不减少上下文占用，也不能让超长 prompt 绕过窗口限制。
- 返回 usage 中的 `cache_creation_input_tokens`、`cache_read_input_tokens` 或 OpenAI 兼容的 `cached_tokens` 会写入 `llm_usage_events`；只保存模型、槽位和 token 数，不保存提示词正文。设置页显示最近 7 天真实可观测请求的命中率。服务商没有返回缓存明细时不计入命中率分母，避免把“无法观测”误算成未命中。本地测试没有触发付费模型请求。
- Claude thinking 工具循环会原样带回 thinking block 与签名，避免缓存或协议改造破坏后续工具调用。

## 摘要与记忆边界

- 摘要 prompt 要求保留事实、时间、不确定性、关系变化、承诺和未完成话题，不把助手原话自动当作用户事实。
- 摘要只进入后续聊天上下文。记忆候选仍只读取近期原始消息与本轮回复，摘要不能自动进入正式记忆或核心记忆。
- 摘要模型失败时不推进覆盖标记；聊天继续使用预算内的近期原文。
- 并发摘要通过 version + through_message_rowid 条件更新，避免两个后台任务重复推进。

## 其他 Prompt

thinking 与 grounding 独立保留并作为聊天固定层。identity/voice 只在新实例第一次初始化时从文件原样导入，之后由关系档案数据库版本生效。autonomous、nudge、tagging、reminder_extract、digest 仍由各自服务读取；其中 nudge 只在当前自主活动允许发主动消息时装载。

## 本地验证

- `cd backend && ./venv/bin/python -m unittest discover -s tests`：96 项通过。
- `cd frontend && npm run build`：通过。
- `cd frontend && npm run lint`：通过。
- 新测试覆盖固定层与最新输入不裁剪、强制层超限明确报错、摘要连续范围不漏不重、槽位预算持久化、Claude/Gemini/DeepSeek 别名识别、服务元数据规范化、跨协议缓存 usage 解析、稳定工具目录、缓存断点与 thinking 签名保留。

本次没有真实调用模型，因此不能把模拟摘要覆盖测试写成真实长期对话质量已经验收。
