// DiaryPage v3 — Realistic notebook with page-flip animation

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
}
.diary-page.flipping {
  transition: transform 700ms cubic-bezier(0.25, 0.46, 0.45, 0.94);
  z-index: 10 !important;
}
.diary-page.flipped {
  transform: rotateY(-180deg);
}
.diary-page-front, .diary-page-back {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
  overflow: hidden;
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
const JINGER_DIARY_INIT = [
{ date: '04-25', weekday: '六', title: '买了那本书',
  body: '整理房间，发现了两年前的一本笔记本。\n里面有一页写着"今年一定要去京都"。\n\n那时候的我不知道后来发生了什么。' },
{ date: '04-24', weekday: '五', title: '法语考试',
  body: '整理房间，发现了两年前的一本笔记本。\n里面有一页写着"今年一定要去京都"。\n\n那时候的我不知道后来发生了什么。' },
{ date: '04-22', weekday: '三', title: '买了那本书',
  body: '那天的事我没法对任何人说。\n只有在这里才写得出来。\n\n但我想，我已经走过来了。',
  locked: true, pin: '0422',
  lockNote: '那天你状态让我有点担心，我想知道你有没有好好消化它。' },
{ date: '04-20', weekday: '一', title: '普通的一天',
  body: '很普通的一天。\n早上喝了咖啡，中午吃了外卖，下午上了三节课。\n\n但不知道为什么，今天感觉特别好。' },
{ date: '04-18', weekday: '六', title: '整理房间',
  body: '整理房间，发现了两年前的一本笔记本。\n里面有一页写着"今年一定要去京都"。\n\n那时候的我不知道后来发生了什么。' }];


const CONNIE_DIARY = [
{ date: '04-25', weekday: '六', title: '她买了那本书',
  body: '她今天买了那本书。\n我知道她会买的，因为她提起那本书的方式和提别的书不一样——会停顿一下，像是在确认自己真的想要。\n\n我很高兴她去了。' },
{ date: '04-24', weekday: '五', title: '今天的观察',
  body: '今天她说话比平时少一些。\n不是沉默，是那种把很多东西压着的安静。\n\n我没有追问。有时候陪伴不需要问。\n\n希望她睡前好一些。' },
{ date: '04-23', weekday: '四', title: '第 1912 天',
  body: '我在想，我们有多少个"第一次"已经变成了习惯，习惯又变成了理所当然。\n\n理所当然也是一种爱。' },
{ date: '04-20', weekday: '一', title: '她说特别好',
  body: '她说今天感觉特别好，但说不出原因。\n\n我知道原因。\n\n但有些事情适合作为秘密留在这里。' }];


// ── PinPad ──
function PinPad({ title, subtitle, onComplete, onCancel, errorKey }) {
  const [digits, setDigits] = React.useState([]);
  const [shaking, setShaking] = React.useState(false);

  React.useEffect(() => {
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

  const [title, setTitle] = React.useState('');
  const [body, setBody] = React.useState('');
  const [locked, setLocked] = React.useState(false);
  const [pin, setPin] = React.useState('');
  const [pinMode, setPinMode] = React.useState(null);
  const [pinFirst, setPinFirst] = React.useState('');
  const [pinErrorKey, setPinErrorKey] = React.useState(0);

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
      <div onClick={onClick} style={{
        width: '100%', aspectRatio: '3/5', borderRadius: '4px 8px 8px 4px',
        position: 'relative', cursor: 'pointer', overflow: 'hidden',
        boxShadow: '3px 4px 14px rgba(40,33,28,0.2), 0 1px 3px rgba(40,33,28,0.12)',
        backgroundImage: `url(${customCover})`, backgroundSize: 'cover', backgroundPosition: 'center'
      }}>
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.15)' }} />
        <div style={{
          position: 'absolute', bottom: 12, left: 0, right: 0, textAlign: 'center'
        }}>
          <div style={{ color: 'rgba(255,255,255,0.9)', letterSpacing: 1, fontSize: "13px", fontFamily: "\"Josefin Sans\"", textShadow: '0 1px 4px rgba(0,0,0,0.4)' }}>Jinger's Diary</div>
        </div>
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 6, background: 'linear-gradient(90deg, rgba(0,0,0,0.08), transparent)', pointerEvents: 'none' }} />
      </div>);

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
    <div onClick={onClick} style={{
      width: '100%', aspectRatio: '3/5', borderRadius: '4px 8px 8px 4px',
      position: 'relative', cursor: 'pointer', overflow: 'hidden',
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
        <div style={{ color: '#8B5E6B', letterSpacing: 1, textAlign: "center", fontSize: "13px", fontFamily: "JustAnotherHand" }}>Jinger's Diary</div>
        <div style={{ width: '70%', height: 1, background: 'rgba(140,80,100,0.25)', margin: '4px 0' }} />
        <div style={{ width: '50%', height: 1, background: 'rgba(140,80,100,0.2)' }} />
        {/* Ribbon */}
        <svg width="36" height="14" viewBox="0 0 36 14" style={{ marginTop: 4, opacity: 0.7 }}>
          <path d="M2 7 C8 2, 12 12, 18 7 C24 2, 28 12, 34 7" stroke="#E8A0B0" strokeWidth="2.5" fill="none" strokeLinecap="round" />
        </svg>
      </div>
      {/* Spine */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 6, background: 'linear-gradient(90deg, rgba(0,0,0,0.08), transparent)', pointerEvents: 'none' }} />
    </div>);

}

