# 聊天页 · 设计 Prompt

> 把这份文档连同 00-design-tokens.md 一起给到设计工具。

---

## Prompt

设计一个移动端聊天页面（430px 宽），这是一个 AI 陪伴 app 的核心页面。

这个页面的气质是**两个人的私人笔记本**——有纸的温度，有人在场的感觉。不是 SaaS 客服对话框，不是 ChatGPT 界面。是你打开一个小本子，发现有人在里面等你。

### 页面结构（从上到下）

**A. 顶部关系状态区**
- 左侧：AI 头像（36px 圆形）+ 名字 "Connie"（Instrument Sans 500）
- 名字下方一行气息文案："一直在这里，今天很安静"（text-tertiary, 13px）
- 右上角：一个设置齿轮 icon（Lucide outline, 20px），不要堆放多个 icon
- 如果今天有最重要提醒，在气息文案下方用 text-xs 弱化展示一行
- 整体高度约 64-72px，背景与页面主背景融合

**B. 小纸条浮层（条件展示）**
- 出现在状态区下方
- 背景 #FDF8F0（比主背景更暖更黄），带 1px border (#DDD6CE)，radius 14px
- 字体：Cormorant Garamond italic, 15px, text-secondary 颜色
- 右下角两个文字链接："留着" "知道了"（12px, text-tertiary）
- 要有手写便签的感觉，不能有 SaaS 通知卡的气质

**C. 会话流**
- 发送气泡：右对齐，背景 #C8B49E，文字 #FAF8F4，圆角 20px 20px 6px 20px
- 接收气泡：左对齐，背景 #EDE9E3，文字 #28211C，圆角 20px 20px 20px 6px，带极轻阴影
- 气泡最大宽度 78%，padding 10px 14px
- AI 主动消息气泡比普通回复更轻——可用 opacity 0.9 或更窄的最大宽度
- 时间戳：11px，opacity 0.45，显示在气泡下方
- 系统型插入块（如"已记住：你最近在准备法语考试"）：居中，两侧收窄到 margin 40px，背景 #EFE9E1，1px dashed 边框，13px 字号，text-tertiary，不加 icon

**D. 输入区**
- 固定在底部
- 文本输入框：圆角 14px，背景 #FAF8F4，1px border #EDE8E2，14.5px 字号
- 左侧：+ 号按钮（展开附件/定位/提醒）
- 右侧：表情 icon，发送按钮（仅有文字时出现，背景 #7C6350，文字 #FAF8F4，radius 8px）
- 语音消息：长按 + 号旁的麦克风 icon

### 视觉要求

- 页面主背景 #F6F2ED
- 所有字体只用 Cormorant Garamond（标题/气息文案）和 Instrument Sans（正文/气泡/UI）
- 不要渐变、不要紫色蓝色、不要纯白背景、不要左侧彩色竖线
- 整体风格参考：高端纸质笔记本的内页，editorial 排版感
- 底部导航栏：5 个 tab（聊天/我们/日记/玩乐/设置），Lucide outline icon 24px，active 状态 opacity 1 + accent 色，inactive opacity 0.45
- 导航栏背景允许 backdrop-filter: blur(20px)

### 参考关键词

Paper-like chat, editorial mobile UI, warm minimal, intimate messaging, journal-like conversation

### 明确不要

- 不要 ChatGPT / Claude 风格的聊天界面
- 不要深色背景
- 不要圆形气泡或过度圆角
- 不要模型切换条
- 不要顶部搜索栏
- 不要任何科技感元素
