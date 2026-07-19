// Cue table + scripted fixture for the hero video (see Lily-Hero-Video-Plan.md
// §1/§4). Timestamps are locked against assembly_v7 (64.54s master). Segment
// anchors, for future retimes:
//   01→0.00  02→2.96  [blk]→4.66  03→5.46  04→10.50  05→14.54  [blk]→18.58
//   06→19.38 07→24.84 08→29.13 09→32.67 [blk]→36.72 10→37.52 11→41.56
//   [blk]→45.60 12→46.40 13→51.44 14→55.48 [blk]→59.52 15→60.32 end→64.54
//
// Choreography rule (plan §4): UI reacts 100–200ms AFTER the on-screen
// gesture, so it reads as cause-and-effect.

// The video is too heavy for the repo — it lives in S3 under
// assets/hero-section/ and the backend 307-redirects to a presigned URL
// (upload with tools/upload-hero-assets.sh). Poster + stills are small and
// ship with the frontend bundle.
export const HERO_VIDEO_SRC = '/api/assets/hero-section/hero-1080.mp4';
export const HERO_POSTER_SRC = '/hero/hero-poster.jpg';
export const HERO_DURATION = 64.54;

// ---------------------------------------------------------------------------
// Fixture events. Shapes match the public timeline API (same contract as
// demoBirth.js) so Timeline/ReactionBar/CommentThread render them exactly as
// production data. Photos ride a demo_url instead of a media_id.

const MIN = 60 * 1000;
const DAY = 24 * 60 * MIN;

function toReactions(counts) {
  return Object.fromEntries(
    Object.entries(counts).map(([kind, count]) => [kind, { count, mine: false }]),
  );
}

// The contraction back-log, oldest first: minutes before "now", duration,
// and whether a real gap precedes it (renders the "gap before" badge).
// Modeled on a real early-mid-labor log — short irregular ones early,
// longer/stronger later, with a few genuine lulls.
const CONTRACTION_LOG = [
  { min: 155, dur: 28 },
  { min: 145, dur: 37 },
  { min: 141, dur: 45 },
  { min: 129, dur: 37 },
  { min: 114, dur: 55 },
  { min: 95, dur: 57, gap: true },
  { min: 85, dur: 35 },
  { min: 75, dur: 61 },
  { min: 52, dur: 31, gap: true },
  { min: 47, dur: 35 },
  { min: 37, dur: 33 },
  { min: 32, dur: 42 },
  { min: 23, dur: 49, gap: true },
  { min: 20, dur: 58 },
  { min: 14, dur: 67 },
];

// Hospital-era contractions — active labor closing in: ~1 minute apart,
// longer and stronger. These sit between "Arrived at the hospital" and the
// water-broke/"game time" beat.
const HOSPITAL_CONTRACTIONS = [
  { min: 11.5, dur: 68 },
  { min: 10.5, dur: 74 },
  { min: 9.5, dur: 79 },
  { min: 8.5, dur: 82 },
];

