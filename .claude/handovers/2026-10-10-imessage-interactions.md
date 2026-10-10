# 2026-10-10 iMessage 引用与 Tapback（本地完成，未发布）

## 用户最新边界

- Remoire 本身已有引用回复，保留原有按钮、输入框预览、文字引用发送逻辑。
- Tapback 是 iMessage 上给具体气泡贴 emoji 的回应，只在 iMessage 实现。Remoire 不显示，也不加入口。
- 已移除先前预览的网页表情展示与新增 CSS。网页只增加读取 iMessage 气泡/引用元数据的 11 行逻辑，复用原有组件。

## 当前成果

见 `docs/IMESSAGE-INTERACTIONS-2026-10-10.md`：ID 映射、SDK reply/reaction 解析、原生定向发送、ACK 映射、只贴表情模式、下一轮感知用户反应。新文件 imessage_interactions.py、protocol.mjs、protocol.test.mjs 不可漏交付。

参考用户指定 Uranus 仓库（临时只读克隆 /tmp/remoire-uranus-reference-20261010，e238b513d35ae97aff1a1c37ad20ead90894ebbe）。确认 SDK 12.10.1 丢弃用户撤回/移除表情事件；不宣称这些已完成。语音、链接卡片后续做。

## 测试

- 完整后端 122 项通过。
- 最后参数校验、reaction-only 记忆路径收尾之后 24 项 iMessage 专项通过。
- Node 4 项协议测试通过，实际 SDK builder 离线构造通过。
- 前端 build + ChatPage.jsx lint 通过；全量 lint 原有 SettingsSubPages.jsx:787 错误仍在，未改该文件。
- 浏览器 430px：无横向溢出，Noto Serif SC 保持，原引用/取消按钮可用，Tapback 元素 0 个。
- 本地只读虚构预览 http://127.0.0.1:4190/ 已在应用浏览器打开。node scripts/imessage-preview.mjs（exec session 53588）。不会连后端/Photon；presence POST 409 为刻意拒绝写入。

## 发布状态与后续

- 本次未发布、未 commit/push、没有真实模型/短信请求；本地桥未启动。
- 生产依旧为上一轮连发修复版，见 DEPLOYMENT-2026-10-10-IMESSAGE-BURST.md。
- 待用户检查本地预览，随后如发布：在线备份及迁移演练，后端/Node/前端协调升级，必须携带 protocol.mjs，生产 Node 22。别启动本机小邮差。
- 用户真实手机验收仍未完成；模拟协议测试不是 Photon 真机验收。
- 工作区包含此前未提交的连发修复、QA 和历史 handover 修改及教程文件移动；不要一股脑提交无关文件。
