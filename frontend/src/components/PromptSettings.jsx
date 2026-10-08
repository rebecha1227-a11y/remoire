import { useEffect, useRef, useState } from 'react';
import { SettingsToggle, SubPageHeader } from './settingsShared';
import { Card } from './primitives';
import { Check, History, RotateCcw, Eye, X } from 'lucide-react';
import { apiErrorMessage, apiJsonFetch } from '../utils/api';
import './PromptSettings.css';

const BASE = '/settings/prompt-profiles';
const descriptions = {
  identity: '你们是谁，如何相处，以及希望一直保留的关系设定。',
  voice: '称呼、语气、日常回应方式，以及喜欢和不喜欢的表达。',
  scene: '仅用于聊天的场景写作偏好。保存并开启后，下一条聊天回复会读取这里的内容。',
};

function approximateTokens(text = '') {
  let wide = 0;
  let compact = 0;
  for (const char of text) {
    const code = char.codePointAt(0);
    if ((code >= 0x3400 && code <= 0x9fff) || (code >= 0xf900 && code <= 0xfaff)
      || (code >= 0x3040 && code <= 0x30ff) || code >= 0x1f000) wide += 1;
    else compact += 1;
  }
  return wide + Math.ceil(compact / 4);
}

async function request(path = '', options = {}) {
  const response = await apiJsonFetch(`${BASE}${path}`, { cache: 'no-store', ...options });
  const payload = await response.json();
  if (!response.ok || !payload.ok) throw new Error(apiErrorMessage(payload, '暂时无法读取或保存，请稍后重试。'));
  return payload.data;
}

