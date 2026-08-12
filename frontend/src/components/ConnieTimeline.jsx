import { useState, useEffect, useMemo } from "react";
import { apiFetch } from "../utils/api";

function toBJ(raw) {
  const d = new Date(raw.endsWith('Z') || raw.includes('+') ? raw : raw + '+08:00');
  return new Date(d.getTime() + 8 * 3600000);
}

function formatTime(raw) {
  const bj = toBJ(raw);
  return `${String(bj.getUTCHours()).padStart(2,'0')}:${String(bj.getUTCMinutes()).padStart(2,'0')}`;
}

const ACTION_LABELS = {
  message: '发了消息',
  diary: '写了日记',
  explore: '上网逛了逛',
  memory_review: '回顾记忆',
  note: '留了纸条',
  breath: '更新了状态',
  none: '想了想事情',
};

const ACTION_ICONS = {
  message: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  ),
  diary: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M4 4h11a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3z"/><path d="M9 8h6"/>
    </svg>
  ),
  explore: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
  ),
  memory_review: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M9.663 17h4.674M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 12 18.469c-.542 0-1.06.19-1.477.53l-.511.46"/>
    </svg>
  ),
  note: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>
    </svg>
  ),
  breath: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/>
    </svg>
  ),
  none: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M17 18a5 5 0 0 0-10 0"/><line x1="12" y1="9" x2="12" y2="9.01"/>
    </svg>
  ),
};

