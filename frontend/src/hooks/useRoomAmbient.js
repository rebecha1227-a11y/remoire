import { useEffect, useState } from 'react';
import { PALETTES, currentBand, isDarkBand } from '../utils/ambient';
import { readRoomAccentColor } from '../components/roomAmbientContext';

export function useRoomAmbient() {
  const [timeOverride, setTimeOverride] = useState(() => localStorage.getItem('remoire_time_override') || 'auto');
  const [weather, setWeather] = useState(() => localStorage.getItem('remoire_weather') || 'clear');
  const [deepMode, setDeepMode] = useState(() => !!localStorage.getItem('remoire_deep_mode'));
  const [chatBgImage, setChatBgImage] = useState(() => localStorage.getItem('remoire_chat_bg') || '');
  const [accentColor, setAccentColor] = useState(readRoomAccentColor);

  useEffect(() => {
    function onStorage(event) {
      if (event.key === 'remoire_time_override') setTimeOverride(event.newValue || 'auto');
      if (event.key === 'remoire_weather') setWeather(event.newValue || 'clear');
      if (event.key === 'remoire_deep_mode') setDeepMode(!!event.newValue);
      if (event.key === 'remoire_chat_bg') setChatBgImage(event.newValue || '');
      if (event.key === 'remoire_tweaks') setAccentColor(readRoomAccentColor());
    }
    function onAmbient(event) {
      const { key, value } = event.detail || {};
      if (key === 'remoire_time_override') setTimeOverride(value || 'auto');
      if (key === 'remoire_weather') setWeather(value || 'clear');
      if (key === 'remoire_deep_mode') setDeepMode(!!value);
      if (key === 'remoire_chat_bg') setChatBgImage(value || '');
    }
    function onTweak(event) {
      if (event.detail?.accentColor !== undefined) setAccentColor(event.detail.accentColor || '');
    }
    window.addEventListener('storage', onStorage);
    window.addEventListener('remoire-ambient', onAmbient);
    window.addEventListener('tweak-update', onTweak);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('remoire-ambient', onAmbient);
      window.removeEventListener('tweak-update', onTweak);
    };
  }, []);

  const band = timeOverride === 'auto' ? currentBand() : timeOverride;
  const palette = PALETTES[band];
  const dark = isDarkBand(band);
  return { band, palette, dark, weather, deepMode, chatBgImage, accentColor };
}

export function useRoomChrome(palette, chatBgImage) {
  useEffect(() => {
    const solidBg = palette.chromeBg || palette.navBg;
    document.documentElement.style.setProperty('--app-chrome-bg', solidBg);
    document.documentElement.style.setProperty('--nav-bg', palette.navBg);
    document.body.style.background = chatBgImage
      ? `${solidBg} url(${chatBgImage}) center / cover no-repeat fixed`
      : palette.bg;
    document.documentElement.style.background = solidBg;
    const root = document.getElementById('root');
    if (root) root.style.background = 'transparent';
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', solidBg);
  }, [palette.chromeBg, palette.navBg, palette.bg, chatBgImage]);
}
