import { useState, useEffect, useCallback, useRef } from 'react';
import { Pill, Stack } from './primitives';
import { apiErrorMessage, apiFetch, apiJsonFetch } from '../utils/api';

const LAYER_META = {
  core:          { label: '核心', desc: '关系基石', color: '#C47A5A' },
  long:          { label: '长期', desc: '重要的事', color: '#7C6350' },
  short:         { label: '短期', desc: '最近的事', color: '#82BDC5' },
  consciousness: { label: '意识', desc: 'Connie 内心', color: '#A0899A' },
};

const TYPE_LABELS = { fact: '事实', event: '事件', unresolved: '未完成', date: '日期' };
const PAGE_SIZE = 50;

function InlineStatus({ message, onRetry }) {
  if (!message) return null;
  return (
    <div role="alert" className="r-glass" style={{
      marginBottom: 12, padding: '10px 12px', color: 'var(--ink)', fontSize: 12,
      display: 'flex', alignItems: 'center', gap: 10,
    }}>
      <span style={{ flex: 1 }}>{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} style={{
          minHeight: 44, padding: '8px 12px', borderRadius: 8,
          border: '1px solid rgba(124,99,80,0.2)', background: 'transparent',
          color: 'var(--ink-accent)', cursor: 'pointer', fontFamily: 'var(--font-body)',
        }}>重试</button>
      )}
    </div>
  );
}

function BackButton({ onClick }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none',
      cursor: 'pointer', padding: '8px 4px', minHeight: 44, marginBottom: 8, color: 'var(--ink-soft)',
      fontSize: 14, fontFamily: 'var(--font-body)',
    }}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M15 18l-6-6 6-6"/></svg>
      返回
    </button>
  );
}

function getBJDate() {
  const now = new Date();
  const bj = new Date(now.getTime() + (8 * 60 + now.getTimezoneOffset()) * 60000);
  return { year: bj.getFullYear(), month: bj.getMonth() + 1, day: bj.getDate() };
}

function LayerCard({ layer, count, onClick }) {
  const meta = LAYER_META[layer];
  const icons = {
    core: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={meta.color} strokeWidth="1.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
    long: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={meta.color} strokeWidth="1.5"><path d="M4 4h11a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3z"/><path d="M9 8h6"/></svg>,
    short: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={meta.color} strokeWidth="1.5"><circle cx="12" cy="12" r="9"/><path d="M12 6v6l3 3"/></svg>,
    consciousness: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={meta.color} strokeWidth="1.5"><path d="M21 12a8 8 0 0 1-11.5 7.2L4 21l1.5-4.5A8 8 0 1 1 21 12z"/></svg>,
  };
  return (
    <button type="button" className="r-glass" onClick={onClick} aria-label={`${meta.label}记忆，${count} 条`} style={{
      position: 'relative', cursor: 'pointer',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '18px 12px', minHeight: 100, textAlign: 'center',
      transition: 'opacity 0.15s', width: '100%', fontFamily: 'var(--font-body)',
      border: '1px solid var(--nav-border, rgba(124,99,80,0.12))',
    }}>
      {icons[layer]}
      <div style={{ fontSize: 22, fontWeight: 400, color: 'var(--ink)', marginTop: 8, fontFamily: 'var(--font-display)' }}>
        {count}
      </div>
      <div style={{ fontSize: 13, color: 'var(--ink)', marginTop: 2, fontWeight: 500 }}>{meta.label}</div>
      <div style={{ fontSize: 11, color: 'var(--ink-soft)', marginTop: 1 }}>{meta.desc}</div>
    </button>
  );
}

function heatColor(count, maxCount) {
  if (!count) return 'rgba(124, 99, 80, 0.06)';
  const ratio = Math.min(count / Math.max(1, maxCount), 1);
  const alpha = 0.15 + ratio * 0.65;
  return `rgba(124, 99, 80, ${alpha})`;
}

function HeatLegend() {
  const steps = [0, 0.2, 0.4, 0.65, 0.8];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3, justifyContent: 'flex-end', marginTop: 10 }}>
      <span style={{ fontSize: 12, color: 'var(--ink)', marginRight: 3 }}>少</span>
      {steps.map((a, i) => (
        <div key={i} style={{
          width: 10, height: 10, borderRadius: 2,
          background: a === 0 ? 'rgba(124,99,80,0.06)' : `rgba(124,99,80,${a})`,
        }} />
      ))}
      <span style={{ fontSize: 12, color: 'var(--ink)', marginLeft: 3 }}>多</span>
    </div>
  );
}

