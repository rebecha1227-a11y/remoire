import { createContext, useContext, useState, useEffect } from "react";
import { PALETTES, currentBand, isDarkBand } from "../utils/ambient";
import Floaters from "./Floaters";
import { RainLayer, FogLayer } from "./WeatherEffects";
import "../styles/room.css";

function readAccentColor() {
  try {
    const tweaks = JSON.parse(localStorage.getItem('remoire_tweaks') || '{}');
    return tweaks.accentColor || '';
  } catch { return ''; }
}

const RoomAmbientContext = createContext(null);

export function RoomAmbientProvider({ value, children }) {
  return <RoomAmbientContext.Provider value={value}>{children}</RoomAmbientContext.Provider>;
}

export function useRoomAmbient() {
  const [timeOverride, setTimeOverride] = useState(() => localStorage.getItem('remoire_time_override') || 'auto');
  const [weather, setWeather] = useState(() => localStorage.getItem('remoire_weather') || 'clear');
  const [deepMode, setDeepMode] = useState(() => !!localStorage.getItem('remoire_deep_mode'));
  const [chatBgImage, setChatBgImage] = useState(() => localStorage.getItem('remoire_chat_bg') || '');
  const [accentColor, setAccentColor] = useState(readAccentColor);

  useEffect(() => {
    function onStorage(e) {
      if (e.key === 'remoire_time_override') setTimeOverride(e.newValue || 'auto');
      if (e.key === 'remoire_weather') setWeather(e.newValue || 'clear');
      if (e.key === 'remoire_deep_mode') setDeepMode(!!e.newValue);
      if (e.key === 'remoire_chat_bg') setChatBgImage(e.newValue || '');
      if (e.key === 'remoire_tweaks') setAccentColor(readAccentColor());
    }
    function onAmbient(e) {
      const { key, value } = e.detail || {};
      if (key === 'remoire_time_override') setTimeOverride(value || 'auto');
      if (key === 'remoire_weather') setWeather(value || 'clear');
      if (key === 'remoire_deep_mode') setDeepMode(!!value);
      if (key === 'remoire_chat_bg') setChatBgImage(value || '');
    }
    function onTweak(e) {
      if (e.detail?.accentColor !== undefined) setAccentColor(e.detail.accentColor || '');
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
    if (chatBgImage) {
      document.body.style.background = `${solidBg} url(${chatBgImage}) center / cover no-repeat fixed`;
    } else {
      document.body.style.background = palette.bg;
    }
    document.documentElement.style.background = solidBg;
    const root = document.getElementById('root');
    if (root) root.style.background = 'transparent';
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', solidBg);
  }, [palette.chromeBg, palette.navBg, palette.bg, chatBgImage]);
}

export default function RoomShell({ children, nav }) {
  const ambient = useContext(RoomAmbientContext);
  const fallbackBand = currentBand();
  const {
    palette,
    dark,
    weather,
    deepMode,
    chatBgImage,
    accentColor,
  } = ambient || {
    palette: PALETTES[fallbackBand],
    dark: isDarkBand(fallbackBand),
    weather: 'clear',
    deepMode: false,
    chatBgImage: '',
    accentColor: readAccentColor(),
  };

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
    '--text-primary': palette.ink,
    '--text-deep': palette.ink,
    '--text-secondary': palette.inkSoft,
    '--text-tertiary': palette.inkSoft,
    '--border-light': palette.navBorder,
    '--border': palette.navBorder,
    '--accent': accentColor || palette.inkAccent,
    '--accent-subtle': palette.aiBubble.bg,
    '--bg-primary': 'transparent',
    '--bg-elevated': palette.navBg,
    '--danger': '#C45C5C',
    '--warning': '#D4935A',
    '--success': '#6B9F78',
    '--accent-pop': palette.inkAccent,
    '--bg-secondary': palette.aiBubble.bg,
  };

  return (
    <div style={{
      ...cssVars,
      width: '100%', flex: 1, minHeight: 0,
      position: 'relative', overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
      fontFamily: "var(--font-display)",
      color: palette.ink,
    }}>
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
      <svg className="r-grain"><filter id="r-noise-shell"><feTurbulence baseFrequency="0.85" numOctaves="2" seed="3" /></filter><rect width="100%" height="100%" filter="url(#r-noise-shell)" opacity="0.06" /></svg>

      <Floaters kind={palette.floaterKind} />

      {weather === 'rain' && <RainLayer />}
      {weather === 'fog'  && <FogLayer />}

      <div className="r-dim" style={{ opacity: deepMode ? 0.32 : 0 }} />

      <div style={{ height: 'env(safe-area-inset-top, 0px)', flexShrink: 0 }} />
      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        {children}
      </div>
      <div className="r-nav-spacer" />
      {nav}
    </div>
  );
}
