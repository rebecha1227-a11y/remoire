# iMessage 引用与 Tapback：第一批实现（本地，未发布）

## 范围（按用户最新要求）

| 能力 | iMessage | Remoire 网页 |
|---|---|---|
| 引用回复 | 新增原生定向回复、读取对方引用目标；Connie 可通过专用工具选择要引用的气泡 | 原有引用按钮、输入框预览及发送逻辑不变；仅复用既有样式显示 iMessage 引用记录 |
| 气泡 Tapback | 双方添加表情；Connie 可只贴表情而不发送文字 | 不新增按钮、不显示表情；history API 不下发表情数据 |
| 消息正文 | 同一聊天服务、记忆、关系档案 | 继续显示同一聊天历史 |
| 撤回/移除表情 | 本批未实现；需补全底层事件通道和状态同步 | 未修改 |
| 语音、链接卡片 | 已核实 SDK 能力，后续开发 | 本批未修改 |

网页原有引用是 `ChatPage.jsx` 的 `quotedMsg` / `quoteMessage`：选中消息，输入框预览，发送时将引用文字加到用户输入。未重做这套行为；新增网页代码只读取持久化的 iMessage 气泡正文与引用内容。

## 核实依据

- Photon 官方：https://photon.codes/docs/spectrum-ts/reactions-and-replies
- Cloud 支持表：https://photon.codes/docs/spectrum-ts/providers/imessage
- 语音：https://photon.codes/docs/spectrum-ts/content/voice
- 链接：https://photon.codes/docs/spectrum-ts/content/rich-links
- 以当前安装的 `spectrum-ts` / `@spectrum-ts/imessage` **12.10.1** 源码为落地依据。Cloud 消息通过 content.type=reply 包裹正文，目标在 content.target；反应为 content.type=reaction；发送结果返回原生消息 ID；space.getMessage 可恢复定向回复目标。
- SDK toMessageItem 当前只映射 message.received、message.reactionAdded、message.read。撤回、移除反应不能仅凭页面开关宣称可用。
- 按用户提供链接参考 Uranus_Imessage，临时只读克隆提交 `e238b513d35ae97aff1a1c37ad20ead90894ebbe`，重点查看 server/src/imessage.js 的 noteSent、runReactPart、handleUserUnsend 与 reaction 入站分支。该仓库也明确注明用户撤回分支因 SDK 不投递事件而不可达。未复制项目、人设或其提示词，没有运行其服务。

## 实现

- 新表 `imessage_bubbles`：chat_guid + external_id 唯一；关联 messages.id / conversation_id，保存方向、单个气泡正文、reply_to 与必要的引用快照。用户连发多条归同一轮，但分别保留原生气泡 ID。
- 新表 `imessage_reactions`：按聊天、目标、actor 保存最新添加的 emoji。旧消息缺少映射时，SDK 提供的目标快照用于下一轮理解，不猜测网页消息 ID。尚不宣称这是支持移除事件的完整实时反应状态。
- 出站 ACK 回写发送结果 ID；根据本轮 save_message 返回的准确 ID 关联，替代查询“最近一条 assistant”。重复成功 ACK 幂等。进程内 ACK 网络失败只重试 ACK，避免当场重复发送；进程恰好在发送与 ACK 间崩溃的 exactly-once 不保证。
- `imessage_reply_to` / `imessage_react` 只向 iMessage 轮次提供。目标限定为当前会话与聊天的消息目录；缺少目标不猜测、不回退到另一个聊天。表情发送首批支持六种标准 Tapback，入站可读取 SDK 提供的其他 emoji。
- 模型选择的引用/表情先保留在本轮，生成被连发补充作废时一起丢弃。最终回复的第一个气泡可作为原生引用发送；表情仅在 ACK 成功后记录为 Connie 已执行的回应。
- 用户贴表情不启动模型、不进入文字合并计时；下一条文字到来时附带反馈。Connie 可选择仅贴表情；这一轮仍保留原有用户记忆/提醒提取路径。
- Node 纯协议模块可离线测试；重启后通过 provider.space.get 与 space.getMessage 定位目标，不依赖上一进程的消息对象缓存。
- 网页 history 仅增加气泡/引用结构，不包含 Tapback。无新 CSS、字体或网页交互入口。

## 验证与边界

- 完整后端 122 项回归通过；最后的参数校验与 reaction-only 记忆路径调整后再运行 24 项 iMessage 专项，全部通过。
- Node 4 项离线协议测试通过；实际 SDK reply / reaction builder 可构造，未建立 Photon 连接。
- 前端 build、本次修改 ChatPage.jsx 的 ESLint 通过。全量 lint 在原有 SettingsSubPages.jsx:787 的 react-hooks/set-state-in-effect 规则失败，未改动该设置页。
- 430px 本地浏览器：原有引用/取消引用按钮可用，Noto Serif SC 保持，无横向溢出，无 Tapback 元素。
- 预览 `http://127.0.0.1:4190/`，由 frontend/scripts/imessage-preview.mjs 提供虚构只读数据，不连接后端/Photon。预览拒绝写请求，presence 返回 409 属于隔离策略，不是生产错误。
- 没有发布、commit、push；没有启动本机小邮差，没有真实模型或真实短信测试。生产目前仍为此前连发修复版。

## 后续发布检查

1. 在线备份生产 SQLite，使用备份副本验证新增表迁移；不以本地数据库覆盖生产。
2. 协调后端与 Node 新协议一起更新（新增 protocol.mjs 不可漏传），重启前确认线路空闲；本机桥保持关闭。
3. 使用生产 Node 22 / Python 环境在隔离目录复验，再检查 readiness 与桥接状态。
4. 用户真机验收：引用一个气泡发送；给 Connie 的气泡贴表情后再发文字；请求 Connie 对某句贴爱心、或只贴表情；验证网页保留引用而没有表情 UI。
5. 对于 SDK 不提供的移除/撤回事件，下一批研究底层 Photon 事件订阅；不能把当前“最近收到的添加”当作完整反应状态。


## 后续 UI 调整（2026-10-10，用户明确要求）

用户认为原引用卡片侧边强调线过于模板化，授权调整网页引用 UI。现已移除消息引用与输入框引用预览的侧边线/卡片底色，改为轻量回指箭头加原文；引用操作图标统一为 lucide CornerUpLeft。保留 Noto Serif SC 与原有引用发送行为，摘录 13px、输入框身份说明 12px、取消区域 44px。覆盖上文“无新 CSS”的早期状态描述；Tapback 仍只限 iMessage。前端 build、ChatPage lint、430px 引用/取消交互与无溢出检查通过。仅本地预览，未发布。
