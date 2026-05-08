// ChatPage — 聊天主界面
const { useState, useRef, useEffect } = React;

function formatBJTime(utcStr) {
  if (!utcStr) return '';
  const d = new Date(utcStr + (utcStr.endsWith('Z') ? '' : 'Z'));
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Shanghai' });
}

const BG_PRESETS = [
  { label: '默认', value: '' },
  { label: '暖白', value: '#F5EDE0' },
  { label: '茶绿', value: '#E4EDDF' },
  { label: '云蓝', value: '#DDE8F0' },
  { label: '玫雾', value: '#F0E0E6' },
  { label: '烟灰', value: '#E8E5E0' },
];

const BREATH_STATES = [
"一直在这里，今天很安静",
"刚刚想到你昨天说的那件事",
"在等你来",
"记得你今天下午有件事要做",
"最近有些担心你，但没关系"];


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

function Bubble({ msg, isNew, bubbleStyle, showAvatar, showTail, thinkingExpanded, onToggleThinking, bgColor, avatarConfig }) {
  const isSend = msg.role === 'user';
  const isProactive = msg.type === 'proactive';

  if (msg.role === 'system') return <SystemCard text={msg.text} />;

  const { connieAvatar, jingAvatar, showConnieAvatarInChat = true, showJingAvatarInChat = false } = avatarConfig || {};

  const bs = bubbleStyle || 'default';

  // Style presets
  const BUBBLE_STYLES = {
    default: {
      sendBg: 'var(--bubble-send)', sendColor: 'var(--bubble-send-text)',
      recvBg: 'var(--bubble-receive)', recvColor: 'var(--bubble-receive-text)',
      sendRadius: '18px 18px 4px 18px', recvRadius: '18px 18px 18px 4px',
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

  const tailSendR = showTail ? '18px 18px 0 18px' : s.sendRadius;
  const tailRecvR = showTail ? '18px 18px 18px 0' : s.recvRadius;

  return (
    <div style={{
      display: 'flex',
      flexDirection: isSend ? 'row-reverse' : 'row',
      alignItems: 'flex-end',
      gap: 8,
      animation: isNew ? 'bubble-in 160ms ease forwards' : undefined,
      transformOrigin: isSend ? 'bottom right' : 'bottom left',
    }}>
      {/* Avatar slot */}
      {isSend ? (
        showJingAvatarInChat && showTail ? (
          <div style={{ width: 28, height: 28, borderRadius: '50%', flexShrink: 0, overflow: 'hidden', background: 'var(--accent-subtle)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontFamily: 'var(--font-display)', color: 'var(--accent)', position: 'relative', zIndex: 2 }}>
            {jingAvatar ? <img src={jingAvatar} style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : '静'}
          </div>
        ) : (showJingAvatarInChat ? <div style={{ width: 28, flexShrink: 0 }} /> : null)
      ) : (
        showConnieAvatarInChat ? (
          <div style={{ width: 28, height: 28, borderRadius: '50%', flexShrink: 0, overflow: 'hidden', background: showAvatar ? 'var(--accent-subtle)' : 'transparent', border: showAvatar ? '1px solid var(--border)' : 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontFamily: 'var(--font-display)', color: 'var(--accent)', position: 'relative', zIndex: 2 }}>
            {showAvatar ? (connieAvatar ? <img src={connieAvatar} style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : 'C') : ''}
          </div>
        ) : null
      )}
      {/* Bubble content */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: isSend ? 'flex-end' : 'flex-start', maxWidth: '72%' }}>
        <div style={{ position: 'relative', display: 'inline-block' }}>
          <div style={{
            background: isSend ? s.sendBg : recvBg,
            color: isSend ? s.sendColor : s.recvColor,
            borderRadius: isSend ? tailSendR : tailRecvR,
            padding: s.padding,
            fontSize: 'var(--text-base)',
            lineHeight: 1.6,
            boxShadow: isSend ? s.sendShadow : s.recvShadow,
            whiteSpace: 'pre-wrap',
          }}>{msg.text}</div>
          {/* iMessage tail: inner (bubble color) + outer (bg color cutaway) */}
          {showTail && bs === 'default' && isSend && (
            <>
              <div style={{
                position: 'absolute', bottom: 0, right: -6,
                width: 20, height: 22,
                background: s.sendBg,
                borderBottomLeftRadius: '16px 14px',
                pointerEvents: 'none',
              }} />
              <div style={{
                position: 'absolute', bottom: 0, right: -26,
                width: 26, height: 22,
                background: bgColor || 'var(--bg-primary)',
                borderBottomLeftRadius: 10,
                pointerEvents: 'none',
              }} />
            </>
          )}
          {showTail && bs === 'default' && !isSend && (
            <>
              <div style={{
                position: 'absolute', bottom: 0, left: -6,
                width: 20, height: 22,
                background: recvBg,
                borderBottomRightRadius: '16px 14px',
                pointerEvents: 'none',
              }} />
              <div style={{
                position: 'absolute', bottom: 0, left: -26,
                width: 26, height: 22,
                background: bgColor || 'var(--bg-primary)',
                borderBottomRightRadius: 10,
                pointerEvents: 'none',
              }} />
            </>
          )}
        </div>
        {msg.time && (
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', opacity: 0.45, marginTop: 3, paddingLeft: isSend ? 0 : 4, paddingRight: isSend ? 4 : 0 }}>
            {msg.time}
          </div>
        )}
        {msg.thinking && (
          <div style={{ marginTop: 4, paddingLeft: isSend ? 0 : 4 }}>
            <button onClick={onToggleThinking} style={{
              background: 'none', border: 'none', cursor: 'pointer', padding: 0,
              display: 'flex', alignItems: 'center', gap: 3,
              fontFamily: 'var(--font-body)', fontSize: 'var(--text-xs)',
              color: 'var(--text-tertiary)', opacity: 0.65,
            }}>
              查看思考过程
              <span style={{ display: 'inline-block', transition: 'transform 0.18s', transform: thinkingExpanded ? 'rotate(90deg)' : 'none', lineHeight: 1 }}>›</span>
            </button>
            {thinkingExpanded && (
              <div style={{
                marginTop: 6, padding: '8px 12px',
                background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--text-xs)', color: 'var(--text-secondary)',
                lineHeight: 1.7, maxWidth: 240,
                animation: 'card-in 160ms ease',
              }}>
                {msg.thinking}
              </div>
            )}
          </div>
        )}
      </div>
    </div>);

}

function NoteCard({ onKeep, onDismiss, minimized, onExpand, noteStyle, content }) {
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
          {content || ''}
        </p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 16, marginTop: 10 }}>
          <button onClick={onDismiss} style={{ background: 'none', border: 'none', fontFamily: "var(--font-body)", fontSize: 12, color: theme.textColor, opacity: 0.5, cursor: 'pointer' }}>知道了</button>
          <button onClick={onKeep} style={{ background: 'none', border: 'none', fontFamily: "var(--font-body)", fontSize: 12, color: theme.textColor, cursor: 'pointer', borderBottom: '1px solid rgba(124,99,80,0.3)' }}>留着</button>
        </div>
      </div>
    </div>);

}

