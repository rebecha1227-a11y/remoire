import { useState, useEffect, useCallback } from 'react';
import { Pill, Stack } from './primitives';
import { apiFetch, apiJsonFetch } from '../utils/api';

const LAYER_META = {
  core:          { label: '核心', desc: '关系基石', color: '#C47A5A' },
  long:          { label: '长期', desc: '重要的事', color: '#7C6350' },
  short:         { label: '短期', desc: '最近的事', color: '#82BDC5' },
  consciousness: { label: '意识', desc: 'Connie 内心', color: '#A0899A' },
};

const TYPE_LABELS = { fact: '事实', event: '事件', unresolved: '未完成', date: '日期' };

function BackButton({ onClick }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none',
      cursor: 'pointer', padding: '4px 0', marginBottom: 12, color: 'var(--ink-soft)',
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
    <div className="r-glass" onClick={onClick} style={{
      position: 'relative', cursor: 'pointer',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '18px 12px', minHeight: 100, textAlign: 'center',
      transition: 'opacity 0.15s',
    }}>
      {icons[layer]}
      <div style={{ fontSize: 22, fontWeight: 400, color: 'var(--ink)', marginTop: 8, fontFamily: 'var(--font-display)' }}>
        {count}
      </div>
      <div style={{ fontSize: 13, color: 'var(--ink)', marginTop: 2, fontWeight: 500 }}>{meta.label}</div>
      <div style={{ fontSize: 11, color: 'var(--ink-soft)', marginTop: 1 }}>{meta.desc}</div>
    </div>
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
            <div key={i} onClick={() => d && onDayClick(year, month, d)} style={{
              aspectRatio: '1', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, cursor: d ? 'pointer' : 'default',
              color: count > 0 ? '#FAF8F4' : d ? 'var(--ink-soft)' : 'transparent',
              background: d ? heatColor(count, maxCount) : 'transparent',
              boxShadow: isToday ? 'inset 0 0 0 1.5px var(--ink-accent)' : 'none',
              fontWeight: isToday ? 600 : 400,
              transition: 'background 0.2s',
            }}>
              {d || ''}
            </div>
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
              <div key={wi} style={{ width: 11, fontSize: 10, color: 'var(--ink-faint)', textAlign: 'left', overflow: 'visible', whiteSpace: 'nowrap' }}>
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
              if (!cell) return <div key={wi} style={{ width: 11, height: 11, borderRadius: 2 }} />;
              const isToday = cell.year === today.year && cell.month === today.month && cell.d === today.day;
              return (
                <div key={wi} onClick={() => onDayClick(cell.year, cell.month, cell.d)} style={{
                  width: 11, height: 11, borderRadius: 2, cursor: 'pointer',
                  background: heatColor(cell.count, maxCount),
                  boxShadow: isToday ? 'inset 0 0 0 1.5px var(--ink-accent)' : 'none',
                  transition: 'background 0.2s',
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
            padding: '4px 10px', borderRadius: 14, border: '1px solid rgba(0,0,0,0.06)',
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

function CandidateReview({ candidates, onAccept, onReject }) {
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
              <button onClick={() => onReject(c.id)} style={{
                padding: '5px 12px', borderRadius: 8,
                border: '1px solid rgba(0,0,0,0.08)', background: 'transparent',
                fontSize: 12, color: 'var(--ink-soft)', cursor: 'pointer', fontFamily: 'var(--font-body)',
              }}>不要</button>
              <button onClick={() => onAccept(c.id)} style={{
                padding: '5px 12px', borderRadius: 8,
                border: 'none', background: 'var(--ink-accent)',
                fontSize: 12, color: '#FAF8F4', cursor: 'pointer', fontWeight: 500, fontFamily: 'var(--font-body)',
              }}>记住</button>
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

  return (
    <div style={{
      padding: '12px 0',
      borderBottom: '1px solid rgba(0,0,0,0.06)',
    }}>
      <div onClick={() => !editing && setExpanded(!expanded)} style={{ cursor: editing ? 'default' : 'pointer' }}>
        {editing ? (
          <textarea
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', minHeight: 80, border: '1px solid rgba(0,0,0,0.1)',
              borderRadius: 8, padding: '8px 10px', fontSize: 14, color: 'var(--ink)',
              lineHeight: 1.6, fontFamily: 'var(--font-body)', background: 'rgba(0,0,0,0.02)',
              outline: 'none', resize: 'vertical', boxSizing: 'border-box',
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
            padding: '5px 14px', borderRadius: 8, border: '1px solid rgba(0,0,0,0.08)',
            background: 'transparent', fontSize: 12, color: 'var(--ink-soft)',
            cursor: 'pointer', fontFamily: 'var(--font-body)',
          }}>取消</button>
          <button onClick={handleSave} disabled={saving} style={{
            padding: '5px 14px', borderRadius: 8, border: 'none',
            background: 'var(--ink-accent)', fontSize: 12, color: '#FAF8F4',
            cursor: saving ? 'default' : 'pointer', fontWeight: 500,
            fontFamily: 'var(--font-body)', opacity: saving ? 0.6 : 1,
          }}>{saving ? '保存中…' : '保存'}</button>
        </div>
      )}
      {expanded && !editing && (
        <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: 'var(--ink-faint)', lineHeight: '28px' }}>
            权重 {mem.weight != null ? (mem.weight * 100).toFixed(0) + '%' : '—'}
            {mem.pinned && ' · 已固定'}
          </span>
          <div style={{ flex: 1 }} />
          <button onClick={() => { setEditing(true); setEditContent(mem.content); }} style={{
            padding: '4px 10px', borderRadius: 6, border: '1px solid rgba(0,0,0,0.08)',
            background: 'transparent', fontSize: 11, color: 'var(--ink-accent)',
            cursor: 'pointer', fontFamily: 'var(--font-body)',
          }}>编辑</button>
          {mem.unresolved && (
            <button onClick={() => onResolve(mem.id)} style={{
              padding: '4px 10px', borderRadius: 6, border: '1px solid rgba(122,158,126,0.35)',
              background: 'transparent', fontSize: 11, color: 'var(--success)',
              cursor: 'pointer', fontFamily: 'var(--font-body)',
            }}>标记已解决</button>
          )}
          {Object.keys(LAYER_META).filter(l => l !== mem.layer).map(l => (
            <button key={l} onClick={() => onMove(mem.id, l)} style={{
              padding: '4px 10px', borderRadius: 6, border: '1px solid rgba(0,0,0,0.08)',
              background: 'transparent', fontSize: 11, color: 'var(--ink-soft)',
              cursor: 'pointer', fontFamily: 'var(--font-body)',
            }}>→ {LAYER_META[l].label}</button>
          ))}
          <button onClick={() => onDelete(mem.id)} style={{
            padding: '4px 10px', borderRadius: 6, border: '1px solid rgba(200,80,80,0.2)',
            background: 'transparent', fontSize: 11, color: '#c85050',
            cursor: 'pointer', fontFamily: 'var(--font-body)',
          }}>删除</button>
        </div>
      )}
    </div>
  );
}

