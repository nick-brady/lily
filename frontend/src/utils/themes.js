/**
 * Theme registry for the birth page.
 *
 * Each theme is a full design package, not just an accent color: it owns
 * the page background (including a subtle SVG pattern), a display font,
 * and every surface tint on the timeline — in both light and dark modes.
 * Themes are applied as CSS custom properties (see themeVars below);
 * index.css defines neutral defaults so unthemed surfaces (the manage
 * page) keep the standard look.
 *
 * Keepsake rule: patterns stay quiet. They should read as texture from
 * arm's length, never compete with photos or words.
 */

const pat = (svg) => `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;

/* ── Patterns ──
 * Each is a function of (color, opacity) so light and dark modes can
 * tint the same artwork. Motifs are placed off-grid so the tile repeat
 * doesn't read as a checkerboard.
 */

// Lily buds on curved stems, line art.
const sprigs = (c, o) => pat(
  `<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180' viewBox='0 0 180 180'>` +
  `<g stroke='${c}' stroke-opacity='${o}' fill='none' stroke-width='1.4' stroke-linecap='round'>` +
  `<g transform='translate(40 52) rotate(-14)'>` +
  `<path d='M0 0 C-7 -5 -9 -16 -4 -24 C-2 -18 0 -15 0 -13 C0 -15 2 -18 4 -24 C9 -16 7 -5 0 0 Z'/>` +
  `<path d='M0 0 C0 10 -2 18 -8 26'/>` +
  `<path d='M-5 14 C-11 12 -14 8 -15 3'/>` +
  `</g>` +
  `<g transform='translate(132 136) rotate(18)'>` +
  `<path d='M0 0 C-7 -5 -9 -16 -4 -24 C-2 -18 0 -15 0 -13 C0 -15 2 -18 4 -24 C9 -16 7 -5 0 0 Z'/>` +
  `<path d='M0 0 C0 10 -2 18 -8 26'/>` +
  `<path d='M-5 14 C-11 12 -14 8 -15 3'/>` +
  `</g>` +
  `<circle cx='150' cy='44' r='1.6' fill='${c}' fill-opacity='${o}' stroke='none'/>` +
  `<circle cx='24' cy='148' r='1.6' fill='${c}' fill-opacity='${o}' stroke='none'/>` +
  `<circle cx='92' cy='96' r='1.3' fill='${c}' fill-opacity='${o}' stroke='none'/>` +
  `</g></svg>`,
);

// Drifting rose petals with one full blossom.
const petals = (c, o) => pat(
  `<svg xmlns='http://www.w3.org/2000/svg' width='150' height='150' viewBox='0 0 150 150'>` +
  `<g fill='${c}' fill-opacity='${o}'>` +
  `<g transform='translate(38 36)'>` +
  `<ellipse rx='4' ry='7.5' transform='rotate(0) translate(0 -8)'/>` +
  `<ellipse rx='4' ry='7.5' transform='rotate(72) translate(0 -8)'/>` +
  `<ellipse rx='4' ry='7.5' transform='rotate(144) translate(0 -8)'/>` +
  `<ellipse rx='4' ry='7.5' transform='rotate(216) translate(0 -8)'/>` +
  `<ellipse rx='4' ry='7.5' transform='rotate(288) translate(0 -8)'/>` +
  `<circle r='2.4'/>` +
  `</g>` +
  `<ellipse cx='110' cy='28' rx='3.5' ry='6.5' transform='rotate(38 110 28)'/>` +
  `<ellipse cx='128' cy='96' rx='3.5' ry='6.5' transform='rotate(-24 128 96)'/>` +
  `<ellipse cx='62' cy='118' rx='3.5' ry='6.5' transform='rotate(64 62 118)'/>` +
  `<ellipse cx='18' cy='92' rx='3' ry='5.5' transform='rotate(-48 18 92)'/>` +
  `<ellipse cx='92' cy='66' rx='2.6' ry='4.8' transform='rotate(20 92 66)'/>` +
  `</g></svg>`,
);

// A sauropod, a stegosaurus, a fern, and footprints.
const dinos = (c, o) => pat(
  `<svg xmlns='http://www.w3.org/2000/svg' width='210' height='210' viewBox='0 0 210 210'>` +
  `<g fill='${c}' fill-opacity='${o}'>` +
  `<g transform='translate(16 26)'>` +
  `<ellipse cx='44' cy='34' rx='19' ry='11'/>` +
  `<path d='M30 28 C25 18 21 11 14 7 C11 5 8 8 10 11 C15 17 19 26 21 33 Z'/>` +
  `<circle cx='12' cy='7' r='5'/>` +
  `<path d='M61 30 C70 31 78 35 84 42 L80 46 C73 40 66 41 60 40 Z'/>` +
  `<rect x='32' y='42' width='6' height='11' rx='2.5'/>` +
  `<rect x='50' y='42' width='6' height='11' rx='2.5'/>` +
  `</g>` +
  `<g transform='translate(108 128)'>` +
  `<ellipse cx='34' cy='30' rx='22' ry='12'/>` +
  `<path d='M14 22 L20 9 L26 21 L32 7 L38 21 L44 9 L50 22 Z'/>` +
  `<path d='M54 28 C62 28 68 32 72 38 L68 41 C63 36 58 36 53 36 Z'/>` +
  `<path d='M16 28 C10 27 6 24 4 20 C8 22 12 23 16 25 Z'/>` +
  `<rect x='24' y='38' width='5' height='9' rx='2'/>` +
  `<rect x='42' y='38' width='5' height='9' rx='2'/>` +
  `</g>` +
  `<circle cx='160' cy='52' r='2'/><circle cx='168' cy='46' r='2'/><circle cx='166' cy='58' r='2'/>` +
  `<circle cx='40' cy='160' r='2'/><circle cx='48' cy='154' r='2'/><circle cx='46' cy='166' r='2'/>` +
  `</g>` +
  `<g stroke='${c}' stroke-opacity='${o}' fill='none' stroke-width='1.3' stroke-linecap='round' transform='translate(150 84)'>` +
  `<path d='M0 24 C2 12 2 6 0 0'/>` +
  `<path d='M0.5 7 C-4 5 -7 2 -8 -2'/><path d='M0.5 7 C5 5 8 2 9 -2'/>` +
  `<path d='M0.5 15 C-5 14 -9 11 -11 7'/><path d='M0.5 15 C6 14 10 11 12 7'/>` +
  `</g></svg>`,
);

