// PlayPage & SettingsPage

function PlayPage() {
  const [space, setSpace] = React.useState(null);

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
    <div style={{ overflowY: 'auto', height: '100%', padding: '20px 16px', paddingBottom: 88 }}>
      {/* 共读 */}
      <div style={{ marginBottom: 'var(--space-6)' }}>
        <SectionLabel>共读</SectionLabel>
        <Card padding="lg" style={{ animation: 'card-in 180ms ease' }}>
          <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
            {/* Book cover placeholder */}
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
          {/* Latest annotation */}
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

      {/* 平行空间 */}
      <div>
        <SectionLabel>平行空间</SectionLabel>
        <div onClick={() => setSpace(true)} style={{
          background: '#1C1814', borderRadius: 'var(--radius-md)',
          padding: '24px 20px', cursor: 'pointer', position: 'relative', overflow: 'hidden',
          animation: 'card-in 180ms 80ms ease both',
        }}>
          {/* Stars bg — 闪烁 + 微漂移 */}
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
  );
}

// ─── Settings ───────────────────────────────────────────

function SettingRow({ label, sub, children, danger }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--border-light)' }}>
      <div>
        <div style={{ fontSize: 'var(--text-sm)', color: danger ? 'var(--danger)' : 'var(--text-primary)', fontWeight: 500 }}>{label}</div>
        {sub && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 1 }}>{sub}</div>}
      </div>
      {children}
    </div>
  );
}

function Toggle({ on, onChange }) {
  return (
    <div onClick={() => onChange(!on)} style={{
      width: 40, height: 22, borderRadius: 11,
      background: on ? 'var(--accent)' : 'var(--border)',
      position: 'relative', cursor: 'pointer', transition: 'background 0.2s',
      flexShrink: 0,
    }}>
      <div style={{
        width: 18, height: 18, borderRadius: '50%', background: '#FAF8F4',
        position: 'absolute', top: 2, left: on ? 20 : 2, transition: 'left 0.2s',
        boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
      }} />
    </div>
  );
}

function SectionTitle({ title }) {
  return <SectionLabel style={{ paddingTop: 'var(--space-5)', paddingBottom: 'var(--space-1)', letterSpacing: 1, textTransform: 'uppercase' }}>{title}</SectionLabel>;
}

