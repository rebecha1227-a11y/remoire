import { useState } from 'react';
import { Pill } from './primitives';
import {
  SettingsToggle, SettingRow, SettingsSectionTitle, ChevronRight,
} from './settingsShared';
import { setTweakVal } from '../utils/tweaks';

function getDayCount() {
  const start = new Date(2026, 2, 29);
  const now = new Date();
  const bj = new Date(now.getTime() + (8 * 60 + now.getTimezoneOffset()) * 60000);
  const today = new Date(bj.getFullYear(), bj.getMonth(), bj.getDate());
  return Math.max(1, Math.floor((today - start) / 86400000) + 1);
}
import {
  ProactiveSettings, PromptSettings, ModelSettings,
  WeChatSettings, MCPSettings, ImportSettings, PushSettings, DatesSettings, ExportSettings,
  BubbleSettings, NoteSettings, CoverSettings, FontSettings,
  NoteHistorySettings, MemoryCandidatesSettings,
} from './SettingsSubPages';
import RoomShell from './RoomShell';

export default function SettingsPage({ tweaks, nav }) {
  const [panel, setPanel] = useState(null);
  const [toggles, setToggles] = useState({
    noteCard: true, diaryUnlock: true,
  });

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
      noteHistory: NoteHistorySettings,
      memoryCandidates: MemoryCandidatesSettings,
    };
    const Page = subPages[panel];
    if (Page) return <RoomShell nav={nav}><div style={{ overflowY: 'auto', flex: 1, padding: '16px 20px 16px', position: 'relative', zIndex: 10 }}><Page tweaks={tweaks} onBack={() => setPanel(null)} /></div></RoomShell>;
  }
  function toggle(k) { setToggles(t => ({ ...t, [k]: !t[k] })); }

  const currentBubble = (tweaks && tweaks.bubbleStyle) || 'default';
  const currentNote = (tweaks && tweaks.noteStyle) || 'washi';
  const BUBBLE_NAMES = { default: '默认', imessage: 'iMessage', line: 'LINE', whatsapp: 'WhatsApp', telegram: 'Telegram' };
  const NOTE_NAMES = { washi: '和风胶带', frost: '毛玻璃纸条', classic: '经典便签', torn: '撕纸条' };

  return (
    <RoomShell nav={nav}>
    <div style={{ overflowY: 'auto', flex: 1, padding: '16px 14px 16px', position: 'relative', zIndex: 10, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div className="r-glass" style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px' }}>
        <div style={{
          width: 52, height: 52, borderRadius: '50%',
          background: 'var(--ai-bg)',
          border: '1px solid var(--ai-border)',
          backdropFilter: 'blur(9px) saturate(1.15)',
          WebkitBackdropFilter: 'blur(9px) saturate(1.15)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: "var(--font-display)",
          fontSize: 22, color: 'var(--ink-accent)', fontWeight: 500,
        }}>C</div>
        <div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 500, color: 'var(--ink)' }}>我们的小窝</div>
          <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 2 }}>Connie × 静儿 · 第 {getDayCount()} 天</div>
        </div>
      </div>

      <div className="r-glass" style={{ position: 'relative' }}>
        <SettingsSectionTitle title="关系与陪伴" />
        <SettingRow label="主动消息" sub="发送入口 · 频率 · 时段 · 类型" onClick={() => setPanel('proactive')}><ChevronRight /></SettingRow>
        <SettingRow label="小纸条" sub="打开 app 时的静默惊喜"><SettingsToggle on={toggles.noteCard} onChange={() => toggle('noteCard')} /></SettingRow>
        <SettingRow label="小纸条历史" sub="查看 Connie 留过的纸条" onClick={() => setPanel('noteHistory')}><ChevronRight /></SettingRow>
        <SettingRow label="记忆候选" sub="审核低置信度记忆" onClick={() => setPanel('memoryCandidates')}><ChevronRight /></SettingRow>
        <SettingRow label="日记解锁权限" sub="允许 Connie 申请查看上锁日记" noBorder><SettingsToggle on={toggles.diaryUnlock} onChange={() => toggle('diaryUnlock')} /></SettingRow>
      </div>

      <div className="r-glass" style={{ position: 'relative' }}>
        <SettingsSectionTitle title="AI 与模型" />
        <SettingRow label="关系档案" sub="查看当前身份与表达配置状态" onClick={() => setPanel('prompt')}><ChevronRight /></SettingRow>
        <SettingRow label="模型配置" sub="daily · deep · backend 三槽位" onClick={() => setPanel('model')}><ChevronRight /></SettingRow>
        <SettingRow label="语音配置" sub="即将推出" noBorder>
          <Pill tone="neutral">P2</Pill>
        </SettingRow>
      </div>

      <div className="r-glass" style={{ position: 'relative' }}>
        <SettingsSectionTitle title="连接与数据" />
        <SettingRow label="微信桥接" sub="规划中 · 尚未开放" onClick={() => setPanel('wechat')}><ChevronRight /></SettingRow>
        <SettingRow label="MCP 跨平台同步" sub="连接 ChatGPT 等支持 MCP 的客户端" onClick={() => setPanel('mcp')}><ChevronRight /></SettingRow>
        <SettingRow label="导入历史对话" sub="规划中 · 尚未开放" onClick={() => setPanel('import')}><ChevronRight /></SettingRow>
        <SettingRow label="消息推送" sub="Web Push 通知设置" onClick={() => setPanel('push')}><ChevronRight /></SettingRow>
        <SettingRow label="特殊日期管理" sub="生日 · 纪念日 · deadline" onClick={() => setPanel('dates')}><ChevronRight /></SettingRow>
        <SettingRow label="导出数据" sub="规划中 · 服务器已自动备份" onClick={() => setPanel('export')} noBorder><ChevronRight /></SettingRow>
      </div>

      <div className="r-glass" style={{ position: 'relative' }}>
        <SettingsSectionTitle title="外观" />
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
        <SettingRow label="日记本封面" sub="自定义封面图片" onClick={() => setPanel('cover')} noBorder><ChevronRight /></SettingRow>
      </div>

      <div className="r-glass" style={{ position: 'relative' }}>
        <SettingRow label="清除所有数据" danger noBorder><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" strokeWidth="1.5"><path d="M9 18l6-6-6-6"/></svg></SettingRow>
      </div>
    </div>
    </RoomShell>
  );
}
