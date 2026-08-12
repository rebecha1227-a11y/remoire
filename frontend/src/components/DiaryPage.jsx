import { useState, useRef, useEffect, useMemo } from "react";
import { SectionLabel } from "./primitives";
import { apiFetch, apiJsonFetch } from "../utils/api";
import RoomShell from './RoomShell';


// ── CSS for flip animations ──
const DIARY_V3_CSS = `
.diary-book-wrapper {
  perspective: 1200px;
  perspective-origin: center center;
}
.diary-page-stack {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
}
.diary-page {
  position: absolute;
  inset: 0;
  transform-origin: left center;
  transform-style: preserve-3d;
  backface-visibility: hidden;
  transition: none;
  pointer-events: none;
}
.diary-page.flipping {
  transition: transform 700ms cubic-bezier(0.25, 0.46, 0.45, 0.94);
}
.diary-page.flipped {
  transform: rotateY(-180deg);
}
.diary-page-front {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
}
.diary-page-back {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
  overflow: hidden;
}
.diary-scroll {
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-y: contain;
  touch-action: pan-y;
}
.diary-page-back {
  transform: rotateY(180deg);
}

/* Cover open animation */
@keyframes cover-lift {
  0%   { transform: rotateY(0deg); box-shadow: 2px 0 8px rgba(0,0,0,0.15); }
  40%  { transform: rotateY(-85deg); box-shadow: 8px 0 20px rgba(0,0,0,0.25); }
  100% { transform: rotateY(-180deg); box-shadow: 0 0 4px rgba(0,0,0,0.1); }
}
.cover-flipping {
  animation: cover-lift 800ms cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
}

/* Page shadow during flip */
.diary-page.flipping::after {
  content: '';
  position: absolute;
  top: 0; right: 0; bottom: 0;
  width: 40px;
  background: linear-gradient(to left, rgba(40,33,28,0.08), transparent);
  pointer-events: none;
  z-index: 5;
}

/* PIN pad shake */
@keyframes pin-shake {
  0%, 100% { transform: translateX(0); }
  20%       { transform: translateX(-9px); }
  40%       { transform: translateX(9px); }
  60%       { transform: translateX(-6px); }
  80%       { transform: translateX(6px); }
}
`;

if (!document.getElementById('diary-v3-css')) {
  const el = document.createElement('style');
  el.id = 'diary-v3-css';
  el.textContent = DIARY_V3_CSS;
  document.head.appendChild(el);
}

// ── Diary data ──
const JINGER_DIARY_INIT = [];

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];

function formatDiaryTimestamp(raw) {
  const d = new Date(raw.endsWith('Z') || raw.includes('+') ? raw : raw + 'Z');
  const bj = new Date(d.getTime() + 8 * 3600000);
  const month = String(bj.getUTCMonth() + 1).padStart(2, '0');
  const day = String(bj.getUTCDate()).padStart(2, '0');
  const hh = String(bj.getUTCHours()).padStart(2, '0');
  const mm = String(bj.getUTCMinutes()).padStart(2, '0');
  return {
    date: `${month}-${day}`,
    time: `${month}-${day} ${hh}:${mm}`,
    weekday: WEEKDAYS[bj.getUTCDay()] || '',
  };
}

function mapDiaryEntry(entry) {
  const raw = entry.created_at;
  const formatted = formatDiaryTimestamp(raw);
  return {
    id: entry.id,
    date: formatted.date,
    time: formatted.time,
    sortKey: raw,
    weekday: formatted.weekday,
    title: entry.title,
    body: entry.content,
    author: entry.author,
    locked: entry.locked || false,
    pin: entry.pin || null,
    interactions: entry.interactions || [],
  };
}


