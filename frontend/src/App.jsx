import { useEffect, useMemo, useState } from 'react';
import ChatPage from './components/ChatPage.jsx';
import UsPage from './components/UsPage.jsx';
import DiaryPage from './components/DiaryPage.jsx';
import PlayPage from './components/PlayPage.jsx';
import SettingsPage from './components/SettingsPage.jsx';
import { RoomAmbientProvider, useRoomAmbient, useRoomChrome } from './components/RoomShell.jsx';
import './styles/room.css';


const TWEAK_STORAGE_KEY = 'remoire_tweaks';

const FONT_SLOTS = {
  Chat: { cssVar: '--font-chat', family: 'RemoireCustomChat', fallback: "'Manrope', 'LXGW WenKai', 'Helvetica Neue', sans-serif" },
  Note: { cssVar: '--font-note', family: 'RemoireCustomNote', fallback: "'ShouShuTi', 'JustAnotherHand', 'Caveat', cursive" },
  Diary: { cssVar: '--font-diary', family: 'RemoireCustomDiary', fallback: "'ShouShuTi', 'JustAnotherHand', cursive" },
  Read: { cssVar: '--font-read', family: 'RemoireCustomRead', fallback: "'Caveat', 'JustAnotherHand', cursive" },
  Parallel: { cssVar: '--font-parallel', family: 'RemoireCustomParallel', fallback: "'Petrona', 'LXGW WenKai', Georgia, serif" },
};