// occurred_at offsets are relative to "now" at reset: bump photos are
// backdated weeks apart (the date groupings help say "months pass"), labor
// events run minutes apart tonight.
function buildEvents(base) {
  const at = (offset) => new Date(base + offset).toISOString();
  return {
    bump20: {
      id: 'hero-bump20',
      event_type: 'photo',
      occurred_at: at(-98 * DAY),
      payload: { demo_url: '/api/assets/hero-section/bump20.jpg', caption: '20 weeks! 🌸' },
      reactions: {},
      comment_count: 0,
    },
    bump40: {
      id: 'hero-bump40',
      event_type: 'photo',
      occurred_at: at(-6 * DAY),
      payload: { demo_url: '/api/assets/hero-section/bump40.jpg', caption: 'get this baby out of me! 😅' },
      reactions: {},
      comment_count: 0,
    },
    laboringPhoto: {
      id: 'hero-laboring-home',
      event_type: 'photo',
      occurred_at: at(-45 * MIN),
      payload: { demo_url: '/api/assets/hero-section/laboring-home.jpg' },
      reactions: {},
      comment_count: 1,
      demo_comments: [
        comment(
          'marco-post',
          'Marco',
          "Sarah's laboring at home right now. We're excited but nervous!",
          base,
          -44 * MIN,
        ),
      ],
    },
    voiceMemo: {
      id: 'hero-voice-memo',
      event_type: 'voice_memo',
      // Sits mid-log, right beside the 61s contraction at -75min — a quiet
      // moment captured between waves, like a real labor timeline.
      occurred_at: at(-74 * MIN),
      payload: {
        demo_url: '/api/assets/hero-section/memo.mp3',
        caption: 'I asked Sarah what she wants to tell the baby',
      },
      reactions: {},
      comment_count: 0,
    },
    contractionLogged: {
      id: 'hero-contraction-live',
      event_type: 'contraction',
      occurred_at: at(-42 * MIN),
      payload: { duration_seconds: 62 },
    },
    // The back-log that floods in during Interstitial B ("the hours
    // compress"): ~2.5 hours of early-mid labor, irregular — short ones,
    // longer ones, and real gaps (`gap: true` → the "gap before" badge).
    contractionFlood: CONTRACTION_LOG.map((c, i) => ({
      id: `hero-contraction-${i}`,
      event_type: 'contraction',
      occurred_at: at(-c.min * MIN),
      payload: {
        duration_seconds: c.dur,
        ...(c.gap ? { ignore_interval_before: true } : {}),
      },
    })),
    hospitalFlood: HOSPITAL_CONTRACTIONS.map((c, i) => ({
      id: `hero-contraction-h${i}`,
      event_type: 'contraction',
      occurred_at: at(-c.min * MIN),
      payload: { duration_seconds: c.dur },
    })),
    arrived: {
      id: 'hero-arrived',
      event_type: 'milestone',
      occurred_at: at(-12 * MIN),
      payload: { kind: 'arrived', body: 'Arrived at the hospital 🏥' },
      reactions: {},
      comment_count: 0,
    },
    waterBroke: {
      id: 'hero-water-broke',
      event_type: 'milestone',
      occurred_at: at(-8 * MIN),
      payload: { kind: 'water_broke', body: 'Water broke 💧' },
      reactions: {},
      comment_count: 0,
    },
    born: {
      id: 'hero-born',
      event_type: 'milestone',
      occurred_at: at(-1 * MIN),
      payload: { kind: 'born', body: "She's here. Lily Wren 🌸 7 lbs 2 oz" },
      reactions: {},
      comment_count: 0,
    },
    lilyPhoto: {
      id: 'hero-lily',
      event_type: 'photo',
      occurred_at: at(0),
      payload: { demo_url: '/api/assets/hero-section/lily.jpg', caption: "Lily Wren. We're so in love." },
      reactions: {},
      comment_count: 0,
    },
  };
}

const comment = (id, author, body, base, offset) => ({
  id,
  author_name: author,
  body,
  created_at: new Date(base + offset).toISOString(),
  user_id: `hero-${id}`,
});

// ---------------------------------------------------------------------------
// The cue table. Each cue: { t, apply(state, ctx) → state }. Cues must be
// pure (the engine replays them after seeks/loops).