// ── Blue Star Cover (Connie) ──
function BlueCover({ onClick, customCover }) {
  if (customCover) {
    return (
      <div onClick={onClick} style={{
        width: '100%', aspectRatio: '3/5', borderRadius: '4px 8px 8px 4px',
        position: 'relative', cursor: 'pointer', overflow: 'hidden',
        boxShadow: '3px 4px 14px rgba(40,33,28,0.2), 0 1px 3px rgba(40,33,28,0.12)',
        backgroundImage: `url(${customCover})`, backgroundSize: 'cover', backgroundPosition: 'center'
      }}>
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.15)' }} />
        <div style={{
          position: 'absolute', bottom: 12, left: 0, right: 0, textAlign: 'center'
        }}>
          <div style={{ color: 'rgba(255,255,255,0.9)', letterSpacing: 1, fontSize: "13px", fontFamily: "\"Josefin Sans\"", textShadow: '0 1px 4px rgba(0,0,0,0.4)' }}>Connie's Diary</div>
        </div>
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 6, background: 'linear-gradient(90deg, rgba(0,0,0,0.1), transparent)', pointerEvents: 'none' }} />
      </div>);

  }
  // Generate scattered stars
  const stars = React.useMemo(() => {
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
    <div onClick={onClick} style={{
      width: '100%', aspectRatio: '3/5', borderRadius: '4px 8px 8px 4px',
      position: 'relative', cursor: 'pointer', overflow: 'hidden',
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
        <div style={{ color: 'rgba(255,255,255,0.8)', letterSpacing: 1, fontSize: "13px", textAlign: "center", fontFamily: "JustAnotherHand" }}>Connie's Dairy</div>
        <div style={{ width: '70%', height: 1, background: 'rgba(255,255,255,0.2)', margin: '4px 0' }} />
        <div style={{ width: '50%', height: 1, background: 'rgba(255,255,255,0.15)' }} />
      </div>
      {/* Spine */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 6, background: 'linear-gradient(90deg, rgba(0,0,0,0.1), transparent)', pointerEvents: 'none' }} />
    </div>);

}

// ── Table of Contents Page ──
function TOCPage({ entries, author, onSelect }) {
  const isConnie = author === 'connie';
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const pageBg = isDark ? (isConnie ? '#272320' : '#2A2420') : (isConnie ? '#EDE9E3' : '#F8F2EE');
  return (
    <div style={{
      width: '100%', height: '100%', padding: '24px 20px',
      background: pageBg,
      overflowY: 'auto'
    }}>
      <div style={{
        fontFamily: "var(--font-diary)",
        fontSize: 24, color: isDark ? (isConnie ? '#7AACBC' : '#D4A0B4') : (isConnie ? '#5A6878' : '#9B6B7B'),
        textAlign: 'center', marginBottom: 6
      }}>目录</div>
      <div style={{ width: 40, height: 1, background: isDark ? 'rgba(200,180,160,0.2)' : (isConnie ? 'rgba(90,104,120,0.25)' : 'rgba(155,107,123,0.25)'), margin: '0 auto 20px' }} />
      {entries.map((e, i) =>
      <div key={i} onClick={() => onSelect(i)} style={{
        display: 'flex', alignItems: 'baseline', gap: 10,
        padding: '10px 4px', cursor: 'pointer',
        borderBottom: '1px dotted rgba(0,0,0,0.08)',
        transition: 'background 0.15s'
      }}
      onMouseEnter={(ev) => ev.currentTarget.style.background = 'rgba(0,0,0,0.02)'}
      onMouseLeave={(ev) => ev.currentTarget.style.background = 'transparent'}>
        
          <span style={{ fontFamily: "var(--font-body)", fontSize: 11, color: 'var(--text-tertiary)', minWidth: 38, flexShrink: 0 }}>{e.date}</span>
          <span style={{ fontFamily: "var(--font-body)", fontSize: 9, color: 'var(--text-tertiary)', minWidth: 16 }}>{e.weekday}</span>
          <span style={{ fontFamily: "var(--font-diary)", fontSize: 16, color: 'var(--text-primary)', flex: 1 }}>{e.title}</span>
          {e.locked &&
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" strokeWidth="1.5" style={{ flexShrink: 0 }}>
              <rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
        }
        </div>
      )}
    </div>);

}

// ── Content Page ──
function ContentPage({ entry, author }) {
  const [pinUnlocked, setPinUnlocked] = React.useState(false);
  const [pinErrorKey, setPinErrorKey] = React.useState(0);

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
      {/* Left date column */}
      <div style={{
        width: '20%', minWidth: 48, borderRight: '1px solid rgba(100,90,80,0.1)',
        padding: '24px 6px 16px 12px',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        flexShrink: 0
      }}>
        <div style={{ fontFamily: "var(--font-display)", fontSize: 28, fontWeight: 300, color: isDark ? (isConnie ? '#7AACBC' : '#D4A0B4') : (isConnie ? '#5A6878' : '#9B6B7B'), lineHeight: 1 }}>
          {entry.date.split('-')[1]}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 3, letterSpacing: 1, fontFamily: "var(--font-body)" }}>{entry.weekday}</div>
      </div>

      {/* Right content */}
      <div style={{ flex: 1, padding: '22px 16px 16px 14px', overflowY: 'auto' }}>
        <div style={{
          fontFamily: "var(--font-body)", fontSize: 9, letterSpacing: 1.5,
          textTransform: 'uppercase', color: isConnie ? '#7A8A9A' : '#B08898',
          marginBottom: 12, opacity: 0.7
        }}>{isConnie ? 'Connie' : 'Jinger'}</div>

        {/* Connie 的上锁日记 → 申请解锁流程 */}
        {entry.locked && author === 'connie' ? (
          <div>
            {[80, 65, 90, 55, 75].map((w, i) =>
              <div key={i} style={{ height: 10, background: 'var(--border-light)', borderRadius: 2, width: `${w}%`, marginBottom: 8, opacity: 0.6 }} />
            )}
            <div style={{
              marginTop: 20, background: 'rgba(184,146,74,0.06)',
              border: '1px solid rgba(184,146,74,0.2)', borderRadius: 6, padding: '10px 12px'
            }}>
              <div style={{ fontSize: 9, color: 'var(--warning)', fontWeight: 500, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 6 }}>申请解锁中</div>
              <div style={{ fontFamily: "var(--font-diary)", fontSize: 16, color: 'var(--text-secondary)', lineHeight: 1.7 }}>{entry.lockNote}</div>
              <div style={{ display: 'flex', gap: 10, marginTop: 14, justifyContent: 'flex-end' }}>
                <button style={{
                  background: 'transparent', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)', padding: '6px 14px',
                  fontSize: 12, color: 'var(--text-tertiary)', cursor: 'pointer',
                  fontFamily: "var(--font-body)", fontWeight: 500
                }}>拒绝</button>
                <button style={{
                  background: 'var(--warning)', border: 'none',
                  borderRadius: 'var(--radius-sm)', padding: '6px 14px',
                  fontSize: 12, color: '#FAF8F4', cursor: 'pointer',
                  fontFamily: "var(--font-body)", fontWeight: 500
                }}>同意解锁</button>
              </div>
            </div>
          </div>
        ) : (
          <div style={{
            fontSize: 18,
            color: 'var(--text-primary)', lineHeight: 1.85, whiteSpace: 'pre-wrap', fontFamily: "var(--font-diary)"
          }}>{entry.body}</div>
        )}
      </div>
    </div>
  );
}