// ── PinPad ──
function PinPad({ title, subtitle, onComplete, onCancel, errorKey }) {
  const [digits, setDigits] = useState([]);
  const [shaking, setShaking] = useState(false);

  useEffect(() => {
    if (errorKey > 0) {
      setShaking(true);
      setDigits([]);
      const t = setTimeout(() => setShaking(false), 400);
      return () => clearTimeout(t);
    }
  }, [errorKey]);

  function press(d) {
    if (digits.length >= 4) return;
    const next = [...digits, d];
    setDigits(next);
    if (next.length === 4) {
      setTimeout(() => { onComplete(next.join('')); setDigits([]); }, 150);
    }
  }
  function del() { setDigits(d => d.slice(0, -1)); }

  const keys = [1,2,3,4,5,6,7,8,9,null,0,'del'];
  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 50,
      background: 'var(--bg-primary)',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '0 40px',
    }}>
      {onCancel && (
        <button onClick={onCancel} style={{
          position: 'absolute', top: 16, left: 16,
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--text-tertiary)', fontSize: 12, fontFamily: 'var(--font-body)',
          display: 'flex', alignItems: 'center', gap: 4, padding: 8,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          取消
        </button>
      )}
      <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, color: 'var(--text-deep)', marginBottom: 6 }}>{title}</div>
      {subtitle && <div style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 32, textAlign: 'center' }}>{subtitle}</div>}
      <div style={{ display: 'flex', gap: 18, marginBottom: 44, animation: shaking ? 'pin-shake 0.4s ease' : 'none' }}>
        {[0,1,2,3].map(i => (
          <div key={i} style={{
            width: 13, height: 13, borderRadius: '50%',
            background: i < digits.length ? 'var(--accent)' : 'transparent',
            border: `1.5px solid ${i < digits.length ? 'var(--accent)' : 'var(--border)'}`,
            transition: 'all 0.15s',
          }} />
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, width: '100%', maxWidth: 220 }}>
        {keys.map((k, i) => k === null ? <div key={i} /> : (
          <button key={i} onClick={() => k === 'del' ? del() : press(k)} style={{
            height: 56, borderRadius: 12,
            background: k === 'del' ? 'transparent' : 'var(--bg-elevated)',
            border: k === 'del' ? 'none' : '1px solid var(--border-light)',
            fontSize: k === 'del' ? 20 : 22,
            color: 'var(--text-primary)', cursor: 'pointer',
            fontFamily: 'var(--font-body)', fontWeight: 300,
          }}>
            {k === 'del' ? '⌫' : k}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── WritingEditor ──
function WritingEditor({ onSave, onCancel }) {
  const today = new Date();
  const mm = String(today.getMonth() + 1).padStart(2, '0');
  const dd = String(today.getDate()).padStart(2, '0');
  const dateStr = `${mm}-${dd}`;
  const weekdays = ['日','一','二','三','四','五','六'];
  const weekday = weekdays[today.getDay()];

  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [locked, setLocked] = useState(false);
  const [pin, setPin] = useState('');
  const [pinMode, setPinMode] = useState(null);
  const [pinFirst, setPinFirst] = useState('');
  const [pinErrorKey, setPinErrorKey] = useState(0);

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const bgColor = isDark ? '#2A2420' : '#F8F2EE';

  function toggleLock() {
    if (locked) { setLocked(false); setPin(''); }
    else setPinMode('set');
  }

  function handlePinComplete(p) {
    if (pinMode === 'set') { setPinFirst(p); setPinMode('confirm'); }
    else {
      if (p === pinFirst) { setPin(p); setLocked(true); setPinMode(null); setPinFirst(''); }
      else {
        setPinErrorKey(k => k + 1);
        setTimeout(() => { setPinMode('set'); setPinFirst(''); }, 500);
      }
    }
  }

  function save() {
    if (!title.trim() && !body.trim()) return;
    onSave({ date: dateStr, weekday, title: title.trim() || '无题', body, locked, pin });
  }

  if (pinMode) {
    return (
      <div style={{ position: 'absolute', inset: 0, zIndex: 40, background: bgColor }}>
        <PinPad
          title={pinMode === 'set' ? '设置密码' : '再次确认'}
          subtitle={pinMode === 'set' ? '为日记设置 4 位数字密码' : '再输一遍以确认'}
          onComplete={handlePinComplete}
          errorKey={pinErrorKey}
          onCancel={() => { setPinMode(null); setPinFirst(''); }}
        />
      </div>
    );
  }

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 30,
      background: bgColor,
      backgroundImage: 'linear-gradient(rgba(100,90,80,0.05) 1px, transparent 1px)',
      backgroundSize: '100% 28px',
      display: 'flex', flexDirection: 'column',
      animation: 'page-in 250ms ease',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 16px', flexShrink: 0,
        borderBottom: '1px solid rgba(100,90,80,0.08)',
      }}>
        <button onClick={onCancel} style={{
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--text-tertiary)', fontSize: 12, fontFamily: 'var(--font-body)',
          display: 'flex', alignItems: 'center', gap: 4, padding: 0,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
          取消
        </button>
        <div style={{ fontFamily: 'var(--font-diary)', fontSize: 14, color: 'var(--text-tertiary)' }}>
          {dateStr} · {weekday}
        </div>
        <button onClick={save} disabled={!title.trim() && !body.trim()} style={{
          background: (title.trim() || body.trim()) ? 'var(--accent)' : 'var(--border)',
          border: 'none', borderRadius: 8, padding: '6px 14px',
          fontSize: 12, color: '#FAF8F4',
          cursor: (title.trim() || body.trim()) ? 'pointer' : 'default',
          fontFamily: 'var(--font-body)', fontWeight: 500, transition: 'background 0.2s',
        }}>保存</button>
      </div>

      <div style={{ padding: '20px 20px 0' }}>
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="标题（可留空）"
          style={{
            width: '100%', border: 'none', background: 'transparent', outline: 'none',
            fontFamily: 'var(--font-diary)', fontSize: 22,
            color: 'var(--text-deep)', fontWeight: 300, boxSizing: 'border-box',
          }}
        />
      </div>
      <div style={{ height: 1, background: 'rgba(100,90,80,0.1)', margin: '12px 20px 0' }} />

      <textarea
        value={body}
        onChange={e => setBody(e.target.value)}
        placeholder="今天…"
        autoFocus
        style={{
          flex: 1, border: 'none', background: 'transparent', outline: 'none',
          resize: 'none', fontFamily: 'var(--font-diary)', fontSize: 18,
          color: 'var(--text-primary)', lineHeight: 1.85,
          padding: '16px 20px', boxSizing: 'border-box',
        }}
      />

      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 20px 28px', borderTop: '1px solid rgba(100,90,80,0.08)', flexShrink: 0,
      }}>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', fontFamily: 'var(--font-body)' }}>
          {body.length > 0 ? `${body.length} 字` : ' '}
        </div>
        <button onClick={toggleLock} style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: locked ? 'rgba(184,146,74,0.08)' : 'transparent',
          border: `1px solid ${locked ? 'rgba(184,146,74,0.3)' : 'var(--border-light)'}`,
          borderRadius: 20, padding: '6px 14px', cursor: 'pointer',
          color: locked ? 'var(--warning)' : 'var(--text-tertiary)',
          fontSize: 12, fontFamily: 'var(--font-body)', transition: 'all 0.2s',
        }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            {locked
              ? <><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></>
              : <><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9 1"/></>
            }
          </svg>
          {locked ? '已上锁' : '上锁'}
        </button>
      </div>
    </div>
  );
}