function LayerDetail({ layer, onBack }) {
  const meta = LAYER_META[layer];
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState(null);
  const [sortBy, setSortBy] = useState('created_at');

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ layer, sort_by: sortBy, limit: '100' });
    if (search) params.set('search', search);
    if (typeFilter) params.set('memory_type', typeFilter);
    try {
      const res = await apiFetch(`/memory?${params}`);
      const data = await res.json();
      setMemories(data.ok ? (data.data?.items || []) : []);
    } catch (e) {
      setMemories([]);
    }
    setLoading(false);
  }, [layer, search, typeFilter, sortBy]);

  useEffect(() => { load(); }, [load]);

  async function handleEdit(id, updates) {
    try {
      const res = await apiJsonFetch(`/memory/${id}`, {
        method: 'PUT', body: JSON.stringify(updates),
      });
      const data = await res.json();
      if (data.ok) {
        setMemories(m => m.map(x => x.id === id ? { ...x, ...updates } : x));
        return true;
      }
    } catch (e) {}
    return false;
  }

  async function handleMove(id, target) {
    try {
      await apiJsonFetch(`/memory/${id}/move`, {
        method: 'POST', body: JSON.stringify({ target_layer: target }),
      });
      setMemories(m => m.filter(x => x.id !== id));
    } catch (e) {}
  }

  async function handleResolve(id) {
    try {
      const res = await apiFetch(`/memory/${id}/resolve`, { method: 'POST' });
      const data = await res.json();
      if (data.ok) {
        setMemories(items => items.map(item => item.id === id ? data.data : item));
      }
    } catch (e) {}
  }

  async function handleDelete(id) {
    try {
      await apiFetch(`/memory/${id}`, { method: 'DELETE' });
      setMemories(m => m.filter(x => x.id !== id));
    } catch (e) {}
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
          <div style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{meta.desc} · {memories.length} 条</div>
        </div>
      </div>

      <div className="r-glass" style={{ position: 'relative', marginBottom: 12 }}>
        <input
          type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder="搜索记忆…"
          style={{
            width: '100%', border: 'none', background: 'transparent', outline: 'none',
            fontSize: 14, color: 'var(--ink)', fontFamily: 'var(--font-body)',
            padding: 0,
          }}
        />
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
        <button onClick={() => setTypeFilter(null)} style={{
          padding: '5px 12px', borderRadius: 20, border: 'none', cursor: 'pointer',
          fontSize: 12, fontFamily: 'var(--font-body)',
          background: !typeFilter ? 'var(--ink-accent)' : 'rgba(0,0,0,0.04)',
          color: !typeFilter ? '#FAF8F4' : 'var(--ink-soft)',
        }}>全部</button>
        {typeOptions.map(t => (
          <button key={t} onClick={() => setTypeFilter(typeFilter === t ? null : t)} style={{
            padding: '5px 12px', borderRadius: 20, border: 'none', cursor: 'pointer',
            fontSize: 12, fontFamily: 'var(--font-body)',
            background: typeFilter === t ? 'var(--ink-accent)' : 'rgba(0,0,0,0.04)',
            color: typeFilter === t ? '#FAF8F4' : 'var(--ink-soft)',
          }}>{TYPE_LABELS[t]}</button>
        ))}
        <div style={{ flex: 1 }} />
        <button onClick={() => setSortBy(s => s === 'created_at' ? 'weight' : 'created_at')} style={{
          padding: '5px 10px', borderRadius: 20, border: '1px solid rgba(0,0,0,0.06)',
          background: 'transparent', fontSize: 11, color: 'var(--ink-soft)',
          cursor: 'pointer', fontFamily: 'var(--font-body)',
        }}>{sortBy === 'created_at' ? '切换按权重' : '切换按时间'}</button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--ink-faint)', fontSize: 13 }}>加载中…</div>
      ) : memories.length === 0 ? (
        <div className="r-glass" style={{ position: 'relative', textAlign: 'center', padding: '30px 16px' }}>
          <div style={{ fontSize: 13, color: 'var(--ink-faint)' }}>
            {typeFilter || search ? `没有符合条件的记忆` : '这里还没有记忆'}
          </div>
          {typeFilter && (
            <button onClick={() => setTypeFilter(null)} style={{
              marginTop: 10, padding: '5px 14px', borderRadius: 20, border: '1px solid rgba(0,0,0,0.08)',
              background: 'transparent', fontSize: 12, color: 'var(--ink-soft)',
              cursor: 'pointer', fontFamily: 'var(--font-body)',
            }}>清除筛选</button>
          )}
        </div>
      ) : (
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
      )}
    </div>
  );
}

