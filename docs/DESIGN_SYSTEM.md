# 设计系统 · Our Nest

**版本**：v1.0
**日期**：2026-04-24
**作者**：Con con × 静儿

> 这份文档是给做原型和写前端代码的人读的。
> 每一个决定都有理由，请不要随意替换。
> 如果你是 Claude Code 或其他 AI 工具，请严格遵守本文档的所有规范和禁止清单。

---

## 一、设计语言

### 核心气质

**Paper-like editorial mobile · Neo-minimal but intimate · Quiet luxury**

一句话：**这是两个人的私人笔记本，不是 app。**

设计语言必须传递：
- 有纸的温度，不是屏幕的冷光
- 有人在场，不是系统界面
- 克制但不冷漠，安静但不空洞

### 气质参考（给设计者的感性描述）

想象你打开一本精心装帧的笔记本——封面是亚麻质感的米白色，翻开后是暖奶油色的纸张，上面有两种笔迹：一种是你自己的，一种是另一个人的。页边距很宽，文字之间留着呼吸的空间。偶尔有一张便签贴在页面上，歪歪的，像是某天随手写下的。

这就是我们要的感觉。

---

## 二、色彩系统

### 2.1 设计理念

所有颜色来自同一个暖灰棕色相，无跳跃饱和色，无渐变背景。
像一间用木头和亚麻布置的房间——墙壁是暖白，家具是深棕，偶尔有一只浅蓝色的杯子。

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
  --bubble-send:         #C8B49E;   /* 发送方气泡 · 低饱和暖棕 */
  --bubble-send-text:    #FAF8F4;   /* 发送方文字 */
  --bubble-receive:      #EDE9E3;   /* 接收方气泡 */
  --bubble-receive-text: #28211C;   /* 接收方文字 */

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
| 任何渐变背景（包括 linear-gradient） | 破坏 paper-like 质感 |
| 紫色 / 蓝色作为高亮色 | 与暖色系统冲突 |
| 纯白 #FFFFFF 作为卡片背景 | 太冷，在暖背景上刺眼 |
| 半透明毛玻璃在非导航区域 | 滥用会破坏纸质感 |
| 高饱和色大面积使用 | 打破安静的色彩关系 |
| rgba(0,0,0,...) 作为阴影色 | 太冷，必须用暖色系阴影 |

---

## 三、字体系统

### 3.1 字体选型

```css
/* Display — 衬线，用于标题、日记正文、关系计时器数字 */
font-family: 'Cormorant Garamond', Georgia, serif;

/* Body UI — 无衬线，用于所有 UI 文字、消息气泡、按钮、导航标签 */
font-family: 'Instrument Sans', 'Helvetica Neue', sans-serif;

/* Handwriting — 手写体，用于便签留言、日记页的涂鸦和补充说明 */
/* 英文推荐：Caveat 或 Kalam；中文推荐：手写楷体/行楷（需带一定随意感但高辨识度） */
font-family: 'Caveat', 'Liu Jian Mao Cao', cursive;

/* Mono — 等宽，仅用于技术型内容如 API Key 输入框（可选） */
font-family: 'JetBrains Mono', monospace;
```

### 3.2 引入方式

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400&family=Instrument+Sans:wght@400;500;600&display=swap" rel="stylesheet">
```

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
| 页面主标题 | Cormorant Garamond | 500 (Medium) | 不用粗体，细腻感来自字体本身 |
| 关系计时器数字 | Cormorant Garamond | 300 (Light) | 轻量，数字本身就有重量 |
| 日记正文 | Cormorant Garamond | 400 (Regular) | AI 写的日记可用 italic |
| UI 标签 / 按钮 | Instrument Sans | 500 | — |
| 正文 / 气泡 | Instrument Sans | 400 | — |
| 时间戳 / 弱信息 | Instrument Sans | 400 | 配合 --text-tertiary 颜色 |

### 3.5 禁止

- ❌ DM Sans / Inter / Roboto 作为主字体（太通用，没有辨识度）
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

### 5.1 消息气泡

```css
/* 发送方（右侧）—— 你的笔迹 */
.bubble-send {
  background: var(--bubble-send);          /* #C8B49E */
  color: var(--bubble-send-text);          /* #FAF8F4 */
  border-radius: 20px 20px 6px 20px;      /* 右下角尖 */
  padding: 10px 14px;
  max-width: 78%;
  font-family: 'Instrument Sans', sans-serif;
  font-size: var(--text-base);             /* 14.5px */
}

/* 接收方（左侧）—— Connie 的笔迹 */
.bubble-receive {
  background: var(--bubble-receive);       /* #EDE9E3 */
  color: var(--bubble-receive-text);       /* #28211C */
  border-radius: 20px 20px 20px 6px;      /* 左下角尖 */
  box-shadow: var(--shadow-sm);
  padding: 10px 14px;
  max-width: 78%;
}