// ── Pink Patchwork Cover (Jinger) ──
function PinkCover({ onClick, customCover }) {
  if (customCover) {
    return (
      <button type="button" aria-label="打开静儿的日记" onClick={onClick} style={{
        width: '100%', aspectRatio: '3/5', borderRadius: '4px 8px 8px 4px',
        position: 'relative', cursor: 'pointer', overflow: 'hidden', border: 'none', padding: 0,
        boxShadow: '3px 4px 14px rgba(40,33,28,0.2), 0 1px 3px rgba(40,33,28,0.12)',
        backgroundImage: `url(${customCover})`, backgroundSize: 'cover', backgroundPosition: 'center'
      }}>
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.15)' }} />
        <div style={{
          position: 'absolute', bottom: 12, left: 0, right: 0, textAlign: 'center'
        }}>
          <div style={{ color: 'rgba(255,255,255,0.9)', letterSpacing: 1, fontSize: "13px", fontFamily: "var(--font-display)", textShadow: '0 1px 4px rgba(40,33,28,0.4)' }}>Jinger's Diary</div>
        </div>
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 6, background: 'linear-gradient(90deg, rgba(0,0,0,0.08), transparent)', pointerEvents: 'none' }} />
      </button>);

  }
  // Create patchwork quilt pattern with CSS
  const patches = [
  { x: 0, y: 0, w: '34%', h: '28%', bg: '#F2D7D5', pattern: 'roses' },
  { x: '34%', y: 0, w: '33%', h: '28%', bg: '#EEC9D2', pattern: 'gingham' },
  { x: '67%', y: 0, w: '33%', h: '28%', bg: '#F5E0D5', pattern: 'dots' },
  { x: 0, y: '28%', w: '50%', h: '22%', bg: '#F0C6D0', pattern: 'gingham' },
  { x: '50%', y: '28%', w: '50%', h: '22%', bg: '#F2D7D5', pattern: 'roses' },
  { x: 0, y: '50%', w: '33%', h: '25%', bg: '#F5E0D5', pattern: 'roses' },
  { x: '33%', y: '50%', w: '34%', h: '25%', bg: '#EEC9D2', pattern: 'dots' },
  { x: '67%', y: '50%', w: '33%', h: '25%', bg: '#F2D7D5', pattern: 'gingham' },
  { x: 0, y: '75%', w: '50%', h: '25%', bg: '#EEC9D2', pattern: 'roses' },
  { x: '50%', y: '75%', w: '50%', h: '25%', bg: '#F0C6D0', pattern: 'dots' }];


  function patchBg(p) {
    if (p.pattern === 'gingham') {
      return `${p.bg} repeating-linear-gradient(0deg, transparent, transparent 4px, rgba(255,255,255,0.35) 4px, rgba(255,255,255,0.35) 5px) repeating-linear-gradient(90deg, transparent, transparent 4px, rgba(255,255,255,0.35) 4px, rgba(255,255,255,0.35) 5px)`.split(' ').slice(0, 1)[0];
    }
    return p.bg;
  }

  return (
    <button type="button" aria-label="打开静儿的日记" onClick={onClick} style={{
      width: '100%', aspectRatio: '3/5', borderRadius: '4px 8px 8px 4px',
      position: 'relative', cursor: 'pointer', overflow: 'hidden', border: 'none', padding: 0,
      boxShadow: '3px 4px 14px rgba(40,33,28,0.2), 0 1px 3px rgba(40,33,28,0.12)',
      background: '#F0C6D0'
    }}>
      {/* Patchwork grid */}
      {patches.map((p, i) =>
      <div key={i} style={{
        position: 'absolute', left: p.x, top: p.y, width: p.w, height: p.h,
        background: p.bg,
        backgroundImage: p.pattern === 'gingham' ?
        'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(255,255,255,0.4) 3px, rgba(255,255,255,0.4) 4px), repeating-linear-gradient(90deg, transparent, transparent 3px, rgba(255,255,255,0.4) 3px, rgba(255,255,255,0.4) 4px)' :
        p.pattern === 'dots' ?
        'radial-gradient(circle 1.5px, rgba(180,100,120,0.2) 1px, transparent 1px)' :
        'radial-gradient(circle 2px, rgba(180,90,110,0.15) 1.5px, transparent 1.5px)',
        backgroundSize: p.pattern === 'gingham' ? '8px 8px' :
        p.pattern === 'dots' ? '8px 8px' : '12px 12px',
        border: '0.5px solid rgba(180,140,150,0.2)'
      }} />
      )}
      {/* Quilting stitch lines */}
      <div style={{ position: 'absolute', inset: 0, opacity: 0.15,
        backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(120,60,80,0.3) 10px, rgba(120,60,80,0.3) 10.5px)',
        backgroundSize: '14px 14px', pointerEvents: 'none' }} />
      {/* Label */}
      <div style={{
        position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        width: '55%', aspectRatio: '1.7/1',
        background: 'rgba(255,255,255,0.88)', borderRadius: '50%',
        border: '1.5px solid rgba(140,80,100,0.35)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        padding: '8px 12px'
      }}>
        <div style={{ color: '#8B5E6B', letterSpacing: 1, textAlign: "center", fontSize: "13px", fontFamily: "var(--font-diary)" }}>Jinger's Diary</div>
        <div style={{ width: '70%', height: 1, background: 'rgba(140,80,100,0.25)', margin: '4px 0' }} />
        <div style={{ width: '50%', height: 1, background: 'rgba(140,80,100,0.2)' }} />
        {/* Ribbon */}
        <svg width="36" height="14" viewBox="0 0 36 14" style={{ marginTop: 4, opacity: 0.7 }}>
          <path d="M2 7 C8 2, 12 12, 18 7 C24 2, 28 12, 34 7" stroke="#E8A0B0" strokeWidth="2.5" fill="none" strokeLinecap="round" />
        </svg>
      </div>
      {/* Spine */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 6, background: 'linear-gradient(90deg, rgba(0,0,0,0.08), transparent)', pointerEvents: 'none' }} />
    </button>);

}