// A baby elephant, a baby giraffe, a drifting cloud, and sparkles.
const safariAnimals = (c, o) => pat(
  `<svg xmlns='http://www.w3.org/2000/svg' width='220' height='220' viewBox='0 0 220 220'>` +
  `<g fill='${c}' fill-opacity='${o}'>` +
  `<g transform='translate(18 34)'>` +
  `<ellipse cx='42' cy='30' rx='21' ry='14'/>` +
  `<circle cx='16' cy='22' r='11'/>` +
  `<ellipse cx='22' cy='17' rx='6' ry='8'/>` +
  `<path d='M8 28 C3 34 2 41 6 46 C8 48 11 47 10 44 C7 41 8 36 13 31 Z'/>` +
  `<rect x='32' y='39' width='7' height='11' rx='3'/>` +
  `<rect x='48' y='39' width='7' height='11' rx='3'/>` +
  `<path d='M61 26 C65 28 66 32 64 35 L62 34 C63 31 62 29 59 28 Z'/>` +
  `</g>` +
  `<g transform='translate(130 108)'>` +
  `<rect x='12' y='50' width='4.5' height='18' rx='2.2'/>` +
  `<rect x='27' y='50' width='4.5' height='18' rx='2.2'/>` +
  `<ellipse cx='21' cy='46' rx='14' ry='10'/>` +
  `<path d='M28 40 L38 10 L45 12 L36 44 Z'/>` +
  `<ellipse cx='42' cy='9' rx='6.5' ry='5' transform='rotate(15 42 9)'/>` +
  `<circle cx='40' cy='1.5' r='1.5'/>` +
  `<circle cx='46' cy='3' r='1.5'/>` +
  `<ellipse cx='35.5' cy='6' rx='3' ry='2' transform='rotate(-32 35.5 6)'/>` +
  `</g>` +
  `<g transform='translate(146 38)'>` +
  `<circle cx='0' cy='2' r='5'/><circle cx='9' cy='-2' r='7'/><circle cx='18' cy='2' r='5'/>` +
  `<rect x='-5' y='2' width='28' height='5' rx='2.5'/>` +
  `</g>` +
  `<path transform='translate(50 150) scale(0.5)' d='M0 -9 C1.2 -2.5 2.5 -1.2 9 0 C2.5 1.2 1.2 2.5 0 9 C-1.2 2.5 -2.5 1.2 -9 0 C-2.5 -1.2 -1.2 -2.5 0 -9 Z'/>` +
  `<path transform='translate(100 88) scale(0.4)' d='M0 -9 C1.2 -2.5 2.5 -1.2 9 0 C2.5 1.2 1.2 2.5 0 9 C-1.2 2.5 -2.5 1.2 -9 0 C-2.5 -1.2 -1.2 -2.5 0 -9 Z'/>` +
  `<circle cx='196' cy='150' r='1.6'/><circle cx='28' cy='112' r='1.4'/><circle cx='112' cy='196' r='1.6'/>` +
  `</g></svg>`,
);

// A sitting fox, a bunny, a spotted mushroom, and a sprig.
const woodlandFriends = (c, o) => pat(
  `<svg xmlns='http://www.w3.org/2000/svg' width='210' height='210' viewBox='0 0 210 210'>` +
  `<g fill='${c}' fill-opacity='${o}'>` +
  `<g transform='translate(20 30)'>` +
  `<path d='M10 6 L7 -6 L17 2 Z'/>` +
  `<path d='M30 6 L33 -6 L23 2 Z'/>` +
  `<circle cx='20' cy='12' r='10'/>` +
  `<path d='M20 18 C9 26 6 38 8 50 L32 50 C34 38 31 26 20 18 Z'/>` +
  `<path d='M30 50 C46 51 53 40 49 27 C60 36 59 52 44 56 C37 58 31 54 30 50 Z'/>` +
  `</g>` +
  `<g transform='translate(150 44)'>` +
  `<ellipse cx='8' cy='-8' rx='3' ry='10' transform='rotate(-15 8 -8)'/>` +
  `<ellipse cx='15' cy='-8' rx='3' ry='10' transform='rotate(12 15 -8)'/>` +
  `<circle cx='11' cy='4' r='7'/>` +
  `<ellipse cx='14' cy='16' rx='11' ry='9'/>` +
  `<circle cx='26' cy='18' r='3'/>` +
  `</g>` +
  `<g transform='translate(52 158)'>` +
  `<path fill-rule='evenodd' d='M-14 0 C-14 -10 -6 -16 0 -16 C6 -16 14 -10 14 0 Z M-7 -8 a2 2 0 1 0 4 0 a2 2 0 1 0 -4 0 M3 -10 a1.6 1.6 0 1 0 3.2 0 a1.6 1.6 0 1 0 -3.2 0'/>` +
  `<rect x='-4' y='0' width='8' height='12' rx='3'/>` +
  `</g>` +
  `<circle cx='110' cy='100' r='1.6'/><circle cx='186' cy='130' r='1.6'/><circle cx='30' cy='110' r='1.4'/>` +
  `</g>` +
  `<g stroke='${c}' stroke-opacity='${o}' fill='none' stroke-width='1.3' stroke-linecap='round' transform='translate(158 156)'>` +
  `<path d='M0 26 C2 13 2 6 0 0'/>` +
  `<path d='M0.5 8 C-4 6 -7 3 -8 -1'/><path d='M0.5 8 C5 6 8 3 9 -1'/>` +
  `<path d='M0.5 17 C-5 16 -9 13 -11 9'/><path d='M0.5 17 C6 16 10 13 12 9'/>` +
  `</g></svg>`,
);

