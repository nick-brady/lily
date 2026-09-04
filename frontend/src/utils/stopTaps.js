/**
 * Counts STOP taps the server quietly declined, so a confused tapper gets
 * told what is going on.
 *
 * In a contraction's first five seconds a STOP does nothing: the tapper
 * cannot have known it had started, so their tap was a second START, not a
 * stop. The server returns the contraction unchanged and the button keeps
 * saying STOP. That is right for the partner who reached for the button at
 * the same moment — and baffling for someone who started it by accident and
 * is now pressing STOP again and again to make it go away.
 *
 * After PROMPT_AFTER such taps on the same contraction, the page shows the
 * "started N seconds ago — keep timing / discard it" dialog it would have
 * shown for a stop between five and ten seconds. The count belongs to one
 * contraction: a new one starts from zero.
 */

export const PROMPT_AFTER = 3;

export const NO_TAPS = { contractionId: null, count: 0 };

/**
 * Record one declined stop. Returns the next tally and whether this tap is
 * the one that should open the dialog.
 */
export function recordSilentStop(tally, contractionId) {
  const count = tally.contractionId === contractionId ? tally.count + 1 : 1;
  return {
    tally: { contractionId, count },
    prompt: count >= PROMPT_AFTER,
  };
}

/** Whole seconds since the contraction began, never negative. */
export function secondsSince(occurredAt, now = Date.now()) {
  const started = new Date(occurredAt).getTime();
  if (Number.isNaN(started)) return 0;
  return Math.max(0, Math.round((now - started) / 1000));
}
