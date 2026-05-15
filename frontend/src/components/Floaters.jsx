import { useMemo } from 'react';

function rand(min, max) { return min + Math.random() * (max - min); }

function generateItems(kind) {
  const counts = { petals: 8, motes: 12, stars: 20, 'stars-candles': 20 };
  const n = counts[kind] ?? 20;
  return Array.from({ length: n }, (_, i) => ({
    x: rand(0, 100), y: rand(0, 100),
    size: rand(0.6, 1), dur: rand(8, 22),
    delay: rand(-20, 0), drift: rand(-12, 12),
    opacity: rand(0.4, 0.95), rot: rand(0, 360), seed: i,
  }));
}

function renderItem(kind, it, i) {
  if (kind === 'stars' || kind === 'stars-candles') {
    const isCandle = kind === 'stars-candles' && i % 6 === 0;
    if (isCandle) {
      return (
        <div key={i} className="r-fl-candle" style={{
          left: `${it.x}%`, top: `${it.y}%`,
          width: 30 * it.size, height: 30 * it.size,
          animationDuration: `${it.dur + 6}s`,
          animationDelay: `${it.delay}s`,
          opacity: it.opacity * 0.7,
        }} />
      );
    }
    const s = 1.4 + it.size * 1.6;
    return (
      <div key={i} className="r-fl-star" style={{
        left: `${it.x}%`, top: `${it.y}%`,
        width: s, height: s,
        animationDuration: `${it.dur * 0.4}s`,
        animationDelay: `${it.delay}s`,
        '--star-opacity-base': it.opacity * 0.3,
        '--star-opacity-peak': it.opacity,
      }} />
    );
  }
  if (kind === 'petals') {
    const s = 8 + it.size * 10;
    return (
      <div key={i} className="r-fl-petal" style={{
        left: `${it.x}%`, top: '-10%',
        width: s, height: s * 1.6,
        animationDuration: `${it.dur + 4}s`,
        animationDelay: `${it.delay}s`,
        opacity: it.opacity * 0.4,
        transform: `rotate(${it.rot}deg)`,
        '--drift': `${it.drift}px`,
      }} />
    );
  }
  const s = 2 + it.size * 3;
  return (
    <div key={i} className="r-fl-mote" style={{
      left: `${it.x}%`, top: `${it.y}%`,
      width: s, height: s,
      animationDuration: `${it.dur}s`,
      animationDelay: `${it.delay}s`,
      opacity: it.opacity * 0.45,
      '--drift': `${it.drift}px`,
    }} />
  );
}

export default function Floaters({ kind }) {
  const items = useMemo(() => generateItems(kind), [kind]);
  return (
    <div className="r-floaters" aria-hidden="true">
      {items.map((it, i) => renderItem(kind, it, i))}
    </div>
  );
}
