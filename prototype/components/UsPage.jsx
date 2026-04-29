const MEMORIES = [
  { id: 1, type: 'fact',       text: '你在备考法语四级',       tag: '进行中'   },
  { id: 2, type: 'event',      text: '那天你第一次说想去京都', tag: '高频浮现' },
  { id: 3, type: 'unresolved', text: '答应了要给自己买那本书', tag: '未完成'   },
  { id: 4, type: 'date',       text: '你在备考法语四级',       tag: '特殊日期' },
];

const REMINDERS = [
  { id: 1, text: '交材料截止',   time: '今天 15:00', urgent: true,  done: false },
  { id: 2, text: '药记得吃',     time: '今天 20:00', urgent: false, done: false },
  { id: 3, text: '法语听力练习', time: '明天',       urgent: false, done: false },
  { id: 4, text: '回复导师邮件', time: '本周内',     urgent: false, done: true  },
];

const CALENDAR_EVENTS = {
  3: 'event', 7: 'reminder', 12: 'reminder', 15: 'special',
  18: 'event', 22: 'reminder', 28: 'special', 30: 'reminder',
};

const TAG_TONE = {
  '进行中':   'success',
  '高频浮现': 'accent',
  '未完成':   'warning',
  '特殊日期': 'pop',
};

function CalendarDot({ type }) {
  const colors = {
    event:    'var(--accent)',
    reminder: 'var(--warning)',
    special:  'var(--accent-pop)',
  };
  return (
    <div style={{
      width: 4, height: 4, borderRadius: '50%',
      background: colors[type] || 'var(--border)',
      margin: '1px auto 0',
    }} />
  );
}

function getBJToday() {
  const now = new Date();
  const bj = new Date(now.getTime() + (8 * 60 + now.getTimezoneOffset()) * 60000);
  return { year: bj.getFullYear(), month: bj.getMonth(), day: bj.getDate() };
}

