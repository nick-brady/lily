import { describe, it, expect } from 'vitest';
import { createLatestBlob } from './latestBlob';

/** A slot that records every revoke, so a test can see what was thrown away. */
function slotWithLog() {
  const revoked = [];
  return { slot: createLatestBlob({ revoke: (u) => revoked.push(u) }), revoked };
}

describe('createLatestBlob', () => {
  it('shows the first result and revokes nothing', () => {
    const { slot, revoked } = slotWithLog();
    const t = slot.start();
    expect(slot.settle(t, 'blob:a')).toBe('blob:a');
    expect(slot.current()).toBe('blob:a');
    expect(revoked).toEqual([]);
  });

  it('replaces what is shown and revokes the one it replaced', () => {
    const { slot, revoked } = slotWithLog();
    slot.settle(slot.start(), 'blob:a');
    slot.settle(slot.start(), 'blob:b');
    expect(slot.current()).toBe('blob:b');
    expect(revoked).toEqual(['blob:a']);
  });

  it('a superseded result throws away its own blob and leaves the screen alone', () => {
    // This is the bug: a slow preview finishing *after* a newer one used to
    // revoke the URL that was already on screen, leaving a broken image.
    const { slot, revoked } = slotWithLog();
    const slow = slot.start();
    const fast = slot.start();

    expect(slot.settle(fast, 'blob:fast')).toBe('blob:fast');
    expect(slot.settle(slow, 'blob:slow')).toBeNull();

    expect(slot.current()).toBe('blob:fast');
    expect(revoked).toEqual(['blob:slow']);
    expect(revoked).not.toContain('blob:fast');
  });

  it('holds the line through a long pile-up of overlapping requests', () => {
    const { slot, revoked } = slotWithLog();
    const tokens = Array.from({ length: 6 }, () => slot.start());
    // they come back in a scrambled order; only the last one started wins
    for (const i of [2, 0, 5, 1, 4, 3]) slot.settle(tokens[i], `blob:${i}`);
    expect(slot.current()).toBe('blob:5');
    expect(revoked).not.toContain('blob:5');
    expect(revoked.sort()).toEqual(
      ['blob:0', 'blob:1', 'blob:2', 'blob:3', 'blob:4'].sort(),
    );
  });

  it('knows whether a request is still the one that matters', () => {
    const slot = createLatestBlob({ revoke: () => {} });
    const first = slot.start();
    expect(slot.isCurrent(first)).toBe(true);
    const second = slot.start();
    expect(slot.isCurrent(first)).toBe(false);
    expect(slot.isCurrent(second)).toBe(true);
  });

  it('clearing revokes what is shown and retires the request with it', () => {
    const { slot, revoked } = slotWithLog();
    const t = slot.start();
    slot.settle(t, 'blob:a');
    slot.clear();
    expect(slot.current()).toBeNull();
    expect(revoked).toEqual(['blob:a']);
    // a request in flight when the slot was cleared must not put itself back
    expect(slot.settle(t, 'blob:late')).toBeNull();
    expect(slot.current()).toBeNull();
    expect(revoked).toEqual(['blob:a', 'blob:late']);
  });

  it('clearing twice does not revoke twice', () => {
    const { slot, revoked } = slotWithLog();
    slot.settle(slot.start(), 'blob:a');
    slot.clear();
    slot.clear();
    expect(revoked).toEqual(['blob:a']);
  });

  it('settling the same url twice does not revoke the thing on screen', () => {
    const { slot, revoked } = slotWithLog();
    const t = slot.start();
    slot.settle(t, 'blob:a');
    slot.settle(t, 'blob:a');
    expect(slot.current()).toBe('blob:a');
    expect(revoked).toEqual([]);
  });
});