// A kite with bow-tie tail, a toy train, and alphabet blocks.
const vintageToys = (c, o) => pat(
  `<svg xmlns='http://www.w3.org/2000/svg' width='210' height='210' viewBox='0 0 210 210'>` +
  `<g fill='${c}' fill-opacity='${o}'>` +
  `<g transform='translate(42 38) rotate(14)'>` +
  `<path d='M0 -16 L11 0 L0 18 L-11 0 Z'/>` +
  `<path transform='translate(-3 32)' d='M0 0 L-6 -3 L-6 3 Z'/>` +
  `<path transform='translate(-3 32)' d='M0 0 L6 -3 L6 3 Z'/>` +
  `<path transform='translate(4 45)' d='M0 0 L-5 -2.5 L-5 2.5 Z'/>` +
  `<path transform='translate(4 45)' d='M0 0 L5 -2.5 L5 2.5 Z'/>` +
  `</g>` +
  `<g transform='translate(110 134)'>` +
  `<rect x='0' y='-2' width='11' height='24' rx='2'/>` +
  `<rect x='0' y='12' width='36' height='11' rx='2'/>` +
  `<rect x='28' y='3' width='5' height='8' rx='1.5'/>` +
  `<circle cx='30.5' cy='-2' r='3'/>` +
  `<circle cx='8' cy='26' r='4'/>` +
  `<circle cx='19' cy='26' r='4'/>` +
  `<circle cx='30' cy='26' r='4'/>` +
  `</g>` +
  `<path transform='translate(30 150) scale(0.55)' d='M0 -9 C1.2 -2.5 2.5 -1.2 9 0 C2.5 1.2 1.2 2.5 0 9 C-1.2 2.5 -2.5 1.2 -9 0 C-2.5 -1.2 -1.2 -2.5 0 -9 Z'/>` +
  `<path transform='translate(100 70) scale(0.4)' d='M0 -9 C1.2 -2.5 2.5 -1.2 9 0 C2.5 1.2 1.2 2.5 0 9 C-1.2 2.5 -2.5 1.2 -9 0 C-2.5 -1.2 -1.2 -2.5 0 -9 Z'/>` +
  `<circle cx='190' cy='180' r='1.6'/><circle cx='70' cy='196' r='1.4'/>` +
  `</g>` +
  `<g stroke='${c}' stroke-opacity='${o}' fill='none' stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round'>` +
  `<g transform='translate(42 38) rotate(14)'><path d='M0 18 C-6 28 4 36 4 45 C4 48 2 52 -2 55'/></g>` +
  `<g transform='translate(158 48)'>` +
  `<rect x='-9' y='-9' width='18' height='18' rx='2.5'/>` +
  `<path d='M-3.5 5 L0 -4.5 L3.5 5 M-2 1.5 L2 1.5'/>` +
  `</g>` +
  `<g transform='translate(176 70) rotate(12)'>` +
  `<rect x='-7.5' y='-7.5' width='15' height='15' rx='2.2'/>` +
  `<path d='M-2.5 -4 L-2.5 4 M-2.5 -4 C2 -4 2 0 -2.5 0 C2.5 0 2.5 4 -2.5 4'/>` +
  `</g>` +
  `</g></svg>`,
);