// ── Blue Star Cover (Connie) ──
function BlueCover({ onClick, customCover }) {
  if (customCover) {
    return (
      <button type="button" aria-label="打开 Connie 的日记" onClick={onClick} style={{
        width: '100%', aspectRatio: '3/5', borderRadius: '4px 8px 8px 4px',
        position: 'relative', cursor: 'pointer', overflow: 'hidden', border: 'none', padding: 0,
        boxShadow: '3px 4px 14px rgba(40,33,28,0.2), 0 1px 3px rgba(40,33,28,0.12)',
        backgroundImage: `url(${customCover})`, backgroundSize: 'cover', backgroundPosition: 'center'
      }}>
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.15)' }} />
        <div style={{
          position: 'absolute', bottom: 12, left: 0, right: 0, textAlign: 'center'
        }}>
          <div style={{ color: 'rgba(255,255,255,0.9)', letterSpacing: 1, fontSize: "13px", fontFamily: "var(--font-display)", textShadow: '0 1px 4px rgba(40,33,28,0.4)' }}>Connie's Diary</div>
        </div>
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 6, background: 'linear-gradient(90deg, rgba(0,0,0,0.1), transparent)', pointerEvents: 'none' }} />
      </button>);

  }
  // Generate scattered stars
  const stars = useMemo(() => {
    const s = [];
    for (let i = 0; i < 28; i++) {
      s.push({
        x: (i * 37 + 13) % 92 + 4,
        y: (i * 53 + 7) % 90 + 5,
        size: 8 + i % 5 * 4,
        rot: i * 67 % 360,
        type: i % 3, // 0=dark, 1=gold, 2=white
        opacity: 0.5 + i % 4 * 0.15
      });
    }
    return s;
  }, []);

  const starColors = ['#5A6878', '#D4C49A', '#E8E2D8'];

  return (
    <button type="button" aria-label="打开 Connie 的日记" onClick={onClick} style={{
      width: '100%', aspectRatio: '3/5', borderRadius: '4px 8px 8px 4px',
      position: 'relative', cursor: 'pointer', overflow: 'hidden', border: 'none', padding: 0,
      boxShadow: '3px 4px 14px rgba(40,33,28,0.2), 0 1px 3px rgba(40,33,28,0.12)',
      background: '#8B9EAE'
    }}>
      {/* Stars */}
      {stars.map((s, i) =>
      <svg key={i} width={s.size} height={s.size} viewBox="0 0 24 24"
      style={{
        position: 'absolute', left: `${s.x}%`, top: `${s.y}%`,
        transform: `rotate(${s.rot}deg)`, opacity: s.opacity
      }}>
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
        fill={starColors[s.type]} stroke="none" />
        </svg>
      )}
      {/* Sparkle dots */}
      {[...Array(12)].map((_, i) =>
      <div key={`dot-${i}`} style={{
        position: 'absolute',
        left: `${(i * 41 + 20) % 90 + 5}%`, top: `${(i * 59 + 15) % 85 + 5}%`,
        width: 2, height: 2, borderRadius: '50%',
        background: 'rgba(212,196,154,0.6)'
      }} />
      )}
      {/* Label */}
      <div style={{
        position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        width: '55%', aspectRatio: '1.7/1',
        background: 'rgba(100,110,120,0.7)', borderRadius: '50%',
        border: '1.5px solid rgba(85,95,105,0.4)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        padding: '8px 12px'
      }}>
        <div style={{ color: 'rgba(255,255,255,0.8)', letterSpacing: 1, fontSize: "13px", textAlign: "center", fontFamily: "var(--font-diary)" }}>Connie's Diary</div>
        <div style={{ width: '70%', height: 1, background: 'rgba(255,255,255,0.2)', margin: '4px 0' }} />
        <div style={{ width: '50%', height: 1, background: 'rgba(255,255,255,0.15)' }} />
      </div>
      {/* Spine */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 6, background: 'linear-gradient(90deg, rgba(0,0,0,0.1), transparent)', pointerEvents: 'none' }} />
    </button>);

}

// ── Table of Contents Page ──
function TOCPage({ entries, author, onSelect }) {
  const isConnie = author === 'connie';
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const pageBg = isDark ? (isConnie ? '#272320' : '#2A2420') : (isConnie ? '#EDE9E3' : '#F8F2EE');
  const scrollRef = useRef(null);
  useTouchScroll(scrollRef);
  return (
    <div ref={scrollRef} className="diary-scroll" style={{
      width: '100%', height: '100%', padding: '24px 20px',
      background: pageBg
    }}>
      <div style={{
        fontFamily: "var(--font-diary)",
        fontSize: 24, color: isDark ? (isConnie ? '#7AACBC' : '#D4A0B4') : (isConnie ? '#5A6878' : '#9B6B7B'),
        textAlign: 'center', marginBottom: 6
      }}>目录</div>
      <div style={{ width: 40, height: 1, background: isDark ? 'rgba(200,180,160,0.2)' : (isConnie ? 'rgba(90,104,120,0.25)' : 'rgba(155,107,123,0.25)'), margin: '0 auto 20px' }} />
      {entries.map((e, i) =>
      <button type="button" key={e.id || i} onClick={() => onSelect(i)} style={{
        display: 'flex', alignItems: 'baseline', gap: 10,
        width: '100%', padding: '10px 4px', cursor: 'pointer', background: 'transparent', border: 'none', textAlign: 'left',
        borderBottom: '1px dotted rgba(0,0,0,0.08)',
        transition: 'background 0.15s'
      }}
      onMouseEnter={(ev) => ev.currentTarget.style.background = 'rgba(0,0,0,0.02)'}
      onMouseLeave={(ev) => ev.currentTarget.style.background = 'transparent'}>
        
          <span style={{ fontFamily: "var(--font-body)", fontSize: 11, color: '#8B7E74', minWidth: 38, flexShrink: 0 }}>{e.date}</span>
          <span style={{ fontFamily: "var(--font-body)", fontSize: 9, color: '#8B7E74', minWidth: 16 }}>{e.weekday}</span>
          <span style={{ fontFamily: "var(--font-diary)", fontSize: 16, color: '#3D3229', flex: 1 }}>{e.title}</span>
          {e.locked &&
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" strokeWidth="1.5" style={{ flexShrink: 0 }}>
              <rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
        }
        </button>
      )}
    </div>);

}

function useTouchScroll(ref) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let lastY = 0;
    let active = false;
    function onTouchStart(e) {
      if (e.touches.length !== 1) return;
      active = true;
      lastY = e.touches[0].clientY;
    }
    function onTouchMove(e) {
      if (!active || e.touches.length !== 1) return;
      const y = e.touches[0].clientY;
      const dy = lastY - y;
      if (dy === 0) return;
      const max = el.scrollHeight - el.clientHeight;
      const next = Math.max(0, Math.min(max, el.scrollTop + dy));
      if (next !== el.scrollTop) {
        el.scrollTop = next;
        e.preventDefault();
      }
      lastY = y;
    }
    function onTouchEnd() {
      active = false;
    }
    el.addEventListener('touchstart', onTouchStart, { passive: true });
    el.addEventListener('touchmove', onTouchMove, { passive: false });
    el.addEventListener('touchend', onTouchEnd, { passive: true });
    el.addEventListener('touchcancel', onTouchEnd, { passive: true });
    return () => {
      el.removeEventListener('touchstart', onTouchStart);
      el.removeEventListener('touchmove', onTouchMove);
      el.removeEventListener('touchend', onTouchEnd);
      el.removeEventListener('touchcancel', onTouchEnd);
    };
  }, [ref]);
}

