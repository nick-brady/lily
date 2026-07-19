// The "Welcoming Lily Wren" scripted fixture that drives the landing-page
// demo phone (see Lily-Landing-Sections.md §1). Shapes match what the public
// timeline API returns, so the real Timeline/ReactionBar/CommentThread render
// it exactly as they render production data. Written to be reusable by the
// hero video cue engine later.

export const DEMO_UPDATE_ID = 'demo-update';

function contraction(id, occurredAtMs, durationSeconds) {
  return {
    id,
    event_type: 'contraction',
    occurred_at: new Date(occurredAtMs).toISOString(),
    payload: { duration_seconds: durationSeconds },
  };
}

export function makeBaseEvents() {
  const now = Date.now();
  return [
    contraction('demo-c1', now - 26 * 60 * 1000, 48),
    contraction('demo-c2', now - 17 * 60 * 1000, 55),
    contraction('demo-c3', now - 9 * 60 * 1000, 62),
  ];
}

export function makeUpdateEvent() {
  return {
    id: DEMO_UPDATE_ID,
    event_type: 'milestone',
    occurred_at: new Date().toISOString(),
    payload: {
      kind: 'active_labor',
      body: 'No big update yet — still in active labor. Contractions are getting closer 💜',
    },
    reactions: {},
    comment_count: 0,
  };
}

function toReactions(counts) {
  return Object.fromEntries(
    Object.entries(counts).map(([kind, count]) => [kind, { count, mine: false }]),
  );
}

// Reaction counts arriving in waves after the update posts (`at` is ms after
// the update appears). Each wave is the full state, not a delta.
export const REACTION_TICKS = [
  { at: 900, reactions: toReactions({ love: 3 }) },
  { at: 1600, reactions: toReactions({ love: 7, wow: 2 }) },
  { at: 2400, reactions: toReactions({ love: 12, wow: 4, pray: 3 }) },
];

export const FINAL_REACTIONS = REACTION_TICKS[REACTION_TICKS.length - 1].reactions;

export function makeDemoComment() {
  return {
    id: 'demo-comment-1',
    author_name: 'Grandma Janet',
    body: 'Thinking of you three every minute. So excited!! 💜',
    created_at: new Date().toISOString(),
    user_id: 'demo-janet',
  };
}

// End state of the whole sequence — used by the reduced-motion static render.
export function makeFinalEvents() {
  return [
    ...makeBaseEvents(),
    {
      ...makeUpdateEvent(),
      reactions: FINAL_REACTIONS,
      comment_count: 1,
      demo_comments: [makeDemoComment()],
    },
  ];
}

// ---- Section 2: the contraction timer ---------------------------------------
// The parent-view fixture behind the timer slide (Lily-Landing-Sections.md §2):
// two contractions already logged ~5 minutes apart, then the live one the
// slide "presses" the real ContractionButton for.

export function makeTimerBaseEvents() {
  const now = Date.now();
  return [
    contraction('demo-t1', now - 11 * 60 * 1000, 49),
    contraction('demo-t2', now - 5 * 60 * 1000, 55),
  ];
}

export function makeLoggedContraction(occurredAtMs, durationSeconds) {
  return contraction('demo-t-live', occurredAtMs, durationSeconds);
}

// ---- Section 3: the keepsake timeline --------------------------------------
// The completed Lily Wren story the keepsake slide scrolls back through
// (Lily-Landing-Sections.md §3). Same family, same active-labor update as
// section 1 — the carousel reads as one continuous story.

const HOUR = 60 * 60 * 1000;

