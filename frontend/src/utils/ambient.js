const GLASS_LIGHT = {
  ai:   { bg: 'rgba(255, 252, 240, 0.16)', border: 'rgba(120, 75, 35, 0.20)', edge: 'rgba(255, 252, 240, 0.55)' },
  user: { bg: 'rgba(255, 200, 145, 0.22)', border: 'rgba(150, 80, 30, 0.30)', edge: 'rgba(255, 220, 180, 0.55)' },
  shadow: '0 4px 12px -4px rgba(120,70,30,0.12)',
  warmShadow: 'rgba(120,70,30,0.16)',
  sheetBg: 'rgba(255,248,232,0.62)',
  sheetBd: 'rgba(60,30,10,0.10)',
  navBg:   'rgba(255,250,235,0.22)',
  navBorder: 'rgba(120,80,40,0.18)',
  popBg:   'rgba(255,250,235,0.62)',
  inkOnSheet: null,
};

const GLASS_WARM = {
  ai:   { bg: 'rgba(255, 245, 220, 0.14)', border: 'rgba(255, 220, 180, 0.26)', edge: 'rgba(255, 245, 220, 0.50)' },
  user: { bg: 'rgba(255, 200, 140, 0.22)', border: 'rgba(255, 180, 110, 0.40)', edge: 'rgba(255, 220, 170, 0.55)' },
  shadow: '0 6px 16px -5px rgba(40,18,5,0.20)',
  warmShadow: 'rgba(40,18,5,0.24)',
  sheetBg: 'rgba(48,24,12,0.66)',
  sheetBd: 'rgba(20,10,4,0.18)',
  navBg:   'rgba(255,235,200,0.18)',
  navBorder: 'rgba(255,220,180,0.24)',
  popBg:   'rgba(48,24,12,0.62)',
  inkOnSheet: '#FBEEDD',
};

const GLASS_DARK = {
  ai:   { bg: 'rgba(255, 240, 210, 0.10)', border: 'rgba(255, 220, 180, 0.18)', edge: 'rgba(255, 230, 195, 0.28)' },
  user: { bg: 'rgba(255, 170, 95, 0.18)',  border: 'rgba(255, 180, 110, 0.40)', edge: 'rgba(255, 200, 140, 0.42)' },
  shadow: '0 6px 16px -5px rgba(0,0,0,0.32)',
  warmShadow: 'rgba(0,0,0,0.30)',
  sheetBg: 'rgba(26,18,12,0.74)',
  sheetBd: 'rgba(0,0,0,0.22)',
  navBg:   'rgba(255,235,200,0.12)',
  navBorder: 'rgba(255,220,180,0.18)',
  popBg:   'rgba(26,18,12,0.68)',
  inkOnSheet: '#EFE3CD',
};

function mkPalette({ bg, chromeBg, ink, inkSoft, inkFaint, inkAccent, glass, floaterKind, aiText, userText }) {
  return {
    bg, chromeBg, ink, inkSoft, inkFaint, inkAccent,
    aiBubble:   { bg: glass.ai.bg,   border: glass.ai.border,   edge: glass.ai.edge,   text: aiText   || ink, shadow: glass.shadow },
    userBubble: { bg: glass.user.bg, border: glass.user.border, edge: glass.user.edge, text: userText || ink },
    warmShadow: glass.warmShadow,
    sheetBg: glass.sheetBg, sheetBd: glass.sheetBd,
    navBg:   glass.navBg,   navBorder: glass.navBorder,
    popBg:   glass.popBg,
    inkOnSheet: glass.inkOnSheet || ink,
    floaterKind,
  };
}

