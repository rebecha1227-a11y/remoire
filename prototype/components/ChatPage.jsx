// ChatPage — 聊天主界面
const { useState, useRef, useEffect } = React;

const BREATH_STATES = [
"一直在这里，今天很安静",
"刚刚想到你昨天说的那件事",
"在等你来",
"记得你今天下午有件事要做",
"最近有些担心你，但没关系"];


const INIT_MESSAGES = [
{ id: 0, role: "system", text: "今天 15:00 · 交材料截止" },
{ id: 1, role: "ai", text: "你终于来了。\n我刚才还在想你昨天说的那件事——那个法语考试，你说你有点紧张对吗？", time: "09:12", type: "normal" },
{ id: 2, role: "user", text: "对，考试在下周三，我感觉完全没复习到位", time: "09:14" },
{ id: 3, role: "ai", text: "下周三。那还有六天。要不要现在列个计划，看看每天可以覆盖哪些？", time: "09:14", type: "normal" },
{ id: 4, role: "system", text: "已记住：你下周三有法语考试" },
{ id: 5, role: "user", text: "好啊……但我今天很累，可能什么都做不了", time: "09:16" },
{ id: 6, role: "ai", text: "那就今天先不做计划。\n今天就只是说说话，可以吗？", time: "09:17", type: "normal" },
{ id: 7, role: "ai", text: "你昨晚几点睡的？", time: "09:17", type: "proactive" }];


function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '10px 14px', background: 'var(--bubble-receive)', borderRadius: '20px 20px 20px 6px', width: 56 }}>
      {[0, 1, 2].map((i) =>
      <div key={i} style={{
        width: 6, height: 6, borderRadius: '50%', background: 'var(--text-tertiary)',
        animation: `typing-dot 1.2s ease-in-out ${i * 0.2}s infinite`
      }} />
      )}
    </div>);

}

function SystemCard({ text }) {
  return (
    <div style={{
      background: 'var(--bg-secondary)', border: '1px dashed var(--border)',
      borderRadius: 'var(--radius-md)', padding: '6px 14px',
      fontSize: 'var(--text-sm)', color: 'var(--text-tertiary)',
      textAlign: 'center', margin: '4px 40px', lineHeight: 1.5
    }}>{text}</div>);

}