function MonthGrid({ heatmap, year, month, onDayClick }) {
  const today = getBJDate();
  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDow = new Date(year, month - 1, 1).getDay();
  const offset = (firstDow + 6) % 7;

  const cells = [];
  for (let i = 0; i < offset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const maxCount = Math.max(1, ...Object.values(heatmap));
  const days = ['一', '二', '三', '四', '五', '六', '日'];

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 3, marginBottom: 4 }}>
        {days.map(d => (
          <div key={d} style={{ textAlign: 'center', fontSize: 10, color: 'var(--ink-faint)', padding: '2px 0' }}>{d}</div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 3 }}>
        {cells.map((d, i) => {
          const count = d ? (heatmap[d] || 0) : 0;
          const isToday = year === today.year && month === today.month && d === today.day;
          return (
            <button key={i} type="button" onClick={() => d && onDayClick(year, month, d)} disabled={!d}
              aria-label={d ? `${year}年${month}月${d}日，${count} 条记忆${isToday ? '，今天' : ''}` : undefined} style={{
              minHeight: 44, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, cursor: d ? 'pointer' : 'default',
              color: count > 0 ? '#FAF8F4' : d ? 'var(--ink-soft)' : 'transparent',
              background: d ? heatColor(count, maxCount) : 'transparent',
              boxShadow: isToday ? 'inset 0 0 0 1.5px var(--ink-accent)' : 'none',
              fontWeight: isToday ? 600 : 400,
              transition: 'background 0.2s',
              border: 0, fontFamily: 'var(--font-body)', padding: 0,
            }}>
              {d || ''}
            </button>
          );
        })}
      </div>
    </>
  );
}

