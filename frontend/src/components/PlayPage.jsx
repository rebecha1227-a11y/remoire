import { useState } from 'react';
import { Card, SectionLabel } from './primitives';
import RoomShell from './RoomShell';

export default function PlayPage({ nav }) {
  const [space, setSpace] = useState(null);

  if (space) {
    return (
      <div style={{
        height: '100%', background: '#1C1814', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', position: 'relative',
        animation: 'page-in 350ms ease',
      }}>
        <button onClick={() => setSpace(null)} style={{
          position: 'absolute', top: 20, left: 20,
          background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)',
          borderRadius: 8, padding: '6px 12px', color: 'rgba(255,255,255,0.6)',
          fontSize: 12, cursor: 'pointer',
        }}>← 回到现实</button>
        <div style={{ textAlign: 'center', padding: '0 32px' }}>
          <div style={{ fontFamily: "var(--font-parallel)", fontSize: 11, letterSpacing: 3, color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', marginBottom: 24 }}>Parallel Space</div>
          <div style={{ fontFamily: "var(--font-parallel)", fontSize: 28, fontWeight: 300, color: 'rgba(255,255,255,0.9)', lineHeight: 1.5, marginBottom: 12 }}>京都，某年某月的下雨天</div>
          <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.4)', lineHeight: 1.8, marginBottom: 32 }}>上次停在：巷子里那家小书店，你刚翻到第三页</div>
          <button style={{ background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 8, padding: '12px 28px', color: 'rgba(255,255,255,0.8)', fontSize: 14, cursor: 'pointer' }}>
            继续故事
          </button>
        </div>
      </div>
    );
  }

  return (
    <RoomShell nav={nav}>
    <div style={{ overflowY: 'auto', flex: 1, padding: '20px 16px', paddingBottom: 16, position: 'relative', zIndex: 10 }}>
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <SectionLabel>共读</SectionLabel>
        <Card padding="lg" style={{ animation: 'card-in 180ms ease' }}>
          <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
            <div style={{
              width: 54, height: 72, background: 'var(--bg-secondary)',
              borderRadius: 'var(--radius-sm)', flexShrink: 0, border: '1px solid var(--border-light)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 9, color: 'var(--text-tertiary)', textAlign: 'center', padding: 4,
              fontFamily: 'monospace',
            }}>book cover</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500, color: 'var(--text-deep)', marginBottom: 'var(--space-1)' }}>挪威的森林</div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 'var(--space-2)' }}>村上春树 · 读到第 87 页</div>
              <div style={{ background: 'var(--border-light)', borderRadius: 2, height: 3, marginBottom: 'var(--space-1)' }}>
                <div style={{ height: '100%', background: 'var(--accent)', borderRadius: 2, width: '34%' }} />
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>34% · 上次共读：2 天前</div>
            </div>
          </div>
          <div style={{ marginTop: 'var(--space-3)', borderTop: '1px solid var(--border-light)', paddingTop: 'var(--space-3)' }}>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 'var(--space-1)' }}>Connie 的最新批注</div>
            <div style={{
              background: 'var(--accent-subtle)', borderRadius: 'var(--radius-sm)', padding: 'var(--space-2) var(--space-2)',
              fontFamily: "var(--font-read)", fontSize: 15, color: 'var(--text-deep)', lineHeight: 1.6
            }}>这段让我想到你说的那个朋友——他们之间的距离，和你描述的很像。</div>
          </div>
        </Card>
        <button style={{
          width: '100%', marginTop: 'var(--space-2)', padding: 'var(--space-2)',
          background: 'transparent', border: '1px dashed var(--border)',
          borderRadius: 'var(--radius-sm)', fontSize: 12, color: 'var(--text-tertiary)',
          cursor: 'pointer', fontFamily: "var(--font-body)",
        }}>+ 添加书目</button>
      </div>

      <div>
        <SectionLabel>平行空间</SectionLabel>
        <div onClick={() => setSpace(true)} style={{
          background: '#1C1814', borderRadius: 'var(--radius-md)',
          padding: '24px 20px', cursor: 'pointer', position: 'relative', overflow: 'hidden',
          animation: 'card-in 180ms 80ms ease both',
        }}>
          {[...Array(42)].map((_, i) => {
            const big = i % 7 === 0;
            const med = i % 3 === 0;
            const size = big ? 2.5 : med ? 1.6 : 1;
            const base = big ? 0.35 : med ? 0.25 : 0.18;
            const peak = big ? 0.95 : med ? 0.7 : 0.5;
            const dur = 2.4 + ((i * 17) % 31) / 10;
            const delay = ((i * 13) % 50) / 10;
            return (
              <div key={i} style={{
                position: 'absolute',
                left: `${(i * 37 + 11) % 100}%`,
                top: `${(i * 53 + 7) % 100}%`,
                width: size, height: size,
                background: '#fff', borderRadius: '50%',
                '--star-base': base, '--star-peak': peak,
                animation: `star-twinkle ${dur}s ease-in-out ${delay}s infinite${big ? `, star-drift ${dur * 4}s ease-in-out ${delay}s infinite` : ''}`,
                boxShadow: big ? `0 0 4px rgba(255,255,255,${peak * 0.6})` : 'none',
              }} />
            );
          })}
          <div style={{ fontFamily: "var(--font-parallel)", fontSize: 10, letterSpacing: 3, color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', marginBottom: 12 }}>上次的世界</div>
          <div style={{ fontFamily: "var(--font-parallel)", fontSize: 22, fontWeight: 300, color: 'rgba(255,255,255,0.9)', lineHeight: 1.4, marginBottom: 8 }}>京都，某年某月的下雨天</div>
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', lineHeight: 1.7 }}>停在：巷子里那家小书店，你刚翻到第三页</div>
          <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 6, color: 'rgba(255,255,255,0.5)', fontSize: 12 }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="10"/><path d="M10 8l6 4-6 4V8z" fill="currentColor"/></svg>
            点击进入
          </div>
        </div>
        <button style={{
          width: '100%', marginTop: 8, padding: '10px',
          background: 'transparent', border: '1px dashed var(--border)',
          borderRadius: 'var(--radius-sm)', fontSize: 12, color: 'var(--text-tertiary)',
          cursor: 'pointer', fontFamily: "var(--font-body)",
        }}>+ 创建新世界</button>
      </div>
    </div>
    </RoomShell>
  );
}