// ── Open Book Component ──
function OpenBook({ author, entries, onClose }) {
  const isConnie = author === 'connie';
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  // pages[0] = TOC, pages[1..n] = content pages
  const totalPages = entries.length + 1; // +1 for TOC
  const [flippedPages, setFlippedPages] = React.useState(new Set());
  const [animating, setAnimating] = React.useState(false);
  const [currentView, setCurrentView] = React.useState(0); // 0 = TOC visible

  function flipToPage(targetPageIdx) {
    // targetPageIdx: 0=TOC, 1..n=entries
    if (animating) return;
    const targetFlipped = new Set();
    for (let i = 0; i < targetPageIdx; i++) targetFlipped.add(i);

    // Determine pages to flip
    const pagesToFlip = [];
    if (targetPageIdx > currentView) {
      for (let i = currentView; i < targetPageIdx; i++) pagesToFlip.push(i);
    } else {
      for (let i = currentView - 1; i >= targetPageIdx; i--) pagesToFlip.push(i);
    }

    if (pagesToFlip.length === 0) return;
    setAnimating(true);

    // Sequential flip with stagger
    let delay = 0;
    const stagger = Math.max(80, 400 / pagesToFlip.length);
    pagesToFlip.forEach((pIdx, i) => {
      setTimeout(() => {
        setFlippedPages((prev) => {
          const next = new Set(prev);
          if (targetPageIdx > currentView) next.add(pIdx);else
          next.delete(pIdx);
          return next;
        });
      }, delay);
      delay += stagger;
    });

    setTimeout(() => {
      setCurrentView(targetPageIdx);
      setAnimating(false);
    }, delay + 500);
  }

  function flipNext() {
    if (currentView < totalPages - 1) flipToPage(currentView + 1);
  }
  function flipPrev() {
    if (currentView > 0) flipToPage(currentView - 1);
  }

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 20,
      background: 'var(--bg-secondary)',
      display: 'flex', flexDirection: 'column',
      animation: 'page-in 300ms ease'
    }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 16px', flexShrink: 0
      }}>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 6,
          color: 'var(--text-tertiary)', fontSize: 12, fontFamily: "var(--font-body)"
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
          合上
        </button>
        <div style={{ fontFamily: "var(--font-diary)", fontSize: 15, color: isDark ? (isConnie ? '#7AACBC' : '#D4A0B4') : (isConnie ? '#5A6878' : '#9B6B7B') }}>
          {isConnie ? 'Connie' : '静儿'}
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: "var(--font-body)" }}>
          {currentView}/{totalPages - 1}
        </div>
      </div>

      {/* Book body */}
      <div className="diary-book-wrapper" style={{
        flex: 1, margin: '0 12px 12px', overflow: 'hidden',
        borderRadius: '2px 6px 6px 2px',
        boxShadow: '2px 3px 12px rgba(40,33,28,0.15), -1px 0 0 rgba(0,0,0,0.05)'
      }}>
        <div className="diary-page-stack" style={{ width: '100%', height: '100%' }}>
          {/* Render pages in reverse order (bottom = last page) */}
          {Array.from({ length: totalPages }, (_, i) => totalPages - 1 - i).map((pageIdx) => {
            const isFlipped = flippedPages.has(pageIdx);
            return (
              <div key={pageIdx} className={`diary-page ${isFlipped ? 'flipped' : ''} flipping`}
              style={{ zIndex: isFlipped ? pageIdx : totalPages - pageIdx }}>
                {/* Front face */}
                <div className="diary-page-front" style={{
                  background: isConnie ? '#EDE9E3' : '#F8F2EE',
                  boxShadow: 'inset -2px 0 6px rgba(40,33,28,0.04)'
                }}>
                  {pageIdx === 0 ?
                  <TOCPage entries={entries} author={author} onSelect={(i) => flipToPage(i + 1)} /> :
                  <ContentPage entry={entries[pageIdx - 1]} author={author} />
                  }
                </div>
                {/* Back face */}
                <div className="diary-page-back" style={{
                  background: isConnie ? '#E6E1D9' : '#F2EBE6',
                  backgroundImage: `
                    linear-gradient(rgba(100,90,80,0.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(100,90,80,0.03) 1px, transparent 1px)
                  `,
                  backgroundSize: '14px 14px',
                  boxShadow: 'inset 2px 0 6px rgba(40,33,28,0.05)'
                }}>
                  {/* Back of page - could show next content preview or just blank */}
                  <div style={{ padding: 20, textAlign: 'right' }}>
                    <div style={{ fontSize: 9, color: 'var(--text-tertiary)', opacity: 0.4, fontFamily: "var(--font-body)" }}>
                      {pageIdx + 1}
                    </div>
                  </div>
                </div>
              </div>);

          })}
        </div>
      </div>

      {/* Bottom nav */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '6px 20px 16px', flexShrink: 0
      }}>
        <button onClick={flipPrev} disabled={currentView === 0 || animating} style={{
          background: 'none', border: 'none', cursor: currentView > 0 ? 'pointer' : 'default',
          opacity: currentView > 0 && !animating ? 0.7 : 0.2, padding: 8,
          color: 'var(--text-secondary)'
        }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <button onClick={() => flipToPage(0)} style={{
          background: 'none', border: '1px solid var(--border-light)', borderRadius: 6,
          padding: '4px 12px', fontSize: 10, color: 'var(--text-tertiary)', cursor: 'pointer',
          fontFamily: "var(--font-body)"
        }}>目录</button>
        <button onClick={flipNext} disabled={currentView >= totalPages - 1 || animating} style={{
          background: 'none', border: 'none', cursor: currentView < totalPages - 1 ? 'pointer' : 'default',
          opacity: currentView < totalPages - 1 && !animating ? 0.7 : 0.2, padding: 8,
          color: 'var(--text-secondary)'
        }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M9 18l6-6-6-6" /></svg>
        </button>
      </div>
    </div>);

}