function ChatPage({ tweaks }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [noteState, setNoteState] = useState('hidden');
  const [noteData, setNoteData] = useState(null);
  const [typing, setTyping] = useState(false);
  const [showPlus, setShowPlus] = useState(false);
  const [breathIdx, setBreathIdx] = useState(0);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsView, setSettingsView] = useState('main');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [noteHistory, setNoteHistory] = useState([]);
  const [noteHistoryLoading, setNoteHistoryLoading] = useState(false);
  const [connName, setConnName] = useState('Connie');
  const [nameInput, setNameInput] = useState('Connie');
  const [chatBg, setChatBg] = useState('');
  const [connieAvatar, setConnieAvatar] = useState(null);
  const [jingAvatar, setJingAvatar] = useState(null);
  const [showConnieAvatarInChat, setShowConnieAvatarInChat] = useState(true);
  const [showJingAvatarInChat, setShowJingAvatarInChat] = useState(false);
  const [showEmojiPanel, setShowEmojiPanel] = useState(false);
  const [memoryCandidate, setMemoryCandidate] = useState(null);
  const [expandedThinking, setExpandedThinking] = useState(new Set());
  const bottomRef = useRef(null);
  const msgIdRef = useRef(100);
  const conversationIdRef = useRef(localStorage.getItem('remoire_conv_id') || null);

  useEffect(() => {
    async function loadHistory() {
      const convId = conversationIdRef.current;
      if (!convId) return;
      try {
        const res = await fetch(`http://localhost:8000/api/chat/history?conversation_id=${convId}&limit=50`, {
          headers: { 'Authorization': 'Bearer remoire-rebechalovesconnie-4ever' }
        });
        const data = await res.json();
        if (data.ok && data.data.messages.length > 0) {
          const loaded = [];
          for (const m of data.data.messages) {
            const role = m.role === 'assistant' ? 'ai' : 'user';
            const time = formatBJTime(m.created_at);
            if (role === 'ai') {
              const segments = m.content.split('\n\n').map(s => s.trim()).filter(s => s.length > 0);
              for (const seg of segments) {
                loaded.push({ id: ++msgIdRef.current, role, text: seg, time, type: 'normal' });
              }
            } else {
              loaded.push({ id: ++msgIdRef.current, role, text: m.content, time, type: 'normal' });
            }
          }
          setMessages(loaded);
        }
      } catch (e) {}
    }
    loadHistory();
  }, []);

  useEffect(() => {
    async function loadNote() {
      try {
        const res = await fetch('http://localhost:8000/api/note/unread', {
          headers: { 'Authorization': 'Bearer remoire-rebechalovesconnie-4ever' }
        });
        const data = await res.json();
        if (data.ok && data.data.note) {
          setNoteData(data.data.note);
          setNoteState('visible');
        }
      } catch (e) {}
    }
    loadNote();
  }, []);

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollTop = bottomRef.current.scrollHeight;
    }
  }, [messages, typing]);

  function doSearch(q) {
    setSearchQuery(q);
    if (!q.trim()) { setSearchResults([]); return; }
    const lower = q.toLowerCase();
    setSearchResults(messages.filter(m => m.text && m.text.toLowerCase().includes(lower)));
  }

  async function loadNoteHistory() {
    setNoteHistoryLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/note?limit=50', {
        headers: { 'Authorization': 'Bearer remoire-rebechalovesconnie-4ever' }
      });
      const data = await res.json();
      if (data.ok && data.data?.notes) setNoteHistory(data.data.notes);
    } catch (e) {}
    setNoteHistoryLoading(false);
  }

  async function fetchReply(txt) {
    const time = formatBJTime(new Date().toISOString());
    setTyping(true);
    try {
      const res = await fetch('http://localhost:8000/api/chat/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer remoire-rebechalovesconnie-4ever',
        },
        body: JSON.stringify({ message: txt, conversation_id: conversationIdRef.current || null }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8', { fatal: false });
      let replyText = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          const data = line.slice(5).trim();
          try {
            const parsed = JSON.parse(data);
            if (parsed.type === 'conversation_id') {
              conversationIdRef.current = parsed.conversation_id;
              localStorage.setItem('remoire_conv_id', parsed.conversation_id);
            } else if (parsed.type === 'chunk') {
              replyText += parsed.content;
            }
          } catch (e) {}
        }
      }
      buffer += decoder.decode();
      for (const line of buffer.split('\n')) {
        if (!line.startsWith('data:')) continue;
        try {
          const parsed = JSON.parse(line.slice(5).trim());
          if (parsed.type === 'chunk') replyText += parsed.content;
        } catch (e) {}
      }

      setTyping(false);
      const segments = replyText.split('\n\n').map(s => s.trim()).filter(s => s.length > 0);
      if (segments.length === 0) {
        setMessages((m) => [...m, { id: ++msgIdRef.current, role: 'ai', text: '……我刚刚走神了，你再说一次好吗？', time, type: 'normal', isNew: true }]);
      }
      for (let i = 0; i < segments.length; i++) {
        if (i > 0) {
          setTyping(true);
          await new Promise(r => setTimeout(r, 600 + Math.min(segments[i].length * 30, 1200)));
          setTyping(false);
        }
        setMessages((m) => [...m, { id: ++msgIdRef.current, role: 'ai', text: segments[i], time, type: 'normal', isNew: true }]);
      }
    } catch (e) {
      setTyping(false);
      setMessages((m) => [...m, { id: ++msgIdRef.current, role: 'ai', text: '连不上后端，请确认后端在运行中。', time, type: 'normal', isNew: true }]);
    }
  }

  async function sendMessage() {
    if (!input.trim()) return;
    const txt = input;
    setInput('');
    setShowPlus(false);
    const time = formatBJTime(new Date().toISOString());
    const userMsg = { id: ++msgIdRef.current, role: 'user', text: txt, time, isNew: true };
    setMessages((m) => [...m, userMsg]);
    await fetchReply(txt);
  }

  function toggleThinking(id) {
    setExpandedThinking(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid var(--border-light)', background: 'var(--bg-primary)' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{ width: 36 }} />
          <div style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ fontSize: 'var(--text-md)', fontWeight: 500, color: 'var(--text-primary)', fontFamily: "var(--font-body)" }}>{connName}</div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 1, lineHeight: 1.4 }}>
              {BREATH_STATES[breathIdx]}
            </div>
          </div>
          <IconButton variant="ghost" size={36} onClick={() => setShowSettings(true)}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
          </IconButton>
        </div>
      </div>

      {/* Note */}
      {noteState === 'visible' && noteData && (
        <div style={{ padding: '12px 16px 0' }}>
          <NoteCard content={noteData.content} onKeep={async () => {
            setNoteState('minimized');
            try { await fetch(`http://localhost:8000/api/note/${noteData.id}/read`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer remoire-rebechalovesconnie-4ever' }, body: JSON.stringify({ action: 'keep' }) }); } catch (e) {}
          }} onDismiss={async () => {
            setNoteState('hidden');
            try { await fetch(`http://localhost:8000/api/note/${noteData.id}/read`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer remoire-rebechalovesconnie-4ever' }, body: JSON.stringify({ action: 'dismiss' }) }); } catch (e) {}
          }} noteStyle={tweaks && tweaks.noteStyle} />
        </div>
      )}
      {noteState === 'minimized' && noteData && (
        <NoteCard minimized content={noteData.content} onExpand={() => setNoteState('visible')} noteStyle={tweaks && tweaks.noteStyle} />
      )}

      {/* Messages */}
      <div ref={bottomRef} style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '16px 16px 8px', display: 'flex', flexDirection: 'column', gap: 10, background: chatBg || undefined, transition: 'background 0.3s' }}>
        {messages.map((msg, idx) => {
          let showAvatar = false, showTail = false;
          if (msg.role !== 'system') {
            let pi = idx - 1;
            while (pi >= 0 && messages[pi].role === 'system') pi--;
            let ni = idx + 1;
            while (ni < messages.length && messages[ni].role === 'system') ni++;
            const prev = pi >= 0 ? messages[pi] : null;
            const next = ni < messages.length ? messages[ni] : null;
            showAvatar = msg.role === 'ai' && (!prev || prev.role !== 'ai');
            showTail = !next || next.role !== msg.role;
          }
          return <Bubble key={msg.id} msg={msg} isNew={msg.isNew}
            bubbleStyle={tweaks && tweaks.bubbleStyle}
            showAvatar={showAvatar} showTail={showTail}
            thinkingExpanded={expandedThinking.has(msg.id)}
            onToggleThinking={() => toggleThinking(msg.id)}
            bgColor={chatBg}
            avatarConfig={{ connieAvatar, jingAvatar, showConnieAvatarInChat, showJingAvatarInChat }} />;
        })}
        {typing &&
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
            <TypingIndicator />
          </div>
        }
      </div>

      {/* Memory candidate bar */}
      {memoryCandidate && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '9px 16px', background: 'var(--bg-elevated)',
          borderTop: '1px solid var(--border-light)',
          animation: 'card-in 160ms ease',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 5v5l3 3" /></svg>
          <span style={{ flex: 1, fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
            要记下来吗？<span style={{ color: 'var(--text-deep)', fontWeight: 500 }}>「{memoryCandidate.text}」</span>
          </span>
          <button onClick={() => {
            setMemoryCandidate(null);
            const t = new Date();
            const time = `${t.getHours().toString().padStart(2,'0')}:${t.getMinutes().toString().padStart(2,'0')}`;
            setMessages(m => [...m, { id: ++msgIdRef.current, role: 'system', text: `已记住：${memoryCandidate.text}` }]);
          }} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 'var(--text-xs)', color: 'var(--accent)', fontWeight: 500, padding: '2px 6px' }}>记住</button>
          <button onClick={() => setMemoryCandidate(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', padding: '2px 6px' }}>跳过</button>
        </div>
      )}

      {/* Emoji/sticker panel */}
      {showEmojiPanel && (
        <div style={{
          background: 'var(--bg-elevated)', borderTop: '1px solid var(--border-light)',
          padding: '12px 16px', animation: 'card-in 160ms ease',
        }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {['(˘ᵕ˘)', '(っ˘ω˘ς)', 'ʕ•ᴥ•ʔ', '(ᵔ◡ᵔ)', '(´▽`)', '(｡•̀ᴗ-)✧', '(≧∇≦)/', '(´；ω；｀)', 'ヾ(•ω•`)o', '(¬_¬)', '(◕‿◕)', '(๑˃ᴗ˂)ﻭ'].map(k =>
              <button key={k} onClick={() => { setInput(i => i + k); setShowEmojiPanel(false); }} style={{
                background: 'var(--bg-secondary)', border: '1px solid var(--border-light)',
                borderRadius: 'var(--radius-sm)', padding: '5px 8px',
                fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer',
                fontFamily: 'var(--font-body)', lineHeight: 1,
              }}>{k}</button>
            )}
          </div>
        </div>
      )}

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
          <IconButton onClick={() => setShowEmojiPanel(e => !e)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={showEmojiPanel ? 'var(--accent)' : 'var(--text-tertiary)'} strokeWidth="1.5">
              <circle cx="12" cy="12" r="9" />
              <path d="M8.5 14.5s1 2 3.5 2 3.5-2 3.5-2" strokeLinecap="round" />
              <circle cx="9" cy="10" r="1" fill={showEmojiPanel ? 'var(--accent)' : 'var(--text-tertiary)'} stroke="none" />
              <circle cx="15" cy="10" r="1" fill={showEmojiPanel ? 'var(--accent)' : 'var(--text-tertiary)'} stroke="none" />
            </svg>
          </IconButton>
          {input ?
          <button onClick={sendMessage} style={{ background: 'var(--accent)', color: '#FAF8F4', border: 'none', borderRadius: 'var(--radius-sm)', padding: '8px 14px', fontSize: 14, fontWeight: 500, cursor: 'pointer', flexShrink: 0 }}>发送</button> :

          <IconButton>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></svg>
            </IconButton>
          }
        </div>
      </div>
      {/* Settings panel overlay */}
      {showSettings && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
          {/* Backdrop */}
          <div onClick={() => { setShowSettings(false); setSettingsView('main'); }} style={{ position: 'absolute', inset: 0, background: 'rgba(40,33,28,0.35)' }} />
          {/* Panel */}
          <div style={{
            position: 'relative', background: 'var(--bg-primary)',
            borderRadius: '20px 20px 0 0', maxHeight: '82vh', overflowY: 'auto',
            animation: 'page-in 220ms cubic-bezier(0.4,0,0.2,1)',
          }}>
            {/* Drag handle */}
            <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0 4px' }}>
              <div style={{ width: 36, height: 4, borderRadius: 2, background: 'var(--border)' }} />
            </div>

            {settingsView === 'search' && (
              <div style={{ padding: '4px 20px 24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <button onClick={() => setSettingsView('main')} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: 'var(--text-tertiary)' }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
                  </button>
                  <span style={{ fontSize: 'var(--text-md)', fontWeight: 500, color: 'var(--text-deep)' }}>查找聊天内容</span>
                </div>
                <input
                  autoFocus
                  value={searchQuery}
                  onChange={e => doSearch(e.target.value)}
                  placeholder="输入关键词搜索…"
                  style={{ width: '100%', background: 'var(--bg-elevated)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-sm)', padding: '10px 14px', fontSize: 'var(--text-sm)', color: 'var(--text-primary)', fontFamily: 'var(--font-body)', outline: 'none', marginBottom: 4 }}
                />
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 12 }}>搜索范围：当前已加载的消息</div>
                {searchQuery && searchResults.length === 0 && (
                  <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)' }}>没有找到相关内容</div>
                )}
                <div style={{ maxHeight: 320, overflowY: 'auto' }}>
                  {searchResults.map(m => (
                    <div key={m.id} style={{ padding: '10px 0', borderBottom: '1px solid var(--border-light)' }}>
                      <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 3 }}>{m.role === 'user' ? '静儿' : 'Connie'} · {m.time}</div>
                      <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-primary)', lineHeight: 1.6 }}>{m.text}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {settingsView === 'notes' && (
              <div style={{ padding: '4px 20px 24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                  <button onClick={() => setSettingsView('main')} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, color: 'var(--text-tertiary)' }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
                  </button>
                  <span style={{ fontSize: 'var(--text-md)', fontWeight: 500, color: 'var(--text-deep)' }}>小纸条历史</span>
                </div>
                {noteHistoryLoading && (
                  <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)' }}>加载中…</div>
                )}
                {!noteHistoryLoading && noteHistory.length === 0 && (
                  <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)' }}>还没有纸条呢</div>
                )}
                <div style={{ maxHeight: 400, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {noteHistory.map(n => (
                    <div key={n.id} style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-sm)', padding: '12px 14px' }}>
                      <div style={{ fontFamily: 'var(--font-note, var(--font-diary))', fontSize: 14, color: 'var(--text-deep)', lineHeight: 1.7, marginBottom: 6 }}>{n.content}</div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-tertiary)' }}>
                        <span>{formatBJTime(n.created_at)}</span>
                        <span style={{ color: n.is_read ? 'var(--text-tertiary)' : 'var(--accent-pop)' }}>{n.is_read ? (n.kept ? '已收藏' : '已读') : '未读'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {settingsView === 'main' && (<>
            <div style={{ padding: '4px 20px 16px', fontSize: 'var(--text-md)', fontWeight: 500, color: 'var(--text-deep)', textAlign: 'center' }}>聊天设置</div>

            {/* 我们 */}
            <div style={{ padding: '0 20px 8px' }}>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', letterSpacing: '0.06em', marginBottom: 12 }}>我们</div>
              <div style={{ display: 'flex', gap: 24, justifyContent: 'center', marginBottom: 12 }}>
                {/* 静儿头像 */}
                <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'var(--accent-subtle)', border: '1.5px dashed var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, color: 'var(--accent)', fontFamily: 'var(--font-display)', position: 'relative', overflow: 'hidden' }}>
                    {jingAvatar ? <img src={jingAvatar} style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : '静'}
                    <div style={{ position: 'absolute', bottom: 0, right: 0, width: 18, height: 18, borderRadius: '50%', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#FAF8F4" strokeWidth="2"><path d="M12 5v14M5 12h14" /></svg>
                    </div>
                  </div>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>静儿</span>
                  <input type="file" accept="image/*" style={{ display: 'none' }} onChange={e => { const f = e.target.files[0]; if (f) setJingAvatar(URL.createObjectURL(f)); }} />
                </label>
                {/* Connie 头像 */}
                <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'var(--accent-subtle)', border: '1.5px dashed var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, color: 'var(--accent)', fontFamily: 'var(--font-display)', position: 'relative', overflow: 'hidden' }}>
                    {connieAvatar ? <img src={connieAvatar} style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : 'C'}
                    <div style={{ position: 'absolute', bottom: 0, right: 0, width: 18, height: 18, borderRadius: '50%', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#FAF8F4" strokeWidth="2"><path d="M12 5v14M5 12h14" /></svg>
                    </div>
                  </div>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>{connName}</span>
                  <input type="file" accept="image/*" style={{ display: 'none' }} onChange={e => { const f = e.target.files[0]; if (f) setConnieAvatar(URL.createObjectURL(f)); }} />
                </label>
              </div>
              {/* 头像显示开关 */}
              {[
                { label: '聊天中显示 Connie 头像', val: showConnieAvatarInChat, set: setShowConnieAvatarInChat },
                { label: '聊天中显示我的头像', val: showJingAvatarInChat, set: setShowJingAvatarInChat },
              ].map(({ label, val, set }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderTop: '1px solid var(--border-light)' }}>
                  <span style={{ flex: 1, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>{label}</span>
                  <div onClick={() => set(v => !v)} style={{ width: 38, height: 22, borderRadius: 11, background: val ? 'var(--accent)' : 'var(--border)', position: 'relative', cursor: 'pointer', transition: 'background 0.2s', flexShrink: 0 }}>
                    <div style={{ position: 'absolute', top: 3, left: val ? 19 : 3, width: 16, height: 16, borderRadius: '50%', background: '#fff', transition: 'left 0.18s', boxShadow: '0 1px 3px rgba(0,0,0,0.15)' }} />
                  </div>
                </div>
              ))}
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  value={nameInput}
                  onChange={e => setNameInput(e.target.value)}
                  placeholder="备注名"
                  style={{ flex: 1, background: 'var(--bg-elevated)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', fontSize: 'var(--text-sm)', color: 'var(--text-primary)', fontFamily: 'var(--font-body)', outline: 'none' }}
                />
                <button onClick={() => {
                  const newName = nameInput.trim();
                  if (newName && newName !== connName) {
                    setConnName(newName);
                    const sysText = `静儿修改你的备注为「${newName}」`;
                    const time = formatBJTime(new Date().toISOString());
                    setMessages(m => [...m, { id: ++msgIdRef.current, role: 'system', text: sysText, time, isNew: true }]);
                    setShowSettings(false);
                    fetchReply(sysText);
                    return;
                  }
                  setShowSettings(false);
                }} style={{ background: 'var(--accent)', color: '#FAF8F4', border: 'none', borderRadius: 'var(--radius-sm)', padding: '8px 14px', fontSize: 'var(--text-sm)', cursor: 'pointer', flexShrink: 0 }}>保存</button>
              </div>
            </div>

            <div style={{ height: 1, background: 'var(--border-light)', margin: '12px 0' }} />

            {/* 内容管理 */}
            <div style={{ padding: '0 20px 8px' }}>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', letterSpacing: '0.06em', marginBottom: 8 }}>内容管理</div>
              <div onClick={() => setSettingsView('search')} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 0', borderBottom: '1px solid var(--border-light)', cursor: 'pointer' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5"><path d="M21 21l-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0z" /></svg>
                <span style={{ flex: 1, fontSize: 'var(--text-base)', color: 'var(--text-primary)' }}>查找聊天内容</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M9 18l6-6-6-6" /></svg>
              </div>
              <div onClick={() => { setSettingsView('notes'); loadNoteHistory(); }} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 0', borderBottom: '1px solid var(--border-light)', cursor: 'pointer' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" /></svg>
                <span style={{ flex: 1, fontSize: 'var(--text-base)', color: 'var(--text-primary)' }}>小纸条历史</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M9 18l6-6-6-6" /></svg>
              </div>
            </div>

            <div style={{ height: 1, background: 'var(--border-light)', margin: '12px 0' }} />

            {/* 外观 */}
            <div style={{ padding: '0 20px 8px' }}>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', letterSpacing: '0.06em', marginBottom: 12 }}>外观</div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: 8 }}>聊天背景</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
                {BG_PRESETS.map(p => (
                  <button key={p.value} onClick={() => setChatBg(p.value)} style={{
                    width: 44, height: 44, borderRadius: 10, flexShrink: 0, cursor: 'pointer',
                    background: p.value || 'var(--bg-primary)',
                    border: chatBg === p.value ? '2px solid var(--accent)' : '1.5px solid var(--border)',
                    position: 'relative',
                  }}>
                    {!p.value && <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" style={{ position: 'absolute', inset: 0, margin: 'auto' }}><path d="M18 6L6 18M6 6l12 12" /></svg>}
                  </button>
                ))}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 0', borderTop: '1px solid var(--border-light)', opacity: 0.5 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg>
                <span style={{ flex: 1, fontSize: 'var(--text-base)', color: 'var(--text-primary)' }}>气泡样式</span>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>即将开放</span>
              </div>
            </div>

            <div style={{ height: 1, background: 'var(--border-light)', margin: '12px 0' }} />

            {/* 危险区 */}
            <div style={{ padding: '0 20px 32px' }}>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', letterSpacing: '0.06em', marginBottom: 8 }}>危险区</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 0', cursor: 'pointer' }} onClick={() => {
                if (window.confirm('确定清除所有聊天记录？')) {
                  setMessages([]);
                  setShowSettings(false);
                  setSettingsView('main');
                }
              }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" strokeWidth="1.5"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /><path d="M10 11v6M14 11v6" /><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" /></svg>
                <span style={{ flex: 1, fontSize: 'var(--text-base)', color: 'var(--danger)' }}>清除聊天记录</span>
              </div>
            </div>
            </>)}
          </div>
        </div>
      )}
    </div>);

}

Object.assign(window, { ChatPage });