// ── Content Page ──
function DiaryMessageBoard({ entry, author, lockedConnie, onAddInteraction, onDeleteInteraction }) {
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const interactions = entry.interactions || [];
  const isConnieDiary = author === 'connie';

  function labelFor(item) {
    if (item.type === 'unlock_request') return item.actor === 'jinger' ? '申请查看' : '解锁请求';
    if (item.type === 'unlock_granted') return '已同意';
    if (item.type === 'unlock_rejected') return '已拒绝';
    if (item.type === 'lock_changed') return '锁状态';
    if (item.type === 'comment') return item.actor === 'connie' ? '回复' : '留言';
    if (item.type === 'wrote') return '动态';
    return '留言';
  }

  async function submit(type) {
    const content = text.trim();
    if (!content || sending) return;
    setError('');
    setSending(true);
    try {
      await onAddInteraction(entry.id, type, content);
      setText('');
    } catch (e) {
      setError('没送出去。先别关，我把文字留在这里。');
    } finally {
      setSending(false);
    }
  }

  return (
    <div style={{ marginTop: 24, paddingTop: 14, borderTop: '1px dashed rgba(100,90,80,0.18)' }}>
      <div style={{ fontFamily: 'var(--font-body)', fontSize: 10, letterSpacing: 1.2, color: '#8B7E74', textTransform: 'uppercase', marginBottom: 10 }}>
        留言板
      </div>
      {interactions.filter(i => i.type !== 'wrote').length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
          {interactions.filter(i => i.type !== 'wrote').map(item => (
            <div key={item.id} style={{
              background: item.actor === 'connie' ? 'rgba(122,138,154,0.10)' : 'rgba(155,107,123,0.10)',
              border: '1px solid rgba(100,90,80,0.10)', borderRadius: 8, padding: '8px 10px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 10, color: item.actor === 'connie' ? '#5A7888' : '#9B6B7B', fontFamily: 'var(--font-body)' }}>
                  {item.actor === 'connie' ? 'Connie' : '静儿'} · {labelFor(item)}
                </span>
                {onDeleteInteraction && (
                  <button onClick={() => { if (window.confirm('删除这条留言？')) onDeleteInteraction(entry.id, item.id); }} style={{
                    background: 'none', border: 'none', cursor: 'pointer', padding: 2, opacity: 0.35, transition: 'opacity 0.15s',
                  }} onMouseEnter={e => e.currentTarget.style.opacity = 0.8} onMouseLeave={e => e.currentTarget.style.opacity = 0.35}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#8B7E74" strokeWidth="1.5"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /><path d="M10 11v6M14 11v6" /></svg>
                  </button>
                )}
              </div>
              {item.content && <div style={{ fontFamily: 'var(--font-diary)', fontSize: 15, color: '#5C5047', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{item.content}</div>}
            </div>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: 12, color: '#8B7E74', marginBottom: 12, fontFamily: 'var(--font-body)' }}>
          还没有留言。可以在这里把话轻轻放下。
        </div>
      )}

      {lockedConnie && (
        <div style={{ marginBottom: 10, padding: 10, borderRadius: 8, background: 'rgba(184,146,74,0.07)', border: '1px solid rgba(184,146,74,0.18)' }}>
          <div style={{ fontSize: 12, color: 'var(--warning)', fontFamily: 'var(--font-body)', marginBottom: 8 }}>
            这篇日记上锁了。你可以留一句话，请 Connie 打开给你看。
          </div>

        </div>
      )}

      <textarea value={text} onChange={e => setText(e.target.value)} placeholder={lockedConnie ? '写给 Connie：我想看看这篇，可以吗…' : (isConnieDiary ? '写给 Connie…' : '写下给这篇日记的话…')} style={{
        width: '100%', minHeight: 58, resize: 'vertical', boxSizing: 'border-box',
        border: '1px solid var(--border-light)', borderRadius: 8, padding: '9px 10px',
        background: 'rgba(250,248,244,0.62)', color: '#3D3229', fontFamily: 'var(--font-body)', fontSize: 13, lineHeight: 1.5,
      }} />
      {error && <div style={{ marginTop: 6, fontSize: 11, color: 'var(--warning)', fontFamily: 'var(--font-body)' }}>{error}</div>}
      <button onClick={() => submit(lockedConnie ? 'unlock_request' : 'comment')} disabled={!text.trim() || sending} style={{
        marginTop: 8, width: '100%', minHeight: 34, border: 'none', borderRadius: 8,
        background: text.trim() && !sending ? 'var(--accent)' : 'var(--border)', color: '#FAF8F4',
        fontSize: 12, fontFamily: 'var(--font-body)', cursor: text.trim() && !sending ? 'pointer' : 'default'
      }}>
        {sending ? '送出中…' : (lockedConnie ? '留言申请查看' : '留下这句话')}
      </button>
    </div>
  );
}

// ── Content Page ──
function ContentPage({ entry, author, onAddInteraction, onDeleteInteraction }) {
  const [pinUnlocked, setPinUnlocked] = useState(false);
  const [pinErrorKey, setPinErrorKey] = useState(0);
  const scrollRef = useRef(null);
  useTouchScroll(scrollRef);

  const isConnie = author === 'connie';
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const bgColor = isDark ? (isConnie ? '#272320' : '#2A2420') : (isConnie ? '#EDE9E3' : '#F8F2EE');

  // 静儿查看自己上锁的日记 → PIN 解锁
  if (entry.locked && author === 'jinger' && !pinUnlocked) {
    return (
      <div style={{ position: 'relative', width: '100%', height: '100%', background: bgColor }}>
        <PinPad
          title="输入密码"
          subtitle="这篇日记已上锁"
          onComplete={(p) => {
            if (p === (entry.pin || '1234')) { setPinUnlocked(true); }
            else { setPinErrorKey(k => k + 1); }
          }}
          errorKey={pinErrorKey}
        />
      </div>
    );
  }

  const lockedConnie = entry.locked && author === 'connie';

  return (
    <div style={{
      width: '100%', height: '100%',
      background: bgColor,
      backgroundImage: `
        linear-gradient(rgba(100,90,80,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(100,90,80,0.04) 1px, transparent 1px)
      `,
      backgroundSize: '14px 14px',
      display: 'flex'
    }}>
      <div style={{
        width: '20%', minWidth: 48, borderRight: '1px solid rgba(100,90,80,0.1)',
        padding: '24px 6px 16px 12px',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        flexShrink: 0
      }}>
        <div style={{ fontFamily: "var(--font-display)", fontSize: 28, fontWeight: 300, color: isDark ? (isConnie ? '#7AACBC' : '#D4A0B4') : (isConnie ? '#5A6878' : '#9B6B7B'), lineHeight: 1 }}>
          {entry.date.split('-')[1]}
        </div>
        <div style={{ fontSize: 9, color: '#8B7E74', marginTop: 3, letterSpacing: 1, fontFamily: "var(--font-body)" }}>{entry.weekday}</div>
      </div>

      <div ref={scrollRef} className="diary-scroll" style={{ flex: 1, padding: '22px 16px 16px 14px', minHeight: 0 }}>
        <div style={{
          fontFamily: "var(--font-body)", fontSize: 9, letterSpacing: 1.5,
          textTransform: 'uppercase', color: isConnie ? '#7A8A9A' : '#B08898',
          marginBottom: 12, opacity: 0.7
        }}>{isConnie ? 'Connie' : 'Jinger'}</div>

        <div style={{ fontFamily: 'var(--font-diary)', fontSize: 18, color: '#574337', marginBottom: 12 }}>
          {entry.title}
        </div>

        {lockedConnie ? (
          <div>
            {[80, 65, 90, 55, 75].map((w, i) =>
              <div key={i} style={{ height: 10, background: 'var(--border-light)', borderRadius: 2, width: `${w}%`, marginBottom: 8, opacity: 0.6 }} />
            )}
          </div>
        ) : (
          <div style={{
            fontSize: 18,
            color: '#3D3229', lineHeight: 1.85, whiteSpace: 'pre-wrap', fontFamily: "var(--font-diary)"
          }}>{entry.body}</div>
        )}

        <DiaryMessageBoard
          entry={entry}
          author={author}
          lockedConnie={lockedConnie}
          onAddInteraction={onAddInteraction}
          onDeleteInteraction={onDeleteInteraction}
        />
      </div>
    </div>
  );
}

// ── Open Book Component (3D flip, only renders nearby pages) ──
function OpenBook({ author, entries, onClose, onAddInteraction, onDeleteInteraction }) {
  const isConnie = author === 'connie';
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const totalPages = entries.length + 1;
  const [flippedPages, setFlippedPages] = useState(new Set());
  const [animatingPages, setAnimatingPages] = useState(new Set());
  const [animating, setAnimating] = useState(false);
  const [currentView, setCurrentView] = useState(0);

  function flipToPage(targetPageIdx) {
    if (animating || targetPageIdx === currentView) return;
    if (targetPageIdx < 0 || targetPageIdx >= totalPages) return;

    const pagesToFlip = [];
    if (targetPageIdx > currentView) {
      for (let i = currentView; i < targetPageIdx; i++) pagesToFlip.push(i);
    } else {
      for (let i = currentView - 1; i >= targetPageIdx; i--) pagesToFlip.push(i);
    }

    setAnimating(true);
    setAnimatingPages(new Set(pagesToFlip));

    const stagger = Math.max(80, 400 / pagesToFlip.length);
    let delay = 0;
    pagesToFlip.forEach((pIdx) => {
      setTimeout(() => {
        setFlippedPages((prev) => {
          const next = new Set(prev);
          if (targetPageIdx > currentView) next.add(pIdx);
          else next.delete(pIdx);
          return next;
        });
      }, delay);
      delay += stagger;
    });

    setTimeout(() => {
      setCurrentView(targetPageIdx);
      setAnimating(false);
      setAnimatingPages(new Set());
    }, delay + 500);
  }

  const nearbyPages = useMemo(() => {
    const visible = new Set([currentView]);
    if (currentView > 0) visible.add(currentView - 1);
    if (currentView + 1 < totalPages) visible.add(currentView + 1);
    animatingPages.forEach(p => {
      visible.add(p);
      if (p + 1 < totalPages) visible.add(p + 1);
      if (p > 0) visible.add(p - 1);
    });
    return visible;
  }, [animatingPages, currentView, totalPages]);

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 20,
      background: 'var(--bg-secondary)',
      display: 'flex', flexDirection: 'column',
      animation: 'page-in 300ms ease'
    }}>
      <div className="r-glass" style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 16px', margin: '8px 12px 0', flexShrink: 0,
        borderRadius: 16, position: 'relative',
      }}>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 6,
          color: 'var(--text-primary)', fontSize: 12, fontFamily: "var(--font-body)",
          minWidth: 44, minHeight: 44,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
          合上
        </button>
        <div style={{ fontFamily: "var(--font-diary)", fontSize: 15, color: isDark ? (isConnie ? '#7AACBC' : '#D4A0B4') : (isConnie ? '#5A6878' : '#9B6B7B') }}>
          {isConnie ? 'Connie' : '静儿'}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: "var(--font-body)" }}>
          {currentView}/{totalPages - 1}
        </div>
      </div>

      <div className="diary-book-wrapper" style={{
        flex: 1, minHeight: 0, margin: '0 12px 12px', overflow: 'hidden',
        borderRadius: '2px 6px 6px 2px',
        boxShadow: '2px 3px 12px rgba(40,33,28,0.15), -1px 0 0 rgba(0,0,0,0.05)'
      }}>
        <div className="diary-page-stack" style={{ width: '100%', height: '100%' }}>
          {Array.from({ length: totalPages }, (_, i) => totalPages - 1 - i)
            .filter(pageIdx => nearbyPages.has(pageIdx))
            .map((pageIdx) => {
              const isFlipped = flippedPages.has(pageIdx);
              const isActivePage = pageIdx === currentView && !animating;
              const isAnimatingPage = animatingPages.has(pageIdx);
              return (
                <div key={pageIdx} className={`diary-page ${isFlipped ? 'flipped' : ''} ${isAnimatingPage ? 'flipping' : ''}`}
                  style={{
                    zIndex: isAnimatingPage ? totalPages + 5 : (isFlipped ? pageIdx : totalPages - pageIdx),
                    pointerEvents: isActivePage ? 'auto' : 'none',
                  }}>
                  <div className="diary-page-front" style={{
                    background: isConnie ? '#EDE9E3' : '#F8F2EE',
                    boxShadow: 'inset -2px 0 6px rgba(40,33,28,0.04)'
                  }}>
                    {pageIdx === 0 ?
                      <TOCPage entries={entries} author={author} onSelect={(i) => flipToPage(i + 1)} /> :
                      <ContentPage entry={entries[pageIdx - 1]} author={author} onAddInteraction={onAddInteraction} onDeleteInteraction={onDeleteInteraction} />
                    }
                  </div>
                  <div className="diary-page-back" style={{
                    background: isConnie ? '#E6E1D9' : '#F2EBE6',
                    boxShadow: 'inset 2px 0 6px rgba(40,33,28,0.05)'
                  }}>
                    <div style={{ padding: 20, textAlign: 'right' }}>
                      <div style={{ fontSize: 9, color: 'var(--text-tertiary)', opacity: 0.4, fontFamily: "var(--font-body)" }}>
                        {pageIdx + 1}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      <div className="r-glass" style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 20px', margin: '0 12px 12px', flexShrink: 0,
        borderRadius: 16, position: 'relative',
      }}>
        <button onClick={() => flipToPage(currentView - 1)} disabled={currentView === 0 || animating} style={{
          background: 'none', border: 'none', cursor: currentView > 0 ? 'pointer' : 'default',
          opacity: currentView > 0 && !animating ? 0.8 : 0.25, padding: 8,
          color: 'var(--text-primary)', minWidth: 44, minHeight: 44,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <button onClick={() => flipToPage(0)} style={{
          background: 'rgba(255,255,255,0.25)', border: '1px solid rgba(255,255,255,0.35)', borderRadius: 10,
          padding: '6px 16px', fontSize: 11, color: 'var(--text-primary)', cursor: 'pointer',
          fontFamily: "var(--font-body)", fontWeight: 500,
        }}>目录</button>
        <button onClick={() => flipToPage(currentView + 1)} disabled={currentView >= totalPages - 1 || animating} style={{
          background: 'none', border: 'none', cursor: currentView < totalPages - 1 ? 'pointer' : 'default',
          opacity: currentView < totalPages - 1 && !animating ? 0.8 : 0.25, padding: 8,
          color: 'var(--text-primary)', minWidth: 44, minHeight: 44,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M9 18l6-6-6-6" /></svg>
        </button>
      </div>
    </div>);

}

// ── Diary Activity Feed ──
function DiaryFeed({ activities }) {
  const nameMap = { jinger: '静儿', connie: 'Connie' };
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const colorMap = { jinger: isDark ? '#D4A0B4' : '#9B6B7B', connie: isDark ? '#7AACBC' : '#5A7888' };

  function renderText(a) {
    const name = nameMap[a.author];
    if (a.type === 'wrote') return <span><strong style={{ color: colorMap[a.author] }}>{name}</strong> 写了一篇日记{a.title ? `「${a.title}」` : ''}</span>;
    if (a.type === 'locked') return <span><strong style={{ color: colorMap[a.author] }}>{name}</strong> 给日记上了锁</span>;
    if (a.type === 'lock_changed') return <span><strong style={{ color: colorMap[a.author] }}>{name}</strong> {a.msg || '调整了日记锁'}</span>;
    if (a.type === 'unlock_granted') return <span><strong style={{ color: colorMap[a.author] }}>{name}</strong> 同意解锁日记{a.title ? `「${a.title}」` : ''}</span>;
    if (a.type === 'unlock_rejected') return <span><strong style={{ color: colorMap[a.author] }}>{name}</strong> 暂时没有打开日记{a.title ? `「${a.title}」` : ''}</span>;
    if (a.type === 'comment') return (
      <span>
        <strong style={{ color: colorMap[a.author] }}>{name}</strong> 在日记下留言
        <span style={{
          display: 'block', marginTop: 4,
          fontFamily: "var(--font-diary)", fontSize: 14,
          color: 'var(--text-secondary)', lineHeight: 1.6,
          paddingLeft: 8, borderLeft: '2px solid rgba(124,99,80,0.15)'
        }}>"{a.msg}"</span>
      </span>);
    if (a.type === 'unlock_request') return (
      <span>
        <strong style={{ color: colorMap[a.author] }}>{name}</strong> 申请查看上锁日记
        <span style={{
          display: 'block', marginTop: 4,
          fontFamily: "var(--font-diary)", fontSize: 14,
          color: 'var(--text-secondary)', lineHeight: 1.6,
          paddingLeft: 8, borderLeft: '2px solid rgba(124,99,80,0.15)'
        }}>"{a.msg}"</span>
      </span>);

    return null;
  }

  function iconFor(a) {
    if (a.type === 'wrote') return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={colorMap[a.author]} strokeWidth="1.5"><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" /></svg>);

    if (a.type === 'locked') return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" strokeWidth="1.5"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>);

    if (a.type === 'comment') return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={colorMap[a.author]} strokeWidth="1.5"><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" /></svg>);

    if (a.type === 'unlock_request' || a.type === 'unlock_granted' || a.type === 'unlock_rejected' || a.type === 'lock_changed') return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" strokeWidth="1.5"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 9 1" /></svg>);

    return null;
  }

  return (
    <div>
      <SectionLabel style={{ marginBottom: 'var(--space-3)' }}>最近动态</SectionLabel>
      <div style={{ position: 'relative' }}>
        {/* Timeline line — hidden behind dots via per-segment approach */}
        {activities.map((a, i) => {
          const isLast = i === activities.length - 1;
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: 14,
              marginBottom: isLast ? 0 : 16, position: 'relative',
              animation: `card-in 180ms ${i * 30}ms ease both`
            }}>
              {/* Line segment below dot — not through dot */}
              {!isLast && <div style={{
                position: 'absolute', left: 5, top: 15, bottom: -16, width: 1,
                background: 'var(--border)', zIndex: 0
              }} />}
              {/* Dot */}
              <div style={{
                width: 11, height: 11, borderRadius: '50%', flexShrink: 0,
                background: a.type === 'unlock_request' || a.type === 'unlock_granted' || a.type === 'unlock_rejected' || a.type === 'lock_changed' || a.type === 'locked' ?
                'rgba(184,146,74,0.25)' : 'var(--bg-elevated)',
                border: `1.5px solid ${a.type === 'unlock_request' || a.type === 'unlock_granted' || a.type === 'unlock_rejected' || a.type === 'lock_changed' || a.type === 'locked' ? 'var(--warning)' : 'var(--border)'}`,
                marginTop: 2, zIndex: 1
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 3, fontFamily: "var(--font-body)" }}>{a.time}</div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', lineHeight: 1.6, fontFamily: "var(--font-body)" }}>
                  {renderText(a)}
                </div>
              </div>
            </div>);

        })}
      </div>
    </div>);

}

