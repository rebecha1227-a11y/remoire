const RAIN_DROPS = Array.from({ length: 24 }, (_, index) => ({
  left: (index * 37 + 11) % 100,
  dur: 2.5 + ((index * 17) % 35) / 10,
  delay: -((index * 29) % 60) / 10,
  opacity: 0.18 + ((index * 7) % 22) / 100,
  length: 28 + ((index * 31) % 60),
}));

export function RainLayer() {
  return (
    <div className="r-rain">
      {RAIN_DROPS.map((d, i) => (
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
