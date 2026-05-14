import { useMemo } from 'react';

export function RainLayer() {
  const drops = useMemo(() =>
    Array.from({ length: 24 }, () => ({
      left: Math.random() * 100,
      dur: 2.5 + Math.random() * 3.5,
      delay: -Math.random() * 6,
      opacity: 0.18 + Math.random() * 0.22,
      length: 28 + Math.random() * 60,
    })), []);
  return (
    <div className="r-rain">
      {drops.map((d, i) => (
        <div key={i} className="r-rain-drop" style={{
          left: `${d.left}%`,
          animationDuration: `${d.dur}s`,
          animationDelay: `${d.delay}s`,
          opacity: d.opacity, height: d.length,
        }} />
      ))}
    </div>
  );
}

export function FogLayer() {
  return (
    <div className="r-fog">
      <div className="r-fog-band" />
      <div className="r-fog-band" style={{ animationDelay: '-15s', top: '40%', opacity: 0.5 }} />
      <div className="r-fog-band" style={{ animationDelay: '-26s', top: '60%', opacity: 0.4 }} />
    </div>
  );
}