function SettingsPage({ tweaks }) {
  const [toggles, setToggles] = React.useState({
    proactive: true, lateNight: false, noteCard: true,
    diaryUnlock: true, mcp: true,
  });
  const [customPanel, setCustomPanel] = React.useState(null); // 'bubble' | 'note' | 'cover' | null

  function toggle(k) { setToggles(t => ({ ...t, [k]: !t[k] })); }

  // Bubble style options
  const BUBBLE_OPTIONS = [
    { id: 'default', name: '默认', preview: { send: 'var(--bubble-send)', recv: 'var(--bubble-receive)', radius: 20 } },
    { id: 'imessage', name: 'iMessage', preview: { send: '#007AFF', recv: '#E9E9EB', radius: 18 } },
    { id: 'line', name: 'LINE', preview: { send: '#06C755', recv: '#E9E9EB', radius: 18 } },
{ id: 'whatsapp', name: 'WhatsApp', preview: { send: '#DCF8C6', recv: '#fff', radius: 8 } },
    { id: 'telegram', name: 'Telegram', preview: { send: '#EFFDDE', recv: '#fff', radius: 14 } },
  ];

  const NOTE_OPTIONS = [
    { id: 'classic', name: '经典便签', desc: '横线纸 + 和纸胶带' },
    { id: 'kraft', name: '牛皮纸', desc: '质朴牛皮纸质感' },
    { id: 'pastel', name: '柔彩便签', desc: '淡紫色渐变' },
    { id: 'torn', name: '撕纸条', desc: '手撕纸边缘效果' },
    { id: 'postit', name: '便利贴', desc: '经典黄色便利贴' },
  ];

  const currentBubble = (tweaks && tweaks.bubbleStyle) || 'default';
  const currentNote = (tweaks && tweaks.noteStyle) || 'classic';

  function setTweakVal(key, val) {
    // Post to parent for persistence
    window.parent.postMessage({ type: '__edit_mode_set_keys', edits: { [key]: val } }, '*');
    // Also dispatch a custom event so the Root component picks it up immediately
    window.dispatchEvent(new CustomEvent('tweak-update', { detail: { [key]: val } }));
  }

  function handleCoverUpload(who) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        const key = who === 'jinger' ? 'diaryCoverJinger' : 'diaryCoverConnie';
        setTweakVal(key, ev.target.result);
      };
      reader.readAsDataURL(file);
    };
    input.click();
  }

  // Sub-panels
  if (customPanel === 'bubble') {
    return (
      <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px', paddingBottom: 88 }}>
        <button onClick={() => setCustomPanel(null)} style={{
          background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          color: 'var(--text-tertiary)', fontSize: 12, fontFamily: "var(--font-body)", marginBottom: 16
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
          返回
        </button>
        <div style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 500, color: 'var(--text-deep)', marginBottom: 4 }}>聊天气泡样式</div>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 20 }}>选择你喜欢的聊天气泡风格</div>
        <Stack gap="sm">
          {BUBBLE_OPTIONS.map(opt => (
            <Card key={opt.id} onClick={() => setTweakVal('bubbleStyle', opt.id)} padding="md"
              style={{ border: currentBubble === opt.id ? '2px solid var(--accent)' : undefined, transition: 'all 0.15s' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>{opt.name}</span>
                {currentBubble === opt.id && <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M5 13l4 4L19 7"/></svg>
                </div>}
              </div>
              {/* Mini preview */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <div style={{ background: opt.preview.recv, padding: '6px 12px', borderRadius: `${opt.preview.radius}px ${opt.preview.radius}px ${opt.preview.radius}px 4px`, fontSize: 12, color: '#333', maxWidth: '65%' }}>你好呀 ☺️</div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <div style={{ background: opt.preview.gradient ? undefined : opt.preview.send, backgroundImage: opt.preview.gradient ? opt.preview.send : undefined, padding: '6px 12px', borderRadius: `${opt.preview.radius}px ${opt.preview.radius}px 4px ${opt.preview.radius}px`, fontSize: 12, color: opt.id === 'whatsapp' || opt.id === 'telegram' ? '#111' : (opt.id === 'default' ? 'var(--bubble-send-text)' : '#fff'), maxWidth: '65%' }}>在呢，想你了</div>
                </div>
              </div>
            </Card>
          ))}
        </Stack>
      </div>
    );
  }

  if (customPanel === 'note') {
    return (
      <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px', paddingBottom: 88 }}>
        <button onClick={() => setCustomPanel(null)} style={{
          background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          color: 'var(--text-tertiary)', fontSize: 12, fontFamily: "var(--font-body)", marginBottom: 16
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
          返回
        </button>
        <div style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 500, color: 'var(--text-deep)', marginBottom: 4 }}>便签样式</div>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 20 }}>选择 Connie 留纸条的风格</div>
        <Stack gap="sm">
          {NOTE_OPTIONS.map(opt => {
            const notePreviewStyles = {
              classic: { bg: '#FDF8F0', bgImage: 'repeating-linear-gradient(transparent, transparent 15px, rgba(124,99,80,0.12) 16px)', tape: true, tapeColor: 'rgba(130,189,197,0.45)' },
              kraft: { bg: '#C4A882', bgImage: 'none', tape: false },
              pastel: { bg: 'linear-gradient(135deg, #F0E6F6, #E6EFF6)', bgImage: 'none', tape: true, tapeColor: 'rgba(180,140,200,0.35)' },
              torn: { bg: '#FDF8F0', bgImage: 'none', tape: false, torn: true },
              postit: { bg: '#FFF9B1', bgImage: 'none', tape: false },
            };
            const ps = notePreviewStyles[opt.id] || notePreviewStyles.classic;
            return (
              <Card key={opt.id} onClick={() => setTweakVal('noteStyle', opt.id)} padding="md"
                style={{ border: currentNote === opt.id ? '2px solid var(--accent)' : undefined }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                  <div>
                    <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>{opt.name}</span>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>{opt.desc}</div>
                  </div>
                  {currentNote === opt.id && <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3"><path d="M5 13l4 4L19 7"/></svg>
                  </div>}
                </div>
                {/* Mini preview */}
                <div style={{
                  background: ps.bg.startsWith('linear') ? undefined : ps.bg,
                  backgroundImage: ps.bg.startsWith('linear') ? ps.bg : ps.bgImage,
                  borderRadius: opt.id === 'postit' ? '2px 2px 2px 16px' : 4,
                  padding: '10px 12px', position: 'relative', minHeight: 44,
                  boxShadow: opt.id === 'postit' ? '2px 3px 8px rgba(0,0,0,0.1)' : 'var(--shadow-sm)',
                  transform: opt.id === 'postit' ? 'rotate(-1deg)' : (opt.id === 'torn' ? 'none' : 'rotate(-0.5deg)'),
                  borderBottom: opt.id === 'torn' ? '3px wavy rgba(124,99,80,0.2)' : 'none',
                  clipPath: opt.id === 'torn' ? 'polygon(0 0, 100% 0, 100% 85%, 98% 88%, 95% 85%, 92% 90%, 88% 85%, 85% 88%, 80% 85%, 75% 90%, 70% 85%, 65% 88%, 60% 85%, 55% 90%, 50% 85%, 45% 88%, 40% 85%, 35% 90%, 30% 85%, 25% 88%, 20% 85%, 15% 90%, 10% 85%, 5% 88%, 2% 85%, 0 90%)' : 'none',
                }}>
                  {ps.tape && <div style={{ position: 'absolute', top: -5, left: '50%', transform: 'translateX(-50%) rotate(2deg)', width: 30, height: 10, background: ps.tapeColor, borderRadius: 1 }} />}
                  <div style={{ fontFamily: "'ShouShuTi', 'JustAnotherHand', cursive", fontSize: 13, color: opt.id === 'kraft' ? '#3C2F20' : 'var(--text-deep)', lineHeight: 1.5 }}>今天也要好好的呀~</div>
                </div>
              </Card>
            );
          })}
        </Stack>
      </div>
    );
  }

  if (customPanel === 'cover') {
    const coverJ = tweaks && tweaks.diaryCoverJinger;
    const coverC = tweaks && tweaks.diaryCoverConnie;
    return (
      <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px', paddingBottom: 88 }}>
        <button onClick={() => setCustomPanel(null)} style={{
          background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          color: 'var(--text-tertiary)', fontSize: 12, fontFamily: "var(--font-body)", marginBottom: 16
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
          返回
        </button>
        <div style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 500, color: 'var(--text-deep)', marginBottom: 4 }}>日记本封面</div>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 20 }}>上传自定义封面图片</div>
        <Stack gap="md">
          {/* Jinger cover */}
          <Card padding="lg">
            <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 'var(--space-3)' }}>静儿的日记本</div>
            <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
              <div style={{
                width: 72, height: 120, borderRadius: '4px 8px 8px 4px', overflow: 'hidden',
                background: coverJ ? `url(${coverJ}) center/cover` : '#F0C6D0',
                border: '1px solid var(--border-light)', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {!coverJ && <span style={{ fontSize: 10, color: 'rgba(139,94,107,0.6)', textAlign: 'center' }}>默认</span>}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button onClick={() => handleCoverUpload('jinger')} style={{
                  background: 'var(--accent)', color: '#FAF8F4', border: 'none', borderRadius: 'var(--radius-sm)',
                  padding: '8px 16px', fontSize: 12, cursor: 'pointer', fontWeight: 500,
                }}>上传图片</button>
                {coverJ && <button onClick={() => setTweakVal('diaryCoverJinger', '')} style={{
                  background: 'transparent', color: 'var(--text-tertiary)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)', padding: '6px 14px', fontSize: 11, cursor: 'pointer',
                }}>恢复默认</button>}
              </div>
            </div>
          </Card>
          {/* Connie cover */}
          <Card padding="lg">
            <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 'var(--space-3)' }}>Connie 的日记本</div>
            <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
              <div style={{
                width: 72, height: 120, borderRadius: '4px 8px 8px 4px', overflow: 'hidden',
                background: coverC ? `url(${coverC}) center/cover` : '#8B9EAE',
                border: '1px solid var(--border-light)', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {!coverC && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', textAlign: 'center' }}>默认</span>}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button onClick={() => handleCoverUpload('connie')} style={{
                  background: 'var(--accent)', color: '#FAF8F4', border: 'none', borderRadius: 'var(--radius-sm)',
                  padding: '8px 16px', fontSize: 12, cursor: 'pointer', fontWeight: 500,
                }}>上传图片</button>
                {coverC && <button onClick={() => setTweakVal('diaryCoverConnie', '')} style={{
                  background: 'transparent', color: 'var(--text-tertiary)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)', padding: '6px 14px', fontSize: 11, cursor: 'pointer',
                }}>恢复默认</button>}
              </div>
            </div>
          </Card>
        </Stack>
      </div>
    );
  }

  if (customPanel === 'font') {
    const FONT_SLOTS = [
      { key: 'Chat',     label: '聊天',     desc: '聊天界面正文' },
      { key: 'Note',     label: '小纸条',   desc: 'Connie 的纸条' },
      { key: 'Diary',    label: '日记',     desc: '日记本正文' },
      { key: 'Read',     label: '共读',     desc: 'Connie 的批注' },
      { key: 'Parallel', label: '平行世界', desc: '平行世界标题' },
    ];

    function uploadFont(slot) {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.ttf,.otf,font/ttf,font/otf';
      input.onchange = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (ev) => {
          setTweakVal('font' + slot, ev.target.result);
          setTweakVal('font' + slot + 'Name', file.name);
        };
        reader.readAsDataURL(file);
      };
      input.click();
    }

    return (
      <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px', paddingBottom: 88 }}>
        <button onClick={() => setCustomPanel(null)} style={{
          background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          color: 'var(--text-tertiary)', fontSize: 12, fontFamily: "var(--font-body)", marginBottom: 16
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
          返回
        </button>
        <div style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 500, color: 'var(--text-deep)', marginBottom: 4 }}>字体</div>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 20, lineHeight: 1.6 }}>
          为不同区域上传字体文件（.ttf / .otf）。上传后会保存在你本地。
        </div>
        <Stack gap="sm">
          {FONT_SLOTS.map(slot => {
            const data = tweaks && tweaks['font' + slot.key];
            const name = tweaks && tweaks['font' + slot.key + 'Name'];
            return (
              <Card key={slot.key} padding="md" elevated={false}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>{slot.label}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>{slot.desc}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {data && <button onClick={() => { setTweakVal('font' + slot.key, ''); setTweakVal('font' + slot.key + 'Name', ''); }} style={{
                      background: 'transparent', color: 'var(--text-tertiary)', border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-sm)', padding: '6px 12px', fontSize: 11, cursor: 'pointer',
                    }}>恢复默认</button>}
                    <button onClick={() => uploadFont(slot.key)} style={{
                      background: 'var(--accent)', color: 'var(--bg-elevated)', border: 'none',
                      borderRadius: 'var(--radius-sm)', padding: '6px 14px', fontSize: 12, cursor: 'pointer', fontWeight: 500,
                    }}>{data ? '更换' : '上传'}</button>
                  </div>
                </div>
                {/* Preview */}
                <div style={{
                  borderTop: '1px solid var(--border-light)', paddingTop: 10, marginTop: 4,
                  fontFamily: `var(--font-${slot.key.toLowerCase()})`,
                  fontSize: 16, color: 'var(--text-deep)', lineHeight: 1.6,
                }}>今天也要好好的呀，亲爱的</div>
                {name && <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 6, fontFamily: 'monospace' }}>{name}</div>}
              </Card>
            );
          })}
        </Stack>
      </div>
    );
  }

  return (
    <div style={{ overflowY: 'auto', height: '100%', padding: '16px 20px', paddingBottom: 88 }}>
      {/* Profile */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 0 16px', borderBottom: '1px solid var(--border-light)', marginBottom: 4 }}>
        <div style={{ width: 52, height: 52, borderRadius: '50%', background: 'var(--accent-subtle)', border: '1.5px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: "var(--font-display)", fontSize: 22, color: 'var(--accent)', fontWeight: 500 }}>C</div>
        <div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 500, color: 'var(--text-deep)' }}>我们的小窝</div>
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>Connie × 静儿 · 第 142 天</div>
        </div>
      </div>

      <SectionTitle title="关系与陪伴" />
      <SettingRow label="主动消息" sub="允许 Connie 主动来找你"><Toggle on={toggles.proactive} onChange={() => toggle('proactive')} /></SettingRow>
      <SettingRow label="允许深夜消息" sub="23:00 之后"><Toggle on={toggles.lateNight} onChange={() => toggle('lateNight')} /></SettingRow>
      <SettingRow label="小纸条" sub="打开 app 时的静默惊喜"><Toggle on={toggles.noteCard} onChange={() => toggle('noteCard')} /></SettingRow>
      <SettingRow label="日记解锁权限" sub="允许 Connie 申请解锁"><Toggle on={toggles.diaryUnlock} onChange={() => toggle('diaryUnlock')} /></SettingRow>

      <SectionTitle title="记忆与数据" />
      <SettingRow label="MCP 跨平台同步" sub="在 Claude.ai 恢复记忆"><Toggle on={toggles.mcp} onChange={() => toggle('mcp')} /></SettingRow>
      <SettingRow label="导入历史对话" sub="上传 Claude 导出 JSON">
        <button style={{ background: 'transparent', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '5px 12px', fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}>选择文件</button>
      </SettingRow>
      <SettingRow label="特殊日期管理">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M9 18l6-6-6-6"/></svg>
      </SettingRow>
      <SettingRow label="导出数据">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M9 18l6-6-6-6"/></svg>
      </SettingRow>

      <SectionTitle title="外观与高级" />
      <SettingRow label="深色模式" sub={tweaks && tweaks.darkMode ? '当前：深色' : '当前：浅色'}>
        <Toggle on={!!(tweaks && tweaks.darkMode)} onChange={(v) => setTweakVal('darkMode', v)} />
      </SettingRow>
      <div onClick={() => setCustomPanel('font')} style={{ cursor: 'pointer' }}>
        <SettingRow label="字体" sub="为聊天、纸条、日记等分别上传字体">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M9 18l6-6-6-6"/></svg>
        </SettingRow>
      </div>
      <div onClick={() => setCustomPanel('bubble')} style={{ cursor: 'pointer' }}>
        <SettingRow label="聊天气泡样式" sub={BUBBLE_OPTIONS.find(b => b.id === currentBubble)?.name || '默认'}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M9 18l6-6-6-6"/></svg>
        </SettingRow>
      </div>
      <div onClick={() => setCustomPanel('note')} style={{ cursor: 'pointer' }}>
        <SettingRow label="便签样式" sub={NOTE_OPTIONS.find(n => n.id === currentNote)?.name || '经典便签'}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M9 18l6-6-6-6"/></svg>
        </SettingRow>
      </div>
      <div onClick={() => setCustomPanel('cover')} style={{ cursor: 'pointer' }}>
        <SettingRow label="日记本封面" sub="自定义封面图片">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M9 18l6-6-6-6"/></svg>
        </SettingRow>
      </div>
      <SettingRow label="模型配置" sub="daily · deep · backend">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5"><path d="M9 18l6-6-6-6"/></svg>
      </SettingRow>

      <SectionTitle title="" />
      <SettingRow label="清除所有数据" danger><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" strokeWidth="1.5"><path d="M9 18l6-6-6-6"/></svg></SettingRow>
    </div>
  );
}

Object.assign(window, { PlayPage, SettingsPage });