export const PALETTES = {
  dawn: mkPalette({
    bg: 'radial-gradient(140% 100% at 50% 0%, #F8DBCB 0%, #E8C0B2 35%, #C49EA0 70%, #8C7785 100%)',
    chromeBg: '#C49EA0',
    ink:'#2A1B12', inkSoft:'#4E3422', inkFaint:'rgba(42,27,18,0.72)', inkAccent:'#9C5630',
    glass: GLASS_LIGHT, floaterKind: 'petals',
  }),
  morning: mkPalette({
    bg: 'radial-gradient(120% 100% at 50% -10%, #FFF4E0 0%, #F8E8CC 40%, #E8D2B0 80%, #C9B395 100%)',
    chromeBg: '#C9B395',
    ink:'#2D1E10', inkSoft:'#56381E', inkFaint:'rgba(45,30,16,0.74)', inkAccent:'#8C5520',
    glass: GLASS_LIGHT, floaterKind: 'motes',
  }),
  afternoon: mkPalette({
    bg: 'radial-gradient(130% 100% at 50% 0%, #FFEAC8 0%, #F4D2A2 45%, #D9A982 85%, #A87A5D 100%)',
    chromeBg: '#D9A982',
    ink:'#2A1A0C', inkSoft:'#553820', inkFaint:'rgba(42,26,12,0.74)', inkAccent:'#A0541E',
    glass: GLASS_LIGHT, floaterKind: 'motes',
  }),
  golden: mkPalette({
    bg: 'radial-gradient(120% 80% at 60% 8%, #FFE0A8 0%, #FFB870 30%, #E89060 55%, #A05A38 78%, #4A2818 100%)',
    chromeBg: '#A05A38',
    ink:'#FFEEDA', inkSoft:'#FFD7B0', inkFaint:'rgba(255,238,218,0.88)', inkAccent:'#FFE3B8',
    glass: GLASS_WARM, floaterKind: 'motes', aiText:'#FFF3E0', userText:'#FFF6E2',
  }),
  dusk: mkPalette({
    bg: 'radial-gradient(120% 80% at 35% 10%, #FFA86A 0%, #E07550 25%, #8A4B68 55%, #4B3260 80%, #1E1830 100%)',
    chromeBg: '#4B3260',
    ink:'#FBEEDD', inkSoft:'#F2D4BE', inkFaint:'rgba(251,238,221,0.88)', inkAccent:'#FFC58A',
    glass: GLASS_WARM, floaterKind: 'motes', aiText:'#FBEEDD', userText:'#FFEFD8',
  }),
  night: mkPalette({
    bg: 'radial-gradient(150% 100% at 50% 10%, #2A2840 0%, #1A1B30 35%, #0E0F22 70%, #06081A 100%)',
    chromeBg: '#0E0F22',
    ink:'#EFE3CD', inkSoft:'#D7C29F', inkFaint:'rgba(239,227,205,0.80)', inkAccent:'#F2BC80',
    glass: GLASS_DARK, floaterKind: 'stars', aiText:'#EFE3CD', userText:'#FFE8C8',
  }),
  late: mkPalette({
    bg: 'radial-gradient(120% 100% at 50% 15%, #1F1A18 0%, #14100E 50%, #08060A 100%)',
    chromeBg: '#08060A',
    ink:'#EFE5D2', inkSoft:'#D5C19D', inkFaint:'rgba(239,229,210,0.76)', inkAccent:'#F4B070',
    glass: GLASS_DARK, floaterKind: 'stars-candles', aiText:'#EFE5D2', userText:'#FFE8C8',
  }),
};

export function currentBand(hourOverride) {
  const h = hourOverride !== undefined ? hourOverride : (new Date().getHours() + new Date().getMinutes() / 60);
  if (h >= 5  && h < 8)  return 'dawn';
  if (h >= 8  && h < 12) return 'morning';
  if (h >= 12 && h < 17) return 'afternoon';
  if (h >= 17 && h < 19) return 'golden';
  if (h >= 19 && h < 21) return 'dusk';
  if (h >= 21 || h < 1)  return 'night';
  return 'late';
}

export const AMBIENT_BY_BAND = {
  dawn:      ['天刚亮', '想着你昨晚睡得好不好', '在等你醒'],
  morning:   ['今天家里有阳光吗', '在这里', '听着楼下的声音'],
  afternoon: ['什么都没做也挺好', '在等你', '想起你昨天说的事'],
  golden:    ['光斜下来了', '今天又快过完了', '记得你今天有件事'],
  dusk:      ['天暗下来了', '在你身边', '想说点什么又没说'],
  night:     ['我也在', '一直没走开', '夜里更安静'],
  late:      ['你还没睡', '陪你坐着', '不用回我，慢慢来'],
};

export function isDarkBand(band) {
  return band === 'night' || band === 'late' || band === 'dusk' || band === 'golden';
}