function DayMemories({ year, month, day, onBack }) {
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(true);
  const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch(`/memory?date_from=${dateStr}&date_to=${dateStr}&limit=100`);
        const data = await res.json();
        if (data.ok) setMemories(data.data?.items || []);
      } catch (e) {}
      setLoading(false);
    })();
  }, [dateStr]);

  return (
    <div>
      <BackButton onClick={onBack} />
      <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--ink)', marginBottom: 14, fontFamily: 'var(--font-display)' }}>
        {month} 月 {day} 日的记忆
      </div>
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--ink-faint)', fontSize: 13 }}>加载中…</div>
      ) : memories.length === 0 ? (
        <div className="r-glass" style={{ position: 'relative', textAlign: 'center', padding: '30px 16px' }}>
          <div style={{ fontSize: 13, color: 'var(--ink-faint)' }}>这一天没有记忆</div>
        </div>
      ) : (
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

  const bj = getBJDate();
  const [calYear, setCalYear] = useState(bj.year);
  const [calMonth, setCalMonth] = useState(bj.month);

  useEffect(() => {
    (async () => {
      try {
        const [statsRes, candRes] = await Promise.all([
          apiFetch('/memory/stats'),
          apiFetch('/memory/candidates?status=pending&limit=50'),
        ]);
        const sd = await statsRes.json();
        const cd = await candRes.json();
        if (sd.ok) setStats(sd.data);
        if (cd.ok && Array.isArray(cd.data)) setCandidates(cd.data);
      } catch (e) {}
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
      } catch (e) {}
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
      } catch (e) {}
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
    try {
      const res = await apiJsonFetch(`/memory/candidates/${id}/accept`, { method: 'POST', body: '{}' });
      const data = await res.json();
      if (data.ok) {
        setCandidates(c => c.filter(x => x.id !== id));
        const statsRes = await apiFetch('/memory/stats');
        const sd = await statsRes.json();
        if (sd.ok) setStats(sd.data);
      }
    } catch (e) {}
  }

  async function rejectCandidate(id) {
    try {
      const res = await apiFetch(`/memory/candidates/${id}/reject`, { method: 'POST' });
      const data = await res.json();
      if (data.ok) setCandidates(c => c.filter(x => x.id !== id));
    } catch (e) {}
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
        <DayMemories year={calYear} month={calMonth} day={selectedDay} onBack={() => { setView('home'); setSelectedDay(null); }} />
      </div>
    );
  }

  const totalMemories = stats.core + stats.long + stats.short + stats.consciousness;

  return (
    <div style={{ padding: '16px 14px 16px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      <BackButton onClick={onBack} />

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
        onDayClick={(y, m, d) => { setCalYear(y); setCalMonth(m); setSelectedDay(d); setView('day'); }}
      />

      <CandidateReview candidates={candidates} onAccept={acceptCandidate} onReject={rejectCandidate} />
    </div>
  );
}