function MiniCalendar({ selectedDate, onSelect, activeDates, onMonthChange }) {
  const [viewMonth, setViewMonth] = useState(() => {
    const d = selectedDate ? new Date(selectedDate + 'T00:00:00+08:00') : new Date();
    return { year: d.getFullYear(), month: d.getMonth() };
  });

  const days = useMemo(() => {
    const first = new Date(viewMonth.year, viewMonth.month, 1);
    const startDay = (first.getDay() + 6) % 7;
    const daysInMonth = new Date(viewMonth.year, viewMonth.month + 1, 0).getDate();
    const cells = [];
    for (let i = 0; i < startDay; i++) cells.push(null);
    for (let d = 1; d <= daysInMonth; d++) cells.push(d);
    return cells;
  }, [viewMonth]);

  const monthStr = `${viewMonth.year}-${String(viewMonth.month + 1).padStart(2, '0')}`;
  const activeSet = new Set(activeDates || []);

  useEffect(() => {
    onMonthChange?.(monthStr);
  }, [monthStr, onMonthChange]);

  function prevMonth() {
    setViewMonth(v => v.month === 0 ? { year: v.year - 1, month: 11 } : { ...v, month: v.month - 1 });
  }
  function nextMonth() {
    setViewMonth(v => v.month === 11 ? { year: v.year + 1, month: 0 } : { ...v, month: v.month + 1 });
  }

  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <button onClick={prevMonth} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink-soft, var(--text-tertiary))', padding: 8 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M15 18l-6-6 6-6"/></svg>
        </button>
        <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--ink, var(--text-primary))', fontFamily: 'var(--font-body)' }}>
          {viewMonth.year}年{viewMonth.month + 1}月
        </span>
        <button onClick={nextMonth} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink-soft, var(--text-tertiary))', padding: 8 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M9 18l6-6-6-6"/></svg>
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2, textAlign: 'center' }}>
        {['一', '二', '三', '四', '五', '六', '日'].map(w => (
          <div key={w} style={{ fontSize: 11, color: 'var(--ink-faint, var(--text-tertiary))', padding: '4px 0' }}>{w}</div>
        ))}
        {days.map((d, i) => {
          if (d === null) return <div key={`e${i}`} />;
          const dateStr = `${monthStr}-${String(d).padStart(2, '0')}`;
          const isActive = activeSet.has(dateStr);
          const isSelected = dateStr === selectedDate;
          const isToday = dateStr === todayStr;
          return (
            <button
              key={i}
              onClick={() => onSelect(dateStr)}
              style={{
                minWidth: 44, minHeight: 44, margin: '0 auto',
                borderRadius: 8, border: 'none',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column',
                background: isSelected ? 'var(--ink-accent, var(--accent))' : 'transparent',
                color: isSelected ? '#fff' : isActive ? 'var(--ink, var(--text-primary))' : 'var(--ink-faint, var(--text-tertiary))',
                fontWeight: isToday ? 600 : 400,
                fontSize: 13, cursor: 'pointer',
                fontFamily: 'var(--font-body)',
                position: 'relative',
                opacity: isActive ? 1 : 0.55,
              }}
            >
              {d}
              {isActive && !isSelected && (
                <span style={{
                  width: 4, height: 4, borderRadius: '50%',
                  marginTop: 2,
                  background: 'var(--ink-accent, var(--accent))',
                }} />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}


function TimelineItem({ log }) {
  const [expanded, setExpanded] = useState(false);
  const icon = ACTION_ICONS[log.action_type] || ACTION_ICONS.none;
  const label = log.action_summary || ACTION_LABELS[log.action_type] || log.action_type;

  return (
    <div style={{ display: 'flex', gap: 12, paddingBottom: 16, position: 'relative' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
        <div style={{
          width: 28, height: 28, borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(124,99,80,0.08)',
          color: 'var(--ink-accent, var(--accent))',
        }}>
          {icon}
        </div>
        <div style={{ flex: 1, width: 1, background: 'var(--border-light, rgba(0,0,0,0.06))', marginTop: 4 }} />
      </div>
      <div style={{ flex: 1, minWidth: 0, paddingTop: 2 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 12, color: 'var(--ink-faint, var(--text-tertiary))', fontFamily: 'var(--font-body)' }}>
            {formatTime(log.created_at)}
          </span>
          <span style={{ fontSize: 13, color: 'var(--ink, var(--text-primary))', fontFamily: 'var(--font-body)' }}>
            {label}
          </span>
        </div>
        {log.thinking && (
          <div
            onClick={() => setExpanded(!expanded)}
            style={{
              fontSize: 12, color: 'var(--ink-soft, var(--text-secondary))',
              fontFamily: 'var(--font-body)', lineHeight: 1.6,
              cursor: 'pointer',
              background: 'rgba(124,99,80,0.04)',
              borderRadius: 8, padding: '6px 10px', marginTop: 4,
              maxHeight: expanded ? 'none' : 60, overflow: 'hidden',
              position: 'relative',
            }}
          >
            <span style={{ fontStyle: 'italic', opacity: 0.7, marginRight: 4 }}>内心独白</span>
            {log.thinking.slice(0, expanded ? undefined : 120)}
            {!expanded && log.thinking.length > 120 && '...'}
          </div>
        )}
      </div>
    </div>
  );
}


export default function ConnieTimeline({ onBack }) {
  const [selectedDate, setSelectedDate] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
  });
  const [activeDates, setActiveDates] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [calendarMonth, setCalendarMonth] = useState(() => selectedDate.slice(0, 7));

  useEffect(() => {
    if (!calendarMonth) return;
    setError('');
    apiFetch(`/autonomous/dates?month=${calendarMonth}`)
      .then(async r => {
        const data = await r.json().catch(() => ({}));
        if (!r.ok || !data.ok) throw new Error(data.detail || data.error || '活动日期加载失败');
        setActiveDates(data.data || []);
      })
      .catch(err => setError(err.message || '活动日期加载失败'));
  }, [calendarMonth]);

  useEffect(() => {
    if (!selectedDate) return;
    setLoading(true);
    setError('');
    apiFetch(`/autonomous/logs?date=${selectedDate}`)
      .then(async r => {
        const data = await r.json().catch(() => ({}));
        if (!r.ok || !data.ok) throw new Error(data.detail || data.error || '生活日志加载失败');
        setLogs(data.data || []);
      })
      .catch(err => {
        setLogs([]);
        setError(err.message || '生活日志加载失败');
      })
      .finally(() => setLoading(false));
  }, [selectedDate]);

  function handleSelectDate(dateStr) {
    setSelectedDate(dateStr);
    setCalendarMonth(dateStr.slice(0, 7));
  }

  return (
    <div style={{
      flex: 1,
      minHeight: 0,
      background: 'transparent',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
      position: 'relative',
      zIndex: 10,
    }}>
      <div style={{
        padding: '16px 14px 8px',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <button onClick={onBack} style={{
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--ink-soft, var(--text-tertiary))', padding: 8,
          display: 'flex', alignItems: 'center',
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
        </button>
        <div>
          <div style={{
            fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 300,
            color: 'var(--ink, var(--text-deep))',
          }}>Connie的生活日志和碎碎念</div>
          <div style={{ fontSize: 11, color: 'var(--ink-faint, var(--text-tertiary))' }}>他自己醒来、游荡、想起你的记录</div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 14px 100px' }}>
        <div className="r-glass" style={{ padding: '14px 12px', marginBottom: 12 }}>
          <MiniCalendar
            selectedDate={selectedDate}
            onSelect={handleSelectDate}
            activeDates={activeDates}
            onMonthChange={setCalendarMonth}
          />
        </div>

        {error && (
          <div role="alert" style={{ padding: '10px 12px', marginBottom: 10, color: 'var(--danger)', fontSize: 12, lineHeight: 1.6 }}>
            {error}
          </div>
        )}
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--ink-faint, var(--text-tertiary))', fontSize: 13 }}>
            加载中...
          </div>
        ) : logs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--ink-faint, var(--text-tertiary))', fontSize: 13, fontFamily: 'var(--font-body)' }}>
            这天 Connie 还没有活动记录
          </div>
        ) : (
          <div className="r-glass" style={{ padding: '16px 14px 4px' }}>
            {logs.map(log => (
              <TimelineItem key={log.id} log={log} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