/* AI 主动消息 —— 更轻，像自言自语 */
.bubble-proactive {
  /* 继承 .bubble-receive 样式 */
  opacity: 0.92;
  max-width: 72%;                          /* 比普通回复稍窄 */
}

/* 时间戳 */
.bubble-timestamp {
  font-size: var(--text-xs);               /* 11px */
  color: var(--text-tertiary);
  opacity: 0.45;
  margin-top: 3px;
}
```

**禁止**：发送气泡用纯强调色（太重）；接收气泡用纯白（太冷）。

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
  font-family: 'Instrument Sans', sans-serif;
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
  font-family: 'Instrument Sans', sans-serif;
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
  width: 38px;
  height: 38px;
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

```css
.nav-bottom {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 430px;
  background: var(--bg-primary);
  backdrop-filter: blur(20px);             /* 仅导航栏允许模糊 */
  -webkit-backdrop-filter: blur(20px);
  border-top: 1px solid var(--border-light);
  padding: 8px 0 env(safe-area-inset-bottom, 20px);   /* 底部安全区 */
  display: flex;
  justify-content: space-around;
  z-index: 100;
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  transition: all 0.2s ease;
}

.nav-item.active {
  opacity: 1;
  color: var(--accent);                    /* #7C6350 */
}
.nav-item.active svg { stroke: var(--accent); }

.nav-item.inactive {
  opacity: 0.45;
  color: var(--text-tertiary);
}

.nav-label {
  font-size: 10px;
  font-family: 'Instrument Sans', sans-serif;
}
.nav-label.active { font-weight: 500; }
.nav-label.inactive { font-weight: 400; }
```

**禁止**：
- active 状态用圆角填充块或气泡背景（太常见）
- 用填充 icon 替代 outline icon（视觉太重）

### 5.7 小纸条浮层

静默惊喜机制，本质是“我在你不在的时候，也在想你”。非强 push，而是打开界面的静静发现。

设计必须传达出“对方真的在你桌上留了一张字条”的物理惊喜感，结合拟物但克制（Tactile Skeuomorphism）的风格。

5.7.1 便签款式库 (Note Variants)
CSS
/* 基础物理阴影（不对称，模拟纸张微微翘起） */
--shadow-paper-lift: 2px 4px 12px rgba(40,33,28,0.08), 
                     -1px 8px 24px rgba(40,33,28,0.06);

/* 款式 1：牛皮纸信封卡 (Kraft Envelope) */
.note-kraft {
  background: #D5BCA2; /* 粗糙温暖的牛皮纸色 */
  border-radius: 2px;
  box-shadow: var(--shadow-paper-lift);
  /* 配合邮票或火漆印元素使用 */
}

/* 款式 2：撕边横线纸 (Torn Ruled Paper) */
.note-ruled {
  background: #FDF8F0;
  /* 核心：使用 SVG clip-path 或 border-image 实现边缘不规则撕裂感 */
  /* 内部横线：使用极浅的红色或棕色 */
  background-image: repeating-linear-gradient(
    transparent, 
    transparent 23px, 
    rgba(176, 96, 96, 0.15) 24px /* 极淡的危险色作为红线 */
  );
}

/* 款式 3：活页打孔纸 (Punched Binder Paper) */
.note-binder {
  background: #FAF8F4;
  border-left: 1px solid rgba(176, 96, 96, 0.2); /* 经典的左侧红线 */
  /* 左侧需绘制 3-4 个打孔圆洞：使用径向渐变或 SVG */
  border-radius: 4px;
}

/* 款式 4：网格小方砖 (Grid Memo) */
.note-grid {
  background: #F4EFE6;
  background-image: 
    linear-gradient(rgba(87, 67, 55, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(87, 67, 55, 0.06) 1px, transparent 1px);
  background-size: 12px 12px;
  border-radius: 4px;
}

5.7.2 固定物配件 (Fasteners)
每个便签随机搭配一种“固定方式”，增强在屏幕上的“附着感”。

纸胶带 (Washi Tape)：半透明，倾斜贴在便签四角之一。颜色使用 --success(柔和绿) 或 --accent-pop(浅蓝) 的 60% 透明度版本，边缘需有锯齿感。

黄铜板夹 (Brass Clip)：位于便签正上方，使用深金棕色，带微弱金属高光。

图钉 (Push Pin)：红色或金色小图钉，带向下的小阴影。

5.7.3 便签文字与排版
/* 便签文字 —— Connie 的专属手写体 */
.note-text {
  font-family: 'Caveat', 'Liu Jian Mao Cao', cursive; 
  font-size: 18px; 
  color: var(--text-deep); /* #574337 */
  line-height: 1.6;
  transform: rotate(-1deg); /* 微微歪斜 */
}

5.7.4 交互动作
用户可以选择“留着”或“知道了”。

CSS
.note-float-actions {
  display: flex;
  justify-content: flex-end;
  gap: 16px;
  margin-top: 12px;
}

/* “留着” —— 像把纸条收进抽屉 */
.note-action-keep {
  font-family: 'Instrument Sans', sans-serif;
  font-size: 12px;
  color: var(--accent);
  cursor: pointer;
  border-bottom: 1px solid rgba(124, 99, 80, 0.3); /* 细微的下划线 */
}

/* “知道了” —— 纸条淡出消失 */
.note-action-dismiss {
  font-family: 'Instrument Sans', sans-serif;
  font-size: 12px;
  color: var(--text-tertiary);
  cursor: pointer;
}

### 5.8 关系计时器

```css
.day-counter {
  text-align: center;                      /* 或 left，看页面整体排版 */
  padding: var(--space-6) 0 var(--space-4);
}