// Sparkle stars, dust, and a crescent moon.
const stars = (c, o) => pat(
  `<svg xmlns='http://www.w3.org/2000/svg' width='190' height='190' viewBox='0 0 190 190'>` +
  `<g fill='${c}' fill-opacity='${o}'>` +
  `<path transform='translate(34 44)' d='M0 -9 C1.2 -2.5 2.5 -1.2 9 0 C2.5 1.2 1.2 2.5 0 9 C-1.2 2.5 -2.5 1.2 -9 0 C-2.5 -1.2 -1.2 -2.5 0 -9 Z'/>` +
  `<path transform='translate(126 26) scale(0.55)' d='M0 -9 C1.2 -2.5 2.5 -1.2 9 0 C2.5 1.2 1.2 2.5 0 9 C-1.2 2.5 -2.5 1.2 -9 0 C-2.5 -1.2 -1.2 -2.5 0 -9 Z'/>` +
  `<path transform='translate(162 142) scale(0.8)' d='M0 -9 C1.2 -2.5 2.5 -1.2 9 0 C2.5 1.2 1.2 2.5 0 9 C-1.2 2.5 -2.5 1.2 -9 0 C-2.5 -1.2 -1.2 -2.5 0 -9 Z'/>` +
  `<path transform='translate(64 154) scale(0.5)' d='M0 -9 C1.2 -2.5 2.5 -1.2 9 0 C2.5 1.2 1.2 2.5 0 9 C-1.2 2.5 -2.5 1.2 -9 0 C-2.5 -1.2 -1.2 -2.5 0 -9 Z'/>` +
  `<path transform='translate(98 96) scale(0.4)' d='M0 -9 C1.2 -2.5 2.5 -1.2 9 0 C2.5 1.2 1.2 2.5 0 9 C-1.2 2.5 -2.5 1.2 -9 0 C-2.5 -1.2 -1.2 -2.5 0 -9 Z'/>` +
  `<path transform='translate(138 64) scale(1.1) rotate(-18)' d='M21 12.79 A9 9 0 1 1 11.21 3 A7 7 0 0 0 21 12.79 Z'/>` +
  `<circle cx='18' cy='110' r='1.2'/><circle cx='86' cy='20' r='1.2'/><circle cx='176' cy='84' r='1.2'/>` +
  `<circle cx='110' cy='176' r='1.2'/><circle cx='52' cy='88' r='1'/><circle cx='150' cy='178' r='1'/>` +
  `</g></svg>`,
);

// Boho arches and a small radiant sun.
const arches = (c, o) => pat(
  `<svg xmlns='http://www.w3.org/2000/svg' width='160' height='120' viewBox='0 0 160 120'>` +
  `<g stroke='${c}' stroke-opacity='${o}' fill='none' stroke-width='1.4' stroke-linecap='round'>` +
  `<path d='M20 66 a28 28 0 0 1 56 0'/>` +
  `<path d='M28 66 a20 20 0 0 1 40 0'/>` +
  `<path d='M36 66 a12 12 0 0 1 24 0'/>` +
  `<g transform='translate(122 92)'>` +
  `<circle r='6'/>` +
  `<path d='M0 -10 L0 -13'/><path d='M7 -7 L9 -9'/><path d='M10 0 L13 0'/><path d='M7 7 L9 9'/>` +
  `<path d='M0 10 L0 13'/><path d='M-7 7 L-9 9'/><path d='M-10 0 L-13 0'/><path d='M-7 -7 L-9 -9'/>` +
  `</g>` +
  `</g>` +
  `<circle cx='130' cy='28' r='1.6' fill='${c}' fill-opacity='${o}'/>` +
  `<circle cx='14' cy='100' r='1.6' fill='${c}' fill-opacity='${o}'/>` +
  `</svg>`,
);

// Two rows of rolling waves; tile width is an exact multiple of the
// wave period so the repeat is seamless.
const waves = (c, o) => pat(
  `<svg xmlns='http://www.w3.org/2000/svg' width='88' height='64' viewBox='0 0 88 64'>` +
  `<g stroke='${c}' stroke-opacity='${o}' fill='none' stroke-width='1.5' stroke-linecap='round'>` +
  `<path d='M0 18 q11 -8 22 0 t22 0 t22 0 t22 0'/>` +
  `<path d='M0 48 q11 -8 22 0 t22 0 t22 0 t22 0'/>` +
  `</g></svg>`,
);

/* ── Themes ── */