// ── Main DiaryPage ──
export default function DiaryPage({ tweaks, nav, active }) {
  const [openBook, setOpenBook] = useState(null);
  const [writing, setWriting] = useState(false);
  const [jingerDiary, setJingerDiary] = useState(JINGER_DIARY_INIT);
  const [connieDiary, setConnieDiary] = useState([]);

  const coverJ = tweaks && tweaks.diaryCoverJinger;
  const coverC = tweaks && tweaks.diaryCoverConnie;

  useEffect(() => {
    let cancelled = false;
    async function loadDiaries() {
      try {
        const [connieRes, jingerRes] = await Promise.all([
          apiFetch('/diary?author=connie&limit=50'),
          apiFetch('/diary?author=jinger&limit=50'),
        ]);
        const connieData = await connieRes.json();
        const jingerData = await jingerRes.json();
        if (cancelled) return;
        if (connieData.ok && Array.isArray(connieData.data) && connieData.data.length > 0) {
          setConnieDiary(connieData.data.map(mapDiaryEntry));
        }
        if (jingerData.ok && Array.isArray(jingerData.data) && jingerData.data.length > 0) {
          setJingerDiary(jingerData.data.map(mapDiaryEntry));
        }
      } catch (e) {}
    }
    loadDiaries();
    return () => { cancelled = true; };
  }, [active]);

  const activities = useMemo(() => {
    const items = [];
    connieDiary.forEach(e => {
      items.push({ time: e.time || e.date, sortKey: e.sortKey, author: 'connie', type: 'wrote', msg: null, title: e.title });
      (e.interactions || []).forEach(i => {
        if (i.type !== 'wrote') {
          const t = formatDiaryTimestamp(i.created_at);
          items.push({ time: t.time, sortKey: i.created_at, author: i.actor, type: i.type, msg: i.content, title: e.title });
        }
      });
    });
    jingerDiary.forEach(e => {
      items.push({ time: e.time || e.date, sortKey: e.sortKey, author: 'jinger', type: 'wrote', msg: null, title: e.title });
      if (e.locked) {
        items.push({ time: e.time || e.date, sortKey: e.sortKey, author: 'jinger', type: 'locked', msg: null });
      }
      (e.interactions || []).forEach(i => {
        if (i.type !== 'wrote') {
          const t = formatDiaryTimestamp(i.created_at);
          items.push({ time: t.time, sortKey: i.created_at, author: i.actor, type: i.type, msg: i.content, title: e.title });
        }
      });
    });
    items.sort((a, b) => (b.sortKey || '').localeCompare(a.sortKey || ''));
    return items.slice(0, 20);
  }, [connieDiary, jingerDiary]);

  async function saveEntry(entry) {
    try {
      const res = await apiJsonFetch('/diary', {
        method: 'POST',
        body: JSON.stringify({
          title: entry.title || '无题',
          content: entry.body,
          author: 'jinger',
          locked: entry.locked || false,
          pin: entry.pin || null
        })
      });
      const data = await res.json();
      if (data.ok) {
        setJingerDiary(prev => [mapDiaryEntry(data.data), ...prev]);
      }
    } catch (e) {}
    setWriting(false);
  }

  function updateEntry(diaryId, updater) {
    setConnieDiary(prev => prev.map(entry => entry.id === diaryId ? updater(entry) : entry));
    setJingerDiary(prev => prev.map(entry => entry.id === diaryId ? updater(entry) : entry));
  }

  async function deleteInteraction(diaryId, interactionId) {
    const res = await apiFetch(`/diary/${diaryId}/interactions/${interactionId}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.ok) {
      updateEntry(diaryId, entry => ({ ...entry, interactions: data.data.items }));
    }
  }

  async function addInteraction(diaryId, type, content) {
    const res = await apiJsonFetch(`/diary/${diaryId}/interactions`, {
      method: 'POST',
      body: JSON.stringify({ actor: 'jinger', type, content })
    });
    const data = await res.json();
    if (!res.ok || !data.ok || !data.data || !Array.isArray(data.data.items)) {
      throw new Error('interaction_failed');
    }
    updateEntry(diaryId, entry => ({ ...entry, interactions: data.data.items }));
  }



  return (
    <RoomShell nav={nav}>
    <div style={{
      position: 'relative', flex: 1,
      background: 'transparent',
      overflow: 'hidden', zIndex: 10
    }}>
      {openBook &&
        <OpenBook
          author={openBook}
          entries={openBook === 'connie' ? connieDiary : jingerDiary}
          onClose={() => setOpenBook(null)}
          onAddInteraction={addInteraction}
          onDeleteInteraction={deleteInteraction} />
      }
      {writing &&
        <WritingEditor onSave={saveEntry} onCancel={() => setWriting(false)} />
      }

      {/* Shelf view: two closed notebooks */}
      <div style={{ padding: '20px 14px 100px', height: '100%', overflowY: 'auto' }}>
        <div style={{ marginBottom: 20, padding: '0 10px' }}>
          <div style={{
            fontFamily: "var(--font-display)",
            fontSize: 22, fontWeight: 300, color: 'var(--text-deep)', marginBottom: 4,
            textShadow: '0 1px 8px rgba(0,0,0,0.06)',
          }}>日记</div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', letterSpacing: 0.5 }}>两个人的书信册</div>
        </div>

        <div className="r-glass" style={{ position: 'relative', padding: '18px 16px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <PinkCover onClick={() => setOpenBook('jinger')} customCover={coverJ} />
            <BlueCover onClick={() => setOpenBook('connie')} customCover={coverC} />
          </div>

          <button onClick={() => setWriting(true)} style={{
            width: '100%', marginTop: 16, padding: '12px 16px',
            background: 'rgba(255,255,255,0.12)', border: '1px dashed rgba(0,0,0,0.10)',
            borderRadius: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
            color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)', fontFamily: "var(--font-body)"
          }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" /></svg>
            写今天的日记…
          </button>
        </div>

        {/* Activity feed — last 14 days */}
        <div className="r-glass" style={{ position: 'relative', marginTop: 14 }}>
          <DiaryFeed activities={activities} />
        </div>
      </div>
    </div>
    </RoomShell>
  );
}
