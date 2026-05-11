import { useState } from 'react';
import ChatPage from './components/ChatPage.jsx';
import UsPage from './components/UsPage.jsx';
import DiaryPage from './components/DiaryPage.jsx';
import PlayPage from './components/PlayPage.jsx';
import SettingsPage from './components/SettingsPage.jsx';

const NAV_TABS = [
  { id: 'chat',     label: '聊天',  icon: () => <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> },
  { id: 'us',       label: '我们',  icon: () => <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg> },
  { id: 'diary',    label: '日记',  icon: () => <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg> },
  { id: 'play',     label: '玩乐',  icon: () => <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polygon points="5 3 19 12 5 21 5 3"/></svg> },
  { id: 'settings', label: '设置',  icon: () => <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg> },
];

export default function App() {
  const [tab, setTab] = useState('chat');

  const pages = {
    chat:     <ChatPage />,
    us:       <UsPage />,
    diary:    <DiaryPage />,
    play:     <PlayPage />,
    settings: <SettingsPage />,
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-primary)', position: 'relative' }}>
      {Object.entries(pages).map(([id, page]) => (
        <div key={id} style={{ flex: 1, overflow: 'hidden', position: 'relative', display: tab === id ? 'flex' : 'none', flexDirection: 'column' }}>
          {page}
        </div>
      ))}

      <div style={{
        display: 'flex', justifyContent: 'space-around',
        padding: '8px 0 16px',
        background: 'var(--bg-primary)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderTop: '1px solid var(--border-light)',
        flexShrink: 0,
      }}>
        {NAV_TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
            background: 'none', border: 'none', cursor: 'pointer', padding: '4px 12px',
            color: tab === t.id ? 'var(--accent)' : 'var(--text-secondary)',
            opacity: 1,
            transition: 'all 0.2s ease',
            minWidth: 44, minHeight: 44, justifyContent: 'center',
          }}>
            {t.icon()}
            <span style={{ fontSize: 10, fontWeight: tab === t.id ? 500 : 400, fontFamily: "var(--font-body)" }}>{t.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