export const HERO_CUES = [
  // -- Scene 1: the first entry (01/02) -------------------------------------
  { t: 3.9, apply: (s, { ev }) => addEvent(s, ev.bump20) },

  // -- Interstitial A: the bump grows (fade + black) ------------------------
  { t: 5.0, apply: (s, { ev }) => addEvent(s, ev.bump40) },
  { t: 6.0, apply: (s) => patchEvent(s, 'hero-bump40', { reactions: toReactions({ love: 4 }) }) },
  {
    t: 6.4,
    apply: (s, { base }) =>
      patchEvent(s, 'hero-bump40', {
        comment_count: 1,
        demo_comments: [
          comment('lisa-bump', 'Lisa', "😂😂 you've got this, mama", base, -6 * DAY + 90 * MIN),
        ],
      }),
  },
  { t: 7.0, apply: (s) => patchEvent(s, 'hero-bump40', { reactions: toReactions({ love: 9, wow: 2 }) }) },

  // -- Scene 2: labor begins (03) — Marco posts the laboring-at-home photo
  //    first, THEN his tap starts the contraction timer -----------------------
  { t: 7.6, apply: (s, { ev }) => addEvent(s, ev.laboringPhoto) },
  { t: 9.0, apply: (s) => ({ ...s, contractionActive: true, status: "Lily's family is timing contractions. Following along 🤍" }) },

  // -- Scene 3: the family lights up (04 Janet, 05 Emma) --------------------
  {
    t: 12.4,
    apply: (s, { base }) =>
      patchEvent(s, 'hero-laboring-home', {
        comment_count: 2,
        demo_comments: [
          comment('marco-post', 'Marco', "Sarah's laboring at home right now. We're excited but nervous!", base, -44 * MIN),
          comment('janet-1', 'Grandma Janet', "It's happening!! We love you three so much ❤️", base, -43 * MIN),
        ],
      }),
  },
  { t: 15.8, apply: (s) => patchEvent(s, 'hero-laboring-home', { reactions: toReactions({ love: 14, wow: 3 }) }) },
  {
    t: 16.6,
    apply: (s, { base }) =>
      patchEvent(s, 'hero-laboring-home', {
        comment_count: 3,
        demo_comments: [
          comment('marco-post', 'Marco', "Sarah's laboring at home right now. We're excited but nervous!", base, -44 * MIN),
          comment('janet-1', 'Grandma Janet', "It's happening!! We love you three so much ❤️", base, -43 * MIN),
          comment('marco-1', 'Marco', 'thank you!! Us too!! ❤️', base, -42 * MIN),
        ],
      }),
  },
  // Contraction logs as the scene fades — the fade means "time passes".
  { t: 17.9, apply: (s, { ev }) => addEvent({ ...s, contractionActive: false }, ev.contractionLogged) },

  // -- Interstitial B: the hours compress (black) — the whole back-log
  //    cascades in during the dip, the voice memo landing mid-cascade among
  //    the contractions it sits between ---------------------------------------
  ...[
    ...CONTRACTION_LOG.map((c, i) => ({
      t: 18.6 + i * 0.05,
      apply: (s, { ev }) => addEvent(s, ev.contractionFlood[i]),
    })),
    { t: 18.98, apply: (s, { ev }) => addEvent(s, ev.voiceMemo) },
  ].sort((a, b) => a.t - b.t),

  // -- Scene 4: leaving for the hospital (06) — the shared look --------------
  { t: 22.0, apply: (s) => ({ ...s, status: 'Contractions 5 minutes apart. Heading in 🚗' }) },
  { t: 23.5, apply: (s) => patchEvent(s, 'hero-voice-memo', { reactions: toReactions({ love: 5, pray: 2 }) }) },

  // -- Scene 5: hospital arrival (07) — milestone lands as the scene opens ---
  { t: 25.0, apply: (s, { ev }) => addEvent(s, ev.arrived) },

  // -- Scene 6: Emma lights up in her kitchen (08) ----------------------------
  { t: 29.9, apply: (s) => patchEvent(s, 'hero-arrived', { reactions: toReactions({ love: 6 }) }) },
  {
    t: 31.0,
    apply: (s, { base }) =>
      patchEvent(s, 'hero-arrived', {
        comment_count: 1,
        demo_comments: [
          comment('emma-1', 'Emma', "We're with you. We're so proud. 🤍", base, -11 * MIN),
        ],
        reactions: toReactions({ love: 11, pray: 4 }),
      }),
  },

  // -- Scene 7: active labor (09) — the hospital contractions flood in as
  //    she breathes through them, THEN the water-broke milestone lands -------
  ...HOSPITAL_CONTRACTIONS.map((c, i) => ({
    t: 33.0 + i * 0.2,
    apply: (s, { ev }) => addEvent(s, ev.hospitalFlood[i]),
  })),
  { t: 34.2, apply: (s, { ev }) => addEvent(s, ev.waterBroke) },
  { t: 35.2, apply: (s) => patchEvent(s, 'hero-water-broke', { reactions: toReactions({ love: 8, muscle: 5 }) }) },

  // -- Scene 8: Marco takes out his phone (10) --------------------------------
  {
    t: 39.2,
    apply: (s, { base }) =>
      patchEvent(s, 'hero-water-broke', {
        comment_count: 1,
        demo_comments: [
          comment('marco-2', 'Marco', 'Getting close!! Game time 💪', base, -4 * MIN),
        ],
      }),
  },

  // -- Scene 9: grandparents follow along at night (11) -----------------------
  {
    t: 43.5,
    apply: (s, { base }) =>
      patchEvent(s, 'hero-water-broke', {
        comment_count: 2,
        demo_comments: [
          comment('marco-2', 'Marco', 'Getting close!! Game time 💪', base, -4 * MIN),
          comment('janet-2', 'Grandma Janet', "Give her our love. We're wide awake too 💜", base, -3 * MIN),
        ],
      }),
  },

  // -- Scene 10: she's here (12) — milestone lands as the scene opens ---------
  { t: 46.6, apply: (s, { ev }) => addEvent(s, ev.born) },
  { t: 47.2, apply: (s) => ({ ...s, celebrate: true, status: 'Lily Wren is here 🌸' }) },
  { t: 51.0, apply: (s, { ev }) => addEvent(s, ev.lilyPhoto) },

  // -- Scenes 11a/11b: everyone at once (13 bar, 14 grandparents) -------------
  {
    t: 52.7,
    apply: (s, { base }) =>
      patchEvent(s, 'hero-born', {
        comment_count: 1,
        demo_comments: [comment('emma-2', 'Emma', 'Welcome to the world, Lily 🌎💕', base, -40 * 1000)],
        reactions: toReactions({ love: 7 }),
      }),
  },
  {
    t: 53.8,
    apply: (s, { base }) =>
      patchEvent(s, 'hero-born', {
        comment_count: 2,
        demo_comments: [
          comment('emma-2', 'Emma', 'Welcome to the world, Lily 🌎💕', base, -40 * 1000),
          comment('lisa-2', 'Lisa', "I can't stop crying!! CONGRATULATIONS 🎉", base, -25 * 1000),
        ],
        reactions: toReactions({ love: 15, party: 6 }),
      }),
  },
  {
    t: 56.3,
    apply: (s, { base }) =>
      patchEvent(s, 'hero-born', {
        comment_count: 3,
        demo_comments: [
          comment('emma-2', 'Emma', 'Welcome to the world, Lily 🌎💕', base, -40 * 1000),
          comment('lisa-2', 'Lisa', "I can't stop crying!! CONGRATULATIONS 🎉", base, -25 * 1000),
          comment('janet-3', 'Grandma Janet', "SHE'S HERE!! 😭❤️", base, -8 * 1000),
        ],
        reactions: toReactions({ love: 24, party: 9, wow: 5 }),
      }),
  },

  // -- Scene 12: the keepsake (15) ---------------------------------------------
  { t: 60.8, apply: (s) => ({ ...s, scrollTour: true, celebrate: false }) },
  // Scrim goes near-opaque just before the wrap; the engine resets state at 0.
  { t: 63.6, apply: (s) => ({ ...s, seam: true }) },
];

// ---------------------------------------------------------------------------
// State helpers used by the cue engine.

function addEvent(state, event) {
  if (state.events.some((e) => e.id === event.id)) return state;
  return { ...state, events: [...state.events, event] };
}

function patchEvent(state, id, patch) {
  return {
    ...state,
    events: state.events.map((e) => (e.id === id ? { ...e, ...patch } : e)),
  };
}

export function initialHeroState(base) {
  return {
    base,
    events: [],
    status: 'Following along 🤍',
    contractionActive: false,
    celebrate: false,
    scrollTour: false,
    seam: false,
  };
}

// Replays every cue at once — the reduced-motion / data-saver end state.
export function finalHeroState(base) {
  const ctx = { ev: buildEvents(base), base };
  const s = HERO_CUES.reduce((acc, cue) => cue.apply(acc, ctx), initialHeroState(base));
  return { ...s, seam: false, celebrate: false, scrollTour: false };
}

export function makeCueContext(base) {
  return { ev: buildEvents(base), base };
}
