import { SectionLabel } from './primitives';

export function SettingsToggle({ on, onChange }) {
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

export function SettingRow({ label, sub, children, danger, onClick, noBorder }) {
  return (
    <div onClick={onClick} style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 0', borderBottom: noBorder ? 'none' : '1px solid rgba(0,0,0,0.06)',
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

export function SettingsSectionTitle({ title }) {
  return <SectionLabel style={{ paddingTop: 'var(--space-5)', paddingBottom: 'var(--space-1)', letterSpacing: 1, textTransform: 'uppercase' }}>{title}</SectionLabel>;
}

export function SubPageHeader({ onBack, title, subtitle }) {
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

export const ChevronRight = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" style={{ flexShrink: 0 }}><path d="M9 18l6-6-6-6"/></svg>
);

const TWEAK_STORAGE_KEY = 'remoire_tweaks';

export function setTweakVal(key, val) {
  try {
    const current = JSON.parse(window.localStorage.getItem(TWEAK_STORAGE_KEY) || '{}');
    const next = { ...current, [key]: val };
    window.localStorage.setItem(TWEAK_STORAGE_KEY, JSON.stringify(next));
  } catch (error) {
    console.warn('保存外观设置失败', error);
  }
  window.parent.postMessage({ type: '__edit_mode_set_keys', edits: { [key]: val } }, '*');
  window.dispatchEvent(new CustomEvent('tweak-update', { detail: { [key]: val } }));
}
