import { useContext } from "react";
import { PALETTES, currentBand, isDarkBand } from "../utils/ambient";
import { RoomAmbientContext, readRoomAccentColor } from './roomAmbientContext';
import Floaters from "./Floaters";
import { RainLayer, FogLayer } from "./WeatherEffects";
import "../styles/room.css";

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
    accentColor: readRoomAccentColor(),
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
