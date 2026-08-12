import { useState, useRef, useEffect, memo, useCallback } from "react";
import { apiFetch, apiJsonFetch, API_BASE } from "../utils/api";
import { PALETTES, currentBand, AMBIENT_BY_BAND, isDarkBand } from "../utils/ambient";
import Floaters from "./Floaters";
import { RainLayer, FogLayer } from "./WeatherEffects";
import "../styles/room.css";

function formatBJTime(utcStr) {
  if (!utcStr) return '';
  const d = new Date(utcStr + (utcStr.endsWith('Z') ? '' : 'Z'));
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Shanghai' });
}

function FormattedText({ text }) {
  const lines = text.split('\n');
  return lines.map((line, i) => {
    const parts = [];
    let remaining = line;
    let key = 0;
    const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|_(.+?)_)/g;
    let lastIdx = 0;
    let match;
    while ((match = regex.exec(remaining)) !== null) {
      if (match.index > lastIdx) parts.push(<span key={key++}>{remaining.slice(lastIdx, match.index)}</span>);
      if (match[2]) parts.push(<strong key={key++} style={{ fontWeight: 600 }}>{match[2]}</strong>);
      else if (match[3] || match[4]) parts.push(<em key={key++}>{match[3] || match[4]}</em>);
      lastIdx = match.index + match[0].length;
    }
    if (lastIdx < remaining.length) parts.push(<span key={key}>{remaining.slice(lastIdx)}</span>);
    if (parts.length === 0 && line === '') parts.push(<br key={key} />);
    return <span key={i}>{parts}{i < lines.length - 1 && line !== '' && <br />}</span>;
  });
}

const TOOL_LABELS = {
  remember: '记忆', search_memories: '搜索记忆', leave_note: '留纸条',
  get_current_time: '看时间', write_diary: '写日记', set_breath_state: '更新状态',
  web_search: '搜索', browse_url: '看网页', browse_xiaohongshu: '刷小红书',
  browse_twitter: '刷推特', search_xiaohongshu: '搜小红书', search_twitter: '搜推特',
  save_browsed: '保存内容', read_diary: '翻日记', read_jinger_diary: '看静儿日记',
  try_unlock_diary: '猜密码', reply_diary_interaction: '回复日记',
};

