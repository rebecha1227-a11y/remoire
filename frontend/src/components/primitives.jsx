export function Card({ children, padding = 'md', elevated = true, style = {}, onClick, className, ...rest }) {
  const padMap = {
    sm: 'var(--space-2) var(--space-3)',
    md: 'var(--space-3) var(--space-4)',
    lg: 'var(--space-4) var(--space-5)',
  };
  const Element = onClick ? 'button' : 'div';
  return (
    <Element
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={className}
      style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border-light)',
        borderRadius: 'var(--radius-md)',
        padding: padMap[padding] || padMap.md,
        boxShadow: elevated ? 'var(--shadow-sm)' : 'none',
        cursor: onClick ? 'pointer' : 'default',
        width: onClick ? '100%' : undefined,
        textAlign: onClick ? 'left' : undefined,
        color: onClick ? 'inherit' : undefined,
        fontFamily: onClick ? 'var(--font-body)' : undefined,
        ...style,
      }}
      {...rest}
    >
      {children}
    </Element>
  );
}

export function SectionLabel({ children, style = {} }) {
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

export function Pill({ children, tone = 'neutral', style = {} }) {
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

export function IconButton({ children, onClick, size = 36, variant = 'outline', style = {}, ...rest }) {
  const variants = {
    outline: { background: 'var(--bg-elevated)', border: '1px solid var(--border-light)' },
    ghost:   { background: 'transparent', border: 'none' },
    accent:  { background: 'var(--accent)', border: 'none', color: 'var(--bg-elevated)' },
  };
  const v = variants[variant] || variants.outline;
  return (
    <button
      onClick={onClick}
      style={{
        width: Math.max(size, 44),
        height: Math.max(size, 44),
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

export function Row({ children, onClick, urgent = false, dimmed = false, style = {}, ...rest }) {
  const Element = onClick ? 'button' : 'div';
  return (
    <Element
      type={onClick ? 'button' : undefined}
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
        width: '100%',
        textAlign: onClick ? 'left' : undefined,
        color: 'inherit',
        fontFamily: 'var(--font-body)',
        opacity: dimmed ? 0.5 : 1,
        transition: 'opacity 0.2s',
        ...style,
      }}
      {...rest}
    >
      {children}
    </Element>
  );
}

export function Stack({ children, gap = 'sm', style = {}, ...rest }) {
  const gapMap = {
    xs: 'var(--space-1)',
    sm: 'var(--space-2)',
    md: 'var(--space-3)',
    lg: 'var(--space-5)',
    xl: 'var(--space-6)',
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