export const THEMES = {
  lily: {
    id: 'lily',
    label: 'Lily',
    description: 'Orchid & ivory',
    display: { family: "'Cormorant Garamond', serif", weight: 600, style: 'italic' },
    swatch: ['#d8b4fe', '#a21caf'],
    modes: {
      light: {
        pageBg: '#faf7fc',
        pattern: sprigs('#a855f7', 0.16),
        patternSize: '180px',
        headerBg: 'rgba(253, 251, 254, 0.88)',
        headerBorder: '#ecdcf6',
        title: '#86198f',
        titleSize: '1.9rem',
        cardBg: '#ffffff',
        cardBorder: '#f3e6fa',
        ink: '#44364a',
        inkMuted: '#82718c',
        inkFaint: '#b09fbb',
        divider: '#f3eaf8',
        accent: '#a21caf',
        accentHover: '#86198f',
        softBg: '#faeefe',
        softText: '#a21caf',
        softRing: '#f0ccfa',
        milestoneBg: '#f9ecfd',
        milestoneBorder: '#efd3fa',
        milestoneText: '#98189f',
        memoBg: '#fdf2f8',
        memoBorder: '#fbd8ec',
        memoText: '#be185d',
        noteBg: '#f8f4fb',
        dot: '#d946ef',
      },
      dark: {
        pageBg: '#1c1524',
        pattern: sprigs('#c084fc', 0.12),
        patternSize: '180px',
        headerBg: 'rgba(28, 21, 36, 0.88)',
        headerBorder: '#3b2a4d',
        title: '#e9c8fb',
        titleSize: '1.9rem',
        cardBg: '#261b33',
        cardBorder: '#38284a',
        ink: '#e3d9eb',
        inkMuted: '#a795b5',
        inkFaint: '#75648a',
        divider: '#352647',
        accent: '#d946ef',
        accentHover: '#c026d3',
        softBg: 'rgba(192, 38, 211, 0.16)',
        softText: '#e9aef5',
        softRing: 'rgba(217, 70, 239, 0.35)',
        milestoneBg: 'rgba(134, 25, 143, 0.25)',
        milestoneBorder: 'rgba(192, 38, 211, 0.4)',
        milestoneText: '#f0abfc',
        memoBg: 'rgba(190, 24, 93, 0.15)',
        memoBorder: 'rgba(190, 24, 93, 0.35)',
        memoText: '#f9a8d4',
        noteBg: 'rgba(56, 40, 74, 0.5)',
        dot: '#e879f9',
      },
    },
  },

  blossom: {
    id: 'blossom',
    label: 'Blossom',
    description: 'Rose garden',
    display: { family: "'Great Vibes', cursive", weight: 400, style: 'normal' },
    swatch: ['#fda4af', '#be123c'],
    modes: {
      light: {
        pageBg: '#fdf6f6',
        pattern: petals('#e11d48', 0.12),
        patternSize: '150px',
        headerBg: 'rgba(255, 251, 251, 0.88)',
        headerBorder: '#f8dada',
        title: '#be123c',
        titleSize: '2.3rem',
        cardBg: '#ffffff',
        cardBorder: '#f9e3e6',
        ink: '#4a3438',
        inkMuted: '#95707a',
        inkFaint: '#c2a4ab',
        divider: '#f8e8ea',
        accent: '#e11d48',
        accentHover: '#be123c',
        softBg: '#fdedf0',
        softText: '#be123c',
        softRing: '#fbcfd8',
        milestoneBg: '#fdeef1',
        milestoneBorder: '#fad2da',
        milestoneText: '#be123c',
        memoBg: '#fff1f2',
        memoBorder: '#fecdd3',
        memoText: '#be123c',
        noteBg: '#fbf3f3',
        dot: '#fb7185',
      },
      dark: {
        pageBg: '#241418',
        pattern: petals('#fb7185', 0.1),
        patternSize: '150px',
        headerBg: 'rgba(36, 20, 24, 0.88)',
        headerBorder: '#4a2630',
        title: '#fda4af',
        titleSize: '2.3rem',
        cardBg: '#2e1a20',
        cardBorder: '#44262e',
        ink: '#ecdce0',
        inkMuted: '#b2919a',
        inkFaint: '#7d5f68',
        divider: '#40232b',
        accent: '#fb7185',
        accentHover: '#f43f5e',
        softBg: 'rgba(225, 29, 72, 0.16)',
        softText: '#fda4af',
        softRing: 'rgba(251, 113, 133, 0.35)',
        milestoneBg: 'rgba(190, 18, 60, 0.22)',
        milestoneBorder: 'rgba(225, 29, 72, 0.4)',
        milestoneText: '#fda4af',
        memoBg: 'rgba(190, 18, 60, 0.15)',
        memoBorder: 'rgba(225, 29, 72, 0.3)',
        memoText: '#fda4af',
        noteBg: 'rgba(68, 38, 46, 0.5)',
        dot: '#fb7185',
      },
    },
  },

  dino: {
    id: 'dino',
    label: 'Little Dino',
    description: 'Playful meadow',
    display: { family: "'Fredoka', sans-serif", weight: 600, style: 'normal' },
    swatch: ['#86efac', '#2f9e63'],
    modes: {
      light: {
        pageBg: '#f4f8ef',
        pattern: dinos('#3f6e4f', 0.14),
        patternSize: '210px',
        headerBg: 'rgba(252, 254, 250, 0.88)',
        headerBorder: '#dcead2',
        title: '#2f6846',
        titleSize: '1.7rem',
        cardBg: '#ffffff',
        cardBorder: '#e2eedb',
        ink: '#35443a',
        inkMuted: '#71836f',
        inkFaint: '#a4b3a0',
        divider: '#e8f0e2',
        accent: '#2f9e63',
        accentHover: '#268552',
        softBg: '#e7f5e9',
        softText: '#2f7d4f',
        softRing: '#c6e8cf',
        milestoneBg: '#ecf7e9',
        milestoneBorder: '#cfe8c8',
        milestoneText: '#2f7d4f',
        memoBg: '#fef7e0',
        memoBorder: '#fae8b5',
        memoText: '#92681c',
        noteBg: '#f3f7ef',
        dot: '#4cb87a',
      },
      dark: {
        pageBg: '#16211a',
        pattern: dinos('#7fd4a1', 0.1),
        patternSize: '210px',
        headerBg: 'rgba(22, 33, 26, 0.88)',
        headerBorder: '#2b4234',
        title: '#a7e3bd',
        titleSize: '1.7rem',
        cardBg: '#1f2d24',
        cardBorder: '#2e4435',
        ink: '#d9e6db',
        inkMuted: '#97ad9b',
        inkFaint: '#64785f',
        divider: '#2a3f31',
        accent: '#4cb87a',
        accentHover: '#3da569',
        softBg: 'rgba(76, 184, 122, 0.16)',
        softText: '#a7e3bd',
        softRing: 'rgba(76, 184, 122, 0.35)',
        milestoneBg: 'rgba(47, 125, 79, 0.25)',
        milestoneBorder: 'rgba(76, 184, 122, 0.4)',
        milestoneText: '#a7e3bd',
        memoBg: 'rgba(146, 104, 28, 0.18)',
        memoBorder: 'rgba(250, 232, 181, 0.25)',
        memoText: '#f3d489',
        noteBg: 'rgba(46, 68, 53, 0.45)',
        dot: '#6fd198',
      },
    },
  },

  safari: {
    id: 'safari',
    label: 'Little Safari',
    description: 'Savanna sunset',
    display: { family: "'Baloo 2', sans-serif", weight: 600, style: 'normal' },
    swatch: ['#f0d9bb', '#c2622f'],
    modes: {
      light: {
        pageBg: '#fbf6ee',
        pattern: safariAnimals('#a05c2c', 0.15),
        patternSize: '220px',
        headerBg: 'rgba(255, 252, 246, 0.88)',
        headerBorder: '#f0e2cd',
        title: '#8a4b25',
        titleSize: '1.7rem',
        cardBg: '#ffffff',
        cardBorder: '#f0e4d2',
        ink: '#4a3a2c',
        inkMuted: '#8c7a64',
        inkFaint: '#bcab93',
        divider: '#f2e8d8',
        accent: '#c2622f',
        accentHover: '#a8511f',
        softBg: '#f9eddd',
        softText: '#a8551f',
        softRing: '#f0d9bb',
        milestoneBg: '#faf0dc',
        milestoneBorder: '#eedcb4',
        milestoneText: '#96601c',
        memoBg: '#eef4e6',
        memoBorder: '#d5e3c4',
        memoText: '#5a7a3a',
        noteBg: '#f7f0e3',
        dot: '#d98e4a',
      },
      dark: {
        pageBg: '#221a11',
        pattern: safariAnimals('#dca06a', 0.1),
        patternSize: '220px',
        headerBg: 'rgba(34, 26, 17, 0.88)',
        headerBorder: '#43331f',
        title: '#ecc89a',
        titleSize: '1.7rem',
        cardBg: '#2c2316',
        cardBorder: '#41331f',
        ink: '#ecdfc9',
        inkMuted: '#b3a187',
        inkFaint: '#7d6c52',
        divider: '#3b2e1c',
        accent: '#dd8a4e',
        accentHover: '#c97335',
        softBg: 'rgba(221, 138, 78, 0.15)',
        softText: '#ecc89a',
        softRing: 'rgba(221, 138, 78, 0.35)',
        milestoneBg: 'rgba(150, 96, 28, 0.25)',
        milestoneBorder: 'rgba(194, 98, 47, 0.45)',
        milestoneText: '#f0c98f',
        memoBg: 'rgba(90, 122, 58, 0.2)',
        memoBorder: 'rgba(141, 177, 103, 0.35)',
        memoText: '#bcd99a',
        noteBg: 'rgba(65, 51, 31, 0.45)',
        dot: '#dd8a4e',
      },
    },
  },

  woodland: {
    id: 'woodland',
    label: 'Woodland',
    description: 'Sage & rust',
    display: { family: "'Alice', serif", weight: 400, style: 'normal' },
    swatch: ['#c7d2a8', '#b0552f'],
    modes: {
      light: {
        pageBg: '#f3f4ec',
        pattern: woodlandFriends('#9c5f3f', 0.14),
        patternSize: '210px',
        headerBg: 'rgba(251, 252, 247, 0.88)',
        headerBorder: '#e2e6d4',
        title: '#8c4a2a',
        titleSize: '1.8rem',
        cardBg: '#ffffff',
        cardBorder: '#e6e9d9',
        ink: '#3f4536',
        inkMuted: '#7c8370',
        inkFaint: '#aab39b',
        divider: '#e9ecdd',
        accent: '#b0552f',
        accentHover: '#96431f',
        softBg: '#eef0e2',
        softText: '#5f6f4a',
        softRing: '#d8dec2',
        milestoneBg: '#f7ede2',
        milestoneBorder: '#ecd5bd',
        milestoneText: '#8c4a2a',
        memoBg: '#ecf0df',
        memoBorder: '#d3dcb8',
        memoText: '#56683b',
        noteBg: '#f1f2e8',
        dot: '#c4683e',
      },
      dark: {
        pageBg: '#191d15',
        pattern: woodlandFriends('#d2a075', 0.1),
        patternSize: '210px',
        headerBg: 'rgba(25, 29, 21, 0.88)',
        headerBorder: '#323a29',
        title: '#e3b48d',
        titleSize: '1.8rem',
        cardBg: '#222719',
        cardBorder: '#343b28',
        ink: '#e0e4d6',
        inkMuted: '#a2ab93',
        inkFaint: '#6e7860',
        divider: '#303826',
        accent: '#cf7244',
        accentHover: '#b85e33',
        softBg: 'rgba(143, 165, 107, 0.16)',
        softText: '#c4d3a4',
        softRing: 'rgba(143, 165, 107, 0.35)',
        milestoneBg: 'rgba(176, 85, 47, 0.2)',
        milestoneBorder: 'rgba(207, 114, 68, 0.4)',
        milestoneText: '#eab48f',
        memoBg: 'rgba(86, 104, 59, 0.25)',
        memoBorder: 'rgba(143, 165, 107, 0.4)',
        memoText: '#c9d8a9',
        noteBg: 'rgba(52, 59, 40, 0.5)',
        dot: '#cf7244',
      },
    },
  },

  heritage: {
    id: 'heritage',
    label: 'Toy Chest',
    description: 'Vintage toys',
    display: { family: "'Chelsea Market', cursive", weight: 400, style: 'normal' },
    swatch: ['#9db8d9', '#bf4a3a'],
    modes: {
      light: {
        pageBg: '#faf6ee',
        pattern: vintageToys('#41608c', 0.13),
        patternSize: '210px',
        headerBg: 'rgba(254, 251, 244, 0.88)',
        headerBorder: '#ecdfc8',
        title: '#34527c',
        titleSize: '1.55rem',
        cardBg: '#fffdf7',
        cardBorder: '#ece4d2',
        ink: '#433f36',
        inkMuted: '#857d6d',
        inkFaint: '#b5ac99',
        divider: '#eee6d6',
        accent: '#bf4a3a',
        accentHover: '#a63a2b',
        softBg: '#eaeff5',
        softText: '#41608c',
        softRing: '#cdd9e8',
        milestoneBg: '#f7e9e0',
        milestoneBorder: '#ecccba',
        milestoneText: '#a04432',
        memoBg: '#f2f0e0',
        memoBorder: '#e2dab2',
        memoText: '#8a7019',
        noteBg: '#f5f1e6',
        dot: '#cd5b4a',
      },
      dark: {
        pageBg: '#201c15',
        pattern: vintageToys('#d6c79e', 0.1),
        patternSize: '210px',
        headerBg: 'rgba(32, 28, 21, 0.88)',
        headerBorder: '#3e3727',
        title: '#a8c0e0',
        titleSize: '1.55rem',
        cardBg: '#2a251c',
        cardBorder: '#3f3828',
        ink: '#e8e2d4',
        inkMuted: '#ada390',
        inkFaint: '#766d5b',
        divider: '#3a3325',
        accent: '#d96c59',
        accentHover: '#c55543',
        softBg: 'rgba(120, 150, 190, 0.16)',
        softText: '#a8c0e0',
        softRing: 'rgba(120, 150, 190, 0.35)',
        milestoneBg: 'rgba(191, 74, 58, 0.2)',
        milestoneBorder: 'rgba(217, 108, 89, 0.4)',
        milestoneText: '#efb0a3',
        memoBg: 'rgba(138, 112, 25, 0.18)',
        memoBorder: 'rgba(211, 164, 37, 0.35)',
        memoText: '#e6c96a',
        noteBg: 'rgba(63, 56, 40, 0.5)',
        dot: '#d96c59',
      },
    },
  },

  ocean: {
    id: 'ocean',
    label: 'Little Waves',
    description: 'Sea air & sky',
    display: { family: "'Quicksand', sans-serif", weight: 600, style: 'normal' },
    swatch: ['#7dd3fc', '#0284c7'],
    modes: {
      light: {
        pageBg: '#f3f9fc',
        pattern: waves('#0284c7', 0.14),
        patternSize: '88px',
        headerBg: 'rgba(250, 253, 255, 0.88)',
        headerBorder: '#d8eaf5',
        title: '#075985',
        titleSize: '1.65rem',
        cardBg: '#ffffff',
        cardBorder: '#def0f9',
        ink: '#2e4a57',
        inkMuted: '#6d8a99',
        inkFaint: '#a3bdc9',
        divider: '#e3f1f8',
        accent: '#0284c7',
        accentHover: '#0369a1',
        softBg: '#e5f4fc',
        softText: '#0369a1',
        softRing: '#bbdff5',
        milestoneBg: '#e9f6fd',
        milestoneBorder: '#c8e7f8',
        milestoneText: '#075985',
        memoBg: '#ecfbf6',
        memoBorder: '#c8eee0',
        memoText: '#0f766e',
        noteBg: '#f0f7fb',
        dot: '#38bdf8',
      },
      dark: {
        pageBg: '#0d1b26',
        pattern: waves('#67c8f5', 0.1),
        patternSize: '88px',
        headerBg: 'rgba(13, 27, 38, 0.88)',
        headerBorder: '#1e3a4f',
        title: '#9bdcf9',
        titleSize: '1.65rem',
        cardBg: '#14283a',
        cardBorder: '#1f3c52',
        ink: '#d7e7ef',
        inkMuted: '#8fadbd',
        inkFaint: '#5c7c8e',
        divider: '#1d384c',
        accent: '#38bdf8',
        accentHover: '#0ea5e9',
        softBg: 'rgba(56, 189, 248, 0.15)',
        softText: '#9bdcf9',
        softRing: 'rgba(56, 189, 248, 0.35)',
        milestoneBg: 'rgba(7, 89, 133, 0.3)',
        milestoneBorder: 'rgba(2, 132, 199, 0.45)',
        milestoneText: '#7dd3fc',
        memoBg: 'rgba(15, 118, 110, 0.2)',
        memoBorder: 'rgba(20, 184, 166, 0.35)',
        memoText: '#5eead4',
        noteBg: 'rgba(31, 60, 82, 0.45)',
        dot: '#38bdf8',
      },
    },
  },

  golden: {
    id: 'golden',
    label: 'Golden Hour',
    description: 'Warm sun & arches',
    display: { family: "'Fraunces', serif", weight: 600, style: 'normal' },
    swatch: ['#fcd34d', '#b45309'],
    modes: {
      light: {
        pageBg: '#fbf5ec',
        pattern: arches('#b45309', 0.13),
        patternSize: '160px',
        headerBg: 'rgba(255, 251, 244, 0.88)',
        headerBorder: '#f0dfc4',
        title: '#92400e',
        titleSize: '1.7rem',
        cardBg: '#fffdf8',
        cardBorder: '#f1e3cb',
        ink: '#4a3b28',
        inkMuted: '#8d7a5e',
        inkFaint: '#bfae93',
        divider: '#f2e7d4',
        accent: '#b45309',
        accentHover: '#92400e',
        softBg: '#faefda',
        softText: '#92400e',
        softRing: '#f3ddb5',
        milestoneBg: '#fbf1de',
        milestoneBorder: '#f3ddb5',
        milestoneText: '#92400e',
        memoBg: '#fcefe8',
        memoBorder: '#f6d4c2',
        memoText: '#b0481f',
        noteBg: '#f8f1e5',
        dot: '#e9a23b',
      },
      dark: {
        pageBg: '#211a10',
        pattern: arches('#e9a23b', 0.1),
        patternSize: '160px',
        headerBg: 'rgba(33, 26, 16, 0.88)',
        headerBorder: '#41331d',
        title: '#f3cd8c',
        titleSize: '1.7rem',
        cardBg: '#2b2316',
        cardBorder: '#3f3320',
        ink: '#ecdfc8',
        inkMuted: '#b3a285',
        inkFaint: '#7d6f55',
        divider: '#3a2e1c',
        accent: '#e9a23b',
        accentHover: '#d98c1f',
        softBg: 'rgba(233, 162, 59, 0.15)',
        softText: '#f3cd8c',
        softRing: 'rgba(233, 162, 59, 0.35)',
        milestoneBg: 'rgba(146, 64, 14, 0.28)',
        milestoneBorder: 'rgba(180, 83, 9, 0.45)',
        milestoneText: '#fcd34d',
        memoBg: 'rgba(176, 72, 31, 0.2)',
        memoBorder: 'rgba(234, 124, 77, 0.35)',
        memoText: '#f4b49a',
        noteBg: 'rgba(63, 51, 32, 0.45)',
        dot: '#e9a23b',
      },
    },
  },

  starry: {
    id: 'starry',
    label: 'Starry Night',
    description: 'Navy & gold',
    // Forces the page into dark mode so .dark-gated components (forms,
    // comment threads) stay legible on the midnight surfaces.
    alwaysDark: true,
    display: { family: "'Cormorant Garamond', serif", weight: 600, style: 'normal' },
    swatch: ['#e8cd8a', '#1e2c54'],
    // Inherently dark — both modes share the same midnight palette, so
    // the page looks intentional whether or not the viewer flips dark mode.
    modes: (() => {
      const midnight = {
        pageBg: '#101a33',
        pattern: stars('#e3c577', 0.3),
        patternSize: '190px',
        headerBg: 'rgba(16, 26, 51, 0.88)',
        headerBorder: '#263354',
        title: '#e8cd8a',
        titleSize: '1.85rem',
        cardBg: '#182444',
        cardBorder: '#263558',
        ink: '#dde4f5',
        inkMuted: '#9fadd1',
        inkFaint: '#66739b',
        divider: '#243250',
        accent: '#c9a23f',
        accentHover: '#b08a2e',
        softBg: 'rgba(212, 175, 95, 0.15)',
        softText: '#e8cd8a',
        softRing: 'rgba(212, 175, 95, 0.35)',
        milestoneBg: 'rgba(201, 162, 63, 0.16)',
        milestoneBorder: 'rgba(201, 162, 63, 0.4)',
        milestoneText: '#ecd9a0',
        memoBg: 'rgba(99, 102, 241, 0.15)',
        memoBorder: 'rgba(129, 140, 248, 0.35)',
        memoText: '#b6bcf5',
        noteBg: 'rgba(38, 53, 88, 0.5)',
        dot: '#e8cd8a',
      };
      return { light: midnight, dark: midnight };
    })(),
  },
};