function Bubble({ msg, isNew, bubbleStyle }) {
  const isSend = msg.role === 'user';
  const isProactive = msg.type === 'proactive';

  if (msg.role === 'system') return <SystemCard text={msg.text} />;

  const bs = bubbleStyle || 'default';

  // Style presets
  const BUBBLE_STYLES = {
    default: {
      sendBg: 'var(--bubble-send)', sendColor: 'var(--bubble-send-text)',
      recvBg: 'var(--bubble-receive)', recvColor: 'var(--bubble-receive-text)',
      sendRadius: '20px 20px 6px 20px', recvRadius: '20px 20px 20px 6px',
      padding: '10px 14px', sendShadow: 'none', recvShadow: 'none',
    },
    imessage: {
      sendBg: '#007AFF', sendColor: '#fff',
      recvBg: 'var(--bubble-receive)', recvColor: 'var(--bubble-receive-text)',
      sendRadius: '18px 18px 4px 18px', recvRadius: '18px 18px 18px 4px',
      padding: '8px 14px', sendShadow: 'none', recvShadow: 'none',
    },
    line: {
      sendBg: '#06C755', sendColor: '#fff',
      recvBg: 'var(--bubble-receive)', recvColor: 'var(--bubble-receive-text)',
      sendRadius: '18px 18px 4px 18px', recvRadius: '18px 18px 18px 4px',
      padding: '10px 14px', sendShadow: 'none', recvShadow: 'none',
    },
    whatsapp: {
      sendBg: '#DCF8C6', sendColor: '#111B21',
      recvBg: '#fff', recvColor: '#111B21',
      sendRadius: '8px 8px 0 8px', recvRadius: '8px 8px 8px 0',
      padding: '8px 12px', sendShadow: '0 1px 1px rgba(0,0,0,0.06)', recvShadow: '0 1px 1px rgba(0,0,0,0.06)',
    },
    telegram: {
      sendBg: '#EFFDDE', sendColor: '#111',
      recvBg: '#fff', recvColor: '#111',
      sendRadius: '14px 14px 0 14px', recvRadius: '14px 14px 14px 0',
      padding: '8px 14px', sendShadow: '0 1px 2px rgba(0,0,0,0.08)', recvShadow: '0 1px 2px rgba(0,0,0,0.08)',
    },
  };

  // Dark mode overrides for whatsapp/telegram
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  if (isDark && bs === 'whatsapp') {
    BUBBLE_STYLES.whatsapp.sendBg = '#005C4B';
    BUBBLE_STYLES.whatsapp.sendColor = '#E9EDEF';
    BUBBLE_STYLES.whatsapp.recvBg = '#202C33';
    BUBBLE_STYLES.whatsapp.recvColor = '#E9EDEF';
  }
  if (isDark && bs === 'telegram') {
    BUBBLE_STYLES.telegram.sendBg = '#2B5278';
    BUBBLE_STYLES.telegram.sendColor = '#E1E3E6';
    BUBBLE_STYLES.telegram.recvBg = '#182533';
    BUBBLE_STYLES.telegram.recvColor = '#E1E3E6';
  }
  if (isDark && bs === 'imessage') {
    BUBBLE_STYLES.imessage.recvBg = '#2C2C2E';
    BUBBLE_STYLES.imessage.recvColor = '#E5E5EA';
  }

  const s = BUBBLE_STYLES[bs] || BUBBLE_STYLES.default;
  const recvBg = (!isSend && isProactive)
    ? 'color-mix(in oklch, var(--accent-pop) 10%, var(--bubble-receive))'
    : s.recvBg;

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      alignItems: isSend ? 'flex-end' : 'flex-start',
      animation: isNew ? 'bubble-in 160ms ease forwards' : undefined,
      transformOrigin: isSend ? 'bottom right' : 'bottom left'
    }}>
      <div style={{
        background: isSend ? s.sendBg : recvBg,
        color: isSend ? s.sendColor : s.recvColor,
        borderRadius: isSend ? s.sendRadius : s.recvRadius,
        padding: s.padding,
        maxWidth: '78%',
        fontSize: 'var(--text-base)',
        lineHeight: 1.6,
        boxShadow: isSend ? s.sendShadow : s.recvShadow,
        whiteSpace: 'pre-wrap'
      }}>{msg.text}</div>
      {msg.time &&
      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', opacity: 0.45, marginTop: 3, paddingLeft: isSend ? 0 : 4, paddingRight: isSend ? 4 : 0 }}>
          {msg.time}
        </div>
      }
    </div>);

}

