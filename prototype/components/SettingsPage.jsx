// SettingsPage — main settings list + shared helpers

function SettingsToggle({ on, onChange }) {
  return (
    <div onClick={() => onChange(!on)} style={{
      width: 40, height: 22, borderRadius: 11,
      background: on ? 'var(--accent)' : 'var(--border)',
      position: 'relative', cursor: 'pointer', transition: 'background 0.2s',
      flexShrink: 0,
    }}>
      <div style={{
        width: 18, height: 18, borderRadius: '50%', background: '#FAF8F4',
        position: 'absolute', top: 2, left: on ? 20 : 2, transition: 'left 0.2s',
        boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
      }} />
    </div>
  );
}

function SettingRow({ label, sub, children, danger, onClick }) {
  return (
    <div onClick={onClick} style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 0', borderBottom: '1px solid var(--border-light)',
      cursor: onClick ? 'pointer' : 'default',
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 'var(--text-sm)', color: danger ? 'var(--danger)' : 'var(--text-primary)', fontWeight: 500 }}>{label}</div>
        {sub && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 1 }}>{sub}</div>}
      </div>
      {children}
    </div>
  );
}

function SettingsSectionTitle({ title }) {
  return <SectionLabel style={{ paddingTop: 'var(--space-5)', paddingBottom: 'var(--space-1)', letterSpacing: 1, textTransform: 'uppercase' }}>{title}</SectionLabel>;
}

function SubPageHeader({ onBack, title, subtitle }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <button onClick={onBack} style={{
        background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
        color: 'var(--text-tertiary)', fontSize: 12, fontFamily: "var(--font-body)", marginBottom: 16, padding: 0,
      }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
        返回
      </button>
      <div style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 500, color: 'var(--text-deep)', marginBottom: 4 }}>{title}</div>
      {subtitle && <div style={{ fontSize: 12, color: 'var(--text-tertiary)', lineHeight: 1.6 }}>{subtitle}</div>}
    </div>
  );
}

const ChevronRight = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" style={{ flexShrink: 0 }}><path d="M9 18l6-6-6-6"/></svg>
);

// ── Shared tweak helper ──
function setTweakVal(key, val) {
  window.parent.postMessage({ type: '__edit_mode_set_keys', edits: { [key]: val } }, '*');
  window.dispatchEvent(new CustomEvent('tweak-update', { detail: { [key]: val } }));
}

