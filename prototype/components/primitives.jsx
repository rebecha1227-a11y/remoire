// ── Design Primitives ──
// 所有页面共享的基础组件。每个组件只负责"形态"，token 全部走 CSS 变量。
// 修改 token 在 tokens.css 里改一次，所有地方跟着变。

// ── Card ──
// 统一的卡片：bg-elevated + border-light + radius-md + shadow-sm
// padding 三档：sm / md / lg；不要再写 inline padding。
function Card({ children, padding = 'md', elevated = true, style = {}, onClick, className, ...rest }) {
  const padMap = {
    sm: 'var(--space-2) var(--space-3)',   //  8 12
    md: 'var(--space-3) var(--space-4)',   // 12 16
    lg: 'var(--space-4) var(--space-5)',   // 16 20
  };
  return (
    <div
      onClick={onClick}
      className={className}
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border-light)',
        borderRadius: 'var(--radius-md)',
        padding: padMap[padding] || padMap.md,
        boxShadow: elevated ? 'var(--shadow-sm)' : 'none',
        cursor: onClick ? 'pointer' : 'default',
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}

// ── SectionLabel ──
// 章节小灰标题（"今日概览""提醒与待办"那种）
function SectionLabel({ children, style = {} }) {
  return (
    <div
      style={{
        fontSize: 'var(--text-xs)',
        color: 'var(--text-tertiary)',
        letterSpacing: 0.5,
        fontWeight: 500,
        marginBottom: 'var(--space-2)',
        fontFamily: "var(--font-body)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// ── Pill ──
// 小标签胶囊。tone: neutral / accent / success / warning / pop
function Pill({ children, tone = 'neutral', style = {} }) {
  const tones = {
    neutral: { bg: 'var(--accent-subtle)', color: 'var(--text-secondary)' },
    accent:  { bg: 'var(--accent-subtle)', color: 'var(--accent)' },
    success: { bg: 'color-mix(in srgb, var(--success) 12%, transparent)', color: 'var(--success)' },
    warning: { bg: 'color-mix(in srgb, var(--warning) 12%, transparent)', color: 'var(--warning)' },
    pop:     { bg: 'color-mix(in srgb, var(--accent-pop) 15%, transparent)', color: 'var(--accent-pop)' },
  };
  const t = tones[tone] || tones.neutral;
  return (
    <span
      style={{
        background: t.bg,
        color: t.color,
        borderRadius: 'var(--radius-full)',
        padding: '2px var(--space-2)',
        fontSize: 'var(--text-xs)',
        fontWeight: 500,
        letterSpacing: 0.3,
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {children}
    </span>
  );
}

// ── IconButton ──
// 方形图标按钮，默认 36×36；用作输入栏旁的 + / 麦克风等
function IconButton({ children, onClick, size = 36, variant = 'outline', style = {}, ...rest }) {
  const variants = {
    outline: { background: 'var(--bg-elevated)', border: '1px solid var(--border)' },
    ghost:   { background: 'transparent', border: 'none' },
    accent:  { background: 'var(--accent)', border: 'none', color: 'var(--bg-elevated)' },
  };
  const v = variants[variant] || variants.outline;
  return (
    <button
      onClick={onClick}
      style={{
        width: size,
        height: size,
        borderRadius: 'var(--radius-sm)',
        ...v,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        flexShrink: 0,
        padding: 0,
        ...style,
      }}
      {...rest}
    >
      {children}
    </button>
  );
}

// ── Row ──
// 列表行：提醒、设置项、记忆条目共用
function Row({ children, onClick, urgent = false, dimmed = false, style = {}, ...rest }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--bg-elevated)',
        border: `1px solid ${urgent ? 'color-mix(in srgb, var(--warning) 30%, transparent)' : 'var(--border-light)'}`,
        borderRadius: 'var(--radius-sm)',
        padding: 'var(--space-3) var(--space-4)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        cursor: onClick ? 'pointer' : 'default',
        opacity: dimmed ? 0.5 : 1,
        transition: 'opacity 0.2s',
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}

// ── Stack ──
// 垂直堆叠；用 gap 而不是 margin
function Stack({ children, gap = 'sm', style = {}, ...rest }) {
  const gapMap = {
    xs: 'var(--space-1)',  //  4
    sm: 'var(--space-2)',  //  8
    md: 'var(--space-3)',  // 12
    lg: 'var(--space-5)',  // 20
    xl: 'var(--space-6)',  // 24
  };
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: gapMap[gap] || gapMap.sm,
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}

Object.assign(window, { Card, SectionLabel, Pill, IconButton, Row, Stack });
