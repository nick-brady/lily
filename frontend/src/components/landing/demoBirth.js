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