// Placeholder "photos": soft abstract gradients so the demo ships without
// licensed imagery. Swap for real stills when we have them — captions carry
// the meaning either way.
function svgDataUri(body) {
  return `data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 300'>${body}</svg>`,
  )}`;
}

export const BABY_PHOTO_URL = svgDataUri(
  "<defs>" +
    "<radialGradient id='a' cx='35%' cy='40%' r='80%'>" +
    "<stop offset='0%' stop-color='#fdf2f4'/><stop offset='55%' stop-color='#f6dfe8'/><stop offset='100%' stop-color='#e3cfef'/>" +
    "</radialGradient>" +
    "<radialGradient id='b' cx='68%' cy='28%' r='45%'>" +
    "<stop offset='0%' stop-color='#ffffff' stop-opacity='0.9'/><stop offset='100%' stop-color='#ffffff' stop-opacity='0'/>" +
    "</radialGradient>" +
    "</defs>" +
    "<rect width='400' height='300' fill='url(#a)'/>" +
    "<circle cx='272' cy='92' r='95' fill='url(#b)'/>" +
    "<circle cx='138' cy='212' r='115' fill='#f3d3de' opacity='0.5'/>" +
    "<circle cx='212' cy='168' r='62' fill='#fbe9ee' opacity='0.8'/>",
);

export const BUMP_PHOTO_URL = svgDataUri(
  "<defs>" +
    "<radialGradient id='a' cx='60%' cy='35%' r='85%'>" +
    "<stop offset='0%' stop-color='#f7f3ea'/><stop offset='55%' stop-color='#e9eedf'/><stop offset='100%' stop-color='#d8e2d0'/>" +
    "</radialGradient>" +
    "<radialGradient id='b' cx='30%' cy='70%' r='45%'>" +
    "<stop offset='0%' stop-color='#ffffff' stop-opacity='0.8'/><stop offset='100%' stop-color='#ffffff' stop-opacity='0'/>" +
    "</radialGradient>" +
    "</defs>" +
    "<rect width='400' height='300' fill='url(#a)'/>" +
    "<circle cx='128' cy='202' r='100' fill='url(#b)'/>" +
    "<circle cx='268' cy='138' r='90' fill='#eef2e4' opacity='0.7'/>",
);

// A valid silent WAV built at runtime, so the voice-memo card renders a real
// audio player with a real duration instead of a broken src. Lazy singleton;
// object URLs live for the page's lifetime, which is what we want here.
let voiceMemoUrl = null;
export function demoVoiceMemoUrl(seconds = 34) {
  if (voiceMemoUrl) return voiceMemoUrl;
  const rate = 8000;
  const samples = rate * seconds;
  const buf = new ArrayBuffer(44 + samples);
  const view = new DataView(buf);
  const ascii = (offset, text) => {
    for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
  };
  ascii(0, 'RIFF');
  view.setUint32(4, 36 + samples, true);
  ascii(8, 'WAVE');
  ascii(12, 'fmt ');
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, rate, true);
  view.setUint32(28, rate, true); // byte rate (8-bit mono)
  view.setUint16(32, 1, true); // block align
  view.setUint16(34, 8, true); // bits per sample
  ascii(36, 'data');
  view.setUint32(40, samples, true);
  new Uint8Array(buf, 44).fill(128); // 8-bit PCM silence
  voiceMemoUrl = URL.createObjectURL(new Blob([buf], { type: 'audio/wav' }));
  return voiceMemoUrl;
}

function keepsakeComment(id, authorName, body, occurredAtMs) {
  return {
    id,
    author_name: authorName,
    body,
    created_at: new Date(occurredAtMs).toISOString(),
    user_id: `demo-${id}`,
  };
}

// No absolute clock times in copy — occurred_at is relative to "now", so a
// caption like "3 AM" would contradict the rendered timestamps.
export function makeKeepsakeEvents() {
  const now = Date.now();
  return [
    // Yesterday — the story begins.
    {
      id: 'ks-bump',
      event_type: 'photo',
      occurred_at: new Date(now - 30 * HOUR).toISOString(),
      payload: {
        demo_media_url: BUMP_PHOTO_URL,
        caption: '40 weeks today. Any day now, little one.',
      },
      reactions: toReactions({ love: 11, wow: 2 }),
      comment_count: 0,
    },
    {
      id: 'ks-water',
      event_type: 'milestone',
      occurred_at: new Date(now - 26 * HOUR).toISOString(),
      payload: { kind: 'water_broke', body: "It's happening!! Bags are in the car." },
      reactions: toReactions({ love: 14, pray: 6 }),
      comment_count: 1,
      demo_comments: [
        keepsakeComment('ks-water-c1', 'Grandpa Joe', "Go time!! We're so excited ❤️", now - 25.8 * HOUR),
      ],
    },
    contraction('ks-c1', now - 25.4 * HOUR, 44),
    contraction('ks-c2', now - 25 * HOUR, 51),
    // Overnight — the long middle.
    {
      id: 'ks-active',
      event_type: 'milestone',
      occurred_at: new Date(now - 11 * HOUR).toISOString(),
      payload: {
        kind: 'active_labor',
        body: 'No big update yet — still in active labor. Contractions are getting closer 💜',
      },
      reactions: FINAL_REACTIONS,
      comment_count: 1,
      demo_comments: [
        keepsakeComment(
          'ks-active-c1',
          'Grandma Janet',
          'Thinking of you three every minute. So excited!! 💜',
          now - 10.9 * HOUR,
        ),
      ],
    },
    contraction('ks-c3', now - 10.6 * HOUR, 58),
    contraction('ks-c4', now - 10.2 * HOUR, 63),
    {
      id: 'ks-memo',
      event_type: 'voice_memo',
      occurred_at: new Date(now - 9 * HOUR).toISOString(),
      payload: {
        demo_media_url: demoVoiceMemoUrl(),
        caption: 'Quick voice update from Dad between contractions.',
      },
      reactions: toReactions({ love: 9, pray: 2 }),
      comment_count: 0,
    },
    // The morning everything changed.
    {
      id: 'ks-born',
      event_type: 'milestone',
      occurred_at: new Date(now - 3.4 * HOUR).toISOString(),
      payload: { kind: 'born', body: "She's here! Mom and baby both doing great. 👶" },
      reactions: toReactions({ love: 21, wow: 5, pray: 4 }),
      comment_count: 0,
    },
    {
      id: 'ks-photo',
      event_type: 'photo',
      occurred_at: new Date(now - 3 * HOUR).toISOString(),
      payload: {
        demo_media_url: BABY_PHOTO_URL,
        caption: "7 lbs 2 oz. We're obsessed. 🤍",
      },
      reactions: toReactions({ love: 24, wow: 8, pray: 3 }),
      comment_count: 1,
      demo_comments: [
        keepsakeComment(
          'ks-photo-c1',
          'Grandma Janet',
          "Crying happy tears. She is absolutely perfect. 💜",
          now - 2.8 * HOUR,
        ),
      ],
    },
    {
      id: 'ks-name',
      event_type: 'milestone',
      occurred_at: new Date(now - 2 * HOUR).toISOString(),
      payload: { kind: 'name_announced', body: 'Her name is Lily Wren 🤍' },
      reactions: toReactions({ love: 18, wow: 6 }),
      comment_count: 1,
      demo_comments: [
        keepsakeComment('ks-name-c1', 'Aunt Em', "LILY!!! I'm already in love 😭💜", now - 1.9 * HOUR),
      ],
    },
  ];
}
