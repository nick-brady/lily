/**
 * Pure helpers for updating the events Map when engagement SSE events
 * arrive. Both BirthManagePage and PublicBirthPage use these — the
 * keepsake page and the parent dashboard speak the same event language.
 */

/**
 * Bump one reaction kind by `delta`. `isMine` indicates whether the SSE
 * event came from the current viewer's own action — only then do we
 * flip the `mine` flag. This avoids the case where two viewers loaded
 * the page at the same instant and one of them sees the other's
 * reaction as "mine".
 */
export function updateReaction(prev, eventId, kind, delta, isMine) {
  const event = prev.get(eventId);
  if (!event) return prev;
  const currentReactions = event.reactions || {};
  const current = currentReactions[kind] || { count: 0, mine: false };
  const nextCount = Math.max(0, current.count + delta);
  const nextMine = isMine ? delta > 0 : current.mine;
  const nextReactions = { ...currentReactions };
  if (nextCount === 0 && !nextMine) {
    delete nextReactions[kind];
  } else {
    nextReactions[kind] = { count: nextCount, mine: nextMine };
  }
  const next = new Map(prev);
  next.set(eventId, { ...event, reactions: nextReactions });
  return next;
}

export function bumpCommentCount(prev, eventId, delta) {
  const event = prev.get(eventId);
  if (!event) return prev;
  const next = new Map(prev);
  next.set(eventId, {
    ...event,
    comment_count: Math.max(0, (event.comment_count ?? 0) + delta),
  });
  return next;
}
