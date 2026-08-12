const TWEAK_STORAGE_KEY = 'remoire_tweaks';

export function setTweakVal(key, value) {
  try {
    const current = JSON.parse(window.localStorage.getItem(TWEAK_STORAGE_KEY) || '{}');
    const next = { ...current, [key]: value };
    window.localStorage.setItem(TWEAK_STORAGE_KEY, JSON.stringify(next));
  } catch (error) {
    console.warn('保存外观设置失败', error);
  }
  window.parent.postMessage({ type: '__edit_mode_set_keys', edits: { [key]: value } }, '*');
  window.dispatchEvent(new CustomEvent('tweak-update', { detail: { [key]: value } }));
}