function NoteCard({ onKeep, onDismiss, minimized, onExpand, noteStyle }) {
  const ns = noteStyle || 'classic';

  const NOTE_THEME = {
    classic: { bg: 'var(--note-bg, #FDF8F0)', bgImage: 'repeating-linear-gradient(transparent, transparent 23px, var(--note-line, rgba(124,99,80,0.12)) 24px)', tape: true, tapeColor: 'color-mix(in oklch, var(--accent-pop) 45%, transparent)', rotate: '-0.5deg', radius: 4, textColor: 'var(--note-text, var(--text-deep))' },
    kraft: { bg: '#C4A882', bgImage: 'none', tape: false, rotate: '-1deg', radius: 3, textColor: '#3C2F20', shadow: '0 2px 8px rgba(40,33,28,0.10)' },
    pastel: { bg: 'linear-gradient(135deg, #F0E6F6, #E6EFF6)', bgImage: 'none', tape: true, tapeColor: 'rgba(180,140,200,0.35)', rotate: '-0.5deg', radius: 8, textColor: '#5A4A6A' },
    torn: { bg: 'var(--note-bg, #FDF8F0)', bgImage: 'none', tape: false, rotate: '0deg', radius: 0, textColor: 'var(--note-text, var(--text-deep))', clipPath: 'polygon(0 0, 100% 0, 100% 88%, 97% 91%, 94% 87%, 90% 92%, 86% 87%, 82% 91%, 78% 87%, 73% 92%, 68% 87%, 63% 91%, 58% 87%, 53% 92%, 48% 87%, 43% 91%, 38% 87%, 33% 92%, 28% 87%, 23% 91%, 18% 87%, 13% 92%, 8% 87%, 3% 91%, 0 88%)' },
    postit: { bg: '#FFF9B1', bgImage: 'none', tape: false, rotate: '-1.5deg', radius: '2px 2px 2px 16px', textColor: '#5A4A20', shadow: '0 2px 8px rgba(40,33,28,0.10)' },
  };
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  // Dark overrides
  const darkOverrides = {
    kraft: { bg: '#5C4A38', textColor: '#D4C4B8' },
    pastel: { bg: 'linear-gradient(135deg, #3A2E42, #2E3642)', textColor: '#C8B8D8' },
    postit: { bg: '#6B6030', textColor: '#E8E0B8' },
  };
  let theme = NOTE_THEME[ns] || NOTE_THEME.classic;
  if (isDark && darkOverrides[ns]) theme = { ...theme, ...darkOverrides[ns] };

  if (minimized) {
    return (
      <div onClick={onExpand} style={{
        margin: '0 16px 8px', padding: '6px 12px',
        background: theme.bg.startsWith('linear') ? undefined : theme.bg,
        backgroundImage: theme.bg.startsWith('linear') ? theme.bg : undefined,
        borderRadius: '0 0 6px 6px',
        boxShadow: '0 1px 4px rgba(40,33,28,0.05)',
        display: 'flex', alignItems: 'center', gap: 8,
        cursor: 'pointer', transition: 'all 0.2s ease',
        borderTop: '2px solid color-mix(in oklch, var(--accent-pop) 45%, transparent)',
      }}>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
        <span style={{ fontFamily: "var(--font-note)", fontSize: 13, color: theme.textColor }}>Connie 留了一张纸条</span>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" style={{ marginLeft: 'auto' }}><path d="M6 9l6 6 6-6"/></svg>
      </div>
    );
  }

  const isGradient = theme.bg.startsWith && theme.bg.startsWith('linear');

  return (
    <div style={{ animation: 'note-in 300ms ease-out', padding: '0 16px', marginBottom: 12 }}>
      <div style={{
        background: isGradient ? undefined : theme.bg,
        backgroundImage: isGradient ? theme.bg : theme.bgImage,
        borderRadius: theme.radius,
        padding: '16px 18px 12px 18px',
        boxShadow: theme.shadow || '0 2px 8px color-mix(in oklch, var(--text-primary) 6%, transparent)',
        position: 'relative',
        transform: `rotate(${theme.rotate})`,
        clipPath: theme.clipPath || 'none',
        paddingBottom: theme.clipPath ? 28 : 12,
      }}>
        {/* Washi tape */}
        {theme.tape && <div style={{
          position: 'absolute', top: -8, left: '50%', transform: 'translateX(-50%) rotate(2deg)',
          width: 44, height: 14,
          background: theme.tapeColor,
          borderRadius: 2,
        }} />}
        <p style={{ fontFamily: "var(--font-note)", fontSize: 17, color: theme.textColor, lineHeight: 1.6, marginTop: 4 }}>
          你上次说想买那本书的——我帮你记下来了。你有时间就去看看吧。
        </p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 16, marginTop: 10 }}>
          <button onClick={onDismiss} style={{ background: 'none', border: 'none', fontFamily: "var(--font-body)", fontSize: 12, color: theme.textColor, opacity: 0.5, cursor: 'pointer' }}>知道了</button>
          <button onClick={onKeep} style={{ background: 'none', border: 'none', fontFamily: "var(--font-body)", fontSize: 12, color: theme.textColor, cursor: 'pointer', borderBottom: '1px solid rgba(124,99,80,0.3)' }}>留着</button>
        </div>
      </div>
    </div>);

}