export default function PromptSettings({ onBack }) {
  const editorRef = useRef(null);
  const [profiles, setProfiles] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [selected, setSelected] = useState('identity');
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [versions, setVersions] = useState(null);
  const [older, setOlder] = useState(false);
  const [historical, setHistorical] = useState(null);
  const [preview, setPreview] = useState(null);
  const current = profiles.find(item => item.key === selected);
  const draft = drafts[selected];
  const changed = (item) => drafts[item.key] && (drafts[item.key].content !== item.content || drafts[item.key].enabled !== item.enabled);
  const dirty = profiles.some(changed);

  useEffect(() => {
    const controller = new AbortController();
    request('', { signal: controller.signal }).then(items => {
      setProfiles(items);
      setDrafts(Object.fromEntries(items.map(item => [item.key, { ...item }])));
      setBusy(false);
    }).catch(err => {
      if (err.name !== 'AbortError') { setError(err.message); setBusy(false); }
    });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!dirty) return;
    const warn = event => { event.preventDefault(); event.returnValue = ''; };
    const warnNavigation = event => {
      if (!window.confirm('还有未保存的修改，离开并放弃吗？')) event.preventDefault();
    };
    window.addEventListener('beforeunload', warn);
    window.addEventListener('remoire-before-navigate', warnNavigation);
    return () => {
      window.removeEventListener('beforeunload', warn);
      window.removeEventListener('remoire-before-navigate', warnNavigation);
    };
  }, [dirty]);

  useEffect(() => {
    if (editorRef.current) editorRef.current.scrollTop = 0;
  }, [selected]);

  async function run(action) {
    setBusy(true); setError(''); setNotice('');
    try { await action(); } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  function accept(item) {
    setProfiles(items => items.map(old => old.key === item.key ? item : old));
    setDrafts(items => ({ ...items, [item.key]: { ...item } }));
    setVersions(null); setHistorical(null); setPreview(null);
  }

  function save() {
    run(async () => {
      const item = await request(`/${selected}`, {
        method: 'PUT', body: JSON.stringify({ content: draft.content, enabled: draft.enabled, expected_version: current.version }),
      });
      accept(item);
      setNotice('已保存。下一次生成会读取新配置。');
    });
  }

  function reload() {
    if (dirty && !window.confirm('重新读取会放弃本页尚未保存的修改，继续吗？')) return;
    run(async () => {
      const items = await request();
      setProfiles(items); setDrafts(Object.fromEntries(items.map(item => [item.key, { ...item }])));
      setVersions(null); setHistorical(null); setPreview(null);
      setNotice('已读取服务器上最新保存的内容。');
    });
  }

  function history(more = false) {
    run(async () => {
      const before = more ? `?before=${versions[versions.length - 1].version}` : '';
      const items = await request(`/${selected}/versions${before}`);
      setPreview(null);
      setVersions(old => more ? [...old, ...items] : items); setOlder(items.length === 20);
    });
  }

  function restore() {
    if (!window.confirm(`恢复到版本 ${historical.version}？${changed(current) ? '当前未保存的编辑将被替换。' : ''}恢复会保存为新版本，原有历史仍会保留。`)) return;
    run(async () => {
      accept(await request(`/${selected}/restore`, { method: 'POST', body: JSON.stringify({ version: historical.version, expected_version: current.version }) }));
      setNotice('已恢复并保存为新版本。');
    });
  }

  return (
    <div className="prompt-settings">
      <SubPageHeader title="关系档案" subtitle="关于我们，也关于每一次回应。"
        onBack={() => { if (!dirty || window.confirm('还有未保存的修改，离开并放弃吗？')) onBack(); }} />
      {profiles.length > 0 && <nav className="prompt-tabs" aria-label="关系档案分类">
        {profiles.map(item => <button key={item.key} type="button" disabled={busy} aria-pressed={selected === item.key}
          onClick={() => { setSelected(item.key); setVersions(null); setHistorical(null); setPreview(null); setNotice(''); setError(''); }}>
          {item.title}{changed(item) && <span className="prompt-dirty" aria-label="未保存" />}
        </button>)}
      </nav>}
      <p className="prompt-scope">身份与表达，在聊天、日记、纸条和主动陪伴中共同生效。</p>
      {error && <p className="prompt-error" role="alert">{error}{dirty ? ' 未保存的编辑仍保留在本页。' : ''}</p>}
      {!current && busy && <p className="prompt-help" role="status">正在读取关系档案…</p>}
      {current && draft && <>
        {selected === 'scene' && <div className="prompt-scene-row">
          <div><div className="prompt-title">使用场景写作</div><p className="prompt-help">仅用于聊天，保存后生效</p></div>
          <SettingsToggle on={draft.enabled} disabled={busy} ariaLabel="使用场景写作"
            onChange={enabled => { setDrafts(items => ({ ...items, scene: { ...items.scene, enabled } })); setNotice(''); }} />
        </div>}
        <Card className="prompt-paper" padding="md" elevated={false}>
          <div className="prompt-editor-heading">
            <label className="prompt-title" htmlFor="profile-content">{current.title}</label>
            <span className="prompt-state">{changed(current) ? '未保存' : '已保存'}</span>
          </div>
          <p id="profile-help" className="prompt-help">{descriptions[selected]}</p>
          <textarea ref={editorRef} id="profile-content" aria-describedby="profile-help" value={draft.content} maxLength={60000} disabled={busy}
            spellCheck={false} placeholder="写下希望保留的设定…"
            onChange={event => { setDrafts(items => ({ ...items, [selected]: { ...items[selected], content: event.target.value } })); setNotice(''); }} />
          <div className="prompt-editor-meta">
            <span>{draft.content.length.toLocaleString()} / 60,000 字符</span>
            <span>约 {approximateTokens(draft.content).toLocaleString()} tokens</span>
            <span>版本 {current.version}</span>
          </div>
        </Card>
        <p className="prompt-budget-note">关系档案每次生成都会作为固定层读取。系统不会静默裁掉身份、表达或已开启的场景配置；超过所选模型预算时会明确提示。</p>
        <div className="prompt-tools" aria-label="配置工具">
          <button type="button" disabled={busy} onClick={() => history()}><History size={15} strokeWidth={1.5} />历史版本</button>
          <button type="button" disabled={busy} onClick={() => run(async () => { setVersions(null); setHistorical(null); setPreview((await request('/preview?scene=true')).content); })}><Eye size={15} strokeWidth={1.5} />预览</button>
          <button type="button" disabled={busy} onClick={reload}><RotateCcw size={15} strokeWidth={1.5} />重新读取</button>
        </div>
        <div className="prompt-save-row">
          <p className="prompt-help" role="status">{notice || (changed(current) ? '修改后记得保存' : '保存后，下次回应开始使用')}</p>
          <button className="prompt-save" type="button" disabled={busy || !changed(current)} onClick={save}><Check size={16} strokeWidth={1.5} />保存</button>
        </div>
      </>}
      {!current && !busy && <button className="prompt-secondary" type="button" onClick={reload}>重新读取</button>}
      {preview !== null && <Card className="prompt-paper prompt-detail" padding="md" elevated={false}>
        <div className="prompt-editor-heading"><h3>已保存的聊天配置</h3><button className="prompt-close" type="button" aria-label="关闭预览" onClick={() => setPreview(null)}><X size={16} strokeWidth={1.5} /></button></div>
        <p className="prompt-help">共同设定与已开启的场景偏好。仅查看文字，不调用模型。</p>
        <pre>{preview || '当前配置为空。'}</pre>
      </Card>}
      {versions && <Card className="prompt-paper prompt-detail" padding="md" elevated={false}>
        <div className="prompt-editor-heading"><h3>历史版本</h3><button className="prompt-close" type="button" aria-label="关闭历史版本" onClick={() => { setVersions(null); setHistorical(null); }}><X size={16} strokeWidth={1.5} /></button></div>
        <p className="prompt-help">每一次修改都留着，可以随时回来。</p>
        {versions.map(item => <button className="prompt-version" key={item.version} type="button" disabled={busy}
          onClick={() => run(async () => setHistorical(await request(`/${selected}/versions/${item.version}`)))}>
          <span>版本 {item.version}{item.version === current.version ? ' · 当前' : ''}</span>
          <time>{new Date(item.updated_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })} · 北京时间</time>
        </button>)}
        {older && <button className="prompt-secondary" disabled={busy} type="button" onClick={() => history(true)}>更早版本</button>}
        {historical && <div className="prompt-history-content">
          <h3>版本 {historical.version}{selected === 'scene' ? (historical.enabled ? ' · 已开启' : ' · 未开启') : ''}</h3>
          <pre>{historical.content || '此版本正文为空。'}</pre>
          <button className="prompt-secondary" type="button" disabled={busy || historical.version === current.version} onClick={restore}>恢复这个版本</button>
        </div>}
      </Card>}
    </div>
  );
}