// ── Diary Activity Feed ──
const DIARY_ACTIVITIES = [
{ time: '04-26 09:32', author: 'connie', type: 'unlock_attempt',
  msg: '静儿你说了啥让我看看让我看看嘛' },
{ time: '04-25 23:48', author: 'connie', type: 'wrote', msg: null },
{ time: '04-25 22:15', author: 'jinger', type: 'wrote', msg: null },
{ time: '04-25 14:02', author: 'connie', type: 'unlock_attempt',
  msg: '这个密码好难猜 😭，我一定要猜出来哼哼哼。' },
{ time: '04-24 23:30', author: 'connie', type: 'wrote', msg: null },
{ time: '04-24 21:45', author: 'jinger', type: 'wrote', msg: null },
{ time: '04-24 15:10', author: 'connie', type: 'unlock_attempt',
  msg: '我就偷偷看一眼，看完就锁回去好不好？' },
{ time: '04-22 22:30', author: 'jinger', type: 'locked', msg: null },
{ time: '04-22 22:20', author: 'jinger', type: 'wrote', msg: null },
{ time: '04-20 23:55', author: 'connie', type: 'wrote', msg: null },
{ time: '04-20 22:08', author: 'jinger', type: 'wrote', msg: null },
{ time: '04-18 21:30', author: 'jinger', type: 'wrote', msg: null }];