function ToolCallBanner({ tools, count, done }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div style={{
      margin: '0 40px', textAlign: 'center',
      animation: 'card-in 180ms ease',
    }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '5px 14px', borderRadius: 12,
          background: 'rgba(124,99,80,0.06)',
          border: '1px solid var(--ink-faint, rgba(0,0,0,0.08))',
          fontSize: 12, color: 'var(--ink-soft, var(--text-secondary))',
          cursor: 'pointer', fontFamily: 'var(--font-body)',
        }}
      >
        <svg
          width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="var(--ink-accent, var(--accent))" strokeWidth="1.5"
          style={{
            animation: done ? 'none' : 'spin 1.2s linear infinite',
            flexShrink: 0,
          }}
        >
          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
        </svg>
        <span>{done ? `调用了 ${count} 个工具` : `正在调用工具…`}</span>
        <svg
          width="10" height="10" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2"
          style={{
            transform: expanded ? 'rotate(180deg)' : 'rotate(0)',
            transition: 'transform 150ms ease',
          }}
        >
          <path d="M6 9l6 6 6-6"/>
        </svg>
      </button>
      {expanded && (
        <div style={{
          marginTop: 6, padding: '6px 12px',
          background: 'rgba(124,99,80,0.04)',
          borderRadius: 8, fontSize: 12,
          color: 'var(--ink-soft, var(--text-secondary))',
          lineHeight: 1.8,
        }}>
          {tools.map((t, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'center' }}>
              <span style={{ opacity: 0.5 }}>›</span>
              <span>{TOOL_LABELS[t] || t}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const CHAT_MODES = {
  daily: { label: '日常', desc: '轻松聊天、日常陪伴' },
  deep:  { label: '深度', desc: '需要更长更深的对话' },
};

const MessageRow = memo(function MessageRow({ m, isKept, isThinkOpen, onToggleThink, onHold, onRelease, onQuote, onRegenerate }) {
  const isAi = m.role === 'ai';
  const [copied, setCopied] = useState(false);
  const handleToggle = useCallback(() => onToggleThink(m.id), [onToggleThink, m.id]);
  const handleHold = useCallback(() => onHold(m.id), [onHold, m.id]);
  const handleCopy = useCallback(() => {
    navigator.clipboard?.writeText(m.text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [m.text]);
  const actBtn = {
    background: 'none', border: 'none', cursor: 'pointer',
    padding: 3, display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: 'var(--ink-faint, rgba(0,0,0,0.25))',
  };
  const ico = { width: 13, height: 13, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round' };
  return (
    <div className={`r-row ${isAi ? 'r-row-ai' : 'r-row-user'}`}
      onMouseDown={handleHold} onMouseUp={onRelease} onMouseLeave={onRelease}
      onTouchStart={handleHold} onTouchEnd={onRelease}
      style={{ opacity: isKept ? 0.6 : 1 }}>
      {isAi && <div className="r-spark">✦</div>}
      <div className="r-bubble-stack">
        {m.quote && (
          <div style={{
            padding: '4px 10px', marginBottom: 2, borderRadius: 8,
            background: 'rgba(124,99,80,0.06)',
            borderLeft: '2px solid var(--ink-faint, rgba(0,0,0,0.15))',
            fontSize: 12, color: 'var(--ink-soft, var(--text-tertiary))',
            lineHeight: 1.4, maxHeight: 36, overflow: 'hidden',
          }}>
            {m.quote}
          </div>
        )}
        {m.image && <img src={m.image} alt="" className="r-bubble-img" />}
        {m.text && (
          <div className={`r-bubble ${isAi ? 'r-bubble-ai' : 'r-bubble-user'}`}>
            {m.formatted ? <FormattedText text={m.text} /> : m.text}
          </div>
        )}
        {m.role === 'system' && (
          <div style={{
            padding: '6px 14px', borderRadius: 12,
            background: 'rgba(255,250,235,0.08)',
            border: '1px dashed var(--ink-faint)',
            fontSize: 12, color: 'var(--ink-soft)',
            textAlign: 'center', fontStyle: 'italic',
          }}>{m.text}</div>
        )}
        {m.text && m.role !== 'system' && (
          <div className={`r-meta ${isAi ? 'r-meta-ai' : 'r-meta-user'}`} style={{
            display: 'flex', alignItems: 'center', gap: 4,
            flexDirection: isAi ? 'row' : 'row-reverse',
          }}>
            {m.time && <span className="r-time" style={{ order: isAi ? 99 : -1 }}>{m.time}</span>}
            <button style={actBtn} onClick={handleCopy} title="复制">
              {copied
                ? <svg {...ico} stroke="var(--success, #6B9)"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><path d="M22 4L12 14.01l-3-3" /></svg>
                : <svg {...ico}><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
              }
            </button>
            <button style={actBtn} onClick={() => onQuote(m)} title="引用">
              <svg {...ico}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
            </button>
            <button style={actBtn} onClick={onRegenerate} title="重新生成">
              <svg {...ico}><path d="M21 2v6h-6" /><path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M3 22v-6h6" /><path d="M21 12a9 9 0 0 1-15 6.7L3 16" /></svg>
            </button>
            {isKept && <span className="r-kept-marker">· 留下</span>}
          </div>
        )}
        {m.role === 'system' && m.time && (
          <div className={`r-meta r-meta-ai`}>
            <span className="r-time">{m.time}</span>
          </div>
        )}
        {isAi && m.thinking && (
          <button className="r-think-handle" onClick={handleToggle}>
            <span className="r-think-icon">✦</span>
            <span>{isThinkOpen ? '收起' : '偷偷看他在想什么'}</span>
            <span style={{
              transform: isThinkOpen ? 'rotate(90deg)' : 'rotate(0deg)',
              transition: 'transform 280ms cubic-bezier(0.16,1,0.3,1)',
            }}>›</span>
          </button>
        )}
        {isAi && m.thinking && isThinkOpen && (
          <div className="r-think-panel">{m.thinking}</div>
        )}
      </div>
    </div>
  );
});

function SettingsSheet({ timeOverride, setTimeOverride, weather, setWeather, deepMode, setDeepMode, connieName, setConnieName, chatBgImage, setChatBgImage, replyStyle, setReplyStyle, onRename, onClose }) {
  const [nameInput, setNameInput] = useState(connieName);
  const prevNameRef = useRef(connieName);
  function commitName() {
    const newName = (nameInput || 'Connie').trim();
    if (newName !== prevNameRef.current) {
      prevNameRef.current = newName;
      setConnieName(newName);
      if (onRename) onRename(newName);
    } else {
      setConnieName(newName);
    }
  }
  const bgFileRef = useRef(null);
  useEffect(() => {
    const closeOnEscape = (event) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [onClose]);
  function pickBg(file) {
    if (!file) return;
    const r = new FileReader();
    r.onload = () => setChatBgImage(r.result);
    r.readAsDataURL(file);
  }
  return (
    <div className="r-sheet-bd" onClick={onClose} role="presentation">
      <div className="r-sheet" role="dialog" aria-modal="true" aria-label="这间房设置" onClick={e => e.stopPropagation()}>
        <div className="r-sheet-grip" />
        <div className="r-sheet-title">这间房</div>

        <div className="r-sheet-section">
          <div className="r-sheet-label">她的备注</div>
          <div className="r-name-edit-row">
            <input
              value={nameInput}
              onChange={e => setNameInput(e.target.value)}
              onBlur={() => commitName()}
              onKeyDown={e => { if (e.key === 'Enter') { commitName(); onClose(); } }}
              placeholder="给她起个名字"
              className="r-sheet-input"
            />
          </div>
          <div className="r-sheet-hint">改名是一种交流。换名字的时候她会知道。</div>
        </div>

        <div className="r-sheet-section">
          <div className="r-sheet-label">聊天背景</div>
          <input ref={bgFileRef} type="file" accept="image/*" style={{ display: 'none' }}
            onChange={e => pickBg(e.target.files?.[0])} />
          <div className="r-bg-picker">
            <button type="button" aria-label="上传聊天背景" className="r-bg-preview" onClick={() => bgFileRef.current?.click()}
              style={chatBgImage ? {
                backgroundImage: `url(${chatBgImage})`,
                backgroundSize: 'cover', backgroundPosition: 'center',
              } : {}}>
              {!chatBgImage && <span>＋ 上传</span>}
            </button>
            <div className="r-bg-actions">
              <button className="r-chip" onClick={() => bgFileRef.current?.click()}>
                {chatBgImage ? '换一张' : '从相册选'}
              </button>
              {chatBgImage && (
                <button className="r-chip" onClick={() => setChatBgImage('')}>用回时刻</button>
              )}
            </div>
          </div>
          <div className="r-sheet-hint">换上自己的背景后，气泡和工具栏都会透出这张图。</div>
        </div>

        <div className="r-sheet-section">
          <div className="r-sheet-label">时刻</div>
          <div className="r-sheet-options">
            {[
              ['auto', '随真实'], ['dawn', '黎明'], ['morning', '上午'], ['afternoon', '午后'],
              ['golden', '黄金'], ['dusk', '黄昏'], ['night', '夜晚'], ['late', '深夜'],
            ].map(([k, label]) => (
              <button key={k} className={`r-chip ${timeOverride === k ? 'active' : ''}`}
                onClick={() => setTimeOverride(k)}>{label}</button>
            ))}
          </div>
        </div>

        <div className="r-sheet-section">
          <div className="r-sheet-label">天气</div>
          <div className="r-sheet-options">
            {[['clear', '晴'], ['rain', '雨'], ['fog', '雾']].map(([k, label]) => (
              <button key={k} className={`r-chip ${weather === k ? 'active' : ''}`}
                onClick={() => setWeather(k)}>{label}</button>
            ))}
          </div>
        </div>

        <div className="r-sheet-section">
          <div className="r-sheet-label">回复方式</div>
          <div className="r-sheet-hint" style={{ marginBottom: 8 }}>想让他怎么回复你？</div>
          <div className="r-sheet-options">
            <button className={`r-chip ${replyStyle === 'split' ? 'active' : ''}`}
              onClick={() => setReplyStyle('split')}>分条发送</button>
            <button className={`r-chip ${replyStyle === 'whole' ? 'active' : ''}`}
              onClick={() => setReplyStyle('whole')}>整条发送</button>
          </div>
          <div className="r-sheet-hint" style={{ marginTop: 6 }}>
            {replyStyle === 'split' ? '一段话拆成多条气泡，像聊天一样。' : '所有内容在一条气泡里，有换行有格式。'}
          </div>
        </div>

        <div className="r-sheet-section">
          <div className="r-sheet-row">
            <div>
              <div className="r-sheet-label">走深一点</div>
              <div className="r-sheet-hint">房间会变暗，她会说得更慢。</div>
            </div>
            <button className={`r-toggle ${deepMode ? 'on' : ''}`}
              onClick={() => setDeepMode(!deepMode)}>
              <span />
            </button>
          </div>
        </div>

        <button className="r-sheet-close" onClick={onClose}>关上门</button>
      </div>
    </div>
  );
}

const NAV_TABS = [
  { id: 'chat',     label: '聊天',  icon: (s) => <svg {...s}><path d="M21 12a8 8 0 0 1-11.5 7.2L4 21l1.5-4.5A8 8 0 1 1 21 12z"/></svg> },
  { id: 'us',       label: '我们',  icon: (s) => <svg {...s}><path d="M20 9a6 6 0 0 0-8-5 6 6 0 0 0-8 5c0 6 8 11 8 11s8-5 8-11z"/></svg> },
  { id: 'diary',    label: '日记',  icon: (s) => <svg {...s}><path d="M4 4h11a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3z"/><path d="M9 8h6M9 12h6"/></svg> },
  { id: 'play',     label: '玩乐',  icon: (s) => <svg {...s}><circle cx="12" cy="12" r="9"/><path d="M10 9l5 3-5 3z" fill="currentColor"/></svg> },
  { id: 'settings', label: '设置',  icon: (s) => <svg {...s}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.65 1.65 0 0 0-1.8-.3 1.65 1.65 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.65 1.65 0 0 0-1-1.5 1.65 1.65 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.65 1.65 0 0 0 .3-1.8 1.65 1.65 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.65 1.65 0 0 0 1.5-1 1.65 1.65 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.65 1.65 0 0 0 1.8.3h.1a1.65 1.65 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.65 1.65 0 0 0 1 1.5h.1a1.65 1.65 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.65 1.65 0 0 0-.3 1.8v.1a1.65 1.65 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.65 1.65 0 0 0-1.5 1z"/></svg> },
];

export default function ChatPage({ tweaks, activeTab, onNavigate }) {
  const [messages, setMessages] = useState([]);
  const [hasInput, setHasInput] = useState(false);
  const inputValRef = useRef('');
  const [typing, setTyping] = useState(false);
  const [streaming, setStreaming] = useState('');
  const [showActions, setShowActions] = useState(false);
  const [showModes, setShowModes] = useState(false);
  const [showSheet, setShowSheet] = useState(false);
  const [chatMode, setChatMode] = useState(() => localStorage.getItem('remoire_chat_mode') || 'daily');
  const [connieName, setConnieName] = useState(() => localStorage.getItem('remoire_conn_name') || 'Connie');
  const [editingName, setEditingName] = useState(false);
  const [breathText, setBreathText] = useState('');
  const [ambientIdx, setAmbientIdx] = useState(0);
  const [expandedThink, setExpandedThink] = useState(new Set());
  const [kept, setKept] = useState(new Set());
  const [pendingImage, setPendingImage] = useState(null);
  const [quotedMsg, setQuotedMsg] = useState(null);
  const [voiceHold, setVoiceHold] = useState(false);
  const [chatBgImage, setChatBgImage] = useState(() => localStorage.getItem('remoire_chat_bg') || '');
  const [timeOverride, setTimeOverride] = useState(() => localStorage.getItem('remoire_time_override') || 'auto');
  const [weather, setWeather] = useState(() => localStorage.getItem('remoire_weather') || 'clear');
  const [deepMode, setDeepMode] = useState(() => !!localStorage.getItem('remoire_deep_mode'));
  const [replyStyle, setReplyStyle] = useState(() => localStorage.getItem('remoire_reply_style') || 'split');
  const [noteData, setNoteData] = useState(null);
  const [noteState, setNoteState] = useState('hidden');
  const [noteError, setNoteError] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const searchInputRef = useRef(null);

  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const fileRef = useRef(null);
  const msgIdRef = useRef(100);
  const conversationIdRef = useRef(localStorage.getItem('remoire_conv_id') || null);
  const msgTimer = useRef(null);
  const nameBeforeEdit = useRef(connieName);

  const band = timeOverride === 'auto' ? currentBand() : timeOverride;
  const palette = PALETTES[band];
  const dark = isDarkBand(band);
  const ambientLines = AMBIENT_BY_BAND[band] || ['在这里'];

  useEffect(() => { localStorage.setItem('remoire_conn_name', connieName); }, [connieName]);
  useEffect(() => {
    if (chatBgImage) localStorage.setItem('remoire_chat_bg', chatBgImage);
    else localStorage.removeItem('remoire_chat_bg');
    window.dispatchEvent(new CustomEvent('remoire-ambient', { detail: { key: 'remoire_chat_bg', value: chatBgImage } }));
  }, [chatBgImage]);
  useEffect(() => { localStorage.setItem('remoire_time_override', timeOverride); window.dispatchEvent(new CustomEvent('remoire-ambient', { detail: { key: 'remoire_time_override', value: timeOverride } })); }, [timeOverride]);
  useEffect(() => { localStorage.setItem('remoire_weather', weather); window.dispatchEvent(new CustomEvent('remoire-ambient', { detail: { key: 'remoire_weather', value: weather } })); }, [weather]);
  useEffect(() => { const v = deepMode ? '1' : ''; localStorage.setItem('remoire_deep_mode', v); window.dispatchEvent(new CustomEvent('remoire-ambient', { detail: { key: 'remoire_deep_mode', value: v } })); }, [deepMode]);
  useEffect(() => { localStorage.setItem('remoire_reply_style', replyStyle); }, [replyStyle]);

  useEffect(() => {
    if (typing) return;
    const t = setInterval(() => setAmbientIdx(i => (i + 1) % ambientLines.length), 11000);
    return () => clearInterval(t);
  }, [typing, band, ambientLines.length]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [messages, streaming, typing]);

  function handleInput(e) {
    const val = e.target.value;
    inputValRef.current = val;
    setHasInput(val.trim().length > 0);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 110) + 'px';
  }

  useEffect(() => {
    apiFetch('/chat/status').then(r => r.json()).then(res => {
      if (res.ok && res.data?.presence_text) setBreathText(res.data.presence_text);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const q = searchQuery.trim();
    const convId = conversationIdRef.current;
    if (!searchOpen || !q || !convId) {
      setSearchResults([]);
      setSearching(false);
      return;
    }
    let cancelled = false;
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const res = await apiFetch(`/chat/search?conversation_id=${encodeURIComponent(convId)}&q=${encodeURIComponent(q)}&limit=80`);
        const data = await res.json();
        if (cancelled) return;
        if (data.ok && Array.isArray(data.data?.messages)) {
          setSearchResults(data.data.messages.map((m, idx) => ({
            id: `search-${idx}-${m.created_at}`,
            role: m.role === 'assistant' ? 'ai' : m.role,
            text: m.content,
            time: formatBJTime(m.created_at),
          })));
        } else {
          setSearchResults([]);
        }
      } catch {
        if (!cancelled) setSearchResults([]);
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 220);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [searchOpen, searchQuery]);

  useEffect(() => {
    let cancelled = false;
    async function fetchWithRetry(url, attempts = 3) {
      for (let i = 0; i < attempts; i++) {
        try {
          const res = await apiFetch(url);
          if (res.ok) return res;
        } catch {
          if (cancelled) return null;
        }
        await new Promise(r => setTimeout(r, 500 * (i + 1)));
      }
      return null;
    }
    async function loadHistory() {
      let convId = conversationIdRef.current;
      if (!convId) {
        const latestRes = await fetchWithRetry('/chat/latest');
        if (latestRes) {
          const latestData = await latestRes.json().catch(() => null);
          if (latestData?.ok && latestData.data?.conversation_id) {
            convId = latestData.data.conversation_id;
            conversationIdRef.current = convId;
            localStorage.setItem('remoire_conv_id', convId);
          }
        }
      }
      if (cancelled || !convId) return;
      const res = await fetchWithRetry(`/chat/history?conversation_id=${convId}&limit=100`);
      if (!res || cancelled) return;
      try {
        const data = await res.json();
        if (data.ok && data.data.messages.length > 0) {
          const loaded = [];
          for (const m of data.data.messages) {
            const time = formatBJTime(m.created_at);
            if (m.role === 'assistant') {
              const mode = m.display_mode || 'split';
              if (mode === 'whole') {
                const msgObj = { id: ++msgIdRef.current, role: 'ai', text: m.content.trim(), time, type: 'normal', formatted: true };
                if (m.thinking) msgObj.thinking = m.thinking;
                loaded.push(msgObj);
              } else {
                const segments = m.content.split('\n\n').map(s => s.trim()).filter(s => s.length > 0);
                for (let si = 0; si < segments.length; si++) {
                  const msgObj = { id: ++msgIdRef.current, role: 'ai', text: segments[si], time, type: 'normal' };
                  if (si === 0 && m.thinking) msgObj.thinking = m.thinking;
                  loaded.push(msgObj);
                }
              }
            } else if (m.content.startsWith('静儿修改')) {
              loaded.push({ id: ++msgIdRef.current, role: 'system', text: m.content, time });
            } else {
              const userMsg = { id: ++msgIdRef.current, role: 'user', text: m.content, time, type: 'normal' };
              if (m.image) userMsg.image = m.image;
              else if (m.image_id) userMsg.image = `${API_BASE}/chat/image/${m.image_id}`;
              loaded.push(userMsg);
            }
          }
          if (!cancelled) setMessages(loaded);
        }
      } catch (e) { console.error('loadHistory error', e); }
    }
    loadHistory();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    async function loadNote() {
      try {
        const res = await apiFetch('/note/unread');
        const data = await res.json();
        if (data.ok && data.data.note) {
          setNoteData(data.data.note);
          setNoteState('visible');
        }
      } catch (error) {
        console.warn('纸条加载失败', error);
      }
    }
    loadNote();
  }, []);

  const [toolCall, setToolCall] = useState(null);

  async function fetchReply(txt, image) {
    const time = formatBJTime(new Date().toISOString());
    setTyping(true);
    setToolCall(null);
    try {
      const body = { message: txt || '（发了一张图片）', conversation_id: conversationIdRef.current || null, mode: chatMode, reply_style: replyStyle };
      if (image) body.image = image;
      const res = await apiJsonFetch('/chat/send', {
        method: 'POST', body: JSON.stringify(body),
      });
      if (!res.ok || !res.body) throw new Error(`后端返回错误：${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8', { fatal: false });
      let replyText = '';
      let thinkingText = '';
      let buffer = '';
      let streamDone = false;
      let streamError = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          try {
            const parsed = JSON.parse(line.slice(5).trim());
            if (parsed.type === 'conversation_id') {
              conversationIdRef.current = parsed.conversation_id;
              localStorage.setItem('remoire_conv_id', parsed.conversation_id);
            } else if (parsed.type === 'tool_start') {
              setToolCall({ tools: parsed.tools, count: parsed.count, done: false });
              setTyping(false);
            } else if (parsed.type === 'tool_done') {
              setMessages(m => [...m, { id: ++msgIdRef.current, type: 'tool_call', tools: parsed.tools, count: parsed.count }]);
              setToolCall(null);
              setTyping(true);
            } else if (parsed.type === 'chunk') {
              replyText += parsed.content;
            } else if (parsed.type === 'thinking') {
              thinkingText += parsed.content;
            } else if (parsed.type === 'note') {
              setNoteData(parsed.note);
              setNoteState('visible');
            } else if (parsed.type === 'done') {
              streamDone = true;
            } else if (parsed.type === 'error') {
              streamError = parsed.content || '后端生成回复时出错了。';
            }
          } catch {
            streamError = '回复数据格式异常，请重试。';
          }
        }
      }
      buffer += decoder.decode();
      for (const line of buffer.split('\n')) {
        if (!line.startsWith('data:')) continue;
        try {
          const parsed = JSON.parse(line.slice(5).trim());
          if (parsed.type === 'tool_start') { setToolCall({ tools: parsed.tools, count: parsed.count, done: false }); setTyping(false); }
          else if (parsed.type === 'tool_done') { setMessages(m => [...m, { id: ++msgIdRef.current, type: 'tool_call', tools: parsed.tools, count: parsed.count }]); setToolCall(null); setTyping(true); }
          else if (parsed.type === 'chunk') { replyText += parsed.content; }
          else if (parsed.type === 'thinking') thinkingText += parsed.content;
          else if (parsed.type === 'note') { setNoteData(parsed.note); setNoteState('visible'); }
          else if (parsed.type === 'done') streamDone = true;
          else if (parsed.type === 'error') streamError = parsed.content || '后端生成回复时出错了。';
        } catch {
          streamError = '回复数据格式异常，请重试。';
        }
      }

      if (streamError) throw new Error(streamError);
      if (!streamDone) throw new Error('后端流式响应中断');

      setTyping(false);
      setStreaming('');
      setToolCall(null);
      if (!replyText.trim()) {
        setMessages(m => [...m, { id: ++msgIdRef.current, role: 'ai', text: '……我刚刚走神了，你再说一次好吗？', time, type: 'normal', isNew: true }]);
      } else if (replyStyle === 'whole') {
        const msgObj = { id: ++msgIdRef.current, role: 'ai', text: replyText.trim(), time, type: 'normal', isNew: true, formatted: true };
        if (thinkingText) msgObj.thinking = thinkingText;
        setMessages(m => [...m, msgObj]);
      } else {
        const segments = replyText.split('\n\n').map(s => s.trim()).filter(s => s.length > 0);
        for (let i = 0; i < segments.length; i++) {
          if (i > 0) {
            setTyping(true);
            await new Promise(r => setTimeout(r, 600 + Math.min(segments[i].length * 30, 1200)));
            setTyping(false);
          }
          const msgObj = { id: ++msgIdRef.current, role: 'ai', text: segments[i], time, type: 'normal', isNew: true };
          if (i === 0 && thinkingText) msgObj.thinking = thinkingText;
          setMessages(m => [...m, msgObj]);
        }
      }
    } catch (e) {
      setTyping(false);
      setStreaming('');
      const message = e.message?.includes('流式响应中断')
        ? '回复中断了，刚刚那次没有完整生成。'
        : e.message?.includes('模型输出被截断')
          ? '模型输出被截断了。可以关掉扩展思考，或换一个输出上限更高的模型。'
          : e.message?.startsWith('后端返回错误')
            ? e.message
            : '连不上后端，请确认后端在运行中。';
      setMessages(m => [...m, { id: ++msgIdRef.current, role: 'ai', text: message, time: formatBJTime(new Date().toISOString()), type: 'normal', isNew: true }]);
    }
  }

  async function sendMessage() {
    if (!inputValRef.current.trim() && !pendingImage) return;
    const txt = inputValRef.current;
    const img = pendingImage;
    const quote = quotedMsg;
    inputValRef.current = '';
    if (inputRef.current) { inputRef.current.value = ''; inputRef.current.style.height = 'auto'; }
    setHasInput(false);
    setPendingImage(null);
    setQuotedMsg(null);
    setShowActions(false);
    const time = formatBJTime(new Date().toISOString());
    const userMsg = { id: ++msgIdRef.current, role: 'user', text: txt, time, isNew: true };
    if (img) userMsg.image = img;
    if (quote) userMsg.quote = quote.text.length > 60 ? quote.text.slice(0, 60) + '…' : quote.text;
    setMessages(m => [...m, userMsg]);
    const msgToSend = quote
      ? `[引用${quote.role === 'ai' ? ' Connie' : '自己'}的话：「${quote.text.slice(0, 120)}」]\n${txt}`
      : txt;
    await fetchReply(msgToSend, img);
  }

  async function regenerate() {
    const lastUserIdx = [...messages].reverse().findIndex(m => m.role === 'user');
    if (lastUserIdx === -1) return;
    const lastUser = messages[messages.length - 1 - lastUserIdx];
    await fetchReply(lastUser.text, lastUser.image);
  }

  function toggleKeep(id) {
    setKept(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  }
  const holdMessage = useCallback((id) => { msgTimer.current = setTimeout(() => toggleKeep(id), 480); }, []);
  const releaseMessage = useCallback(() => { if (msgTimer.current) clearTimeout(msgTimer.current); }, []);
  const quoteMessage = useCallback((m) => { setQuotedMsg(m); inputRef.current?.focus(); }, []);
  const toggleThink = useCallback((id) => {
    setExpandedThink(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  }, []);

  function handleRename(newName) {
    const sysText = `静儿修改你的备注为「${newName}」`;
    const time = formatBJTime(new Date().toISOString());
    setMessages(m => [...m, { id: ++msgIdRef.current, role: 'system', text: sysText, time, isNew: true }]);
    fetchReply(sysText);
    apiJsonFetch('/push/update-name', { method: 'POST', body: JSON.stringify({ display_name: newName }) }).catch(() => {});
  }

  function chooseChatMode(mode) {
    setChatMode(mode);
    localStorage.setItem('remoire_chat_mode', mode);
  }

  function pickPhoto(file) {
    if (!file) return;
    const r = new FileReader();
    r.onload = () => { setPendingImage(r.result); setShowActions(false); inputRef.current?.focus(); };
    r.readAsDataURL(file);
  }

  const cssVars = {
    '--ink': palette.ink,
    '--ink-soft': palette.inkSoft,
    '--ink-faint': palette.inkFaint,
    '--ink-accent': palette.inkAccent,
    '--ai-bg': palette.aiBubble.bg,
    '--ai-border': palette.aiBubble.border,
    '--ai-edge': palette.aiBubble.edge,
    '--ai-text': palette.aiBubble.text,
    '--ai-shadow': palette.aiBubble.shadow,
    '--user-bg': palette.userBubble.bg,
    '--user-border': palette.userBubble.border,
    '--user-edge': palette.userBubble.edge,
    '--user-text': palette.userBubble.text,
    '--warm-shadow': palette.warmShadow,
    '--sheet-bg': palette.sheetBg,
    '--sheet-bd': palette.sheetBd,
    '--nav-bg': palette.navBg,
    '--nav-border': palette.navBorder,
    '--pop-bg': palette.popBg,
    '--ink-on-sheet': palette.inkOnSheet,
  };

  return (
    <div style={{
      ...cssVars,
      width: '100%',
      height: '100%',
      minHeight: '-webkit-fill-available',
      position: 'relative', overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
      background: palette.navBg,
      fontFamily: "var(--font-display)",
      color: palette.ink,
    }}>
      {/* Background */}
      <div className="r-bg" style={chatBgImage ? {
        backgroundImage: `url(${chatBgImage})`,
        backgroundSize: 'cover', backgroundPosition: 'center',
      } : { background: palette.bg }} />
      {chatBgImage && (
        <div className="r-bg-wash" style={{
          background: dark
            ? 'linear-gradient(180deg, rgba(20,12,8,0.32) 0%, rgba(20,12,8,0.22) 50%, rgba(20,12,8,0.38) 100%)'
            : 'linear-gradient(180deg, rgba(255,240,220,0.22) 0%, rgba(255,235,210,0.10) 50%, rgba(120,80,50,0.18) 100%)',
        }} />
      )}
      <svg className="r-grain"><filter id="r-noise"><feTurbulence baseFrequency="0.85" numOctaves="2" seed="3" /></filter><rect width="100%" height="100%" filter="url(#r-noise)" opacity="0.06" /></svg>

      <Floaters kind={palette.floaterKind} />

      {weather === 'rain' && <RainLayer />}
      {weather === 'fog'  && <FogLayer />}

      <div className="r-dim" style={{ opacity: deepMode ? 0.32 : 0 }} />

      {/* Header */}
      <div className="r-header">
        <button className="r-burger" onClick={() => { setSearchOpen(true); setTimeout(() => searchInputRef.current?.focus(), 100); }} title="搜索聊天">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
        </button>
        <div className="r-header-center">
          {editingName ? (
            <input
              autoFocus
              value={connieName}
              onChange={e => setConnieName(e.target.value)}
              onBlur={() => { setEditingName(false); if (connieName !== nameBeforeEdit.current) handleRename(connieName); }}
              onKeyDown={e => { if (e.key === 'Enter') { setEditingName(false); if (connieName !== nameBeforeEdit.current) handleRename(connieName); } }}
              className="r-name-input"
            />
          ) : (
            <button className="r-name" onClick={() => { nameBeforeEdit.current = connieName; setEditingName(true); }} title="改个备注">
              {connieName}
            </button>
          )}
          <div key={`${band}-${ambientIdx}`} className="r-state">
            {breathText || ambientLines[ambientIdx]}
          </div>
        </div>
        <button className="r-burger" onClick={() => setShowSheet(true)} title="这间房">
          <span /><span /><span />
        </button>
      </div>

      {/* Search overlay */}
      {searchOpen && (
        <div className="r-search-overlay">
          <div className="r-search-bar">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <circle cx="11" cy="11" r="7" /><path d="M21 21l-4.35-4.35" />
            </svg>
            <input
              ref={searchInputRef}
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="搜索聊天内容……"
              className="r-search-input"
            />
            <button className="r-search-close" onClick={() => { setSearchOpen(false); setSearchQuery(''); }}>✕</button>
          </div>
          {searchQuery.trim() && (
            <div className="r-search-results">
              {searching ? (
                <div className="r-search-empty">正在翻旧聊天…</div>
              ) : searchResults.length === 0 ? (
                <div className="r-search-empty">没有找到相关内容</div>
              ) : (
                searchResults.map(m => (
                  <div key={m.id} className="r-search-item">
                    <div className="r-search-item-role">{m.role === 'ai' ? connieName : '你'}</div>
                    <div className="r-search-item-text">{m.text}</div>
                    {m.time && <div className="r-search-item-time">{m.time}</div>}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}

      {/* Note card */}
      {noteState === 'visible' && noteData && (() => {
        const noteStyle = tweaks?.noteStyle || 'washi';
        const dismissNote = async () => {
          setNoteError('');
          setNoteState('hidden');
          try {
            const response = await apiJsonFetch(`/note/${noteData.id}/read`, { method: 'POST', body: JSON.stringify({ action: 'dismiss' }) });
            if (!response.ok) throw new Error('纸条状态保存失败');
          } catch {
            setNoteState('visible');
            setNoteError('还没保存成功，请再试一次。');
          }
        };
        const keepNote = async () => {
          setNoteError('');
          setNoteState('hidden');
          try {
            const response = await apiJsonFetch(`/note/${noteData.id}/read`, { method: 'POST', body: JSON.stringify({ action: 'keep' }) });
            if (!response.ok) throw new Error('纸条状态保存失败');
          } catch {
            setNoteState('visible');
            setNoteError('还没保存成功，请再试一次。');
          }
        };
        const noteActions = (
          <div>
            {noteError && <div role="status" style={{ color: 'var(--danger)', fontSize: 11, marginTop: 8 }}>{noteError}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 14, marginTop: 8 }}>
              <button onClick={dismissNote} style={{ background: 'none', border: 'none', minHeight: 44, padding: '8px', fontSize: 12, color: 'var(--ink-soft)', cursor: 'pointer', fontFamily: "var(--font-body)" }}>知道了</button>
              <button onClick={keepNote} style={{ background: 'none', border: 'none', minHeight: 44, padding: '8px', fontSize: 12, color: 'var(--ink-accent)', cursor: 'pointer', fontFamily: "var(--font-body)", textDecoration: 'underline', textUnderlineOffset: 4 }}>留着</button>
            </div>
          </div>
        );
        const noteLabel = <div style={{ fontStyle: 'italic', fontSize: 11, color: 'var(--ink-soft)', marginBottom: 6, letterSpacing: '0.08em' }}>✦ Connie 留了一张纸条</div>;

        if (noteStyle === 'washi') return (
          <div style={{ padding: '0 16px 8px', position: 'relative', zIndex: 10 }}>
            <div style={{ position: 'relative', padding: '16px 16px 12px' }}>
              <div style={{
                position: 'absolute', top: -2, left: 24, right: 24, height: 22,
                background: 'linear-gradient(90deg, rgba(255,220,180,0.35) 0%, rgba(255,200,150,0.25) 40%, rgba(240,190,140,0.30) 100%)',
                borderRadius: 2, transform: 'rotate(-0.8deg)',
                boxShadow: '0 1px 3px rgba(120,70,30,0.08)',
                backdropFilter: 'blur(6px) saturate(1.1)', WebkitBackdropFilter: 'blur(6px) saturate(1.1)',
              }} />
              <div style={{
                position: 'absolute', bottom: 0, left: 34, right: 44, height: 18,
                background: 'linear-gradient(90deg, rgba(180,210,200,0.30) 0%, rgba(160,200,190,0.22) 100%)',
                borderRadius: 2, transform: 'rotate(0.6deg)',
                boxShadow: '0 1px 3px rgba(120,70,30,0.06)',
                backdropFilter: 'blur(6px) saturate(1.1)', WebkitBackdropFilter: 'blur(6px) saturate(1.1)',
              }} />
              <div style={{
                background: 'rgba(255,250,235,0.12)',
                backdropFilter: 'blur(12px) saturate(1.2)', WebkitBackdropFilter: 'blur(12px) saturate(1.2)',
                border: '1px solid rgba(255,240,220,0.18)', borderRadius: 4,
                padding: '12px 14px', transform: 'rotate(-0.4deg)',
                color: 'var(--ink)', fontFamily: "var(--font-note)", fontSize: 14, lineHeight: 1.7,
              }}>
                {noteLabel}
                <div>{noteData.content}</div>
                {noteActions}
              </div>
            </div>
          </div>
        );

        if (noteStyle === 'frost') return (
          <div style={{ padding: '0 16px 8px', position: 'relative', zIndex: 10 }}>
            <div style={{
              position: 'relative', padding: '12px 16px',
              background: 'rgba(255,250,235,0.10)',
              backdropFilter: 'blur(16px) saturate(1.3)', WebkitBackdropFilter: 'blur(16px) saturate(1.3)',
              borderRadius: 16,
              border: '1px solid rgba(255,240,220,0.20)',
              boxShadow: '0 4px 16px -6px rgba(120,70,30,0.10), inset 0 1px 0 rgba(255,250,235,0.30)',
              color: 'var(--ink)', fontFamily: "var(--font-note)", fontSize: 14, lineHeight: 1.7,
            }}>
              <div style={{
                position: 'absolute', inset: 0, borderRadius: 16, overflow: 'hidden', pointerEvents: 'none',
              }}>
                <div style={{
                  position: 'absolute', top: 0, left: 0, right: 0, height: '40%',
                  background: 'linear-gradient(180deg, rgba(255,250,235,0.18) 0%, transparent 100%)',
                  mixBlendMode: 'overlay',
                }} />
              </div>
              <div style={{ position: 'relative' }}>
                {noteLabel}
                <div>{noteData.content}</div>
                {noteActions}
              </div>
            </div>
          </div>
        );

        if (noteStyle === 'torn') return (
          <div style={{ padding: '0 16px 8px', position: 'relative', zIndex: 10 }}>
            <div style={{
              background: 'rgba(255,250,235,0.14)',
              backdropFilter: 'blur(10px) saturate(1.15)', WebkitBackdropFilter: 'blur(10px) saturate(1.15)',
              borderRadius: 3, padding: '12px 14px',
              clipPath: 'polygon(0 0, 100% 0, 100% 88%, 98% 91%, 95% 88%, 92% 92%, 88% 88%, 85% 91%, 80% 88%, 75% 92%, 70% 88%, 65% 91%, 60% 88%, 55% 92%, 50% 88%, 45% 91%, 40% 88%, 35% 92%, 30% 88%, 25% 91%, 20% 88%, 15% 92%, 10% 88%, 5% 91%, 2% 88%, 0 92%)',
              transform: 'rotate(-0.4deg)',
              color: 'var(--ink)', fontFamily: "var(--font-note)", fontSize: 14, lineHeight: 1.7,
            }}>
              {noteLabel}
              <div>{noteData.content}</div>
              {noteActions}
            </div>
          </div>
        );

        return (
          <div style={{ padding: '0 16px 8px', position: 'relative', zIndex: 10 }}>
            <div style={{ position: 'relative', padding: '14px 0 0' }}>
              <div style={{
                position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%) rotate(2deg)',
                width: 36, height: 12, background: 'rgba(130,189,197,0.35)', borderRadius: 1,
                backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)',
              }} />
              <div style={{
                background: 'rgba(255,250,235,0.14)',
                backdropFilter: 'blur(10px) saturate(1.15)', WebkitBackdropFilter: 'blur(10px) saturate(1.15)',
                border: '1px solid rgba(255,240,220,0.15)', borderRadius: 4,
                padding: '12px 14px', transform: 'rotate(-0.4deg)',
                color: 'var(--ink)', fontFamily: "var(--font-note)", fontSize: 14, lineHeight: 1.7,
              }}>
                {noteLabel}
                <div>{noteData.content}</div>
                {noteActions}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Conversation */}
      <div ref={scrollRef} className="r-scroll" style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', scrollbarWidth: 'none' }}>
        <div style={{ padding: '20px 16px 12px', display: 'flex', flexDirection: 'column', gap: 18 }}>
          {messages.map(m => {
            if (m.role === 'system') {
              return (
                <div key={m.id} style={{
                  padding: '6px 14px', borderRadius: 12,
                  background: 'rgba(255,250,235,0.08)',
                  border: '1px dashed var(--ink-faint)',
                  fontSize: 12, color: 'var(--ink-soft)',
                  textAlign: 'center', fontStyle: 'italic',
                  margin: '0 40px',
                }}>{m.text}</div>
              );
            }
            if (m.type === 'tool_call') {
              return <ToolCallBanner key={m.id} tools={m.tools} count={m.count} done />;
            }
            return (
              <MessageRow
                key={m.id} m={m}
                isKept={kept.has(m.id)}
                isThinkOpen={expandedThink.has(m.id)}
                onToggleThink={toggleThink}
                onHold={holdMessage}
                onRelease={releaseMessage}
                onQuote={quoteMessage}
                onRegenerate={regenerate}
              />
            );
          })}

          {toolCall && (
            <ToolCallBanner tools={toolCall.tools} count={toolCall.count} done={false} />
          )}

          {streaming && (
            <div className="r-row r-row-ai">
              <div className="r-spark">✦</div>
              <div className="r-bubble r-bubble-ai r-cursor">{streaming}</div>
            </div>
          )}

          {typing && !streaming && (
            <div className="r-row r-row-ai">
              <div className="r-spark r-spark-active">✦</div>
              <div className="r-thinking-dots">
                <span /><span /><span />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Input bar */}
      <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }}
        onChange={e => pickPhoto(e.target.files?.[0])} />
      <div className="r-input-wrap">
        {quotedMsg && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '6px 12px', margin: '0 0 -2px',
            background: 'rgba(124,99,80,0.06)',
            borderLeft: '2px solid var(--ink-accent, var(--accent))',
            borderRadius: '4px 8px 0 0',
            fontSize: 12, color: 'var(--ink-soft, var(--text-tertiary))',
            lineHeight: 1.4,
          }}>
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {quotedMsg.role === 'ai' ? '引用 Connie：' : '引用自己：'}
              {quotedMsg.text?.slice(0, 50)}{quotedMsg.text?.length > 50 ? '…' : ''}
            </span>
            <button onClick={() => setQuotedMsg(null)} style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--ink-faint, var(--text-tertiary))', fontSize: 14,
              padding: '0 2px', lineHeight: 1,
            }}>✕</button>
          </div>
        )}
        {pendingImage && (
          <div className="r-pending">
            <img src={pendingImage} alt="" />
            <button onClick={() => setPendingImage(null)}>✕</button>
          </div>
        )}
        {showActions && (
          <div className="r-action-row">
            <button className="r-action-tile" onClick={() => fileRef.current?.click()}>
              <span className="r-action-glyph">◰</span>
              <span className="r-action-label">照片</span>
            </button>
          </div>
        )}

        <div className="r-input-bar">
          <button className="r-ibtn" onClick={() => setShowActions(v => !v)}
            style={{ transform: showActions ? 'rotate(45deg)' : 'rotate(0)' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M12 5v14M5 12h14" strokeLinecap="round" />
            </svg>
          </button>

          <div style={{ position: 'relative' }}>
            <button className="r-mode-label" onClick={() => setShowModes(v => !v)}
              title={CHAT_MODES[chatMode].desc}>
              {CHAT_MODES[chatMode].label}
            </button>
            {showModes && (
              <div className="r-mode-pop">
                {Object.entries(CHAT_MODES).map(([k, v]) => (
                  <button key={k} className={`r-mode-row ${chatMode === k ? 'active' : ''}`}
                    onClick={() => { chooseChatMode(k); setShowModes(false); }}>
                    <div className="r-mode-row-name">{v.label}</div>
                    <div className="r-mode-row-desc">{v.desc}</div>
                  </button>
                ))}
                <div className="r-mode-divider" />
                <button className="r-mode-row" onClick={() => { setDeepMode(!deepMode); setShowModes(false); }}>
                  <div className="r-mode-row-name">{deepMode ? '回到浅处' : '走深一点'}</div>
                  <div className="r-mode-row-desc">房间变暗、间隔变长</div>
                </button>
              </div>
            )}
          </div>

          <textarea
            ref={inputRef}
            defaultValue=""
            onChange={handleInput}
            onKeyDown={e => {
              if (e.nativeEvent.isComposing) return;
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
            }}
            onPaste={e => {
              const items = e.clipboardData?.items;
              if (!items) return;
              for (const item of items) {
                if (item.type.startsWith('image/')) {
                  e.preventDefault();
                  pickPhoto(item.getAsFile());
                  return;
                }
              }
            }}
            placeholder={deepMode ? '慢慢说……' : '说点什么……'}
            rows={1}
            className="r-input"
          />

          {(hasInput || pendingImage) ? (
            <button className="r-ibtn r-ibtn-send" onClick={sendMessage}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M12 19V5M5 12l7-7 7 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          ) : (
            <button className={`r-ibtn ${voiceHold ? 'r-ibtn-mic holding' : ''}`}
              onMouseDown={() => setVoiceHold(true)} onMouseUp={() => setVoiceHold(false)} onMouseLeave={() => setVoiceHold(false)}
              onTouchStart={() => setVoiceHold(true)} onTouchEnd={() => setVoiceHold(false)}>
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                <rect x="9" y="3" width="6" height="12" rx="3" />
                <path d="M5 11v1a7 7 0 0 0 14 0v-1M12 19v3" strokeLinecap="round" />
              </svg>
              {voiceHold && <div className="r-mic-ripple" />}
            </button>
          )}
        </div>
      </div>

      <div className="r-nav-spacer" />
      {/* Bottom nav */}
      <div className="r-nav">
        {NAV_TABS.map(t => {
          const svgProps = { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.4 };
          return (
            <button key={t.id} className={`r-nav-btn ${activeTab === t.id ? 'active' : ''}`}
              onClick={() => onNavigate(t.id)}>
              {t.icon(svgProps)}
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>

      {/* Settings sheet */}
      {showSheet && (
        <SettingsSheet
          timeOverride={timeOverride} setTimeOverride={setTimeOverride}
          weather={weather} setWeather={setWeather}
          deepMode={deepMode} setDeepMode={setDeepMode}
          connieName={connieName} setConnieName={setConnieName}
          chatBgImage={chatBgImage} setChatBgImage={setChatBgImage}
          replyStyle={replyStyle} setReplyStyle={setReplyStyle}
          onRename={handleRename}
          onClose={() => setShowSheet(false)}
        />
      )}

      {voiceHold && (
        <div className="r-voice-overlay">
          <div className="r-voice-wave"><span /><span /><span /><span /><span /></div>
          <div className="r-voice-hint">松开发送 · 上滑取消</div>
        </div>
      )}
    </div>
  );
}
