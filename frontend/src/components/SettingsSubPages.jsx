import { useState, useEffect, useRef, useCallback } from "react";
import { Card, Pill, Stack } from "./primitives";
import { SettingsToggle, SettingRow, SettingsSectionTitle, SubPageHeader } from "./settingsShared";
import { setTweakVal } from '../utils/tweaks';
import { apiErrorMessage, apiFetch, apiJsonFetch } from "../utils/api";

function GlassSelect({ value, onChange, options, placeholder = '请选择', style }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const selected = options.find(o => o.value === value);

  useEffect(() => {
    if (!open) return;
    function close(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [open]);

  return (
    <div ref={ref} style={{ position: 'relative', ...style }}>
      <button onClick={() => setOpen(v => !v)} style={{
        width: '100%', minHeight: 40, padding: '8px 32px 8px 10px',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid rgba(255,255,255,0.18)',
        background: 'rgba(255,250,235,0.10)',
        backdropFilter: 'blur(12px) saturate(1.2)',
        WebkitBackdropFilter: 'blur(12px) saturate(1.2)',
        color: 'var(--ink)', fontSize: 'var(--text-sm)', fontFamily: 'var(--font-body)',
        textAlign: 'left', cursor: 'pointer', position: 'relative',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {selected ? selected.label : placeholder}
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--ink)" strokeWidth="2"
          style={{ position: 'absolute', right: 10, top: '50%', transform: `translateY(-50%) rotate(${open ? 180 : 0}deg)`, transition: 'transform 0.2s' }}>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, zIndex: 100,
          borderRadius: 'var(--radius-md)',
          border: '1px solid rgba(255,255,255,0.15)',
          background: 'rgba(255,250,235,0.12)',
          backdropFilter: 'blur(20px) saturate(1.3)',
          WebkitBackdropFilter: 'blur(20px) saturate(1.3)',
          boxShadow: '0 8px 32px rgba(40,33,28,0.25)',
          overflow: 'hidden',
          animation: 'card-in 150ms ease',
        }}>
          {options.map(opt => (
            <button key={opt.value} onClick={() => { onChange(opt.value); setOpen(false); }} style={{
              width: '100%', padding: '10px 12px', border: 'none',
              background: opt.value === value ? 'rgba(255,255,255,0.12)' : 'transparent',
              color: 'var(--ink)', fontSize: 'var(--text-sm)', fontFamily: 'var(--font-body)',
              textAlign: 'left', cursor: 'pointer', display: 'block',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              transition: 'background 0.15s',
            }}
              onPointerEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.10)'}
              onPointerLeave={e => e.currentTarget.style.background = opt.value === value ? 'rgba(255,255,255,0.12)' : 'transparent'}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// SettingsSubPages — all settings detail panels

// ═══════════════════════════════════════════
// 1. 主动消息设置
// ═══════════════════════════════════════════
export function ProactiveSettings({ onBack }) {
  const [cfg, setCfg] = useState({
    enabled: true, allowNight: false,
    startTime: '09:00', endTime: '22:30',
    maxDaily: 5, cooldown: 60, maxBurst: 8, maxRounds: 3, roundInterval: 30,
    endOnReply: true,
    types: { care: true, reminder: true, followup: true, special: true },
  });
  const [status, setStatus] = useState('正在读取设置…');

  useEffect(() => {
    apiFetch('/settings/proactive').then(async response => {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok || !payload.data) {
        throw new Error(apiErrorMessage(payload, '设置加载失败'));
      }
      const d = payload.data;
        setCfg(c => ({
          ...c,
          enabled: d.enabled ?? true,
          allowNight: d.allow_night ?? false,
          startTime: String(d.start_hour ?? 9).padStart(2, '0') + ':00',
          endTime: String(d.end_hour ?? 23).padStart(2, '0') + ':00',
          maxDaily: d.max_daily ?? 5,
          cooldown: d.cooldown_minutes ?? 60,
          maxBurst: d.max_burst ?? 8,
          maxRounds: d.max_rounds ?? 3,
          roundInterval: d.round_interval_minutes ?? 30,
          endOnReply: d.end_on_reply ?? true,
          types: d.types ?? c.types,
        }));
        setStatus('');
    }).catch(() => setStatus('设置加载失败，请稍后重试。'));
  }, []);

  const save = async (patch) => {
    try {
      const response = await apiJsonFetch('/settings/proactive', {
      method: 'PUT',
      body: JSON.stringify(patch),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) throw new Error(apiErrorMessage(payload, '设置保存失败'));
      setStatus('已保存');
      return true;
    } catch {
      setStatus('保存失败，请稍后重试。');
      return false;
    }
  };

  const set = (k, v) => {
    const previous = cfg[k];
    setCfg(c => ({ ...c, [k]: v }));
    const keyMap = {
      enabled: 'enabled', allowNight: 'allow_night',
      maxDaily: 'max_daily', cooldown: 'cooldown_minutes',
      maxBurst: 'max_burst', maxRounds: 'max_rounds',
      roundInterval: 'round_interval_minutes', endOnReply: 'end_on_reply',
    };
    let patch;
    if (k === 'startTime') patch = { start_hour: parseInt(v.split(':')[0], 10) };
    else if (k === 'endTime') patch = { end_hour: parseInt(v.split(':')[0], 10) };
    else if (keyMap[k] !== undefined) patch = { [keyMap[k]]: v };
    if (patch) void save(patch).then(saved => {
      if (!saved) setCfg(current => current[k] === v ? { ...current, [k]: previous } : current);
    });
  };
  const setType = (k) => {
    const previous = cfg.types;
    const next = { ...previous, [k]: !previous[k] };
    setCfg(current => ({ ...current, types: next }));
    void save({ types_json: JSON.stringify(next) }).then(saved => {
      if (!saved) setCfg(current => current.types === next ? { ...current, types: previous } : current);
    });
  };

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="主动消息" subtitle="控制 Connie 主动找你的方式和频率" />

      {/* 总开关 */}
      <SettingRow label="允许主动消息" sub="关闭后 Connie 不会主动发消息">
        <SettingsToggle on={cfg.enabled} onChange={v => set('enabled', v)} />
      </SettingRow>

      {!cfg.enabled ? (
        <div style={{ padding: '20px 0', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
          主动消息已关闭
        </div>
      ) : (
        <>
          <SettingRow label="发送入口" sub="微信桥接开放前，主动消息只发送到 Remoire">
            <Pill tone="neutral">Remoire</Pill>
          </SettingRow>

          {/* 时间段 */}
          <SettingsSectionTitle title="时间段" />
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8 }}>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)' }}>开始</label>
            <input type="time" value={cfg.startTime} onChange={e => set('startTime', e.target.value)}
              style={{ flex: 1, padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)', background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontSize: 13, fontFamily: 'var(--font-body)' }} />
            <label style={{ fontSize: 12, color: 'var(--text-secondary)' }}>结束</label>
            <input type="time" value={cfg.endTime} onChange={e => set('endTime', e.target.value)}
              style={{ flex: 1, padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)', background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontSize: 13, fontFamily: 'var(--font-body)' }} />
          </div>
          <SettingRow label="允许深夜消息" sub="23:00 之后仍可发送">
            <SettingsToggle on={cfg.allowNight} onChange={v => set('allowNight', v)} />
          </SettingRow>

          {/* 频率控制 */}
          <SettingsSectionTitle title="频率控制" />
          <SettingRow label="每日上限" sub={`最多 ${cfg.maxDaily} 次/天`}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button aria-label="减少每日上限" onClick={() => set('maxDaily', Math.max(1, cfg.maxDaily - 1))} style={{ width: 44, height: 44, borderRadius: '50%', border: '1px solid var(--border)', background: 'var(--bg-elevated)', cursor: 'pointer', fontSize: 16, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>−</button>
              <span style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-primary)', minWidth: 20, textAlign: 'center' }}>{cfg.maxDaily}</span>
              <button aria-label="增加每日上限" onClick={() => set('maxDaily', Math.min(20, cfg.maxDaily + 1))} style={{ width: 44, height: 44, borderRadius: '50%', border: '1px solid var(--border)', background: 'var(--bg-elevated)', cursor: 'pointer', fontSize: 16, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>+</button>
            </div>
          </SettingRow>
          <SettingRow label="聊天后冷却" sub={`刚聊完 ${cfg.cooldown} 分钟内不打扰`}>
            <select value={cfg.cooldown} onChange={e => set('cooldown', +e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)', background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontSize: 12, fontFamily: 'var(--font-body)' }}>
              {[30, 60, 90, 120, 180].map(v => <option key={v} value={v}>{v} 分钟</option>)}
            </select>
          </SettingRow>
          <SettingRow label="连续消息上限" sub={`一次 burst 最多 ${cfg.maxBurst} 条`}>
            <select value={cfg.maxBurst} onChange={e => set('maxBurst', +e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)', background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontSize: 12, fontFamily: 'var(--font-body)' }}>
              {[3, 5, 8, 10].map(v => <option key={v} value={v}>{v} 条</option>)}
            </select>
          </SettingRow>
          <SettingRow label="用户回复后结束 burst">
            <SettingsToggle on={cfg.endOnReply} onChange={v => set('endOnReply', v)} />
          </SettingRow>

          {/* 消息类型 */}
          <SettingsSectionTitle title="消息类型" />
          {[
            { id: 'care', label: '日常关心', sub: '早安/晚安/很久没来' },
            { id: 'reminder', label: '提醒到期', sub: '到点提醒/临近截止' },
            { id: 'followup', label: '未完成追问', sub: '答应过的事还没做' },
            { id: 'special', label: '特殊日期', sub: '生日/纪念日/考试' },
          ].map(t => (
            <SettingRow key={t.id} label={t.label} sub={t.sub}>
              <SettingsToggle on={cfg.types[t.id]} onChange={() => setType(t.id)} />
            </SettingRow>
          ))}
          {status && <div role="status" style={{ marginTop: 12, fontSize: 11, color: status.includes('失败') ? 'var(--danger)' : 'var(--text-tertiary)' }}>{status}</div>}
        </>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════
// 2. Prompt 编辑器
// ═══════════════════════════════════════════
export function PromptSettings({ onBack }) {
  const connieName = localStorage.getItem('remoire_conn_name') || 'Connie';

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="关系档案" subtitle="查看当前关系身份与表达方式" />
      <Card padding="lg" style={{ marginBottom: 16 }}>
        <SettingRow label="你的名字" sub="当前产品身份">静儿</SettingRow>
        <SettingRow label="TA 的名字" sub="可在聊天设置中修改备注">{connieName}</SettingRow>
        <SettingRow label="关系" sub="当前系统身份" noBorder>恋人</SettingRow>
      </Card>
      <Card padding="md" elevated={false} style={{ borderStyle: 'dashed' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>表达偏好编辑尚未开放</div>
          <Pill tone="neutral">规划中</Pill>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
          当前表达方式由服务器上的身份与语气配置统一控制。等保存、预览和版本回退真正接通后，这里才会提供编辑入口。
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// 3. 模型配置
// ═══════════════════════════════════════════
export function ModelSettings({ onBack }) {
  const SLOTS = [
    { id: 'daily', label: '日常陪伴', desc: '聊天、小纸条、自动日记、气息状态、留言回复' },
    { id: 'deep', label: '深度时刻', desc: '复杂情绪、长对话、需要更深的理解' },
    { id: 'backend', label: '后台任务', desc: '记忆提取、情感打标、摘要压缩、自动回复判断' },
  ];
  const API = '/settings';
  const emptyDraft = { id: null, nickname: '', provider: 'openai-compatible', api_key: '', base_url: '', model_name: '' };

  const [presets, setPresets] = useState([]);
  const [slots, setSlots] = useState([]);
  const [draft, setDraft] = useState(emptyDraft);
  const [expandedPresets, setExpandedPresets] = useState({});
  const [addOpen, setAddOpen] = useState(false);
  const [draftModels, setDraftModels] = useState([]);
  const [modelFetchKey, setModelFetchKey] = useState('');
  const [fetchingModels, setFetchingModels] = useState(false);
  const [testingModel, setTestingModel] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState('');

  const readJson = useCallback(async (res) => {
    const json = await res.json().catch(() => ({}));
    if (!res.ok || json.ok === false) {
      throw new Error(apiErrorMessage(json, `请求失败：${res.status}`));
    }
    return json;
  }, []);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setStatus('');
    try {
      const [presetsRes, slotsRes] = await Promise.all([
        apiFetch(`${API}/model-presets`),
        apiFetch(`${API}/slots`),
      ]);
      const presetsJson = await readJson(presetsRes);
      const slotsJson = await readJson(slotsRes);
      setPresets(presetsJson.data || []);
      setSlots(slotsJson.data || []);
    } catch (err) {
      setStatus(`加载失败：${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [readJson]);

  function updateDraft(field, value) {
    setDraft(d => ({ ...d, [field]: value }));
    if (field === 'api_key' || field === 'base_url') {
      setDraftModels([]);
      setTestResult(null);
    }
    if (field === 'model_name') {
      setTestResult(null);
    }
  }

  async function savePreset() {
    if (!draft.nickname || !draft.base_url || !draft.model_name || (!draft.id && !draft.api_key)) {
      setStatus('请填完预设名字、密钥、接口地址和模型名称。');
      return;
    }
    setSaving(true);
    setStatus('');
    try {
      const body = {
        nickname: draft.nickname,
        provider: draft.provider,
        base_url: draft.base_url,
        model_name: draft.model_name,
      };
      if (draft.api_key) body.api_key = draft.api_key;
      const res = await apiJsonFetch(draft.id ? `${API}/model-presets/${draft.id}` : `${API}/model-presets`, {
        method: draft.id ? 'PUT' : 'POST',
        body: JSON.stringify(body),
      });
      await readJson(res);
      setDraft(emptyDraft);
      setDraftModels([]);
      setModelFetchKey('');
      setTestResult(null);
      setAddOpen(false);
      await loadSettings();
      setStatus('已保存模型预设。');
    } catch (err) {
      setStatus(`保存失败：${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  function startNewPreset() {
    setDraft(emptyDraft);
    setDraftModels([]);
    setModelFetchKey('');
    setTestResult(null);
    setAddOpen(v => !v);
  }

  function editPreset(preset) {
    setDraft({ ...preset, api_key: '' });
    setDraftModels([]);
    setModelFetchKey('');
    setTestResult(null);
    setAddOpen(true);
  }

  async function deletePreset(id) {
    if (!window.confirm('删除后，使用它的槽位会被清空。继续吗？')) return;
    setStatus('');
    try {
      const res = await apiFetch(`${API}/model-presets/${id}`, { method: 'DELETE' });
      await readJson(res);
      if (draft.id === id) setDraft(emptyDraft);
      await loadSettings();
      setStatus('已删除模型预设。');
    } catch (err) {
      setStatus(`删除失败：${err.message}`);
    }
  }

  const fetchDraftModels = useCallback(async ({ silent = false } = {}) => {
    if ((!draft.id && !draft.api_key) || !draft.base_url) {
      setStatus('请先填写密钥和接口地址。');
      return;
    }
    setFetchingModels(true);
    if (!silent) setStatus('');
    try {
      const res = draft.id && !draft.api_key
        ? await apiFetch(`${API}/model-presets/${draft.id}/models`)
        : await apiJsonFetch(`${API}/model-presets/models`, {
            method: 'POST',
            body: JSON.stringify({ api_key: draft.api_key, base_url: draft.base_url }),
          });
      const json = await readJson(res);
      setDraftModels(json.data || []);
      setModelFetchKey(`${draft.id || draft.api_key}|${draft.base_url}`);
      if (!silent) setStatus('已拉取可用模型。');
    } catch (err) {
      setDraftModels([]);
      setStatus(`拉取模型失败：${err.message}`);
    } finally {
      setFetchingModels(false);
    }
  }, [draft.api_key, draft.base_url, draft.id, readJson]);

  useEffect(() => {
    const timer = window.setTimeout(loadSettings, 0);
    return () => window.clearTimeout(timer);
  }, [loadSettings]);

  useEffect(() => {
    if (!addOpen || !draft.base_url || (!draft.id && !draft.api_key)) return;
    const key = `${draft.id || draft.api_key}|${draft.base_url}`;
    if (key === modelFetchKey) return;
    const timer = window.setTimeout(() => fetchDraftModels({ silent: true }), 700);
    return () => window.clearTimeout(timer);
  }, [addOpen, draft.api_key, draft.base_url, draft.id, fetchDraftModels, modelFetchKey]);

  async function testDraftModel() {
    if ((!draft.id && !draft.api_key) || !draft.base_url || !draft.model_name) {
      setStatus('请先填写密钥、接口地址，并选择或填写模型。');
      return;
    }
    setTestingModel(true);
    setTestResult(null);
    setStatus('');
    try {
      const res = draft.id && !draft.api_key
        ? await apiFetch(`${API}/model-presets/${draft.id}/test`, { method: 'POST' })
        : await apiJsonFetch(`${API}/model-presets/test`, {
            method: 'POST',
            body: JSON.stringify({
              api_key: draft.api_key,
              base_url: draft.base_url,
              model_name: draft.model_name,
            }),
          });
      await readJson(res);
      setTestResult('success');
      setStatus('模型检测通过。');
    } catch (err) {
      setTestResult('fail');
      setStatus(`模型检测失败：${err.message}`);
    } finally {
      setTestingModel(false);
    }
  }

  async function saveSlot(slotId, patch) {
    const current = slots.find(s => s.slot === slotId) || {};
    const payload = {
      preset_id: Object.prototype.hasOwnProperty.call(patch, 'preset_id') ? patch.preset_id : current.preset_id,
      extended_thinking: Object.prototype.hasOwnProperty.call(patch, 'extended_thinking') ? patch.extended_thinking : !!current.extended_thinking,
    };
    setSlots(prev => prev.map(s => s.slot === slotId ? { ...s, ...payload } : s));
    try {
      const res = await apiJsonFetch(`${API}/slots/${slotId}`, { method: 'PUT', body: JSON.stringify(payload) });
      await readJson(res);
      await loadSettings();
    } catch (err) {
      setStatus(`槽位保存失败：${err.message}`);
      await loadSettings();
    }
  }

  const fieldStyle = {
    width: '100%', minHeight: 40, padding: '8px 10px', borderRadius: 'var(--radius-sm)',
    border: '1px solid rgba(255,255,255,0.18)', background: 'rgba(255,250,235,0.10)',
    backdropFilter: 'blur(12px) saturate(1.2)',
    WebkitBackdropFilter: 'blur(12px) saturate(1.2)',
    color: 'var(--ink)', fontSize: 'var(--text-sm)', fontFamily: 'var(--font-body)',
  };
  const labelStyle = {
    fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', display: 'block',
    marginBottom: 4, fontFamily: 'var(--font-body)', fontWeight: 500,
  };
  const ghostButton = {
    minHeight: 40, padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
    background: 'var(--bg-elevated)', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)',
    cursor: 'pointer', fontFamily: 'var(--font-body)', fontWeight: 500,
  };
  const primaryButton = {
    minHeight: 40, padding: '9px 12px', borderRadius: 'var(--radius-sm)', border: 'none',
    background: 'var(--accent)', fontSize: 'var(--text-xs)', color: '#FAF8F4',
    cursor: 'pointer', fontFamily: 'var(--font-body)', fontWeight: 500,
  };
  const foldButton = {
    width: '100%', minHeight: 44, padding: 0, border: 'none', background: 'transparent',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    gap: 12, textAlign: 'left', cursor: 'pointer', fontFamily: 'var(--font-body)',
  };
  const titleText = { fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--text-primary)', fontFamily: 'var(--font-body)' };
  const metaText = { fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 2, fontFamily: 'var(--font-body)' };
  const valueText = { fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', wordBreak: 'break-all', fontFamily: 'var(--font-body)' };
  const helperText = { fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', lineHeight: 1.5, marginTop: 5, fontFamily: 'var(--font-body)' };
  const statusStyle = {
    marginBottom: 12, padding: '8px 10px', borderRadius: 'var(--radius-sm)',
    background: 'var(--bg-secondary)', border: '1px solid var(--border-light)',
    fontSize: 'var(--text-xs)', fontFamily: 'var(--font-body)',
  };

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="模型配置" subtitle="给 Connie 的不同场景选择合适的模型。" />

      {status && (
        <div style={{ ...statusStyle, color: status.includes('失败') ? 'var(--danger)' : 'var(--text-secondary)' }}>{status}</div>
      )}

      <SettingsSectionTitle title="使用槽位" />
      <Stack gap="sm">
        {SLOTS.map(slot => {
          const current = slots.find(s => s.slot === slot.id) || {};
          return (
            <Card key={slot.id} padding="md">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
                <div>
                  <div style={titleText}>{slot.label}</div>
                  <div style={metaText}>{slot.desc}</div>
                </div>
                <Pill tone={current.preset_id ? 'success' : 'neutral'}>{current.preset_id ? '已配置' : '未配置'}</Pill>
              </div>
              <GlassSelect
                value={current.preset_id || ''}
                onChange={v => saveSlot(slot.id, { preset_id: v || null })}
                placeholder="不使用预设"
                options={[
                  { value: '', label: '不使用预设' },
                  ...presets.map(p => ({ value: p.id, label: `${p.nickname} · ${p.model_name}` })),
                ]}
                style={{ marginBottom: 10 }}
              />
              <SettingRow label="扩展思考" sub="开启后允许保存思考内容；是否生效取决于模型。">
                <SettingsToggle on={!!current.extended_thinking} onChange={v => saveSlot(slot.id, { extended_thinking: v })} />
              </SettingRow>
            </Card>
          );
        })}
      </Stack>

      <SettingsSectionTitle title="模型预设库" />
      <Stack gap="sm">
        {loading ? (
          <Card padding="md"><div style={metaText}>加载中…</div></Card>
        ) : presets.length === 0 ? (
          <Card padding="md"><div style={metaText}>还没有模型预设。</div></Card>
        ) : presets.map(preset => {
          const open = !!expandedPresets[preset.id];
          return (
            <Card key={preset.id} padding="md">
              <button onClick={() => setExpandedPresets(v => ({ ...v, [preset.id]: !open }))}
                style={foldButton}>
                <div style={{ minWidth: 0 }}>
                  <div style={titleText}>{preset.nickname}</div>
                  <div style={{ ...metaText, wordBreak: 'break-all' }}>{preset.model_name}</div>
                </div>
                <span style={{ ...ghostButton, minHeight: 32, padding: '6px 10px', flexShrink: 0 }}>{open ? '收起' : '展开'}</span>
              </button>
              {open && (
                <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-light)' }}>
                  <div style={{ display: 'grid', gap: 8 }}>
                    <div>
                      <div style={labelStyle}>密钥</div>
                      <div style={{ ...valueText, color: 'var(--text-tertiary)' }}>{preset.api_key || '********'}</div>
                    </div>
                    <div>
                      <div style={labelStyle}>接口地址</div>
                      <div style={valueText}>{preset.base_url}</div>
                    </div>
                    <div>
                      <div style={labelStyle}>模型名称</div>
                      <div style={valueText}>{preset.model_name}</div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                    <button onClick={() => editPreset(preset)} style={{ ...ghostButton, flex: 1 }}>编辑</button>
                    <button onClick={() => deletePreset(preset.id)}
                      style={{ ...ghostButton, color: 'var(--danger)', background: 'transparent' }}>删除</button>
                  </div>
                </div>
              )}
            </Card>
          );
        })}
      </Stack>

      <SettingsSectionTitle title="添加模型预设" />
      <Card padding="md">
        <button onClick={startNewPreset}
          style={foldButton}>
          <div>
            <div style={titleText}>{draft.id ? '编辑模型预设' : '新的模型预设'}</div>
            <div style={metaText}>填入密钥和接口地址后可自动拉取可用模型</div>
          </div>
          <span style={{ ...ghostButton, minHeight: 32, padding: '6px 10px', flexShrink: 0 }}>{addOpen ? '收起' : '展开'}</span>
        </button>

        {addOpen && (
          <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border-light)' }}>
            {[
              { field: 'nickname', label: '自定义预设名字', ph: '如 DeepSeek 日常', type: 'text' },
              { field: 'api_key', label: '密钥', ph: draft.id ? '留空则不修改' : 'sk-xxxxxxxx', type: 'password' },
              { field: 'base_url', label: '接口地址', ph: 'https://api.deepseek.com/v1', type: 'url' },
            ].map(f => (
              <div key={f.field} style={{ marginBottom: 10 }}>
                <label style={labelStyle}>{f.label}</label>
                <input type={f.type} value={draft[f.field]} onChange={e => updateDraft(f.field, e.target.value)}
                  placeholder={f.ph} style={fieldStyle} />
              </div>
            ))}

            <div style={{ marginBottom: 10 }}>
              <label style={labelStyle}>模型名称</label>
              {draftModels.length > 0 ? (
                <GlassSelect
                  value={draft.model_name}
                  onChange={v => updateDraft('model_name', v)}
                  placeholder="选择模型"
                  options={[
                    { value: '', label: '选择模型' },
                    ...draftModels.map(m => ({ value: m.id, label: m.id })),
                  ]}
                />
              ) : (
                <input type="text" value={draft.model_name} onChange={e => updateDraft('model_name', e.target.value)}
                  placeholder="拉取失败时可手动填写" style={fieldStyle} />
              )}
              <div style={helperText}>
                填入密钥和接口地址后会自动拉取可用模型列表。如果拉取不到，也可以手动填写模型名称。
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
              <button onClick={() => fetchDraftModels()} disabled={fetchingModels || (!draft.id && !draft.api_key) || !draft.base_url}
                style={{ ...ghostButton, flex: 1, opacity: fetchingModels ? 0.7 : 1 }}>
                {fetchingModels ? '拉取中…' : '重新拉取模型'}
              </button>
              <button onClick={testDraftModel} disabled={testingModel || (!draft.id && !draft.api_key) || !draft.base_url || !draft.model_name}
                style={{ ...ghostButton, flex: 1, opacity: testingModel ? 0.7 : 1 }}>
                {testingModel ? '检测中…' : '检测可用'}
              </button>
            </div>

            {testResult && (
              <div style={{ ...metaText, marginBottom: 10, color: testResult === 'success' ? 'var(--success)' : 'var(--danger)' }}>
                {testResult === 'success' ? '当前模型可用' : '当前模型不可用'}
              </div>
            )}

            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={savePreset} disabled={saving}
                style={{ ...primaryButton, flex: 1 }}>
                {saving ? '保存中…' : draft.id ? '保存修改' : '保存预设'}
              </button>
              <button onClick={() => { setDraft(emptyDraft); setDraftModels([]); setTestResult(null); setAddOpen(false); }}
                style={ghostButton}>
                取消
              </button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// 4. 微信桥接
// ═══════════════════════════════════════════
export function WeChatSettings({ onBack }) {
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="微信桥接" subtitle="让 Connie 在微信里也保持同一段关系" />

      <Card padding="lg" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10, background: 'var(--accent-subtle)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5" aria-hidden="true">
              <path d="M8.5 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM15.5 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2z" fill="var(--accent)"/>
              <path d="M9 16c1.5 1 4.5 1 6 0"/>
              <path d="M12 2C6.48 2 2 6.04 2 11c0 2.76 1.36 5.22 3.5 6.83V22l3.63-2A11.2 11.2 0 0 0 12 20c5.52 0 10-3.58 10-8s-4.48-9-10-9z"/>
            </svg>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>尚未开放</div>
              <Pill tone="neutral">规划中</Pill>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 3 }}>当前没有可用的扫码登录或连接状态</div>
          </div>
        </div>
      </Card>

      <Card padding="md">
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
          <strong>开放前会完成</strong><br/>
          正式接入需要真实的微信授权、令牌续期、撤销连接和失败反馈。完成这些安全闭环前，Remoire 不会用占位二维码模拟成功。
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// 5. MCP 配置
// ═══════════════════════════════════════════
export function MCPSettings({ onBack }) {
  const mcpUrl = `${window.location.origin}/mcp`;

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="MCP 跨平台同步" subtitle="让支持 MCP 的 AI 客户端访问同一套记忆" />

      <Stack gap="md">
          <Card padding="md">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>MCP Server URL</div>
              <Pill tone="warning">安全配置中</Pill>
            </div>
            <input readOnly value={mcpUrl} aria-label="MCP Server URL"
              style={{ width: '100%', minHeight: 44, padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: 12, fontFamily: 'monospace' }} />
            <div style={{ marginTop: 8, fontSize: 11, lineHeight: 1.6, color: 'var(--text-tertiary)' }}>
              独立 Bearer 鉴权完成端到端验收后才会开放复制与连接指引，避免把私人记忆暴露给未认证客户端。
            </div>
          </Card>

          <Card padding="md">
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 6 }}>暴露的工具</div>
            {[
              { name: 'resume()', desc: '醒来 — 浮现记忆、提醒、未完成事项' },
              { name: 'remember()', desc: '记住 — 生成记忆候选' },
              { name: 'recall()', desc: '回忆 — 检索已有记忆' },
              { name: 'resolve()', desc: '标记 unresolved 为已解决' },
            ].map(t => (
              <div key={t.name} style={{ display: 'flex', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--border-light)' }}>
                <code style={{ fontSize: 11, color: 'var(--accent)', fontFamily: 'monospace', flexShrink: 0, minWidth: 80 }}>{t.name}</code>
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{t.desc}</span>
              </div>
            ))}
          </Card>

          <Card padding="md">
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
              <strong>共享内容</strong>：长期记忆、特殊日期、未完成事项、提醒摘要、近期情绪高点<br/>
              <strong>不共享</strong>：平行空间上下文、未确认候选记忆、完整思考策略
            </div>
          </Card>
      </Stack>
    </div>
  );
}

// ═══════════════════════════════════════════
// 6. 导入历史对话
// ═══════════════════════════════════════════
export function ImportSettings({ onBack }) {
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="导入历史对话" subtitle="上传 Claude 导出的 JSON，把你们的前史带回来" />
      <Card padding="lg" elevated={false} style={{ borderStyle: 'dashed' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>导入能力尚未开放</div>
          <Pill tone="neutral">规划中</Pill>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
          正式版本会先在本地校验文件格式与大小，再把提取结果放进“记忆候选”，由你逐条确认后才写入正式记忆库。
        </div>
        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-tertiary)', lineHeight: 1.7 }}>
          在解析、候选审核和失败恢复真正接通前，这里不会播放虚假的上传进度，也不会声称示例内容已经写入。
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// 7. 消息推送
// ═══════════════════════════════════════════
export function PushSettings({ onBack }) {
  const [enabled, setEnabled] = useState(false);
  const [permission, setPermission] = useState(() => ('Notification' in window ? Notification.permission : 'unsupported'));
  const [status, setStatus] = useState('');
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistration().then(reg => {
        if (reg) reg.pushManager.getSubscription().then(sub => { if (sub) setEnabled(true); });
      });
    }
  }, []);

  async function subscribePush() {
    try {
      setStatus('正在授权...');
      const perm = await Notification.requestPermission();
      setPermission(perm);
      if (perm !== 'granted') { setStatus('授权被拒绝'); return; }

      setStatus('注册 Service Worker...');
      const reg = await navigator.serviceWorker.register('/sw.js');
      await navigator.serviceWorker.ready;

      setStatus('获取密钥...');
      const keyRes = await apiFetch('/push/vapid-public-key');
      const keyData = await keyRes.json();
      const vapidKey = keyData.data.key;

      setStatus('订阅推送...');
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      });
      const subJson = sub.toJSON();

      const connieName = localStorage.getItem('remoire_conn_name') || 'Connie';
      await apiJsonFetch('/push/subscribe', {
        method: 'POST',
        body: JSON.stringify({
          endpoint: subJson.endpoint,
          p256dh: subJson.keys.p256dh,
          auth: subJson.keys.auth,
          user_agent: navigator.userAgent,
          display_name: connieName,
        }),
      });

      setEnabled(true);
      setStatus('推送已开启');
    } catch (e) {
      setStatus('开启失败：' + e.message);
    }
  }

  async function unsubscribePush() {
    try {
      const reg = await navigator.serviceWorker.getRegistration();
      if (reg) {
        const sub = await reg.pushManager.getSubscription();
        if (sub) {
          const subJson = sub.toJSON();
          await sub.unsubscribe();
          await apiJsonFetch('/push/unsubscribe', {
            method: 'POST',
            body: JSON.stringify({ endpoint: subJson.endpoint, p256dh: subJson.keys.p256dh, auth: subJson.keys.auth }),
          });
        }
      }
      setEnabled(false);
      setStatus('推送已关闭');
    } catch (e) {
      setStatus('关闭失败：' + e.message);
    }
  }

  async function testPush() {
    setTesting(true);
    try {
      await apiFetch('/push/test', { method: 'POST' });
      setStatus('测试推送已发送');
    } catch (e) {
      setStatus('测试失败：' + e.message);
    }
    setTesting(false);
  }

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="消息推送" subtitle="在不看 Remoire 时也能收到 Connie 的消息" />

      <Card padding="lg" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10,
            background: enabled ? 'var(--accent)' : 'var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.5">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>
              Web Push 通知
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 1 }}>
              {permission === 'granted' ? '已授权' : permission === 'denied' ? '已拒绝（需在浏览器设置中开启）' : '需要授权通知权限'}
            </div>
          </div>
        </div>

        {permission === 'denied' ? (
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', padding: '8px 0' }}>
            通知权限已被拒绝，请在浏览器/系统设置中手动开启后刷新页面。
          </div>
        ) : !enabled ? (
          <button onClick={subscribePush}
            style={{ width: '100%', padding: '10px', borderRadius: 'var(--radius-sm)', border: 'none', background: 'var(--accent)', fontSize: 13, color: '#FAF8F4', cursor: 'pointer', fontWeight: 500 }}>
            开启推送通知
          </button>
        ) : (
          <>
            <SettingRow label="启用推送">
              <SettingsToggle on={enabled} onChange={(v) => v ? subscribePush() : unsubscribePush()} />
            </SettingRow>
            <button onClick={testPush} disabled={testing}
              style={{ width: '100%', marginTop: 8, padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'transparent', fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}>
              {testing ? '发送中...' : '发送测试推送'}
            </button>
          </>
        )}

        {status && (
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 8 }}>{status}</div>
        )}
      </Card>

      <Card padding="md">
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
          <strong>推送触发规则</strong><br/>
          当你不在 Remoire 页面时（切屏、锁屏、关页面），以下消息会推送通知：<br/>
          · 主动消息<br/>
          · 小纸条<br/>
          · 聊天回复（如果你发了消息但切走了）<br/>
          · 提醒到期<br/><br/>
          <strong>iOS 要求</strong>：需将 Remoire 添加到主屏幕作为 PWA 运行（iOS 16.4+）
        </div>
      </Card>
    </div>
  );
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

// ═══════════════════════════════════════════
// 8. 特殊日期管理
// ═══════════════════════════════════════════
export function DatesSettings({ onBack }) {
  const [dates, setDates] = useState([]);
  const [adding, setAdding] = useState(false);
  const [newDate, setNewDate] = useState({ date: '', title: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [status, setStatus] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch('/memory?memory_type=date&limit=50');
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '特殊日期加载失败'));
        setDates((data.data?.items || []).map(m => ({
          id: m.id,
          date: m.event_date ? m.event_date.slice(5, 10) : '',
          title: m.content,
        })));
      } catch (error) {
        setStatus(error.message || '特殊日期加载失败，请稍后重试。');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function validMonthDay(value) {
    if (!/^\d{2}-\d{2}$/.test(value)) return false;
    const parsed = new Date(`2000-${value}T00:00:00Z`);
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(5, 10) === value;
  }

  async function addDate() {
    const title = newDate.title.trim();
    const monthDay = newDate.date.trim();
    if (!title) {
      setStatus('请填写日期名称。');
      return;
    }
    if (!validMonthDay(monthDay)) {
      setStatus('日期请使用有效的 MM-DD 格式，例如 04-12。');
      return;
    }
    setSaving(true);
    setStatus('');
    try {
      const res = await apiJsonFetch('/memory', {
        method: 'POST',
        body: JSON.stringify({
          content: title,
          memory_type: 'date',
          layer: 'long',
          event_date: `2000-${monthDay}`,
          tags: ['特殊日期'],
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '保存失败'));
      const memory = data.data.memory;
      setDates(current => [...current, { id: memory.id, date: monthDay, title }]
        .sort((a, b) => a.date.localeCompare(b.date)));
      setNewDate({ date: '', title: '' });
      setAdding(false);
      setStatus('已保存到记忆库。');
    } catch (error) {
      setStatus(error.message || '保存失败，请稍后重试。');
    } finally {
      setSaving(false);
    }
  }

  async function removeDate(item) {
    if (!window.confirm(`删除“${item.title}”？这会同时从记忆库移除。`)) return;
    setBusyId(item.id);
    setStatus('');
    try {
      const res = await apiFetch(`/memory/${item.id}`, { method: 'DELETE' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '删除失败'));
      setDates(current => current.filter(date => date.id !== item.id));
      setStatus('已从记忆库删除。');
    } catch (error) {
      setStatus(error.message || '删除失败，请稍后重试。');
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="特殊日期" subtitle="生日与纪念日会写入记忆库，并按年重复出现" />

      {status && <div role="status" style={{ marginBottom: 12, fontSize: 12, color: status.includes('失败') || status.startsWith('请') || status.includes('已经存在') ? 'var(--danger)' : 'var(--text-secondary)' }}>{status}</div>}
      {loading && <div style={{ padding: '24px 0', textAlign: 'center', fontSize: 12, color: 'var(--text-tertiary)' }}>正在读取特殊日期…</div>}

      {!loading && dates.length === 0 && !adding && (
        <div style={{ padding: '18px 0', fontSize: 12, color: 'var(--text-tertiary)', lineHeight: 1.7 }}>
          还没有特殊日期。添加后，它会成为一条正式记忆。
        </div>
      )}

      {!loading && <Stack gap="xs">
        {dates.map(d => (
          <div key={d.id} style={{
            display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px',
            background: 'var(--bg-elevated)', border: '1px solid var(--border-light)',
            borderRadius: 'var(--radius-sm)',
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8, background: 'var(--accent-subtle)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5">
                <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{d.title}</div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 1 }}>
                {d.date} · 每年
              </div>
            </div>
            <button aria-label={`删除特殊日期：${d.title}`} disabled={busyId === d.id} onClick={() => removeDate(d)} style={{
              width: 44, height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'none', border: 'none', cursor: busyId === d.id ? 'wait' : 'pointer', padding: 0,
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          </div>
        ))}
      </Stack>}

      {adding ? (
        <Card padding="md" style={{ marginTop: 12 }}>
          <Stack gap="sm">
            <div>
              <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>标题</label>
              <input value={newDate.title} onChange={e => setNewDate(n => ({ ...n, title: e.target.value }))}
                placeholder="如：静儿生日"
                style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: 13 }} />
            </div>
            <div>
              <label style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>日期 (MM-DD)</label>
              <input value={newDate.date} inputMode="numeric" maxLength={5} onChange={e => setNewDate(n => ({ ...n, date: e.target.value }))}
                placeholder="04-12"
                style={{ width: '100%', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)', background: 'var(--bg-secondary)', color: 'var(--text-primary)', fontSize: 13 }} />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button disabled={saving} onClick={() => { setAdding(false); setStatus(''); }} style={{ flex: 1, minHeight: 44, padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'transparent', fontSize: 12, color: 'var(--text-tertiary)', cursor: 'pointer' }}>取消</button>
              <button disabled={saving} onClick={addDate} style={{ flex: 1, minHeight: 44, padding: '8px', borderRadius: 'var(--radius-sm)', border: 'none', background: 'var(--accent)', fontSize: 12, color: '#FAF8F4', cursor: saving ? 'wait' : 'pointer', fontWeight: 500 }}>{saving ? '保存中…' : '添加'}</button>
            </div>
          </Stack>
        </Card>
      ) : (
        <button disabled={loading} onClick={() => { setAdding(true); setStatus(''); }} style={{
          width: '100%', minHeight: 44, marginTop: 12, padding: '10px', background: 'transparent',
          border: '1px dashed var(--border)', borderRadius: 'var(--radius-sm)',
          fontSize: 12, color: 'var(--text-tertiary)', cursor: 'pointer', fontFamily: 'var(--font-body)',
        }}>+ 添加特殊日期</button>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════
// 9. 导出数据
// ═══════════════════════════════════════════
export function ExportSettings({ onBack }) {
  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="导出数据" subtitle="下载你的数据备份" />

      <Card padding="lg" elevated={false} style={{ borderStyle: 'dashed' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>应用内导出尚未开放</div>
          <Pill tone="neutral">规划中</Pill>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
          当前服务器每天都会生成经过完整性校验的数据库备份，但网页端还没有安全的下载流程。下载权限、脱敏和文件校验完成前，这里不会模拟“下载中”。
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════
// 10–13. 外观子页面（从旧 OtherPages 迁移 + 优化）
// ═══════════════════════════════════════════

// ── Bubble Style ──
export function BubbleSettings({ tweaks, onBack }) {
  const BUBBLE_OPTIONS = [
    { id: 'default', name: '默认', preview: { send: 'var(--bubble-send)', recv: 'var(--bubble-receive)', radius: 20 } },
    { id: 'imessage', name: 'iMessage', preview: { send: '#007AFF', recv: '#E9E9EB', radius: 18 } },
    { id: 'line', name: 'LINE', preview: { send: '#06C755', recv: '#E9E9EB', radius: 18 } },
    { id: 'whatsapp', name: 'WhatsApp', preview: { send: '#DCF8C6', recv: '#fff', radius: 8 } },
    { id: 'telegram', name: 'Telegram', preview: { send: '#EFFDDE', recv: '#fff', radius: 14 } },
  ];
  const current = tweaks?.bubbleStyle || 'default';

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="聊天气泡样式" subtitle="选择你喜欢的聊天气泡风格" />
      <Stack gap="sm">
        {BUBBLE_OPTIONS.map(opt => (
          <Card key={opt.id} onClick={() => setTweakVal('bubbleStyle', opt.id)} padding="md"
            style={{ border: current === opt.id ? '2px solid var(--accent)' : undefined, transition: 'all 0.15s' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>{opt.name}</span>
              {current === opt.id && <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M5 13l4 4L19 7"/></svg></div>}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                <div style={{ background: opt.preview.recv, padding: '6px 12px', borderRadius: `${opt.preview.radius}px ${opt.preview.radius}px ${opt.preview.radius}px 4px`, fontSize: 12, color: '#333', maxWidth: '65%' }}>你好呀 ☺️</div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <div style={{ background: opt.preview.send, padding: '6px 12px', borderRadius: `${opt.preview.radius}px ${opt.preview.radius}px 4px ${opt.preview.radius}px`, fontSize: 12, color: opt.id === 'whatsapp' || opt.id === 'telegram' ? '#111' : (opt.id === 'default' ? 'var(--bubble-send-text)' : '#fff'), maxWidth: '65%' }}>在呢，想你了</div>
              </div>
            </div>
          </Card>
        ))}
      </Stack>
    </div>
  );
}

// ── Note Style ──
function NotePreviewWashi() {
  return (
    <div style={{ position: 'relative', padding: '14px 16px 12px', minHeight: 52 }}>
      <div style={{
        position: 'absolute', top: -3, left: 20, right: 20, height: 22,
        background: 'linear-gradient(90deg, rgba(255,220,180,0.35) 0%, rgba(255,200,150,0.25) 40%, rgba(240,190,140,0.30) 100%)',
        borderRadius: 2,
        transform: 'rotate(-0.8deg)',
        boxShadow: '0 1px 3px rgba(120,70,30,0.08)',
        backdropFilter: 'blur(6px) saturate(1.1)',
        WebkitBackdropFilter: 'blur(6px) saturate(1.1)',
      }} />
      <div style={{
        position: 'absolute', bottom: -2, left: 30, right: 40, height: 18,
        background: 'linear-gradient(90deg, rgba(180,210,200,0.30) 0%, rgba(160,200,190,0.22) 100%)',
        borderRadius: 2,
        transform: 'rotate(0.6deg)',
        boxShadow: '0 1px 3px rgba(120,70,30,0.06)',
        backdropFilter: 'blur(6px) saturate(1.1)',
        WebkitBackdropFilter: 'blur(6px) saturate(1.1)',
      }} />
      <div style={{
        background: 'rgba(255,250,235,0.12)',
        backdropFilter: 'blur(12px) saturate(1.2)',
        WebkitBackdropFilter: 'blur(12px) saturate(1.2)',
        border: '1px solid rgba(255,240,220,0.18)',
        borderRadius: 3,
        padding: '10px 12px',
        transform: 'rotate(-0.5deg)',
      }}>
        <div style={{ fontFamily: "var(--font-note)", fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6 }}>今天也要好好的呀~</div>
      </div>
    </div>
  );
}

function NotePreviewFrost() {
  return (
    <div style={{
      position: 'relative', padding: '12px 16px', minHeight: 52,
      background: 'rgba(255,250,235,0.10)',
      backdropFilter: 'blur(16px) saturate(1.3)',
      WebkitBackdropFilter: 'blur(16px) saturate(1.3)',
      borderRadius: 16,
      border: '1px solid rgba(255,240,220,0.20)',
      boxShadow: '0 4px 16px -6px rgba(120,70,30,0.10), inset 0 1px 0 rgba(255,250,235,0.30)',
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
      <div style={{ fontFamily: "var(--font-note)", fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6, position: 'relative' }}>今天也要好好的呀~</div>
    </div>
  );
}

export function NoteSettings({ tweaks, onBack }) {
  const NOTE_OPTIONS = [
    { id: 'washi', name: '和风胶带', desc: '半透明胶带贴住的纸条' },
    { id: 'frost', name: '毛玻璃纸条', desc: '磨砂透明的轻薄便签' },
    { id: 'classic', name: '经典便签', desc: '横线纸 + 胶带' },
    { id: 'torn', name: '撕纸条', desc: '手撕纸边缘效果' },
  ];
  const current = tweaks?.noteStyle || 'washi';

  function renderPreview(id) {
    if (id === 'washi') return <NotePreviewWashi />;
    if (id === 'frost') return <NotePreviewFrost />;
    if (id === 'torn') return (
      <div style={{
        background: 'rgba(255,250,235,0.14)', backdropFilter: 'blur(10px) saturate(1.15)',
        WebkitBackdropFilter: 'blur(10px) saturate(1.15)',
        borderRadius: 3, padding: '10px 12px', minHeight: 44,
        clipPath: 'polygon(0 0, 100% 0, 100% 85%, 98% 88%, 95% 85%, 92% 90%, 88% 85%, 85% 88%, 80% 85%, 75% 90%, 70% 85%, 65% 88%, 60% 85%, 55% 90%, 50% 85%, 45% 88%, 40% 85%, 35% 90%, 30% 85%, 25% 88%, 20% 85%, 15% 90%, 10% 85%, 5% 88%, 2% 85%, 0 90%)',
        transform: 'rotate(-0.5deg)',
      }}>
        <div style={{ fontFamily: "var(--font-note)", fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>今天也要好好的呀~</div>
      </div>
    );
    return (
      <div style={{ position: 'relative', padding: '10px 12px', minHeight: 44 }}>
        <div style={{
          position: 'absolute', top: -5, left: '50%', transform: 'translateX(-50%) rotate(2deg)',
          width: 30, height: 10, background: 'rgba(130,189,197,0.35)', borderRadius: 1,
          backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)',
        }} />
        <div style={{
          background: 'rgba(255,250,235,0.14)', backdropFilter: 'blur(10px) saturate(1.15)',
          WebkitBackdropFilter: 'blur(10px) saturate(1.15)',
          borderRadius: 4, padding: '10px 12px', transform: 'rotate(-0.5deg)',
          border: '1px solid rgba(255,240,220,0.15)',
        }}>
          <div style={{ fontFamily: "var(--font-note)", fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>今天也要好好的呀~</div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <SubPageHeader onBack={onBack} title="便签样式" subtitle="选择 Connie 留纸条的风格" />
      <Stack gap="sm">
        {NOTE_OPTIONS.map(opt => (
          <Card key={opt.id} onClick={() => setTweakVal('noteStyle', opt.id)} padding="md"
            style={{ border: current === opt.id ? '2px solid var(--accent)' : undefined }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <div>
                <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>{opt.name}</span>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>{opt.desc}</div>
              </div>
              {current === opt.id && <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M5 13l4 4L19 7"/></svg></div>}
            </div>
            {renderPreview(opt.id)}
          </Card>
        ))}
      </Stack>
    </div>
  );
}

// ── Cover ──
function DiaryCoverCard({ label, cover, defaultBg, onUpload, onReset }) {
  return (
    <Card padding="lg">
      <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 'var(--space-3)' }}>{label}</div>
      <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
        <div style={{
          width: 72, height: 120, borderRadius: '4px 8px 8px 4px', overflow: 'hidden',
          background: cover ? `url(${cover}) center/cover` : defaultBg,
          border: '1px solid var(--border-light)', flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {!cover && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', textAlign: 'center' }}>默认</span>}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button onClick={onUpload} style={{ minHeight: 44, background: 'var(--accent)', color: '#FAF8F4', border: 'none', borderRadius: 'var(--radius-sm)', padding: '8px 16px', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>上传图片</button>
          {cover && <button onClick={onReset} style={{ minHeight: 44, background: 'transparent', color: 'var(--text-tertiary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '6px 14px', fontSize: 11, cursor: 'pointer' }}>恢复默认</button>}
        </div>
      </div>
    </Card>
  );
}

export function CoverSettings({ tweaks, onBack }) {
  const coverJ = tweaks?.diaryCoverJinger;
  const coverC = tweaks?.diaryCoverConnie;

  function handleCoverUpload(who) {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = 'image/*';
    input.onchange = (e) => {
      const file = e.target.files[0]; if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => setTweakVal(who === 'jinger' ? 'diaryCoverJinger' : 'diaryCoverConnie', ev.target.result);
      reader.readAsDataURL(file);
    };
    input.click();
  }

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="日记本封面" subtitle="上传自定义封面图片" />
      <Stack gap="md">
        <DiaryCoverCard label="静儿的日记本" cover={coverJ} defaultBg="#F0C6D0" onUpload={() => handleCoverUpload('jinger')} onReset={() => setTweakVal('diaryCoverJinger', '')} />
        <DiaryCoverCard label="Connie 的日记本" cover={coverC} defaultBg="#8B9EAE" onUpload={() => handleCoverUpload('connie')} onReset={() => setTweakVal('diaryCoverConnie', '')} />
      </Stack>
    </div>
  );
}

// ── Font ──
export function FontSettings({ tweaks, onBack }) {
  const FONT_SLOTS = [
    { key: 'Chat', label: '聊天', desc: '聊天界面正文' },
    { key: 'Note', label: '小纸条', desc: 'Connie 的纸条' },
    { key: 'Diary', label: '日记', desc: '日记本正文' },
    { key: 'Read', label: '共读', desc: 'Connie 的批注' },
    { key: 'Parallel', label: '平行世界', desc: '平行世界标题' },
  ];

  function uploadFont(slot) {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.ttf,.otf';
    input.onchange = (e) => {
      const file = e.target.files[0]; if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => { setTweakVal('font' + slot, ev.target.result); setTweakVal('font' + slot + 'Name', file.name); };
      reader.readAsDataURL(file);
    };
    input.click();
  }

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="字体" subtitle="为不同区域上传字体文件（.ttf / .otf）" />
      <Stack gap="sm">
        {FONT_SLOTS.map(slot => {
          const data = tweaks?.['font' + slot.key];
          const name = tweaks?.['font' + slot.key + 'Name'];
          return (
            <Card key={slot.key} padding="md" elevated={false}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>{slot.label}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>{slot.desc}</div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {data && <button onClick={() => { setTweakVal('font' + slot.key, ''); setTweakVal('font' + slot.key + 'Name', ''); }} style={{ background: 'transparent', color: 'var(--text-tertiary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '6px 12px', fontSize: 11, cursor: 'pointer' }}>恢复默认</button>}
                  <button onClick={() => uploadFont(slot.key)} style={{ background: 'var(--accent)', color: 'var(--bg-elevated)', border: 'none', borderRadius: 'var(--radius-sm)', padding: '6px 14px', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>{data ? '更换' : '上传'}</button>
                </div>
              </div>
              <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: 10, marginTop: 4, fontFamily: `var(--font-${slot.key.toLowerCase()})`, fontSize: 16, color: 'var(--text-deep)', lineHeight: 1.6 }}>今天也要好好的呀，亲爱的</div>
              {name && <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 6, fontFamily: 'monospace' }}>{name}</div>}
            </Card>
          );
        })}
      </Stack>
    </div>
  );
}

// ═══════════════════════════════════════════
// 10. 小纸条历史
// ═══════════════════════════════════════════
export function NoteHistorySettings({ onBack }) {
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      setError('');
      try {
        const res = await apiFetch('/note?limit=50');
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '小纸条加载失败'));
        setNotes(data.data?.notes || []);
      } catch (loadError) {
        setError(loadError.message || '小纸条加载失败，请稍后重试。');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z');
    const bj = new Date(d.getTime() + 8 * 3600000);
    const mm = String(bj.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(bj.getUTCDate()).padStart(2, '0');
    const hh = String(bj.getUTCHours()).padStart(2, '0');
    const mi = String(bj.getUTCMinutes()).padStart(2, '0');
    return `${mm}-${dd} ${hh}:${mi}`;
  }

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="小纸条历史" subtitle="Connie 留过的所有纸条" />

      {loading && <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)', fontSize: 13 }}>加载中…</div>}
      {error && <div role="alert" style={{ padding: '12px 0', color: 'var(--danger)', fontSize: 12 }}>{error}</div>}

      {!loading && !error && notes.length === 0 && (
        <Card padding="lg" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>还没有纸条呢</div>
        </Card>
      )}

      <Stack gap="sm">
        {notes.map(n => (
          <Card key={n.id} padding="md">
            <div style={{ fontFamily: 'var(--font-note, var(--font-diary))', fontSize: 15, color: 'var(--text-deep)', lineHeight: 1.7, marginBottom: 8 }}>
              {n.content}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{formatDate(n.created_at)}</span>
              <span style={{ fontSize: 11, color: n.is_read ? 'var(--text-tertiary)' : 'var(--accent-pop)' }}>
                {n.is_read ? (n.kept ? '已收藏' : '已读') : '未读'}
              </span>
            </div>
          </Card>
        ))}
      </Stack>
    </div>
  );
}

// ═══════════════════════════════════════════
// 11. 记忆候选审核
// ═══════════════════════════════════════════
export function MemoryCandidatesSettings({ onBack }) {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState('');

  async function load() {
    setError('');
    try {
      const res = await apiFetch('/memory/candidates?status=pending&limit=50');
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '候选记忆加载失败'));
      setCandidates(Array.isArray(data.data) ? data.data : []);
    } catch (loadError) {
      setError(loadError.message || '候选记忆加载失败，请稍后重试。');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(load, 0);
    return () => window.clearTimeout(timer);
  }, []);

  async function accept(id) {
    setBusyId(id);
    setError('');
    try {
      const res = await apiJsonFetch(`/memory/candidates/${id}/accept`, {
        method: 'POST',
        body: '{}',
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '候选记忆确认失败'));
      setCandidates(c => c.filter(x => x.id !== id));
    } catch (actionError) {
      setError(actionError.message || '候选记忆确认失败，请稍后重试。');
    } finally {
      setBusyId(null);
    }
  }

  async function reject(id) {
    setBusyId(id);
    setError('');
    try {
      const res = await apiFetch(`/memory/candidates/${id}/reject`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(apiErrorMessage(data, '候选记忆忽略失败'));
      setCandidates(c => c.filter(x => x.id !== id));
    } catch (actionError) {
      setError(actionError.message || '候选记忆忽略失败，请稍后重试。');
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px 88px' }}>
      <SubPageHeader onBack={onBack} title="记忆候选" subtitle="低置信度的候选需要你确认才会进入正式记忆库" />

      {loading && <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)', fontSize: 13 }}>加载中…</div>}
      {error && <div role="alert" style={{ padding: '12px 0', color: 'var(--danger)', fontSize: 12 }}>{error}</div>}

      {!loading && !error && candidates.length === 0 && (
        <Card padding="lg" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>没有待审核的候选</div>
        </Card>
      )}

      <Stack gap="sm">
        {candidates.map(c => (
          <Card key={c.id} padding="md">
            <div style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: 8 }}>
              {c.content}
            </div>
            {c.tags && c.tags.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10 }}>
                {c.tags.map((t, i) => <Pill key={i} tone="neutral">{t}</Pill>)}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button disabled={busyId === c.id} onClick={() => reject(c.id)} style={{
                padding: '6px 14px', borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)', background: 'transparent',
                fontSize: 12, color: 'var(--text-tertiary)', cursor: 'pointer', fontFamily: 'var(--font-body)',
              }}>不要</button>
                <button disabled={busyId === c.id} onClick={() => accept(c.id)} style={{
                padding: '6px 14px', borderRadius: 'var(--radius-sm)',
                border: 'none', background: 'var(--accent)',
                fontSize: 12, color: '#FAF8F4', cursor: 'pointer', fontWeight: 500, fontFamily: 'var(--font-body)',
              }}>记住</button>
            </div>
          </Card>
        ))}
      </Stack>
    </div>
  );
}