function loadTweaks() {
  try {
    return JSON.parse(window.localStorage.getItem(TWEAK_STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

function applyPlainTweaks(tweaks) {
  const root = document.documentElement;
  root.dataset.theme = tweaks.darkMode ? 'dark' : 'light';
  if (tweaks.accentColor) root.style.setProperty('--accent', tweaks.accentColor);
  else root.style.removeProperty('--accent');
}

async function applyCustomFonts(tweaks) {
  if (!('FontFace' in window) || !document.fonts) return;
  await Promise.all(Object.entries(FONT_SLOTS).map(async ([slot, config]) => {
    const dataUrl = tweaks[`font${slot}`];
    const root = document.documentElement;
    if (!dataUrl) {
      root.style.setProperty(config.cssVar, config.fallback);
      return;
    }

    try {
      const fontFace = new FontFace(config.family, `url(${dataUrl})`);
      const loaded = await fontFace.load();
      document.fonts.add(loaded);
      root.style.setProperty(config.cssVar, `'${config.family}', ${config.fallback}`);
    } catch (error) {
      console.warn(`加载自定义字体失败：${slot}`, error);
      root.style.setProperty(config.cssVar, config.fallback);
    }
  }));
}

const ROOM_NAV_TABS = [
  { id: 'chat',     label: '聊天',  icon: (s) => <svg {...s}><path d="M21 12a8 8 0 0 1-11.5 7.2L4 21l1.5-4.5A8 8 0 1 1 21 12z"/></svg> },
  { id: 'us',       label: '我们',  icon: (s) => <svg {...s}><path d="M20 9a6 6 0 0 0-8-5 6 6 0 0 0-8 5c0 6 8 11 8 11s8-5 8-11z"/></svg> },
  { id: 'diary',    label: '日记',  icon: (s) => <svg {...s}><path d="M4 4h11a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3z"/><path d="M9 8h6M9 12h6"/></svg> },
  { id: 'play',     label: '玩乐',  icon: (s) => <svg {...s}><circle cx="12" cy="12" r="9"/><path d="M10 9l5 3-5 3z" fill="currentColor"/></svg> },
  { id: 'settings', label: '设置',  icon: (s) => <svg {...s}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.65 1.65 0 0 0-1.8-.3 1.65 1.65 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.65 1.65 0 0 0-1-1.5 1.65 1.65 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.65 1.65 0 0 0 .3-1.8 1.65 1.65 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.65 1.65 0 0 0 1.5-1 1.65 1.65 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.65 1.65 0 0 0 1.8.3h.1a1.65 1.65 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.65 1.65 0 0 0 1 1.5h.1a1.65 1.65 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.65 1.65 0 0 0-.3 1.8v.1a1.65 1.65 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.65 1.65 0 0 0-1.5 1z"/></svg> },
];

function RoomNav({ activeTab, onNavigate, ambient }) {
  const { palette, accentColor } = ambient;
  const navVars = {
    '--ink': palette.ink,
    '--ink-soft': palette.inkSoft,
    '--ink-accent': accentColor || palette.inkAccent,
    '--nav-bg': palette.navBg,
    '--nav-border': palette.navBorder,
    '--warm-shadow': palette.warmShadow,
    '--ai-edge': palette.aiBubble.edge,
  };
  const svgProps = { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.4 };
  return (
    <div className="r-nav" style={navVars}>
      {ROOM_NAV_TABS.map(t => (
        <button key={t.id} className={`r-nav-btn ${activeTab === t.id ? 'active' : ''}`}
          onClick={() => onNavigate(t.id)}>
          {t.icon(svgProps)}
          <span>{t.label}</span>
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState('chat');
  const [tweaks, setTweaks] = useState(() => loadTweaks());
  const ambient = useRoomAmbient();
  const { palette, chatBgImage } = ambient;
  useRoomChrome(palette, chatBgImage);
  useEffect(() => {
    function onTweakUpdate(event) {
      setTweaks((current) => ({ ...current, ...(event.detail || {}) }));
    }
    window.addEventListener('tweak-update', onTweakUpdate);
    return () => window.removeEventListener('tweak-update', onTweakUpdate);
  }, []);

  useEffect(() => {
    applyPlainTweaks(tweaks);
    applyCustomFonts(tweaks);
  }, [tweaks]);

  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    let lastHeight = vv.height;
    function forceReflow() {
      window.scrollTo(0, 0);
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
      const body = document.body;
      const prev = body.style.height;
      body.style.height = window.innerHeight + 'px';
      void body.offsetHeight;
      body.style.height = '100lvh';
      void body.offsetHeight;
      body.style.height = prev || '100lvh';
    }
    function onResize() {
      const h = vv.height;
      const grew = h > lastHeight + 80;
      lastHeight = h;
      if (grew) {
        requestAnimationFrame(forceReflow);
        setTimeout(forceReflow, 100);
        setTimeout(forceReflow, 400);
      }
    }
    function onBlur(e) {
      const tag = e.target?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
        setTimeout(forceReflow, 250);
      }
    }
    vv.addEventListener('resize', onResize);
    document.addEventListener('focusout', onBlur, true);
    return () => {
      vv.removeEventListener('resize', onResize);
      document.removeEventListener('focusout', onBlur, true);
    };
  }, []);

  const nav = useMemo(
    () => <RoomNav activeTab={tab} onNavigate={setTab} ambient={ambient} />,
    [tab, ambient]
  );

  const pages = useMemo(() => ({
    chat:     <ChatPage tweaks={tweaks} activeTab={tab} onNavigate={setTab} />,
    us:       <UsPage tweaks={tweaks} nav={nav} />,
    diary:    <DiaryPage tweaks={tweaks} nav={nav} active={tab === 'diary'} />,
    play:     <PlayPage tweaks={tweaks} nav={nav} />,
    settings: <SettingsPage tweaks={tweaks} nav={nav} />,
  }), [tweaks, tab, nav]);

  return (
    <RoomAmbientProvider value={ambient}>
      <div style={{
        width: '100%',
        flex: 1,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        background: 'transparent',
        overflow: 'hidden',
      }}>
        {Object.entries(pages).map(([id, page]) => (
          <div key={id} style={{
            flex: 1,
            overflow: 'hidden',
            position: 'relative',
            display: tab === id ? 'flex' : 'none',
            flexDirection: 'column',
          }}>
            {page}
          </div>
        ))}
      </div>
    </RoomAmbientProvider>
  );
}