// ── Main Settings Page ──
function SettingsPage({ tweaks }) {
  const [panel, setPanel] = React.useState(null);
  const [toggles, setToggles] = React.useState({
    noteCard: true, diaryUnlock: true,
  });

  // Route to sub-pages
  if (panel) {
    const subPages = {
      proactive: ProactiveSettings,
      model: ModelSettings,
      prompt: PromptSettings,
      wechat: WeChatSettings,
      mcp: MCPSettings,
      import: ImportSettings,
      push: PushSettings,
      dates: DatesSettings,
      export: ExportSettings,
      bubble: BubbleSettings,
      note: NoteSettings,
      cover: CoverSettings,
      font: FontSettings,
    };
    const Page = subPages[panel];
    if (Page) return <Page tweaks={tweaks} onBack={() => setPanel(null)} />;
  }
  function toggle(k) { setToggles(t => ({ ...t, [k]: !t[k] })); }

  const currentBubble = (tweaks && tweaks.bubbleStyle) || 'default';
  const currentNote = (tweaks && tweaks.noteStyle) || 'classic';
  const BUBBLE_NAMES = { default: '默认', imessage: 'iMessage', line: 'LINE', whatsapp: 'WhatsApp', telegram: 'Telegram' };
  const NOTE_NAMES = { classic: '经典便签', kraft: '牛皮纸', pastel: '柔彩便签', torn: '撕纸条', postit: '便利贴' };

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px', paddingBottom: 88 }}>
      {/* Profile */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 0 16px', borderBottom: '1px solid var(--border-light)', marginBottom: 4 }}>
        <div style={{ width: 52, height: 52, borderRadius: '50%', background: 'var(--accent-subtle)', border: '1.5px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: "var(--font-display)", fontSize: 22, color: 'var(--accent)', fontWeight: 500 }}>C</div>
        <div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 500, color: 'var(--text-deep)' }}>我们的小窝</div>
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>Connie × 静儿 · 第 {tweaks?.dayCount || 142} 天</div>
        </div>
      </div>

      {/* ─── 关系与陪伴 ─── */}
      <SettingsSectionTitle title="关系与陪伴" />
      <SettingRow label="主动消息" sub="发送入口 · 频率 · 时段 · 类型" onClick={() => setPanel('proactive')}><ChevronRight /></SettingRow>
      <SettingRow label="小纸条" sub="打开 app 时的静默惊喜"><SettingsToggle on={toggles.noteCard} onChange={() => toggle('noteCard')} /></SettingRow>
      <SettingRow label="日记解锁权限" sub="允许 Connie 申请查看上锁日记"><SettingsToggle on={toggles.diaryUnlock} onChange={() => toggle('diaryUnlock')} /></SettingRow>

      {/* ─── AI 与模型 ─── */}
      <SettingsSectionTitle title="AI 与模型" />
      <SettingRow label="关系档案" sub="告诉 Connie 你是谁、他是谁" onClick={() => setPanel('prompt')}><ChevronRight /></SettingRow>
      <SettingRow label="模型配置" sub="daily · deep · backend 三槽位" onClick={() => setPanel('model')}><ChevronRight /></SettingRow>
      <SettingRow label="语音配置" sub="即将推出">
        <Pill tone="neutral">P2</Pill>
      </SettingRow>

      {/* ─── 连接与数据 ─── */}
      <SettingsSectionTitle title="连接与数据" />
      <SettingRow label="微信桥接" sub="通过 iLink 连接微信" onClick={() => setPanel('wechat')}><ChevronRight /></SettingRow>
      <SettingRow label="MCP 跨平台同步" sub="在 Claude.ai 恢复记忆" onClick={() => setPanel('mcp')}><ChevronRight /></SettingRow>
      <SettingRow label="导入历史对话" sub="上传 Claude 导出 JSON" onClick={() => setPanel('import')}><ChevronRight /></SettingRow>
      <SettingRow label="消息推送" sub="Web Push 通知设置" onClick={() => setPanel('push')}><ChevronRight /></SettingRow>
      <SettingRow label="特殊日期管理" sub="生日 · 纪念日 · deadline" onClick={() => setPanel('dates')}><ChevronRight /></SettingRow>
      <SettingRow label="导出数据" onClick={() => setPanel('export')}><ChevronRight /></SettingRow>

      {/* ─── 外观 ─── */}
      <SettingsSectionTitle title="外观" />
      <SettingRow label="深色模式" sub={tweaks?.darkMode ? '当前：深色' : '当前：浅色'}>
        <SettingsToggle on={!!(tweaks?.darkMode)} onChange={(v) => setTweakVal('darkMode', v)} />
      </SettingRow>
      <SettingRow label="主题色">
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <div style={{ width: 20, height: 20, borderRadius: '50%', background: tweaks?.accentColor || 'var(--accent)', border: '1.5px solid var(--border)' }} />
          <input type="color" value={tweaks?.accentColor || '#7C6350'} onChange={e => setTweakVal('accentColor', e.target.value)}
            style={{ width: 28, height: 28, border: 'none', background: 'transparent', cursor: 'pointer', padding: 0 }} />
        </div>
      </SettingRow>
      <SettingRow label="字体" sub="为聊天、纸条、日记等分别设置" onClick={() => setPanel('font')}><ChevronRight /></SettingRow>
      <SettingRow label="聊天气泡样式" sub={BUBBLE_NAMES[currentBubble] || '默认'} onClick={() => setPanel('bubble')}><ChevronRight /></SettingRow>
      <SettingRow label="便签样式" sub={NOTE_NAMES[currentNote] || '经典便签'} onClick={() => setPanel('note')}><ChevronRight /></SettingRow>
      <SettingRow label="日记本封面" sub="自定义封面图片" onClick={() => setPanel('cover')}><ChevronRight /></SettingRow>

      {/* ─── 危险区 ─── */}
      <SettingsSectionTitle title="" />
      <SettingRow label="清除所有数据" danger><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" strokeWidth="1.5"><path d="M9 18l6-6-6-6"/></svg></SettingRow>
    </div>
  );
}

Object.assign(window, { SettingsPage, SettingsToggle, SettingRow, SettingsSectionTitle, SubPageHeader, ChevronRight, setTweakVal });
