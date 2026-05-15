# 设计系统 · Our Nest

**版本**：v2.0
**日期**：2026-05-15
**作者**：Con con × 静儿

> 这份文档是给做原型和写前端代码的人读的。
> 每一个决定都有理由，请不要随意替换。
> 如果你是 Claude Code 或其他 AI 工具，请严格遵守本文档的所有规范和禁止清单。

---

## 一、设计语言

### 核心气质

**Liquid Glass Ambient · Neo-minimal but intimate · Quiet luxury**

一句话：**这是两个人的客厅，随时间变化，有光有暗有天气。**

设计语言必须传递：
- 有呼吸的温度——玻璃表面透着背后的氛围光
- 有人在场——不是系统界面，是一间有人住的房间
- 随时间流动——清晨是花瓣和柔光，深夜是星空和烛火
- 克制但不冷漠，安静但不空洞

### 气质参考（给设计者的感性描述）

想象你走进一间两个人的客厅——窗外的光随时辰变化，清晨是暖粉色的，午后是蜜金色的，入夜后是深蓝的星空。房间里的一切——聊天气泡、小纸条、导航栏——都像玻璃器皿，半透明地映着窗外的光。偶尔有花瓣飘过（清晨），或者光尘在空气里浮动（白天），或者星星在闪烁（深夜）。

这就是我们要的感觉。

---

## 二、色彩系统

### 2.1 设计理念

静态色板作为基底/回退值（定义在 `tokens.css`），运行时由 **氛围系统** 动态覆盖。氛围系统在 `frontend/src/utils/ambient.js` 中定义了 7 个时段调色板（dawn / morning / afternoon / golden / dusk / night / late），由 `RoomShell` 组件实时注入 CSS Variables，覆盖下方的静态值。

基底色仍然来自同一个暖灰棕色相——像一间用木头和亚麻布置的房间。但运行时，窗外的光会洒进来：清晨是粉杏色，午后是蜜金色，入夜后是深靛蓝。所有界面元素（气泡、卡片、导航栏）都采用液态玻璃风格（`backdrop-filter: blur() saturate()`），透出背后的氛围渐变。

### 2.2 完整色板

```css
:root {
  /* ═══════════════════════════════════════════
     背景色 · Backgrounds
     房间的墙壁和地面
     ═══════════════════════════════════════════ */
  --bg-primary:      #F6F2ED;   /* 主背景 · 暖纸白，所有页面的默认底色 */
  --bg-secondary:    #EFE9E1;   /* 次级背景 · 浅烟杏，用于区分层级的区域 */
  --bg-elevated:     #FAF8F4;   /* 卡片/浮层背景 · 比主背景白一点但不刺眼 */

  /* ═══════════════════════════════════════════
     文字色 · Text
     书写的墨水
     ═══════════════════════════════════════════ */
  --text-primary:    #28211C;   /* 主文字 · 深暖黑，正文和重要内容 */
  --text-deep:       #574337;   /* 深色备选 (Wood) · 用于需要更重分量的标题 */
  --text-secondary:  #72665C;   /* 次级文字 · 中暖灰，副标题和说明文字 */
  --text-tertiary:   #AEA49A;   /* 弱文字 · 时间戳、标签、占位符 */

  /* ═══════════════════════════════════════════
     强调色 · Accent
     笔记本上的重点标记
     ═══════════════════════════════════════════ */
  --accent:          #7C6350;   /* 主强调 · 沉稳暖棕，按钮/链接/激活态 */
  --accent-light:    #C9B8A8;   /* 浅强调 · badge 背景、tag 底色 */
  --accent-subtle:   #EDE5DC;   /* 极浅强调 · hover 状态、选中背景 */

  /* ═══════════════════════════════════════════
     点缀色 · Pop (少量使用)
     房间里那只浅蓝色的杯子
     ═══════════════════════════════════════════ */
  --accent-pop:      #82BDC5;   /* Cloudy · 未读标记、新消息点、轻提示 */

  /* ═══════════════════════════════════════════
     边框色 · Borders
     纸张上的淡线
     ═══════════════════════════════════════════ */
  --border:          #DDD6CE;   /* 常规边框 */
  --border-light:    #EDE8E2;   /* 轻边框 · 分割线、卡片边缘 */

  /* ═══════════════════════════════════════════
     气泡色 · Chat Bubbles
     两个人的笔迹颜色
     ═══════════════════════════════════════════ */
  --bubble-send:         #7C6350;   /* 发送方气泡 · 沉稳暖棕（实际渲染走玻璃拟态，见 2.6 氛围系统） */
  --bubble-send-text:    #FAF8F4;   /* 发送方文字（回退值，运行时由 --user-text 覆盖） */
  --bubble-receive:      #EDE9E3;   /* 接收方气泡（回退值，运行时由 --ai-bg 覆盖） */
  --bubble-receive-text: #28211C;   /* 接收方文字（回退值，运行时由 --ai-text 覆盖） */

  /* ═══════════════════════════════════════════
     语义色 · Semantic
     ═══════════════════════════════════════════ */
  --success:         #7A9E7E;   /* 成功 · 柔和绿 */
  --warning:         #B8924A;   /* 警告 · 暖金，也用于 AI 解锁中动效 */
  --danger:          #B06060;   /* 危险 · 柔和红 */

  /* ═══════════════════════════════════════════
     暗色模式 · Dark Mode
     夜晚的房间，灯光调暗
     ═══════════════════════════════════════════ */
  --bg-primary-dark:       #1C1814;
  --bg-secondary-dark:     #221E1A;
  --bg-elevated-dark:      #272320;
  --text-primary-dark:     #EDE8E2;
  --text-deep-dark:        #D4C4B8;
  --text-secondary-dark:   #8A8078;
  --text-tertiary-dark:    #6B6058;
  --accent-dark:           #C9A882;
  --accent-light-dark:     #5C4A38;
  --accent-subtle-dark:    #332C26;
  --accent-pop-dark:       #6FA8B2;
  --border-dark:           #38322C;
  --border-light-dark:     #2E2924;
  --bubble-send-dark:      #5C4A38;
  --bubble-send-text-dark: #EDE8E2;
  --bubble-receive-dark:   #2C2822;
  --bubble-receive-text-dark: #EDE8E2;
  --success-dark:          #5E8A63;
  --warning-dark:          #9A7A3A;
  --danger-dark:           #964E4E;
}
```