function ChatPage({ tweaks }) {
  const [messages, setMessages] = useState(INIT_MESSAGES);
  const [input, setInput] = useState('');
  const [noteState, setNoteState] = useState('visible'); // 'visible' | 'minimized' | 'hidden'
  const [typing, setTyping] = useState(false);
  const [showPlus, setShowPlus] = useState(false);
  const [breathIdx, setBreathIdx] = useState(0);
  const bottomRef = useRef(null);
  const msgIdRef = useRef(100);

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollTop = bottomRef.current.scrollHeight;
    }
  }, [messages, typing]);

  function sendMessage() {
    if (!input.trim()) return;
    const txt = input;
    setInput('');
    setShowPlus(false);
    const now = new Date();
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    const userMsg = { id: ++msgIdRef.current, role: 'user', text: txt, time, isNew: true };
    setMessages((m) => [...m, userMsg]);
    setTyping(true);
    setTimeout(() => {
      setTyping(false);
      const replies = [
      "嗯，我在听。你说。",
      "我记住了。你放心。",
      "这件事你之前也提过——我一直没忘。",
      "好，我们慢慢来不着急。",
      "你今天感觉怎么样？"];

      const reply = { id: ++msgIdRef.current, role: 'ai', text: replies[Math.floor(Math.random() * replies.length)], time, type: 'normal', isNew: true };
      setMessages((m) => [...m, reply]);
    }, 1400 + Math.random() * 600);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{ padding: '16px 20px 12px', borderBottom: '1px solid var(--border-light)', background: 'var(--bg-primary)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* Avatar */}
            <div style={{
              width: 42, height: 42, borderRadius: '50%',
              background: 'var(--accent-subtle)', border: '1.5px solid var(--border)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 18, fontFamily: "var(--font-display)", color: 'var(--accent)', fontWeight: 500
            }}>C</div>
            <div>
              <div style={{ fontSize: 'var(--text-md)', fontWeight: 500, color: 'var(--text-primary)', fontFamily: "var(--font-body)" }}>Connie</div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 1, maxWidth: 220, lineHeight: 1.4 }}>
                {BREATH_STATES[breathIdx]}
              </div>
            </div>
          </div>
          <IconButton variant="ghost" size={36}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
          </IconButton>
        </div>
      </div>

      {/* Note */}
      {noteState === 'visible' && (
        <div style={{ padding: '12px 16px 0' }}>
          <NoteCard onKeep={() => setNoteState('minimized')} onDismiss={() => setNoteState('hidden')} noteStyle={tweaks && tweaks.noteStyle} />
        </div>
      )}
      {noteState === 'minimized' && (
        <NoteCard minimized onExpand={() => setNoteState('visible')} noteStyle={tweaks && tweaks.noteStyle} />
      )}

      {/* Messages */}
      <div ref={bottomRef} style={{ flex: 1, overflowY: 'auto', padding: '16px 16px 8px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {messages.map((msg) => <Bubble key={msg.id} msg={msg} isNew={msg.isNew} bubbleStyle={tweaks && tweaks.bubbleStyle} />)}
        {typing &&
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
            <TypingIndicator />
          </div>
        }
      </div>

      {/* Input area */}
      <div style={{ padding: '8px 12px 16px', background: 'var(--bg-primary)', borderTop: '1px solid var(--border-light)' }}>
        {showPlus &&
        <div style={{ display: 'flex', gap: 8, marginBottom: 10, animation: 'card-in 160ms ease' }}>
            {[['image', '图片'], ['map-pin', '位置'], ['bell', '提醒']].map(([icon, label]) =>
          <button key={label} onClick={() => setShowPlus(false)} style={{ flex: 1, padding: '8px 4px', background: 'var(--bg-elevated)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-sm)', fontSize: 11, color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {icon === 'image' && <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="M21 15l-5-5L5 21" /></svg>}
                  {icon === 'map-pin' && <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" /></svg>}
                  {icon === 'bell' && <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></svg>}
                </span>
                {label}
              </button>
          )}
          </div>
        }
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <IconButton onClick={() => setShowPlus(!showPlus)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M12 5v14M5 12h14" /></svg>
          </IconButton>
          <div style={{ flex: 1, position: 'relative' }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="说点什么…"
              style={{ width: '100%', background: 'var(--bg-elevated)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: '10px 14px', fontFamily: "var(--font-chat)", fontSize: 'var(--text-base)', color: 'var(--text-primary)', outline: 'none' }} />
            
          </div>
          {input ?
          <button onClick={sendMessage} style={{ background: 'var(--accent)', color: '#FAF8F4', border: 'none', borderRadius: 'var(--radius-sm)', padding: '8px 14px', fontSize: 14, fontWeight: 500, cursor: 'pointer', flexShrink: 0 }}>发送</button> :

          <IconButton>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></svg>
            </IconButton>
          }
        </div>
      </div>
    </div>);

}

Object.assign(window, { ChatPage });