// Earlier theme ids that no longer exist; map to the closest new look so
// existing births keep a sensible page.
const LEGACY_ALIASES = {
  wildflower: 'lily',
  forest: 'dino',
};

export function getTheme(id) {
  return THEMES[id] || THEMES[LEGACY_ALIASES[id]] || THEMES.lily;
}

/**
 * Flatten a theme into the CSS custom properties the birth page and
 * timeline consume. Spread the result into a `style` prop on the page
 * root; index.css provides neutral fallbacks for unthemed surfaces.
 */
export function themeVars(theme, dark = false) {
  const t = theme.modes[dark ? 'dark' : 'light'];
  return {
    '--t-page-bg': t.pageBg,
    '--t-page-pattern': t.pattern,
    '--t-pattern-size': t.patternSize,
    '--t-header-bg': t.headerBg,
    '--t-header-border': t.headerBorder,
    '--t-title': t.title,
    '--t-title-size': t.titleSize,
    '--t-display-font': theme.display.family,
    '--t-display-weight': String(theme.display.weight),
    '--t-display-style': theme.display.style,
    '--t-card-bg': t.cardBg,
    '--t-card-border': t.cardBorder,
    '--t-ink': t.ink,
    '--t-ink-muted': t.inkMuted,
    '--t-ink-faint': t.inkFaint,
    '--t-divider': t.divider,
    '--t-accent': t.accent,
    '--t-accent-hover': t.accentHover,
    '--t-soft-bg': t.softBg,
    '--t-soft-text': t.softText,
    '--t-soft-ring': t.softRing,
    '--t-milestone-bg': t.milestoneBg,
    '--t-milestone-border': t.milestoneBorder,
    '--t-milestone-text': t.milestoneText,
    '--t-memo-bg': t.memoBg,
    '--t-memo-border': t.memoBorder,
    '--t-memo-text': t.memoText,
    '--t-note-bg': t.noteBg,
    '--t-dot': t.dot,
  };
}