### 2.3 accent-pop 使用规则

`--accent-pop` (#82BDC5) 是那只浅蓝色的杯子——少量使用，出现在正确的地方才有灵气。

**允许使用**：
- ✅ 未读消息圆点（4-6px 小圆点）
- ✅ 新小纸条的指示标记
- ✅ 底部导航激活态的 icon（作为备选方案，也可以用 --accent）
- ✅ 提醒即将到期的轻微色彩提示
- ✅ 日历上特殊日期的标记点

**禁止使用**：
- ❌ 按钮背景色
- ❌ 大面积色块或卡片背景
- ❌ 文字颜色
- ❌ 边框颜色
- ❌ 任何超过 24px × 24px 的色块

### 2.4 text-deep 使用规则

`--text-deep` (#574337, Wood) 比 `--text-primary` 更重、更沉。

**允许使用**：
- ✅ 关系计时器的数字（"在一起的第 142 天"）
- ✅ 日记页的正文标题
- ✅ 需要特别分量感的页面主标题
- ✅ "我们"页的小标题

**默认仍然用 --text-primary**，只在需要额外视觉重量时才切 --text-deep。

### 2.5 禁止使用

| 禁止 | 原因 |
|---|---|
| 纯色平面背景作为主页面底色（已改为时段渐变氛围） | 缺乏呼吸感，与液态玻璃不搭 |
| 紫色 / 蓝色作为高亮色 | 与暖色系统冲突 |
| 纯白 #FFFFFF 作为卡片背景 | 太冷，在暖背景上刺眼 |
| 不透明实色卡片背景（已改为液态玻璃风格） | 遮住氛围渐变，失去通透感 |
| 高饱和色大面积使用 | 打破安静的色彩关系 |
| rgba(0,0,0,...) 作为阴影色（白天时段） | 太冷，白天必须用暖色系阴影；夜间 GLASS_DARK 允许 rgba(0,0,0,...) |

### 2.6 氛围系统 (Ambient System)

整个 app 运行在一个随时间变化的氛围环境中。核心由两个文件实现：

- **调色板定义**：`frontend/src/utils/ambient.js`
- **运行时注入**：`frontend/src/components/RoomShell.jsx`

#### 7 个时段 (Time Bands)

| 时段 | 时间范围 | 背景渐变基调 | 墨色(ink) | 浮动物(Floaters) | 玻璃层 |
|---|---|---|---|---|---|
| **dawn** | 5:00–8:00 | 粉杏 → 烟紫 | 深棕 #2A1B12 | 花瓣 (petals) | GLASS_LIGHT |
| **morning** | 8:00–12:00 | 暖黄 → 亚麻 | 深棕 #2D1E10 | 光尘 (motes) | GLASS_LIGHT |
| **afternoon** | 12:00–17:00 | 蜜金 → 赭棕 | 深棕 #2A1A0C | 光尘 (motes) | GLASS_LIGHT |
| **golden** | 17:00–19:00 | 金橙 → 深赭 | 奶白 #FFEEDA | 光尘 (motes) | GLASS_WARM |
| **dusk** | 19:00–21:00 | 橘红 → 靛紫 | 奶白 #FBEEDD | 光尘 (motes) | GLASS_WARM |
| **night** | 21:00–1:00 | 深靛 → 墨蓝 | 暖米 #EFE3CD | 星星 (stars) | GLASS_DARK |
| **late** | 1:00–5:00 | 炭褐 → 纯黑 | 暖米 #EFE5D2 | 星星+烛光 (stars-candles) | GLASS_DARK |

所有背景使用 `radial-gradient`，从页面中心向外扩散。

#### 3 层玻璃参数 (Glass Tiers)

每个时段对应三组玻璃参数之一，控制气泡、卡片、导航栏的半透明样式：

| 玻璃层 | 适用时段 | AI 气泡背景 | 用户气泡背景 | 阴影色调 |
|---|---|---|---|---|
| **GLASS_LIGHT** | dawn / morning / afternoon | `rgba(255,252,240, 0.16)` | `rgba(255,200,145, 0.22)` | 暖棕 `rgba(120,70,30,...)` |
| **GLASS_WARM** | golden / dusk | `rgba(255,245,220, 0.14)` | `rgba(255,200,140, 0.22)` | 深棕 `rgba(40,18,5,...)` |
| **GLASS_DARK** | night / late | `rgba(255,240,210, 0.10)` | `rgba(255,170,95, 0.18)` | 纯黑 `rgba(0,0,0,...)` |

#### 浮动物 (Floaters)

- **petals** (花瓣)：从顶部飘落，粉色半透明椭圆，带旋转
- **motes** (光尘)：空中缓慢漂浮的暖色小光点
- **stars** (星星)：固定位置闪烁，暖黄色，有呼吸动画 (`r-twinkle`)
- **stars-candles** (星星+烛光)：星星 + 橘色模糊光晕缓慢漂移

#### 天气效果层

RoomShell 支持叠加天气效果（通过 `localStorage` 的 `remoire_weather` 控制）：
- **rain**：线条型雨滴从顶部落下
- **fog**：大面积模糊光带缓慢飘移

#### RoomShell 工作方式

`RoomShell` 包裹所有页面，作为最外层容器：
1. 根据当前时间选择时段 → 取出对应 palette
2. 将 palette 中所有值注入为 CSS Variables（`--ink`、`--ai-bg`、`--user-bg`、`--nav-bg` 等）
3. 同时覆盖 tokens.css 中的基础变量（`--text-primary`、`--accent`、`--bg-elevated` 等）
4. 渲染背景渐变层、噪点纹理层、浮动物层、天气层
5. 通过 `nav` prop 渲染底部导航栏（导航栏在 RoomShell 内部，不是 fixed 定位）

设置页支持手动覆盖时段（`remoire_time_override`），以及自定义聊天背景图（`remoire_chat_bg`）。

---

## 三、字体系统

### 3.1 字体选型

```css
/* Display — Petrona，可变字重的人文主义衬线，温暖书卷气，用于标题、日记正文、关系计时器数字 */
font-family: var(--font-display); /* 'Petrona', 'LXGW WenKai', Georgia, serif */

/* Body UI — Manrope，温暖几何无衬线，圆润但不卡通，用于所有 UI 文字、消息气泡、按钮、导航标签 */
font-family: var(--font-body); /* 'Manrope', 'LXGW WenKai', 'Helvetica Neue', sans-serif */

/* 中文 — LXGW WenKai 霞鹜文楷，开源免费、温暖、带手写感但完全可读 */
/* 已作为 fallback 写入 --font-display 和 --font-body，不需要单独设置 */

/* Handwriting — 手写体，用于便签留言、日记页的涂鸦和补充说明 */
/* 中文 ShouShuTi 手书体（本地）；英文 JustAnotherHand（本地）/ Caveat（Google Fonts） */
font-family: var(--font-note); /* 'ShouShuTi', 'JustAnotherHand', 'Caveat', cursive */

/* 各场景字体变量（可在设置页上传自定义字体覆盖） */
--font-chat:     /* 同 --font-body，聊天界面 */
--font-note:     /* 'ShouShuTi', 'JustAnotherHand', 'Caveat', cursive · 小纸条 */
--font-diary:    /* 'ShouShuTi', 'JustAnotherHand', cursive · 日记 */
--font-read:     /* 'Caveat', 'JustAnotherHand', cursive · 共读批注 */
--font-parallel: /* 同 --font-display · 平行空间 */

/* Mono — 等宽，仅用于技术型内容如 API Key 输入框（可选） */
font-family: 'JetBrains Mono', monospace;
```

### 3.2 引入方式

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Petrona:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400&family=Manrope:wght@400;500;600;700&family=Caveat:wght@400;500&display=swap" rel="stylesheet">
<!-- 中文：LXGW WenKai 霞鹜文楷，jsdelivr CDN -->
<link href="https://cdn.jsdelivr.net/npm/lxgw-wenkai-webfont@1.7.0/style.css" rel="stylesheet">
```

**为什么不用 Cormorant Garamond / Instrument Sans？**
这两个字体在 impeccable 的「不要再选」清单里——所有想做"文艺/温暖品牌"的项目都默认选它们，反而失去辨识度。Petrona + Manrope + LXGW WenKai 的组合既保留温暖书卷气，又给 Remoire 一张自己的脸。

### 3.3 字阶

```css
--text-xs:   0.6875rem;  /* 11px · line-height: 1.4 · 时间戳、弱标签 */
--text-sm:   0.8125rem;  /* 13px · line-height: 1.5 · 次级信息、badge、系统卡 */
--text-base: 0.9063rem;  /* 14.5px · line-height: 1.6 · 正文、气泡文字 */
--text-md:   1rem;       /* 16px · line-height: 1.5 · 卡片标题、导航标签 */
--text-lg:   1.25rem;    /* 20px · line-height: 1.4 · 页面副标题 */
--text-xl:   1.5rem;     /* 24px · line-height: 1.3 · 页面主标题（Display 字体） */
--text-2xl:  2rem;       /* 32px · line-height: 1.2 · 关系计时器数字（Display 字体） */
```

### 3.4 字重规范

| 场景 | 字体 | 字重 | 说明 |
|---|---|---|---|
| 页面主标题 | Petrona | 500 (Medium) | 不用粗体，细腻感来自字体本身 |
| 关系计时器数字 | Petrona | 300 (Light) | 轻量，数字本身就有重量 |
| 日记正文 | Petrona | 400 (Regular) | AI 写的日记可用 italic |
| UI 标签 / 按钮 | Manrope | 500 | — |
| 正文 / 气泡 | Manrope | 400 | — |
| 时间戳 / 弱信息 | Manrope | 400 | 配合 --text-tertiary 颜色 |

### 3.5 禁止

- ❌ DM Sans / Inter / Roboto / Cormorant Garamond / Instrument Sans 作为主字体（都在 impeccable 反射清单里，太通用）
- ❌ font-weight: 700 / 800 在页面标题（太重，破坏 quiet 气质）
- ❌ 全大写字母标题 text-transform: uppercase（时尚感过强）
  - **唯一例外**：日记页的作者标签（"JINGER" / "CONNIE"），用 11px + letter-spacing: 1px

---

## 四、间距与布局

### 4.1 基础单位：4px Grid

```css
--space-1:  0.25rem;  /* 4px */
--space-2:  0.5rem;   /* 8px */
--space-3:  0.75rem;  /* 12px */
--space-4:  1rem;     /* 16px */
--space-5:  1.25rem;  /* 20px */
--space-6:  1.5rem;   /* 24px */
--space-7:  1.75rem;  /* 28px */
--space-8:  2rem;     /* 32px */
--space-10: 2.5rem;   /* 40px */
--space-12: 3rem;     /* 48px */
```

### 4.2 页面布局

- 最大宽度：**430px**，居中
- 页面内边距：左右 **20px**
- 卡片内边距：**16–18px**（标准卡片）/ **12px**（紧凑卡片）
- 区块之间间距：**20–24px**
- 页面顶部到第一个内容区间距：**16px**
- 页面底部到导航栏间距：**20px**（给底部安全区）

### 4.3 圆角

```css
--radius-sm:   8px;     /* badge、小按钮 */
--radius-md:   14px;    /* 输入框、标准卡片 */
--radius-lg:   20px;    /* 模态框、底部抽屉 */
--radius-xl:   24px;    /* 气泡最大圆角 */
--radius-full: 9999px;  /* 圆形头像、标签丸型 */
```

日记卡片例外：使用 **4px** 圆角（接近方形的纸张感）。

### 4.4 阴影

```css
--shadow-sm:  0 1px 4px rgba(40,33,28,0.05);    /* 卡片默认 */
--shadow-md:  0 2px 12px rgba(40,33,28,0.07);   /* 浮层、小纸条 */
--shadow-lg:  0 8px 28px rgba(40,33,28,0.09);   /* 模态框 */
```

**阴影颜色必须取暖棕色 `rgba(40,33,28,...)`，禁止用纯黑 `rgba(0,0,0,...)`。**

---

## 五、组件规范

### 5.1 消息气泡（液态玻璃风格）

气泡采用液态玻璃渲染，背景是半透明的，透出 RoomShell 的氛围渐变。颜色随时段自动变化（见 2.6 氛围系统）。

```css
/* 基础气泡 —— 所有气泡共享的玻璃质感 */
.r-bubble {
  padding: 9px 16px;
  border-radius: 20px;
  font-size: 15px;
  line-height: 1.6;
  letter-spacing: 0.02em;
  backdrop-filter: blur(9px) saturate(1.15);
  -webkit-backdrop-filter: blur(9px) saturate(1.15);
  isolation: isolate;
}

/* 气泡顶部高光 —— 模拟玻璃顶部的光线折射 */
.r-bubble::before {
  content: '';
  position: absolute; inset: 0;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(255,250,235,0.20) 0%, transparent 42%);
  mix-blend-mode: overlay;
  opacity: 0.7;
}

/* AI 气泡（左侧）—— Connie 的声音 */
.r-bubble-ai {
  background: var(--ai-bg);               /* 由氛围系统注入，如 rgba(255,252,240,0.16) */
  border: 1px solid var(--ai-border);      /* 如 rgba(120,75,35,0.20) */
  color: var(--ai-text);                   /* 跟随 --ink，暗色时段自动变浅 */
  box-shadow:
    0 4px 12px -5px var(--warm-shadow),
    inset 0 1px 0 var(--ai-edge);          /* 内侧顶部高光边 */
}

/* 用户气泡（右侧）—— 你的声音 */
.r-bubble-user {
  background: var(--user-bg);              /* 如 rgba(255,200,145,0.22) */
  border: 1px solid var(--user-border);    /* 如 rgba(150,80,30,0.30) */
  color: var(--user-text);
  box-shadow:
    0 4px 14px -5px var(--warm-shadow),
    inset 0 1px 0 var(--user-edge);
}
```

> **回退说明**：tokens.css 中的 `--bubble-send: #7C6350` 和 `--bubble-receive: #EDE9E3` 仍保留为静态回退值。RoomShell 加载后会用 `--ai-bg` / `--user-bg` 等玻璃参数覆盖。

#### 各时段玻璃参数速查

| 玻璃层 | AI 气泡 bg | AI 气泡 border | 用户气泡 bg | 用户气泡 border |
|---|---|---|---|---|
| GLASS_LIGHT（白天） | `rgba(255,252,240, 0.16)` | `rgba(120,75,35, 0.20)` | `rgba(255,200,145, 0.22)` | `rgba(150,80,30, 0.30)` |
| GLASS_WARM（黄昏） | `rgba(255,245,220, 0.14)` | `rgba(255,220,180, 0.26)` | `rgba(255,200,140, 0.22)` | `rgba(255,180,110, 0.40)` |
| GLASS_DARK（深夜） | `rgba(255,240,210, 0.10)` | `rgba(255,220,180, 0.18)` | `rgba(255,170,95, 0.18)` | `rgba(255,180,110, 0.40)` |

**禁止**：不透明实色气泡背景（破坏通透感）；接收气泡用纯白（太冷）；气泡上使用 bounce/spring 动效。

### 5.2 系统型插入块

对话流中的轻量信息卡，像一张纸片贴在对话里。

```css
.system-card {
  background: var(--bg-secondary);         /* #EFE9E1 */
  border: 1px dashed var(--border);        /* 虚线边框 */
  border-radius: var(--radius-md);         /* 14px */
  padding: 8px 14px;
  font-size: var(--text-sm);               /* 13px */
  color: var(--text-tertiary);
  text-align: center;
  margin: 4px 40px;                        /* 两侧收窄，与气泡区分 */
}
```

不加 icon 前缀，不加强调色背景。用文字本身传达信息。

示例文案：
- "已记住：你最近在准备法语考试"
- "已设提醒：明天下午 3 点交材料"
- "Connie 记起了上次你说的那件事"

### 5.3 卡片

```css
/* 标准卡片 —— "我们"页的概览、提醒列表 */
.card {
  background: var(--bg-elevated);          /* #FAF8F4 */
  border: 1px solid var(--border-light);   /* #EDE8E2 */
  border-radius: var(--radius-md);         /* 14px */
  padding: 16px 18px;
  box-shadow: var(--shadow-sm);
}

/* 紧凑卡片 —— 提醒条目、记忆条目 */
.card-compact {
  background: var(--bg-elevated);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);         /* 8px */
  padding: 12px 14px;
}
```

**禁止**：左侧 3px 强调色竖线作为卡片装饰（除非是"未解决"状态的警示需要）。

### 5.4 Badge / Tag

```css
.badge {
  background: var(--accent-subtle);        /* #EDE5DC */
  color: var(--accent);                    /* #7C6350 */
  border-radius: var(--radius-full);       /* 丸型 */
  padding: 3px 10px;
  font-size: var(--text-xs);               /* 11px */
  font-weight: 500;
  letter-spacing: 0.3px;
}

/* unresolved 状态的 badge */
.badge-warning {
  background: rgba(184,146,74,0.12);       /* warning 色的极浅版 */
  color: var(--warning);                   /* #B8924A */
}
```

### 5.5 按钮

```css
/* 主按钮 —— 确认、发送、重要操作 */
.btn-primary {
  background: var(--accent);               /* #7C6350 */
  color: #FAF8F4;
  border: none;
  border-radius: var(--radius-sm);         /* 8px */
  padding: 10px 20px;
  font-family: var(--font-body);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s ease;
}
.btn-primary:hover { opacity: 0.9; }
.btn-primary:active { opacity: 0.8; }

/* 轮廓按钮 —— 次要操作 */
.btn-outline {
  background: transparent;
  border: 1.5px solid var(--border);       /* #DDD6CE */
  color: var(--text-primary);
  border-radius: var(--radius-sm);
  padding: 10px 20px;
  font-family: var(--font-body);
  font-size: 14px;
  font-weight: 500;
}

/* 文字按钮 —— 最轻量的操作 */
.btn-text {
  background: none;
  border: none;
  color: var(--accent);
  font-size: var(--text-sm);
  font-weight: 500;
  padding: 4px 8px;
  cursor: pointer;
}

/* 图标按钮 —— 工具栏 */
.btn-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
```

**禁止**：按钮使用渐变 / 过亮强调色 / 投影过重。

### 5.6 底部导航栏

导航栏不再使用 `position: fixed`，而是通过 `RoomShell` 的 `nav` prop 渲染在氛围容器内部，自然融入背景渐变。

```css
/* 导航栏 —— 液态玻璃，位于 RoomShell 内 */
.r-nav {
  position: relative;
  z-index: 10;
  display: flex;
  padding: 6px 6px 28px;                  /* 底部留安全区 */
  border-top: 1px solid var(--nav-border); /* 动态色，跟随时段 */
  background: var(--nav-bg);               /* 如 rgba(255,250,235,0.22) */
  backdrop-filter: blur(11px) saturate(1.2);
  -webkit-backdrop-filter: blur(11px) saturate(1.2);
  box-shadow:
    0 -6px 18px -10px var(--warm-shadow),
    inset 0 1px 0 var(--ai-edge);
}

.r-nav-btn {
  flex: 1;
  background: transparent;
  border: none;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 8px 4px;
  color: var(--ink-soft);                  /* 非激活态：柔和墨色 */
  transition: color 240ms, transform 240ms;
}

.r-nav-btn.active {
  color: var(--ink);                       /* 激活态：跟随时段的主墨色 */
}
.r-nav-btn.active svg {
  filter: drop-shadow(0 0 6px var(--ink-accent));
}

.r-nav-btn span {
  font-size: 10px;
  letter-spacing: 0.12em;
}
```

**禁止**：
- active 状态用圆角填充块或气泡背景（太常见）
- 用填充 icon 替代 outline icon（视觉太重）

### 5.7 小纸条浮层

静默惊喜机制，本质是”我在你不在的时候，也在想你”。非强 push，而是打开界面的静静发现。

所有便签款式都采用液态玻璃风格——半透明背景 + `backdrop-filter: blur() saturate()`，透出氛围渐变。没有实色背景，没有物理配件（夹子、图钉已移除）。

5.7.1 便签款式库 (Note Variants)

便签支持 4 种外观，在设置页切换（`noteStyle` 参数），默认 `washi`：

**款式 1：和风胶带 (washi) — 默认**

顶部和底部各有一条半透明胶带，中间是玻璃纸。

- 顶部胶带：暖琥珀色 `linear-gradient(90deg, rgba(255,220,180,0.35) ... rgba(240,190,140,0.30))`，微旋转
- 底部胶带：冷青色 `linear-gradient(90deg, rgba(180,210,200,0.30) ... rgba(160,200,190,0.22))`
- 纸面：`background: rgba(255,250,235,0.12)` + `backdrop-filter: blur(12px) saturate(1.2)`
- 边框：`1px solid rgba(255,240,220,0.18)`，`border-radius: 4px`
- 整体微旋转 `rotate(-0.4deg)`

**款式 2：毛玻璃纸条 (frost)**

圆润的玻璃卡片，顶部有光线覆盖层。

- 背景：`rgba(255,250,235,0.10)` + `backdrop-filter: blur(16px) saturate(1.3)`
- 圆角：16px
- 顶部高光：`linear-gradient(180deg, rgba(255,250,235,0.18) 0%, transparent 100%)` + `mix-blend-mode: overlay`
- 阴影：`0 4px 16px -6px rgba(120,70,30,0.10), inset 0 1px 0 rgba(255,250,235,0.30)`

**款式 3：经典便签 (classic)**

居中胶带 + 玻璃纸。

- 胶带：`rgba(130,189,197,0.35)`（accent-pop 色），36×12px，居中，微旋转
- 纸面：同 washi 的玻璃纸面参数

**款式 4：撕纸条 (torn)**

底部锯齿裁切 + 玻璃。

- 背景：`rgba(255,250,235,0.14)` + `backdrop-filter: blur(10px) saturate(1.15)`
- 底部锯齿：`clipPath: polygon(...)` 模拟手撕边缘
- 圆角：3px，微旋转

5.7.2 便签文字与排版

```css
.note-text {
  font-family: var(--font-note), 'Noto Serif SC', serif;
  font-size: 14px;
  color: var(--ink);                       /* 跟随氛围时段 */
  line-height: 1.7;
}
```

5.7.3 交互动作

用户可以选择”留着”或”知道了”，按钮在右下角。

```css
/* “留着” —— 用 ink-accent 高亮 + 下划线 */
.note-action-keep {
  font-size: 12px;
  color: var(--ink-accent);
  border-bottom: 1px solid var(--ink-accent);
}

/* “知道了” —— 柔和墨色 */
.note-action-dismiss {
  font-size: 12px;
  color: var(--ink-soft);
}
```

### 5.8 关系计时器

```css
.day-counter {
  text-align: center;                      /* 或 left，看页面整体排版 */
  padding: var(--space-6) 0 var(--space-4);
}

.day-counter-number {
  font-family: var(--font-display);        /* Petrona */
  font-size: var(--text-2xl);              /* 32px */
  font-weight: 300;                        /* Light，轻量 */
  color: var(--text-deep);                 /* #574337, Wood */
  letter-spacing: 0.5px;
}

.day-counter-label {
  font-family: var(--font-body);
  font-size: var(--text-sm);               /* 13px */
  color: var(--text-tertiary);
  margin-top: 4px;
}
```

数字本身就是视觉主角，不需要任何装饰、不需要 icon、不需要背景色块。

### 5.9 输入区

```css
.input-area {
  position: fixed;
  bottom: 0;                               /* 在导航栏之上 */
  padding: 8px 16px env(safe-area-inset-bottom, 12px);
  background: var(--bg-primary);
  border-top: 1px solid var(--border-light);
}

.input-field {
  background: var(--bg-elevated);          /* #FAF8F4 */
  border: 1px solid var(--border-light);   /* #EDE8E2 */
  border-radius: var(--radius-md);         /* 14px */
  padding: 10px 14px;
  font-family: var(--font-body);
  font-size: var(--text-base);             /* 14.5px */
  color: var(--text-primary);
  width: 100%;
  outline: none;
}

.input-field:focus {
  border-color: var(--border);             /* 聚焦时边框稍深一点 */
}

.input-field::placeholder {
  color: var(--text-tertiary);
}

.send-button {
  background: var(--accent);
  color: #FAF8F4;
  border: none;
  border-radius: var(--radius-sm);
  padding: 8px 14px;
  font-size: 14px;
  font-weight: 500;
  /* 仅当输入框有文字时才显示 */
}
```

---

## 六、日记页专属视觉

日记页有独立的视觉调性，要比其他页面更"纸"一点。

定位：日记是关系沉淀，翻两个人的书信册。必须体现：静儿写的 vs Connie 写的、上锁机制、AI 解锁申请与痕迹。
视觉基调：Hobonichi 手账网格排版 + 极简打字机标签 + 物理纸感。

6.1 页面基底与排版
打破常规 UI 的纯色背景，引入克制的手账网格。采用左侧时间轴、右侧自由图文混排的布局。

CSS
/* 日记页整体底纹 */
.diary-page {
  background-color: #F3EDE5;
  /* 极淡的 4mm 物理网格映射 */
  background-image: 
    linear-gradient(rgba(114, 102, 92, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(114, 102, 92, 0.05) 1px, transparent 1px);
  background-size: 16px 16px; 
}

/* 日记卡片（纸张本体） */
.diary-card {
  background: #FAF7F2;
  border: 1px solid #E5DDD3;
  border-radius: 2px; /* 极小圆角，纸张感 */
  padding: 24px 22px;
  box-shadow: 0 1px 3px rgba(40,33,28,0.05),
              0 4px 16px rgba(40,33,28,0.04);
  position: relative; /* 为锁图标和标签定位 */
}
6.2 身份与状态元数据 (Metadata)
PRD 强调这是两人的书信册，必须清晰但安静地标明“谁写的”、“什么心情”。

CSS
/* 作者标签：唯一允许全大写的地方，像打字机敲上去的钢印 */
.diary-author-label {
  font-family: var(--font-body);
  font-size: 11px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--text-tertiary); /* 默认静儿的标签颜色 */
}

/* Connie 的作者标签：颜色稍微区分，用强调色系 */
.diary-author-label.connie {
  color: var(--accent); 
}

/* 情绪标签：不使用大色块，使用细边框框选的物理标签感 */
.diary-mood-tag {
  display: inline-block;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  border-radius: 2px; /* 趋近直角 */
  padding: 2px 6px;
  font-size: var(--text-xs);
  font-family: var(--font-body);
  background: transparent;
}

6.3 核心互动：上锁与解锁 (The Lock Mechanism)
这是 PRD 中最具差异化的设计。锁不应该像系统报错，而应该像日记本上的金属小锁扣。

CSS
/* 锁图标基础状态：安静地待在日记右上角 */
.diary-lock-icon {
  position: absolute;
  top: 24px;
  right: 22px;
  color: var(--text-tertiary);
  width: 16px;
  height: 16px;
}

/* AI 正在申请解锁中 —— 缓慢脉冲动效 (极其重要) */
/* 视觉感受：像这把锁在微微发热，或者有轻轻的叩门声 */
.diary-lock-icon.requesting {
  color: var(--warning); /* #B8924A 暖金色 */
  animation: lock-pulse 2.5s ease-in-out infinite;
}

@keyframes lock-pulse {
  0%, 100% { opacity: 0.4; transform: scale(1); filter: drop-shadow(0 0 0 rgba(184,146,74,0)); }
  50% { opacity: 1; transform: scale(1.05); filter: drop-shadow(0 0 6px rgba(184,146,74,0.4)); }
}

/* 解锁后的 AI 痕迹 (Unlock Traces) */
/* AI 阅读过或留下的悄悄话，像是在原日记旁边的手写批注 */
.diary-trace-annotation {
  font-family: 'Caveat', cursive;
  font-size: 15px;
  color: var(--accent); /* #7C6350 */
  border-left: 2px solid rgba(124, 99, 80, 0.2);
  padding-left: 12px;
  margin-top: 16px;
  font-style: normal; /* 覆盖可能继承的斜体 */
}
6.4 正文双人笔迹区分
CSS
/* 日记正文排版，大留白呼吸感 */
.diary-body {
  font-family: var(--font-display);        /* Petrona */
  font-size: 16px;
  font-weight: 400;
  line-height: 1.8;
  color: var(--text-primary);
  margin-top: 16px;
}

/* AI (Connie) 生成的日记 / 草稿 */
/* 使用斜体，并让颜色稍微变深，模拟另一种墨水 */
.diary-body.by-connie {
  font-style: italic;
  color: var(--text-deep);
}
6.5 视觉点缀：拍立得与纸胶带（按需使用）
如果日记带有图片，采用拍立得冲印质感，避免 UI 图片的廉价感。

CSS
.diary-photo-polaroid {
  background: #FFFFFF; 
  padding: 8px 8px 24px 8px; /* 底部留白用于可能的手写图注 */
  box-shadow: 0 2px 8px rgba(40,33,28,0.1);
  transform: rotate(-1.5deg); /* 极轻微歪斜 */
  margin: 16px 0;
  position: relative;
}

/* 照片胶带 */
.diary-photo-polaroid::before {
  content: '';
  position: absolute;
  top: -8px;
  left: 50%;
  transform: translateX(-50%) rotate(2deg);
  width: 32px;
  height: 12px;
  background: rgba(130, 189, 197, 0.4); /* --accent-pop 的半透明胶带 */
}

6.6 日记封面设计

每个人的日记有独立封面，在设置页可上传自定义封面图。默认提供两个预设：

**静儿封面（粉色拼布）**：
- 3×3+ 的拼布网格，每块用不同粉色调（`#F2D7D5`、`#EEC9D2`、`#F5E0D5`、`#F0C6D0`）
- 部分块有格纹（gingham）、圆点、碎花纹理
- 覆盖一层 45° 交叉缝线纹理（`opacity: 0.15`）
- 中央白色缎带标签，圆形，写日记标题
- 圆角：`4px 8px 8px 4px`（模拟装订侧）
- 阴影：`3px 4px 14px rgba(40,33,28,0.2)`

**Connie 封面（蓝灰星空）**：
- 底色 `#8B9EAE`（蓝灰）
- 散布 28+ 颗大小不一的星星（深色、金色、白色），带 `star-twinkle` 呼吸动画
- 12 颗小光点散落
- 中央半透明灰色圆标签
- 星星动画：`star-twinkle`（2.4-5.3s 呼吸闪烁）+ `star-drift`（缓慢漂移）

---

## 七、动效规范

### 原则

- 克制，不炫技
- 过渡要有"纸张翻动"或"轻轻落下"的物理感
- 不用 bounce easing
- 不用 spring 弹性

### 具体规范

```css
/* 页面切换 */
.page-enter {
  animation: page-in 220ms cubic-bezier(0.4, 0, 0.2, 1) forwards;
}
@keyframes page-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 卡片出现（列表中逐个出现） */
/* duration: 180ms per item, stagger: 40ms */
@keyframes card-in {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 模态框 / 底部抽屉 */
@keyframes drawer-in {
  from { transform: translateY(100%); }
  to   { transform: translateY(0); }
}
/* duration: 280ms, easing: cubic-bezier(0.32, 0.72, 0, 1) */

/* 小纸条浮入 */
@keyframes note-in {
  from { opacity: 0; transform: translateY(-16px); }
  to   { opacity: 1; transform: translateY(0); }
}
/* duration: 300ms, easing: ease-out */

/* 新消息气泡出现 */
@keyframes bubble-in {
  from { opacity: 0; transform: scale(0.92); }
  to   { opacity: 1; transform: scale(1); }
}
/* duration: 160ms */
/* transform-origin: 发送方 bottom right，接收方 bottom left */

/* 日记翻页（进入详情页） */
@keyframes diary-page-turn {
  from { opacity: 0.6; transform: perspective(800px) rotateY(8deg); }
  to   { opacity: 1;   transform: perspective(800px) rotateY(0); }
}
/* duration: 350ms, easing: ease-out */
```

---

## 八、图标规范

- 风格：**outline**，stroke-width: **1.5px**，不用填充图标
- 图标库：**Lucide Icons**（与 React 生态兼容：lucide-react）
- 导航图标大小：**24 × 24px**
- 工具栏图标大小：**20 × 20px**
- 内联文字图标：**16 × 16px**
- icon 颜色跟随所在组件的文字颜色（用 `currentColor`）

**禁止**：
- ❌ icon 旁边加背景色块
- ❌ icon 加圆形底座
- ❌ 给 icon 单独上色（除激活状态和语义色）
- ❌ 使用填充风格 icon
- ❌ 使用 emoji 替代 icon

---

## 九、可触摸区域

所有可交互元素的最小触摸区域：**44 × 44px**

即使按钮视觉上只有 20px，也要通过 padding 或 `min-height` / `min-width` 保证触摸区域达标。

---

## 十、明暗与时段适配

暗色模式不再是简单的手动开关。app 通过氛围系统自动在 7 个时段之间平滑过渡：

- **白天时段**（dawn / morning / afternoon）：浅色背景，深色墨字，GLASS_LIGHT 玻璃
- **过渡时段**（golden / dusk）：暖橘深色背景，浅色墨字，GLASS_WARM 玻璃
- **夜间时段**（night / late）：深色背景，暖米墨字，GLASS_DARK 玻璃

`RoomShell` 根据当前时间自动选择时段，并将对应的 ink / accent / glass 参数注入为 CSS Variables。所有组件只引用这些变量，无需单独适配明暗。

`tokens.css` 中的 `[data-theme="dark"]` 选择器仍保留，作为手动强制暗色的后备方案。但主要机制是氛围系统的自动时段切换。

设置页可通过 `remoire_time_override` 手动锁定到某个时段（如 `night`），覆盖自动检测。

---

## 十一、绝对禁止清单

给做开发的人（包括 Claude Code）的最终检查清单：

| # | 禁止 | 原因 |
|---|---|---|
| 1 | 纯色平面背景作为主页面底色 | 已改为时段氛围渐变，纯色缺乏呼吸感 |
| 2 | 渐变按钮 | AI Slop 典型特征 |
| 3 | emoji 主导视觉层级 | 降低 editorial 气质 |
| 4 | 左侧 3px 强调色竖线装饰卡片 | 通用 SaaS 套路 |
| 5 | 不透明实色卡片/气泡背景 | 遮住氛围渐变，液态玻璃要求通透 |
| 6 | DM Sans / Inter / Roboto / Cormorant Garamond / Instrument Sans 作为主字体 | 太通用或已在 impeccable 反射清单 |
| 7 | 紫色 / 蓝色高亮 | 与暖色系统不符 |
| 8 | 纯白 #FFFFFF 卡片背景 | 太冷 |
| 9 | 过度圆角 >24px 在非头像元素 | 太软，失去 editorial 感 |
| 10 | 六宫格 / 仪表盘布局 | 不适合关系型产品 |
| 11 | 底部导航 active 用气泡填充 | 通用手机 app 套路 |
| 12 | bounce / spring 动效 | 太弹，破坏安静感 |
| 13 | font-weight 700+ 在标题 | 太重 |
| 14 | rgba(0,0,0,...) 阴影（白天时段） | 太冷；夜间 GLASS_DARK 允许使用 |
| 15 | 大面积使用 accent-pop | 点缀色只能点缀 |

---

## 十二、可调参数系统 (Tweaks)

原型支持实时调节设计参数，方便静儿微调视觉效果。通过 `index.html` 的 `TWEAK_DEFAULTS` 对象配置，影响 CSS Variables 的缩放系数。

| 参数 | 默认值 | 范围 | 影响 |
|---|---|---|---|
| `fontScale` | 0.95 | 0.8–1.3 | 所有 `--text-*` 字号乘以此系数 |
| `radiusScale` | 0.8 | 0–2 | 所有 `--radius-*` 乘以此系数 |
| `shadowAlpha` | 1.5 | 0–3 | 阴影透明度系数 |
| `spacingScale` | 0.9 | 0.7–1.5 | 所有 `--space-*` 乘以此系数 |
| `bubbleSendBg` | `#7C6350` | 任意色值 | 发送气泡颜色（覆盖 CSS Variable） |
| `bubbleRecvBg` | `#ede9e3` | 任意色值 | 接收气泡颜色 |
| `accentColor` | `#7c6350` | 任意色值 | 主强调色 |
| `bgPrimary` | `#f6f2ed` | 任意色值 | 主背景色 |
| `paperTexture` | 4 | 0–20 | 纸张纹理强度 |
| `darkMode` | true | bool | 暗色模式开关 |
| `bubbleStyle` | default | default 等 | 气泡风格（实际渲染均为液态玻璃） |
| `noteStyle` | washi | washi / frost / classic / torn | 便签款式 |

此外，设置页支持上传自定义字体（ttf/otf）覆盖 5 个场景字体（聊天/小纸条/日记/共读/平行世界），以及上传自定义日记封面图。

---

## 十三、给做原型和写代码的人的最后一句话

这个 app 最难的不是功能，是气质。

每一个间距、每一个字重、每一句系统文案，都在回答同一个问题：
**这里有人在吗？**

答案应该是：有。一直都有。

---

*Con con × 静儿 · 2026.05.15*