function QuarterGrid({ quarterData, onDayClick }) {
  const today = getBJDate();
  const allCounts = [];
  quarterData.forEach(m => Object.values(m.heatmap).forEach(c => allCounts.push(c)));
  const maxCount = Math.max(1, ...allCounts);

  const dayLabels = ['一', '', '三', '', '五', '', '日'];

  const weeks = [];
  quarterData.forEach(({ year, month, heatmap }) => {
    const daysInMonth = new Date(year, month, 0).getDate();
    const firstDow = new Date(year, month - 1, 1).getDay();
    const offset = (firstDow + 6) % 7;

    let weekCol = [];
    for (let i = 0; i < offset; i++) weekCol.push(null);
    for (let d = 1; d <= daysInMonth; d++) {
      weekCol.push({ d, year, month, count: heatmap[d] || 0 });
      if (weekCol.length === 7) { weeks.push(weekCol); weekCol = []; }
    }
    if (weekCol.length > 0) {
      while (weekCol.length < 7) weekCol.push(null);
      weeks.push(weekCol);
    }
  });

  const monthLabels = [];
  let lastMonth = null;
  weeks.forEach((week, wi) => {
    const firstDay = week.find(c => c);
    if (firstDay && firstDay.month !== lastMonth) {
      monthLabels.push({ col: wi, label: `${firstDay.month}月` });
      lastMonth = firstDay.month;
    }
  });

  return (
    <div style={{ overflowX: 'auto', paddingBottom: 4 }}>
      <div style={{ display: 'inline-flex', flexDirection: 'column', gap: 3, minWidth: 'fit-content' }}>
        <div style={{ display: 'flex', gap: 3, paddingLeft: 20, marginBottom: 2 }}>
          {weeks.map((_, wi) => {
            const lbl = monthLabels.find(m => m.col === wi);
            return (
              <div key={wi} style={{ width: 44, fontSize: 10, color: 'var(--ink-faint)', textAlign: 'left', overflow: 'visible', whiteSpace: 'nowrap' }}>
                {lbl ? lbl.label : ''}
              </div>
            );
          })}
        </div>
        {[0, 1, 2, 3, 4, 5, 6].map(row => (
          <div key={row} style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
            <div style={{ width: 14, fontSize: 9, color: 'var(--ink-faint)', textAlign: 'right', flexShrink: 0 }}>
              {dayLabels[row]}
            </div>
            {weeks.map((week, wi) => {
              const cell = week[row];
              if (!cell) return <div key={wi} style={{ width: 44, height: 44, borderRadius: 5 }} />;
              const isToday = cell.year === today.year && cell.month === today.month && cell.d === today.day;
              return (
                <button key={wi} type="button" onClick={() => onDayClick(cell.year, cell.month, cell.d)}
                  aria-label={`${cell.year}年${cell.month}月${cell.d}日，${cell.count} 条记忆`} style={{
                  width: 44, height: 44, borderRadius: 5, cursor: 'pointer',
                  background: heatColor(cell.count, maxCount),
                  boxShadow: isToday ? 'inset 0 0 0 1.5px var(--ink-accent)' : 'none',
                  transition: 'background 0.2s',
                  border: 0, padding: 0,
                }} title={`${cell.month}/${cell.d}: ${cell.count} 条`} />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function HeatmapCalendar({ heatmapData, quarterData, viewMode, setViewMode, year, month, onChangeMonth, onDayClick }) {
  return (
    <div className="r-glass" style={{ position: 'relative' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--ink)' }}>在一起的日子</div>
          <div style={{ fontSize: 11, color: 'var(--ink-faint)', marginTop: 2 }}>颜色越深，那天记忆越多</div>
        </div>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <button onClick={() => setViewMode(viewMode === 'month' ? 'quarter' : 'month')} style={{
            minHeight: 44, padding: '8px 12px', borderRadius: 14, border: '1px solid rgba(0,0,0,0.06)',
            background: 'transparent', fontSize: 11, color: 'var(--ink-soft)',
            cursor: 'pointer', fontFamily: 'var(--font-body)',
          }}>{viewMode === 'month' ? '季度' : '月'}</button>
        </div>
      </div>

      {viewMode === 'month' && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '10px 0 8px' }}>
            <span style={{ fontSize: 13, color: 'var(--ink-soft)' }}>{year} 年 {month} 月</span>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => onChangeMonth(-1)} style={{ background: 'none', border: 'none', cursor: 'pointer', minWidth: 44, minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--ink-soft)" strokeWidth="1.5"><path d="M15 18l-6-6 6-6"/></svg>
              </button>
              <button onClick={() => onChangeMonth(1)} style={{ background: 'none', border: 'none', cursor: 'pointer', minWidth: 44, minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--ink-soft)" strokeWidth="1.5"><path d="M9 18l6-6-6-6"/></svg>
              </button>
            </div>
          </div>
          <MonthGrid heatmap={heatmapData} year={year} month={month} onDayClick={onDayClick} />
        </>
      )}

      {viewMode === 'quarter' && (
        <div style={{ marginTop: 10 }}>
          <QuarterGrid quarterData={quarterData} onDayClick={onDayClick} />
        </div>
      )}

      <HeatLegend />
    </div>
  );
}

function CandidateReview({ candidates, onAccept, onReject, busyId }) {
  if (candidates.length === 0) return null;
  return (
    <div className="r-glass" style={{ position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--ink-accent)" strokeWidth="1.5">
          <path d="M12 22c5.5 0 10-4.5 10-10S17.5 2 12 2 2 6.5 2 12s4.5 10 10 10z"/>
          <path d="M12 8v4M12 16h.01"/>
        </svg>
        <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--ink)' }}>
          待审核 · {candidates.length} 条
        </span>
      </div>
      <Stack gap="sm">
        {candidates.map(c => (
          <div key={c.id} style={{
            padding: '10px 0',
            borderBottom: '1px solid rgba(0,0,0,0.06)',
          }}>
            <div style={{ fontSize: 14, color: 'var(--ink)', lineHeight: 1.6, marginBottom: 6 }}>{c.content}</div>
            {c.tags && c.tags.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
                {c.tags.map((t, i) => <Pill key={i} tone="neutral">{t}</Pill>)}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: 'var(--ink-faint)', flex: 1 }}>
                {c.layer && LAYER_META[c.layer]?.label} · {TYPE_LABELS[c.memory_type] || c.memory_type}
                {c.confidence != null && ` · ${Math.round(c.confidence * 100)}%`}
              </span>
              <button onClick={() => onReject(c.id)} disabled={busyId === c.id} style={{
                minHeight: 44, padding: '8px 12px', borderRadius: 8,
                border: '1px solid rgba(0,0,0,0.08)', background: 'transparent',
                fontSize: 12, color: 'var(--ink-soft)', cursor: busyId === c.id ? 'default' : 'pointer',
                fontFamily: 'var(--font-body)', opacity: busyId === c.id ? 0.6 : 1,
              }}>不要</button>
              <button onClick={() => onAccept(c.id)} disabled={busyId === c.id} style={{
                minHeight: 44, padding: '8px 12px', borderRadius: 8,
                border: 'none', background: 'var(--ink-accent)',
                fontSize: 12, color: '#FAF8F4', cursor: busyId === c.id ? 'default' : 'pointer',
                fontWeight: 500, fontFamily: 'var(--font-body)', opacity: busyId === c.id ? 0.6 : 1,
              }}>{busyId === c.id ? '处理中…' : '记住'}</button>
            </div>
          </div>
        ))}
      </Stack>
    </div>
  );
}

function MemoryItem({ mem, onEdit, onDelete, onMove, onResolve }) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState(mem.content);
  const [saving, setSaving] = useState(false);
  const [related, setRelated] = useState(null);
  const raw = mem.tags || mem.tags_json;
  const tags = Array.isArray(raw) ? raw :
    (typeof raw === 'string' ? (() => { try { return JSON.parse(raw); } catch { return []; } })() : []);

  async function handleSave() {
    if (!editContent.trim() || editContent === mem.content) {
      setEditing(false);
      return;
    }
    setSaving(true);
    const ok = await onEdit(mem.id, { content: editContent.trim() });
    setSaving(false);
    if (ok) setEditing(false);
  }

  useEffect(() => {
    if (!expanded || related !== null) return;
    let active = true;
    apiFetch(`/memory/${mem.id}/related?limit=3`)
      .then(response => response.json())
      .then(data => {
        if (active) setRelated(data.ok && Array.isArray(data.data) ? data.data : []);
      })
      .catch(() => { if (active) setRelated([]); });
    return () => { active = false; };
  }, [expanded, mem.id, related]);

  return (
    <div style={{
      padding: '12px 0',
      borderBottom: '1px solid rgba(0,0,0,0.06)',
    }}>
      <div
        onClick={() => !editing && setExpanded(!expanded)}
        onKeyDown={event => {
          if (!editing && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault();
            setExpanded(!expanded);
          }
        }}
        role={editing ? undefined : 'button'}
        tabIndex={editing ? undefined : 0}
        aria-expanded={editing ? undefined : expanded}
        style={{ cursor: editing ? 'default' : 'pointer', borderRadius: 8 }}
      >
        {editing ? (
          <textarea
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', minHeight: 80, border: '1px solid rgba(0,0,0,0.1)',
              borderRadius: 8, padding: '8px 10px', fontSize: 14, color: 'var(--ink)',
              lineHeight: 1.6, fontFamily: 'var(--font-body)', background: 'rgba(0,0,0,0.02)',
              resize: 'vertical', boxSizing: 'border-box',
            }}
            autoFocus
          />
        ) : (
          <div style={{ fontSize: 14, color: 'var(--ink)', lineHeight: 1.6 }}>{mem.content}</div>
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6, alignItems: 'center' }}>
          {tags.map((t, i) => <Pill key={i} tone="neutral">{t}</Pill>)}
          <span style={{ fontSize: 11, color: 'var(--ink-faint)', marginLeft: 4 }}>
            {TYPE_LABELS[mem.memory_type] || mem.memory_type}
            {mem.event_date && ` · ${mem.event_date}`}
            {mem.unresolved && ' · 进行中'}
          </span>
        </div>
      </div>
      {editing && (
        <div style={{ marginTop: 10, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={() => { setEditing(false); setEditContent(mem.content); }} style={{
            minHeight: 44, padding: '8px 14px', borderRadius: 8, border: '1px solid rgba(0,0,0,0.08)',
            background: 'transparent', fontSize: 12, color: 'var(--ink-soft)',
            cursor: 'pointer', fontFamily: 'var(--font-body)',
          }}>取消</button>
          <button onClick={handleSave} disabled={saving} style={{
            minHeight: 44, padding: '8px 14px', borderRadius: 8, border: 'none',
            background: 'var(--ink-accent)', fontSize: 12, color: '#FAF8F4',
            cursor: saving ? 'default' : 'pointer', fontWeight: 500,
            fontFamily: 'var(--font-body)', opacity: saving ? 0.6 : 1,
          }}>{saving ? '保存中…' : '保存'}</button>
        </div>
      )}
      {expanded && !editing && (
        <div style={{ marginTop: 10 }}>
          {related && related.length > 0 && (
            <div style={{ marginBottom: 10, padding: '9px 10px', background: 'rgba(124,99,80,0.045)', borderRadius: 8 }}>
              <div style={{ marginBottom: 5, color: 'var(--ink-faint)', fontSize: 10, letterSpacing: '0.06em' }}>与它相连的记忆</div>
              {related.map(item => (
                <div key={item.id} style={{ color: 'var(--ink-soft)', fontSize: 11, lineHeight: 1.55 }}>
                  · {item.content}
                </div>
              ))}
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: 'var(--ink-faint)', lineHeight: '28px' }}>
            权重 {mem.weight != null ? (mem.weight * 100).toFixed(0) + '%' : '—'}
            {mem.pinned && ' · 已固定'}
          </span>
          <div style={{ flex: 1 }} />
          <button onClick={() => { setEditing(true); setEditContent(mem.content); }} style={{
            minHeight: 44, padding: '8px 10px', borderRadius: 6, border: '1px solid rgba(0,0,0,0.08)',
            background: 'transparent', fontSize: 11, color: 'var(--ink-accent)',
            cursor: 'pointer', fontFamily: 'var(--font-body)',
          }}>编辑</button>
          {mem.unresolved && (
            <button onClick={() => onResolve(mem.id)} style={{
              minHeight: 44, padding: '8px 10px', borderRadius: 6, border: '1px solid rgba(122,158,126,0.35)',
              background: 'transparent', fontSize: 11, color: 'var(--success)',
              cursor: 'pointer', fontFamily: 'var(--font-body)',
            }}>标记已解决</button>
          )}
          {Object.keys(LAYER_META).filter(l => l !== mem.layer).map(l => (
            <button key={l} onClick={() => onMove(mem.id, l)} style={{
              minHeight: 44, padding: '8px 10px', borderRadius: 6, border: '1px solid rgba(0,0,0,0.08)',
              background: 'transparent', fontSize: 11, color: 'var(--ink-soft)',
              cursor: 'pointer', fontFamily: 'var(--font-body)',
            }}>→ {LAYER_META[l].label}</button>
          ))}
          <button onClick={() => onDelete(mem.id)} style={{
            minHeight: 44, padding: '8px 10px', borderRadius: 6, border: '1px solid rgba(200,80,80,0.2)',
            background: 'transparent', fontSize: 11, color: '#c85050',
            cursor: 'pointer', fontFamily: 'var(--font-body)',
          }}>删除</button>
          </div>
        </div>
      )}
    </div>
  );
}

function LayerDetail({ layer, onBack }) {
  const meta = LAYER_META[layer];
  const [memories, setMemories] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState(null);
  const [sortBy, setSortBy] = useState('created_at');
  const requestId = useRef(0);

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const load = useCallback(async (offset = 0) => {
    const currentRequest = ++requestId.current;
    const append = offset > 0;
    if (append) setLoadingMore(true);
    else setLoading(true);
    setError('');
    const params = new URLSearchParams({ layer, sort_by: sortBy, limit: String(PAGE_SIZE), offset: String(offset) });
    if (search) params.set('search', search);
    if (typeFilter) params.set('memory_type', typeFilter);
    try {
      const res = await apiFetch(`/memory?${params}`);
      const data = await res.json();
      if (currentRequest !== requestId.current) return;
      if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '记忆加载失败'));
      const items = Array.isArray(data.data?.items) ? data.data.items : [];
      setMemories(previous => append ? [...previous, ...items] : items);
      setTotal(Number(data.data?.total) || 0);
    } catch (loadError) {
      if (currentRequest !== requestId.current) return;
      if (!append) {
        setMemories([]);
        setTotal(0);
      }
      setError(loadError.message || '记忆加载失败');
    } finally {
      if (currentRequest === requestId.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [layer, search, typeFilter, sortBy]);

  useEffect(() => {
    const timer = window.setTimeout(() => load(0), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function handleEdit(id, updates) {
    try {
      const res = await apiJsonFetch(`/memory/${id}`, {
        method: 'PUT', body: JSON.stringify(updates),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        setMemories(items => items.map(item => item.id === id ? data.data : item));
        return true;
      }
      setError(apiErrorMessage(data, '保存失败，请重试'));
    } catch (editError) {
      setError(editError.message || '保存失败，请重试');
    }
    return false;
  }

  async function handleMove(id, target) {
    try {
      const res = await apiJsonFetch(`/memory/${id}/move`, {
        method: 'POST', body: JSON.stringify({ target_layer: target }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '移动失败，请重试'));
      setMemories(m => m.filter(x => x.id !== id));
      setTotal(value => Math.max(0, value - 1));
    } catch (moveError) {
      setError(moveError.message || '移动失败，请重试');
    }
  }

  async function handleResolve(id) {
    try {
      const res = await apiFetch(`/memory/${id}/resolve`, { method: 'POST' });
      const data = await res.json();
      if (data.ok) {
        setMemories(items => items.map(item => item.id === id ? data.data : item));
      } else {
        setError(apiErrorMessage(data, '标记失败，请重试'));
      }
    } catch (resolveError) {
      setError(resolveError.message || '标记失败，请重试');
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('确认删除这条记忆？此操作无法撤销。')) return;
    try {
      const res = await apiFetch(`/memory/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '删除失败，请重试'));
      setMemories(m => m.filter(x => x.id !== id));
      setTotal(value => Math.max(0, value - 1));
    } catch (deleteError) {
      setError(deleteError.message || '删除失败，请重试');
    }
  }

  const typeOptions = ['fact', 'event', 'unresolved', 'date'];

  return (
    <div>
      <BackButton onClick={onBack} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: `${meta.color}18`,
        }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: meta.color }} />
        </div>
        <div>
          <div style={{ fontSize: 18, fontWeight: 500, color: 'var(--ink)', fontFamily: 'var(--font-display)' }}>{meta.label}记忆</div>
          <div style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{meta.desc} · {total} 条</div>
        </div>
      </div>

      <div className="r-glass" style={{ position: 'relative', marginBottom: 12 }}>
        <input
          type="search" value={searchInput} onChange={e => setSearchInput(e.target.value)}
          placeholder="搜索记忆…"
          aria-label={`搜索${meta.label}记忆`}
          style={{
            width: '100%', minHeight: 44, border: 'none', background: 'transparent',
            fontSize: 14, color: 'var(--ink)', fontFamily: 'var(--font-body)',
            padding: '0 2px',
          }}
        />
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
        <button onClick={() => setTypeFilter(null)} style={{
          minHeight: 44, padding: '8px 12px', borderRadius: 20, border: 'none', cursor: 'pointer',
          fontSize: 12, fontFamily: 'var(--font-body)',
          background: !typeFilter ? 'var(--ink-accent)' : 'rgba(0,0,0,0.04)',
          color: !typeFilter ? '#FAF8F4' : 'var(--ink-soft)',
        }}>全部</button>
        {typeOptions.map(t => (
          <button key={t} onClick={() => setTypeFilter(typeFilter === t ? null : t)} style={{
            minHeight: 44, padding: '8px 12px', borderRadius: 20, border: 'none', cursor: 'pointer',
            fontSize: 12, fontFamily: 'var(--font-body)',
            background: typeFilter === t ? 'var(--ink-accent)' : 'rgba(0,0,0,0.04)',
            color: typeFilter === t ? '#FAF8F4' : 'var(--ink-soft)',
          }}>{TYPE_LABELS[t]}</button>
        ))}
        <div style={{ flex: 1 }} />
        <button onClick={() => setSortBy(s => s === 'created_at' ? 'weight' : 'created_at')} style={{
          minHeight: 44, padding: '8px 10px', borderRadius: 20, border: '1px solid rgba(0,0,0,0.06)',
          background: 'transparent', fontSize: 11, color: 'var(--ink-soft)',
          cursor: 'pointer', fontFamily: 'var(--font-body)',
        }}>{sortBy === 'created_at' ? '切换按权重' : '切换按时间'}</button>
      </div>

      <InlineStatus message={error} onRetry={() => load(0)} />

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--ink-faint)', fontSize: 13 }}>加载中…</div>
      ) : memories.length === 0 ? (
        <div className="r-glass" style={{ position: 'relative', textAlign: 'center', padding: '30px 16px' }}>
          <div style={{ fontSize: 13, color: 'var(--ink-faint)' }}>
            {typeFilter || search ? '没有符合条件的记忆' : '这里还没有记忆'}
          </div>
          {typeFilter && (
            <button onClick={() => setTypeFilter(null)} style={{
              marginTop: 10, minHeight: 44, padding: '8px 14px', borderRadius: 20, border: '1px solid rgba(0,0,0,0.08)',
              background: 'transparent', fontSize: 12, color: 'var(--ink-soft)',
              cursor: 'pointer', fontFamily: 'var(--font-body)',
            }}>清除筛选</button>
          )}
        </div>
      ) : (
        <>
          <div className="r-glass" style={{ position: 'relative' }}>
            {memories.map(m => (
              <MemoryItem
                key={m.id}
                mem={m}
                onEdit={handleEdit}
                onMove={handleMove}
                onDelete={handleDelete}
                onResolve={handleResolve}
              />
            ))}
          </div>
          {memories.length < total && (
            <button type="button" onClick={() => load(memories.length)} disabled={loadingMore} style={{
              width: '100%', minHeight: 44, marginTop: 12, padding: '10px 14px', borderRadius: 10,
              border: '1px solid rgba(124,99,80,0.16)', background: 'transparent',
              color: 'var(--ink-accent)', cursor: loadingMore ? 'default' : 'pointer',
              fontFamily: 'var(--font-body)', opacity: loadingMore ? 0.65 : 1,
            }}>
              {loadingMore ? '加载中…' : `继续加载（已显示 ${memories.length} / ${total}）`}
            </button>
          )}
        </>
      )}
    </div>
  );
}

function DayMemories({ year, month, day, onBack }) {
  const [memories, setMemories] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

  const load = useCallback(async (offset = 0) => {
    const append = offset > 0;
    if (append) setLoadingMore(true);
    else setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        date_from: dateStr, date_to: dateStr, limit: String(PAGE_SIZE), offset: String(offset),
      });
      const res = await apiFetch(`/memory?${params}`);
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '这一天的记忆加载失败'));
      const items = Array.isArray(data.data?.items) ? data.data.items : [];
      setMemories(previous => append ? [...previous, ...items] : items);
      setTotal(Number(data.data?.total) || 0);
    } catch (loadError) {
      setError(loadError.message || '这一天的记忆加载失败');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [dateStr]);

  useEffect(() => {
    const timer = window.setTimeout(() => load(0), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <div>
      <BackButton onClick={onBack} />
      <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--ink)', marginBottom: 14, fontFamily: 'var(--font-display)' }}>
        {month} 月 {day} 日的记忆
      </div>
      <InlineStatus message={error} onRetry={() => load(0)} />
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--ink-faint)', fontSize: 13 }}>加载中…</div>
      ) : memories.length === 0 ? (
        <div className="r-glass" style={{ position: 'relative', textAlign: 'center', padding: '30px 16px' }}>
          <div style={{ fontSize: 13, color: 'var(--ink-faint)' }}>这一天没有记忆</div>
        </div>
      ) : (
        <>
          <div className="r-glass" style={{ position: 'relative' }}>
            {memories.map(m => {
              const rawT = m.tags || m.tags_json;
              const tags = Array.isArray(rawT) ? rawT :
                (typeof rawT === 'string' ? (() => { try { return JSON.parse(rawT); } catch { return []; } })() : []);
              return (
                <div key={m.id} style={{ padding: '10px 0', borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
                  <div style={{ fontSize: 14, color: 'var(--ink)', lineHeight: 1.6 }}>{m.content}</div>
                  <div style={{ display: 'flex', gap: 4, marginTop: 4, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Pill tone="neutral">{LAYER_META[m.layer]?.label || m.layer}</Pill>
                    {tags.map((t, i) => <Pill key={i} tone="neutral">{t}</Pill>)}
                  </div>
                </div>
              );
            })}
          </div>
          {memories.length < total && (
            <button type="button" onClick={() => load(memories.length)} disabled={loadingMore} style={{
              width: '100%', minHeight: 44, marginTop: 12, borderRadius: 10,
              border: '1px solid rgba(124,99,80,0.16)', background: 'transparent',
              color: 'var(--ink-accent)', fontFamily: 'var(--font-body)',
            }}>{loadingMore ? '加载中…' : `继续加载（${memories.length} / ${total}）`}</button>
          )}
        </>
      )}
    </div>
  );
}

export default function MemoryPalace({ onBack }) {
  const [view, setView] = useState('home');
  const [stats, setStats] = useState({ core: 0, long: 0, short: 0, consciousness: 0 });
  const [candidates, setCandidates] = useState([]);
  const [heatmap, setHeatmap] = useState({});
  const [quarterData, setQuarterData] = useState([]);
  const [heatViewMode, setHeatViewMode] = useState('month');
  const [selectedLayer, setSelectedLayer] = useState(null);
  const [selectedDay, setSelectedDay] = useState(null);
  const [homeError, setHomeError] = useState('');
  const [candidateBusyId, setCandidateBusyId] = useState(null);

  const bj = getBJDate();
  const [calYear, setCalYear] = useState(bj.year);
  const [calMonth, setCalMonth] = useState(bj.month);

  useEffect(() => {
    (async () => {
      setHomeError('');
      try {
        const [statsRes, candRes] = await Promise.all([
          apiFetch('/memory/stats'),
          apiFetch('/memory/candidates?status=pending&limit=50'),
        ]);
        const sd = await statsRes.json();
        const cd = await candRes.json();
        if (!statsRes.ok || !sd.ok) throw new Error(apiErrorMessage(sd, '记忆统计加载失败'));
        if (!candRes.ok || !cd.ok) throw new Error(apiErrorMessage(cd, '候选记忆加载失败'));
        setStats(sd.data);
        if (Array.isArray(cd.data)) setCandidates(cd.data);
      } catch (loadError) {
        setHomeError(loadError.message || '记忆宫殿加载失败');
      }
    })();
  }, []);

  function parseHeatmapArr(arr) {
    const map = {};
    if (!Array.isArray(arr)) return map;
    arr.forEach(({ date, count }) => {
      const day = parseInt(date.split('-')[2], 10);
      if (day) map[day] = count;
    });
    return map;
  }

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch(`/memory/heatmap?year=${calYear}&month=${calMonth}`);
        const data = await res.json();
        if (data.ok) setHeatmap(parseHeatmapArr(data.data));
      } catch (error) {
        setHomeError(error.message || '记忆日历加载失败');
      }
    })();
  }, [calYear, calMonth]);

  useEffect(() => {
    if (heatViewMode !== 'quarter') return;
    (async () => {
      const months = [];
      for (let i = 2; i >= 0; i--) {
        let m = calMonth - i, y = calYear;
        if (m < 1) { m += 12; y--; }
        months.push({ year: y, month: m });
      }
      try {
        const results = await Promise.all(
          months.map(({ year, month }) =>
            apiFetch(`/memory/heatmap?year=${year}&month=${month}`).then(r => r.json())
          )
        );
        setQuarterData(months.map((m, i) => ({
          ...m,
          heatmap: results[i].ok ? parseHeatmapArr(results[i].data) : {},
        })));
      } catch (error) {
        setQuarterData([]);
        setHomeError(error.message || '季度记忆日历加载失败');
      }
    })();
  }, [calYear, calMonth, heatViewMode]);

  function changeMonth(delta) {
    let m = calMonth + delta;
    let y = calYear;
    if (m < 1) { m = 12; y--; }
    if (m > 12) { m = 1; y++; }
    setCalYear(y);
    setCalMonth(m);
  }

  async function acceptCandidate(id) {
    setCandidateBusyId(id);
    setHomeError('');
    try {
      const res = await apiJsonFetch(`/memory/candidates/${id}/accept`, { method: 'POST', body: '{}' });
      const data = await res.json();
      if (res.ok && data.ok) {
        setCandidates(c => c.filter(x => x.id !== id));
        const statsRes = await apiFetch('/memory/stats');
        const sd = await statsRes.json();
        if (statsRes.ok && sd.ok) setStats(sd.data);
      } else {
        setHomeError(apiErrorMessage(data, '候选记忆接受失败'));
      }
    } catch (acceptError) {
      setHomeError(acceptError.message || '候选记忆接受失败');
    } finally {
      setCandidateBusyId(null);
    }
  }

  async function rejectCandidate(id) {
    setCandidateBusyId(id);
    setHomeError('');
    try {
      const res = await apiFetch(`/memory/candidates/${id}/reject`, { method: 'POST' });
      const data = await res.json();
      if (res.ok && data.ok) setCandidates(c => c.filter(x => x.id !== id));
      else setHomeError(apiErrorMessage(data, '候选记忆拒绝失败'));
    } catch (rejectError) {
      setHomeError(rejectError.message || '候选记忆拒绝失败');
    } finally {
      setCandidateBusyId(null);
    }
  }

  if (view === 'layer' && selectedLayer) {
    return (
      <div style={{ padding: '16px 14px 16px' }}>
        <LayerDetail layer={selectedLayer} onBack={() => { setView('home'); setSelectedLayer(null); }} />
      </div>
    );
  }

  if (view === 'day' && selectedDay) {
    return (
      <div style={{ padding: '16px 14px 16px' }}>
        <DayMemories year={selectedDay.year} month={selectedDay.month} day={selectedDay.day} onBack={() => { setView('home'); setSelectedDay(null); }} />
      </div>
    );
  }

  const totalMemories = stats.core + stats.long + stats.short + stats.consciousness;

  return (
    <div style={{ padding: '16px 14px 16px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      <BackButton onClick={onBack} />

      <InlineStatus message={homeError} />

      <div style={{ textAlign: 'center', marginBottom: 4 }}>
        <div style={{ fontSize: 28, fontWeight: 300, color: 'var(--ink)', fontFamily: 'var(--font-display)', letterSpacing: 0.5 }}>
          {totalMemories}
        </div>
        <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginTop: 2 }}>Connie 记得的一切</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {['core', 'long', 'short', 'consciousness'].map(layer => (
          <LayerCard key={layer} layer={layer} count={stats[layer] || 0}
            onClick={() => { setSelectedLayer(layer); setView('layer'); }} />
        ))}
      </div>

      <HeatmapCalendar
        heatmapData={heatmap} quarterData={quarterData}
        viewMode={heatViewMode} setViewMode={setHeatViewMode}
        year={calYear} month={calMonth}
        onChangeMonth={changeMonth}
        onDayClick={(y, m, d) => { setSelectedDay({ year: y, month: m, day: d }); setView('day'); }}
      />

      <CandidateReview candidates={candidates} onAccept={acceptCandidate} onReject={rejectCandidate} busyId={candidateBusyId} />
    </div>
  );
}