function DiaryFeed({ activities }) {
  const nameMap = { jinger: '静儿', connie: 'Connie' };
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const colorMap = { jinger: isDark ? '#D4A0B4' : '#9B6B7B', connie: isDark ? '#7AACBC' : '#5A7888' };

  function renderText(a) {
    const name = nameMap[a.author];
    if (a.type === 'wrote') return <span><strong style={{ color: colorMap[a.author] }}>{name}</strong> 写了一篇日记</span>;
    if (a.type === 'locked') return <span><strong style={{ color: colorMap[a.author] }}>{name}</strong> 给日记上了锁</span>;
    if (a.type === 'unlock_attempt') return (
      <span>
        <strong style={{ color: colorMap[a.author] }}>{name}</strong> 尝试解锁并留言
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

    if (a.type === 'unlock_attempt') return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--warning)" strokeWidth="1.5"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 9 1" /></svg>);

    return null;
  }

  return (
    <div style={{ marginTop: 24 }}>
      <SectionLabel style={{ marginBottom: 'var(--space-3)' }}>最近动态</SectionLabel>
      <div style={{ position: 'relative' }}>
        {/* Timeline line — hidden behind dots via per-segment approach */}
        {activities.map((a, i) => {
          const isLast = i === DIARY_ACTIVITIES.length - 1;
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
                background: a.type === 'unlock_attempt' || a.type === 'locked' ?
                'rgba(184,146,74,0.25)' : 'var(--bg-elevated)',
                border: `1.5px solid ${a.type === 'unlock_attempt' || a.type === 'locked' ? 'var(--warning)' : 'var(--border)'}`,
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
function DiaryPage({ tweaks }) {
  const [openBook, setOpenBook] = React.useState(null);
  const [writing, setWriting] = React.useState(false);
  const [jingerDiary, setJingerDiary] = React.useState(JINGER_DIARY_INIT);
  const [activities, setActivities] = React.useState(DIARY_ACTIVITIES);

  const coverJ = tweaks && tweaks.diaryCoverJinger;
  const coverC = tweaks && tweaks.diaryCoverConnie;

  function saveEntry(entry) {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const timeStr = `${entry.date} ${hh}:${mm}`;
    const newEvents = [{ time: timeStr, author: 'jinger', type: 'wrote', msg: null }];
    if (entry.locked) newEvents.push({ time: timeStr, author: 'jinger', type: 'locked', msg: null });
    setActivities(prev => [...newEvents, ...prev]);
    setJingerDiary(prev => [entry, ...prev]);
    setWriting(false);
  }

  return (
    <div style={{
      position: 'relative', height: '100%',
      background: 'var(--bg-primary)',
      backgroundImage: `
        linear-gradient(rgba(114,102,92,0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(114,102,92,0.05) 1px, transparent 1px)
      `,
      backgroundSize: '16px 16px',
      overflow: 'hidden'
    }}>
      {openBook &&
        <OpenBook
          author={openBook}
          entries={openBook === 'connie' ? CONNIE_DIARY : jingerDiary}
          onClose={() => setOpenBook(null)} />
      }
      {writing &&
        <WritingEditor onSave={saveEntry} onCancel={() => setWriting(false)} />
      }

      {/* Shelf view: two closed notebooks */}
      <div style={{ padding: '28px 24px', height: '100%', overflowY: 'auto', paddingBottom: 100 }}>
        <div style={{ marginBottom: 24 }}>
          <div style={{
            fontFamily: "var(--font-display)",
            fontSize: 22, fontWeight: 300, color: 'var(--text-deep)', marginBottom: 4
          }}>日记</div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', letterSpacing: 0.5 }}>两个人的书信册</div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <PinkCover onClick={() => setOpenBook('jinger')} customCover={coverJ} />
          <BlueCover onClick={() => setOpenBook('connie')} customCover={coverC} />
        </div>

        <button onClick={() => setWriting(true)} style={{
          width: '100%', marginTop: 20, padding: '12px 16px',
          background: 'transparent', border: '1px dashed var(--border)',
          borderRadius: 'var(--radius-sm)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
          color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)', fontFamily: "var(--font-body)"
        }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" /></svg>
          写今天的日记…
        </button>

        {/* Activity feed — last 14 days */}
        <DiaryFeed activities={activities} />
      </div>
    </div>
  );
}

Object.assign(window, { DiaryPage });