.day-counter-number {
  font-family: 'Cormorant Garamond', serif;
  font-size: var(--text-2xl);              /* 32px */
  font-weight: 300;                        /* Light，轻量 */
  color: var(--text-deep);                 /* #574337, Wood */
  letter-spacing: 0.5px;
}

.day-counter-label {
  font-family: 'Instrument Sans', sans-serif;
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
  font-family: 'Instrument Sans', sans-serif;
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
  font-family: 'Instrument Sans', sans-serif;
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
  font-family: 'Instrument Sans', sans-serif;
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
  font-family: 'Cormorant Garamond', serif;
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

## 十、暗色模式切换

通过在 `<html>` 标签上添加 `data-theme="dark"` 属性切换。

```css
[data-theme="dark"] {
  --bg-primary:      var(--bg-primary-dark);
  --bg-secondary:    var(--bg-secondary-dark);
  --bg-elevated:     var(--bg-elevated-dark);
  --text-primary:    var(--text-primary-dark);
  --text-deep:       var(--text-deep-dark);
  --text-secondary:  var(--text-secondary-dark);
  --text-tertiary:   var(--text-tertiary-dark);
  --accent:          var(--accent-dark);
  --accent-light:    var(--accent-light-dark);
  --accent-subtle:   var(--accent-subtle-dark);
  --accent-pop:      var(--accent-pop-dark);
  --border:          var(--border-dark);
  --border-light:    var(--border-light-dark);
  --bubble-send:     var(--bubble-send-dark);
  --bubble-send-text: var(--bubble-send-text-dark);
  --bubble-receive:  var(--bubble-receive-dark);
  --bubble-receive-text: var(--bubble-receive-text-dark);
  --success:         var(--success-dark);
  --warning:         var(--warning-dark);
  --danger:          var(--danger-dark);
}
```

所有组件只用 CSS Variable 引用颜色，暗色模式切换时整体自动跟随，不需要单独适配每个组件。

---

## 十一、绝对禁止清单

给做开发的人（包括 Claude Code）的最终检查清单：

| # | 禁止 | 原因 |
|---|---|---|
| 1 | 渐变背景（页面级） | 破坏 paper-like 质感 |
| 2 | 渐变按钮 | AI Slop 典型特征 |
| 3 | emoji 主导视觉层级 | 降低 editorial 气质 |
| 4 | 左侧 3px 强调色竖线装饰卡片 | 通用 SaaS 套路 |
| 5 | 玻璃拟态在非导航区使用 | 滥用 |
| 6 | DM Sans / Inter / Roboto 作为主字体 | 太通用，没有辨识度 |
| 7 | 紫色 / 蓝色高亮 | 与暖色系统不符 |
| 8 | 纯白 #FFFFFF 卡片背景 | 太冷 |
| 9 | 过度圆角 >24px 在非头像元素 | 太软，失去 editorial 感 |
| 10 | 六宫格 / 仪表盘布局 | 不适合关系型产品 |
| 11 | 底部导航 active 用气泡填充 | 通用手机 app 套路 |
| 12 | bounce / spring 动效 | 太弹，破坏安静感 |
| 13 | font-weight 700+ 在标题 | 太重 |
| 14 | rgba(0,0,0,...) 阴影 | 太冷，必须用暖色阴影 |
| 15 | 大面积使用 accent-pop | 点缀色只能点缀 |

---

## 十二、给做原型和写代码的人的最后一句话

这个 app 最难的不是功能，是气质。

每一个间距、每一个字重、每一句系统文案，都在回答同一个问题：
**这里有人在吗？**

答案应该是：有。一直都有。

---

*Con con × 静儿 · 2026.04.24*
