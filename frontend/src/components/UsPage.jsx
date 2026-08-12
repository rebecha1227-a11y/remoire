import { useState, useEffect, useCallback } from 'react';
import { SectionLabel, Stack } from './primitives';
import RoomShell from './RoomShell';
import MemoryPalace from './MemoryPalace';
import { apiErrorMessage, apiFetch, apiJsonFetch } from '../utils/api';

const DEFAULT_SPECIAL_DATES = {
  '01-01': '元旦',
  '02-14': '情人节',
  '04-12': '静儿生日',
  '05-20': '520',
  '12-25': '圣诞节',
  '03-29': '第一次聊天',
  '04-01': '在一起纪念日',
};

function CalendarDot({ type }) {
  const colors = {
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

function formatRemindTime(remindAt) {
  if (!remindAt) return '';
  const today = getBJToday();
  const todayStr = `${today.year}-${String(today.month + 1).padStart(2, '0')}-${String(today.day).padStart(2, '0')}`;
  const [datePart, timePart] = remindAt.split(' ');
  if (datePart === todayStr) return `今天 ${timePart || ''}`.trim();
  const tomorrow = new Date(today.year, today.month, today.day + 1);
  const tomorrowStr = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`;
  if (datePart === tomorrowStr) return `明天 ${timePart || ''}`.trim();
  return `${datePart.slice(5)} ${timePart || ''}`.trim();
}

function MiniCalendar({ reminderDays, onDaySelect, selectedDay, specialDates = {} }) {
  const today = getBJToday();
  const [viewYear, setViewYear] = useState(today.year);
  const [viewMonth, setViewMonth] = useState(today.month);

  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const firstDow = new Date(viewYear, viewMonth, 1).getDay();
  const offset = (firstDow + 6) % 7;

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
  const isSel = (d) => selectedDay && selectedDay.year === viewYear && selectedDay.month === viewMonth && selectedDay.day === d;
  const days = ['一', '二', '三', '四', '五', '六', '日'];

  function getDotType(d) {
    if (!d) return null;
    const mmdd = `${String(viewMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    if (specialDates[mmdd]) return 'special';
    const dateStr = `${viewYear}-${mmdd}`;
    if (reminderDays.has(dateStr)) return 'reminder';
    return null;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--ink, var(--text-primary))' }}>
          {viewYear} 年 {viewMonth + 1} 月
        </span>
        <div style={{ display: 'flex', gap: 4 }}>
          <button onClick={prevMonth} style={{ background: 'none', border: 'none', cursor: 'pointer', minWidth: 44, minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--ink-soft, var(--text-tertiary))" strokeWidth="1.5"><path d="M15 18l-6-6 6-6" /></svg>
          </button>
          <button onClick={nextMonth} style={{ background: 'none', border: 'none', cursor: 'pointer', minWidth: 44, minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--ink-soft, var(--text-tertiary))" strokeWidth="1.5"><path d="M9 18l6-6-6-6" /></svg>
          </button>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2, marginBottom: 4 }}>
        {days.map((d) => (
          <div key={d} style={{ textAlign: 'center', fontSize: 10, color: 'var(--ink-faint, var(--text-tertiary))', padding: '2px 0' }}>{d}</div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 2 }}>
        {cells.map((d, i) => {
          const sel = isSel(d);
          const tod = isToday(d);
          const dot = getDotType(d);
          return (
            <button type="button" key={i} disabled={!d} aria-label={d ? `选择 ${viewMonth + 1} 月 ${d} 日` : undefined} onClick={() => {
              if (!d) return;
              const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
              onDaySelect({ year: viewYear, month: viewMonth, day: d, dateStr });
            }} style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              minHeight: 44,
              borderRadius: 8,
              background: sel ? 'var(--ink-accent, var(--accent))' : 'transparent',
              boxShadow: (!sel && tod) ? 'inset 0 0 0 1.5px var(--ink-accent, var(--accent))' : 'none',
              color: sel ? '#FAF8F4'
                : tod ? 'var(--ink, var(--text-primary))'
                : d ? 'var(--ink, var(--text-primary))' : 'transparent',
              width: '100%', border: 'none', padding: 0, fontFamily: 'inherit',
              fontSize: 13, cursor: d ? 'pointer' : 'default',
              fontWeight: (sel || tod) ? 600 : 400,
            }}>
              {d || ''}
              {d && dot && !sel && <CalendarDot type={dot} />}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function DayDetail({ day, reminders, specialLabel }) {
  if (!day) return null;
  const dateLabel = `${day.month + 1} 月 ${day.day} 日`;
  return (
    <div style={{ marginTop: 10, padding: '10px 0 0', borderTop: '1px solid rgba(0,0,0,0.06)' }}>
      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink, var(--text-primary))', marginBottom: 6 }}>
        {dateLabel}
        {specialLabel && <span style={{ fontSize: 11, color: 'var(--accent-pop)', marginLeft: 8 }}>{specialLabel}</span>}
      </div>
      {reminders.length === 0 && !specialLabel && (
        <div style={{ fontSize: 12, color: 'var(--ink-faint, var(--text-tertiary))' }}>这天没有待办</div>
      )}
      {reminders.map(r => (
        <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: r.status === 'done' ? 'var(--success)' : 'var(--warning)',
            flexShrink: 0,
          }} />
          <span style={{
            fontSize: 13, color: 'var(--ink, var(--text-secondary))',
            textDecoration: r.status === 'done' ? 'line-through' : 'none',
            opacity: r.status === 'done' ? 0.5 : 1,
          }}>{r.content}</span>
          <span style={{ fontSize: 11, color: 'var(--ink-faint, var(--text-tertiary))', marginLeft: 'auto' }}>
            {r.remind_at?.split(' ')[1] || ''}
          </span>
        </div>
      ))}
    </div>
  );
}

function getDayCount() {
  const start = new Date(2026, 2, 29); // 2026-03-29 (month is 0-indexed)
  const bj = getBJToday();
  const today = new Date(bj.year, bj.month, bj.day);
  return Math.max(1, Math.floor((today - start) / 86400000) + 1);
}

export default function UsPage({ tweaks = {}, nav }) {
  const dayCount = getDayCount();
  const [showPalace, setShowPalace] = useState(false);
  const [memStats, setMemStats] = useState(null);
  const [latestMemory, setLatestMemory] = useState(null);
  const [reminders, setReminders] = useState([]);
  const [todayReminders, setTodayReminders] = useState([]);
  const [selectedDay, setSelectedDay] = useState(null);
  const [dayReminders, setDayReminders] = useState([]);
  const [reminderDays, setReminderDays] = useState(new Set());
  const [weather, setWeather] = useState(null);
  const [specialDates, setSpecialDates] = useState(DEFAULT_SPECIAL_DATES);
  const [status, setStatus] = useState('');

  const loadData = useCallback(async () => {
    setStatus('');
    try {
      const [statsRes, memRes, remRes, todayRes, weatherRes] = await Promise.all([
        apiFetch('/memory/stats'),
        apiFetch('/memory?limit=1&sort_by=created_at'),
        apiFetch('/reminder?status=&limit=50'),
        apiFetch('/reminder/today'),
        apiFetch('/weather'),
      ]);
      const sd = await statsRes.json();
      const md = await memRes.json();
      const rd = await remRes.json();
      const td = await todayRes.json();
      const wd = await weatherRes.json();
      if (!statsRes.ok || !sd.ok || !memRes.ok || !md.ok || !remRes.ok || !rd.ok || !todayRes.ok || !td.ok) {
        throw new Error('共同生活数据加载失败');
      }
      if (sd.ok) setMemStats(sd.data);
      if (wd.ok && wd.data) setWeather(wd.data);
      try {
        const dateRes = await apiFetch('/memory?memory_type=date&limit=50');
        const dd = await dateRes.json();
        if (dd.ok && dd.data?.items) {
          const merged = { ...DEFAULT_SPECIAL_DATES };
          dd.data.items.forEach(m => {
            const ed = m.event_date;
            if (ed) {
              const mmdd = ed.slice(5, 10);
              if (!merged[mmdd]) merged[mmdd] = m.content;
            }
          });
          setSpecialDates(merged);
        }
      } catch {
        setStatus('特殊日期暂时没有加载出来。');
      }
      const items = md.ok ? (md.data?.items || []) : [];
      if (items.length > 0) setLatestMemory(items[0]);
      const allReminders = (rd.ok ? (rd.data?.items || []) : []).filter(r => r.status !== 'dismissed');
      setReminders(allReminders);
      if (td.ok) setTodayReminders(td.data || []);
      const daySet = new Set();
      allReminders.forEach(r => {
        if (r.remind_at) daySet.add(r.remind_at.split(' ')[0]);
      });
      setReminderDays(daySet);
    } catch (error) {
      setStatus(error.message || '页面数据加载失败，请稍后重试。');
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData, showPalace]);

  async function handleDaySelect(day) {
    setSelectedDay(day);
    try {
      const res = await apiFetch(`/reminder/date/${day.dateStr}`);
      const data = await res.json();
      setDayReminders(data.ok ? (data.data || []) : []);
    } catch (e) { setDayReminders([]); }
  }

  async function toggleDone(id) {
    setStatus('');
    try {
      const res = await apiJsonFetch(`/reminder/${id}/done`, { method: 'POST', body: '{}' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '提醒更新失败'));
      setReminders(r => r.map(x => x.id === id ? { ...x, status: 'done' } : x));
      setTodayReminders(r => r.map(x => x.id === id ? { ...x, status: 'done' } : x));
      if (selectedDay) handleDaySelect(selectedDay);
    } catch (error) {
      setStatus(error.message || '提醒更新失败，请稍后重试。');
    }
  }

  async function dismissReminder(id) {
    setStatus('');
    try {
      const res = await apiJsonFetch(`/reminder/${id}/dismiss`, { method: 'POST', body: '{}' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '提醒忽略失败'));
      setReminders(r => r.filter(x => x.id !== id));
      setTodayReminders(r => r.filter(x => x.id !== id));
      if (selectedDay) handleDaySelect(selectedDay);
    } catch (error) {
      setStatus(error.message || '提醒忽略失败，请稍后重试。');
    }
  }

  if (showPalace) {
    return (
      <RoomShell nav={nav}>
        <div style={{ overflowY: 'auto', flex: 1, position: 'relative', zIndex: 10 }}>
          <MemoryPalace onBack={() => setShowPalace(false)} />
        </div>
      </RoomShell>
    );
  }

  const totalMem = memStats ? (memStats.core + memStats.long + memStats.short + memStats.consciousness) : null;
  const pendingCount = todayReminders.filter(r => r.status !== 'done').length;
  const selectedSpecial = selectedDay
    ? specialDates[`${String(selectedDay.month + 1).padStart(2, '0')}-${String(selectedDay.day).padStart(2, '0')}`]
    : null;

  return (
    <RoomShell nav={nav}>
    <div style={{ overflowY: 'auto', flex: 1, paddingBottom: 16, position: 'relative', zIndex: 10 }}>
      <div style={{
        textAlign: 'center',
        padding: 'var(--space-7) 0 var(--space-5)',
      }}>
        <div style={{
          fontFamily: "var(--font-display)",
          fontSize: 'var(--text-2xl)', fontWeight: 300,
          color: 'var(--text-deep)', letterSpacing: 0.5,
          textShadow: '0 1px 8px rgba(0,0,0,0.06)',
        }}>{dayCount}</div>
        <div style={{
          fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)',
          marginTop: 'var(--space-1)',
        }}>在一起的第 {dayCount} 天</div>
      </div>

      <div style={{ padding: '0 14px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {status && <div role="status" style={{ fontSize: 12, color: status.includes('失败') ? 'var(--danger)' : 'var(--ink-soft)', lineHeight: 1.6 }}>{status}</div>}
        <button type="button" className="r-glass" onClick={() => setShowPalace(true)} style={{
          width: '100%', border: 'none', textAlign: 'left', fontFamily: 'inherit',
          position: 'relative', animation: 'card-in 180ms 20ms ease both',
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 14,
        }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(124,99,80,0.10)',
          }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--ink-accent, var(--accent))" strokeWidth="1.5">
              <path d="M4 4h11a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3z"/><path d="M9 8h6M9 12h6"/>
            </svg>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 15, fontWeight: 500, color: 'var(--ink, var(--text-primary))' }}>记忆宫殿</span>
              {totalMem != null && (
                <span style={{ fontSize: 12, color: 'var(--ink-soft, var(--text-tertiary))' }}>{totalMem} 条记忆</span>
              )}
            </div>
            {latestMemory && (
              <div style={{
                fontSize: 12, color: 'var(--ink-faint, var(--text-tertiary))',
                marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {latestMemory.content}
              </div>
            )}
          </div>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--ink-soft, var(--text-tertiary))" strokeWidth="1.5" style={{ flexShrink: 0 }}>
            <path d="M9 18l6-6-6-6"/>
          </svg>
        </button>

        <div className="r-glass" style={{ position: 'relative', animation: 'card-in 180ms 60ms ease both' }}>
          <SectionLabel style={{ marginBottom: 'var(--space-4)' }}>今日概览</SectionLabel>
          <Stack gap="md">
            {weather && (
              <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--ink-accent, var(--accent))" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 3 }}>
                  <circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
                </svg>
                <span style={{ fontSize: 14, color: 'var(--ink, var(--text-secondary))', lineHeight: 1.8 }}>
                  {weather.text} {weather.temp}°C
                  {weather.feels_like && weather.feels_like !== weather.temp && <span style={{ color: 'var(--ink-soft, var(--text-tertiary))' }}> · 体感 {weather.feels_like}°C</span>}
                  {weather.humidity && <span style={{ color: 'var(--ink-soft, var(--text-tertiary))' }}> · 湿度 {weather.humidity}%</span>}
                </span>
              </div>
            )}
            {pendingCount > 0 ? (
              <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 3 }}>
                  <circle cx="12" cy="12" r="9" /><path d="M12 6v6l3 3" />
                </svg>
                <span style={{ fontSize: 14, color: 'var(--ink, var(--text-secondary))', lineHeight: 1.8 }}>
                  今天有 <strong style={{ color: 'var(--ink, var(--text-primary))', fontWeight: 500 }}>{pendingCount} 件事</strong> 需要处理
                </span>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--success, #6B9)" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 3 }}>
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><path d="M22 4L12 14.01l-3-3" />
                </svg>
                <span style={{ fontSize: 14, color: 'var(--ink-soft, var(--text-tertiary))', lineHeight: 1.8 }}>
                  今天没有待办，放松一下吧
                </span>
              </div>
            )}
            {latestMemory && (
              <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'flex-start' }}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--ink-accent, var(--accent))" strokeWidth="1.5" style={{ flexShrink: 0, marginTop: 3 }}>
                  <path d="M4 4h11a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3z"/><path d="M9 8h6"/>
                </svg>
                <span style={{ fontSize: 14, color: 'var(--ink, var(--text-secondary))', lineHeight: 1.8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  最新记忆：{latestMemory.content}
                </span>
              </div>
            )}
          </Stack>
        </div>

        <div className="r-glass" style={{ position: 'relative', animation: 'card-in 180ms 100ms ease both' }}>
          <SectionLabel>今日待办</SectionLabel>
          {todayReminders.length === 0 ? (
            <div style={{ padding: '12px 0', fontSize: 13, color: 'var(--ink-faint, var(--text-tertiary))' }}>
              今天没有待办，跟 Connie 聊天时说"提醒我…"就会自动创建
            </div>
          ) : (
            <div>
              {[...todayReminders].sort((a, b) => (a.status === 'done') - (b.status === 'done')).map((r, idx) => {
                const isDone = r.status === 'done';
                return (
                <div
                  key={r.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '10px 0',
                    borderBottom: idx < todayReminders.length - 1 ? '1px solid rgba(0,0,0,0.06)' : 'none',
                    opacity: isDone ? 0.45 : 1,
                    transition: 'opacity 0.3s ease',
                  }}
                >
                  <button type="button" aria-label={isDone ? '提醒已完成' : `完成提醒：${r.content}`} disabled={isDone} onClick={() => toggleDone(r.id)} style={{
                    width: 44, height: 44, borderRadius: '50%', padding: 0,
                    border: `1.5px solid ${isDone ? 'var(--ink-faint, #aaa)' : 'var(--warning)'}`,
                    background: isDone ? 'var(--ink-faint, #aaa)' : 'transparent',
                    flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: isDone ? 'default' : 'pointer',
                  }}>
                    {isDone && <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M5 12l5 5L19 7"/></svg>}
                  </button>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, color: 'var(--ink, var(--text-primary))', textDecoration: isDone ? 'line-through' : 'none' }}>{r.content}</div>
                    {!isDone && <div style={{ fontSize: 11, color: 'var(--warning)', marginTop: 2 }}>
                      {formatRemindTime(r.remind_at)}
                    </div>}
                  </div>
                  {!isDone && <button onClick={() => dismissReminder(r.id)} style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    fontSize: 11, color: 'var(--ink-faint, var(--text-tertiary))', padding: '4px 8px',
                  }}>忽略</button>}
                </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="r-glass" style={{ position: 'relative', animation: 'card-in 180ms 140ms ease both', marginBottom: 'var(--space-6)' }}>
          <SectionLabel>共同日历</SectionLabel>
          <MiniCalendar
            reminderDays={reminderDays}
            onDaySelect={handleDaySelect}
            selectedDay={selectedDay}
            specialDates={specialDates}
          />
          <DayDetail day={selectedDay} reminders={dayReminders} specialLabel={selectedSpecial} />
        </div>
      </div>
    </div>
    </RoomShell>
  );
}