function MiniCalendar() {
  const today = getBJToday();
  const [viewYear, setViewYear] = React.useState(today.year);
  const [viewMonth, setViewMonth] = React.useState(today.month);
  const [selected, setSelected] = React.useState(today.day);

  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const firstDow = new Date(viewYear, viewMonth, 1).getDay();
  const offset = (firstDow + 6) % 7; // 周一=0

  const cells = [];
  for (let i = 0; i < offset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const prevMonth = () => {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11); }
    else setViewMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0); }
    else setViewMonth(m => m + 1);
  };

  const isCurrentMonth = viewYear === today.year && viewMonth === today.month;
  const isToday = (d) => isCurrentMonth && d === today.day;
  const isSelected = (d) => isCurrentMonth && d === selected;
  const days = ['一', '二', '三', '四', '五', '六', '日'];

  return (
    <div>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: 'var(--space-3)',
      }}>
        <span style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-primary)' }}>
          {viewYear} 年 {viewMonth + 1} 月
        </span>
        <div style={{ display: 'flex', gap: 'var(--space-1)' }}>
          <button onClick={prevMonth} style={{ background: 'none', border: 'none', cursor: 'pointer', minWidth: 44, minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M15 18l-6-6 6-6" /></svg>
          </button>
          <button onClick={nextMonth} style={{ background: 'none', border: 'none', cursor: 'pointer', minWidth: 44, minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M9 18l6-6-6-6" /></svg>
          </button>
        </div>
      </div>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
        gap: 2, marginBottom: 'var(--space-1)',
      }}>
        {days.map((d) => (
          <div key={d} style={{
            textAlign: 'center', fontSize: 10,
            color: 'var(--text-tertiary)', padding: '2px 0',
          }}>{d}</div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2 }}>
        {cells.map((d, i) => (
          <div key={i} onClick={() => d && setSelected(d)} style={{
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            minHeight: 44,
            borderRadius: 'var(--radius-sm)',
            background: isSelected(d) ? 'var(--accent)' : 'transparent',
            color: isSelected(d) ? 'var(--bg-elevated)'
              : isToday(d) ? 'var(--accent)'
              : d ? 'var(--text-primary)' : 'transparent',
            fontSize: 12, cursor: d ? 'pointer' : 'default',
            fontWeight: (isSelected(d) || isToday(d)) ? 500 : 400,
          }}>
            {d || ''}
            {d && CALENDAR_EVENTS[d] && !isSelected(d) && <CalendarDot type={CALENDAR_EVENTS[d]} />}
          </div>
        ))}
      </div>
    </div>
  );
}

function UsPage({ tweaks = {} }) {
  const dayCount = tweaks.dayCount || 142;
  const [reminders, setReminders] = React.useState(REMINDERS);

  function toggleDone(id) {
    setReminders((r) => r.map((x) => x.id === id ? { ...x, done: !x.done } : x));
  }

  const sep = {
    marginTop: 'var(--space-7)',
    paddingTop: 'var(--space-5)',
    borderTop: '1px solid var(--border-light)',
  };

  return (
    <div style={{ overflowY: 'auto', height: '100%', paddingBottom: 88 }}>
      {/* Day counter */}
      <div style={{
        textAlign: 'center',
        padding: 'var(--space-7) 0 var(--space-5)',
        borderBottom: '1px solid var(--border-light)',
      }}>
        <div style={{
          fontFamily: "var(--font-display)",
          fontSize: 'var(--text-2xl)', fontWeight: 300,
          color: 'var(--text-deep)', letterSpacing: 0.5,
        }}>{dayCount}</div>
        <div style={{
          fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)',
          marginTop: 'var(--space-1)',
        }}>在一起的第 {dayCount} 天</div>
      </div>

      <div style={{ padding: '0 var(--space-5)' }}>

        {/* ── 今日概览：最高权重，字更大，上方留白最多 ── */}
        <div style={{ paddingTop: 'var(--space-7)', animation: 'card-in 180ms 40ms ease both' }}>
          <SectionLabel style={{ marginBottom: 'var(--space-4)' }}>今日概览</SectionLabel>
          <Stack gap="md">
            <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 3 }}>
                <circle cx="12" cy="12" r="9" /><path d="M12 6v6l3 3" />
              </svg>
              <span style={{ fontSize: 'var(--text-base)', color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                今天有 <strong style={{ color: 'var(--text-primary)', fontWeight: 500 }}>2 件事</strong> 需要处理
              </span>
            </div>
            <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent-pop)" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 3 }}>
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
              </svg>
              <span style={{ fontSize: 'var(--text-base)', color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                Connie 说他今天晚些会主动找你
              </span>
            </div>
            <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 3 }}>
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              <span style={{ fontSize: 'var(--text-base)', color: 'var(--text-tertiary)', lineHeight: 1.8 }}>
                你这几天睡得比上周少了一些
              </span>
            </div>
          </Stack>
        </div>

        {/* ── 提醒与待办：分隔线列表 ── */}
        <div style={{ ...sep, animation: 'card-in 180ms 80ms ease both' }}>
          <SectionLabel>提醒与待办</SectionLabel>
          <div>
            {reminders.map((r, idx) => (
              <div
                key={r.id}
                onClick={() => toggleDone(r.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-3)',
                  padding: 'var(--space-3) 0',
                  borderBottom: idx < reminders.length - 1 ? '1px solid var(--border-light)' : 'none',
                  cursor: 'pointer',
                  opacity: r.done ? 0.45 : 1,
                  transition: 'opacity 0.2s',
                }}
              >
                <div style={{
                  width: 16, height: 16, borderRadius: '50%',
                  border: `1.5px solid ${r.done ? 'var(--success)' : r.urgent ? 'var(--warning)' : 'var(--border)'}`,
                  background: r.done ? 'var(--success)' : 'transparent',
                  flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {r.done && <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="var(--bg-elevated)" strokeWidth="3"><path d="M5 13l4 4L19 7" /></svg>}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontSize: 'var(--text-sm)',
                    color: r.done ? 'var(--text-tertiary)' : 'var(--text-primary)',
                    textDecoration: r.done ? 'line-through' : 'none',
                  }}>{r.text}</div>
                  <div style={{
                    fontSize: 'var(--text-xs)',
                    color: r.urgent && !r.done ? 'var(--warning)' : 'var(--text-tertiary)',
                    marginTop: 1,
                  }}>{r.time}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── 共同日历 ── */}
        <div style={{ ...sep, animation: 'card-in 180ms 120ms ease both' }}>
          <SectionLabel>共同日历</SectionLabel>
          <MiniCalendar />
        </div>

        {/* ── 记忆摘要 ── */}
        <div style={{ ...sep, marginBottom: 'var(--space-6)', animation: 'card-in 180ms 160ms ease both' }}>
          <SectionLabel>记忆摘要</SectionLabel>
          <div>
            {MEMORIES.map((m, idx) => (
              <div
                key={m.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 'var(--space-3)',
                  padding: 'var(--space-3) 0',
                  borderBottom: idx < MEMORIES.length - 1 ? '1px solid var(--border-light)' : 'none',
                }}
              >
                <span style={{
                  fontSize: 'var(--text-sm)',
                  color: 'var(--text-secondary)',
                  lineHeight: 1.5,
                }}>{m.text}</span>
                <Pill tone={TAG_TONE[m.tag] || 'accent'}>{m.tag}</Pill>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}

Object.assign(window, { UsPage });
