import { describe, it, expect } from 'vitest';
import {
  CENTRE, coverOverflow, focusAfterDrag, objectPosition, canReframe, focusOf,
} from './photoFocus';

// The timeline: full card width, capped at max-h-96 (384px).
const BOX = { width: 736, height: 384 };
// A phone photo held upright — the shape that loses its head today.
const PORTRAIT = { width: 3024, height: 4032 };
const LANDSCAPE = { width: 4032, height: 3024 };

describe('coverOverflow', () => {
  it('a tall photo hides its top and bottom, nothing at the sides', () => {
    const o = coverOverflow(PORTRAIT, BOX);
    expect(o.x).toBe(0);
    // scaled to 736 wide it stands 981px tall in a 384px box
    expect(Math.round(o.y)).toBe(597);
  });

  it('a wide photo in this box still hides its top and bottom', () => {
    // the box is wider than it is tall, but not as wide as the photo
    const o = coverOverflow(LANDSCAPE, BOX);
    expect(o.x).toBe(0);
    expect(o.y).toBeGreaterThan(0);
  });

  it('a photo the same shape as the box hides nothing', () => {
    expect(coverOverflow({ width: 1472, height: 768 }, BOX)).toEqual({ x: 0, y: 0 });
  });

  it('a photo whose size we do not know yet cannot be dragged', () => {
    expect(coverOverflow(null, BOX)).toEqual({ x: 0, y: 0 });
    expect(coverOverflow({ width: 0, height: 0 }, BOX)).toEqual({ x: 0, y: 0 });
    expect(coverOverflow(PORTRAIT, null)).toEqual({ x: 0, y: 0 });
  });
});

describe('focusAfterDrag', () => {
  const overflow = { x: 0, y: 600 };

  it('dragging the photo down reveals what was above it', () => {
    // a hand on a photograph moves the photograph, not the window
    const after = focusAfterDrag(CENTRE, { dx: 0, dy: 120 }, overflow);
    expect(after.y).toBeCloseTo(0.3, 5);
    expect(after.x).toBe(0.5);
  });

  it('dragging up reveals what was below', () => {
    expect(focusAfterDrag(CENTRE, { dx: 0, dy: -120 }, overflow).y).toBeCloseTo(0.7, 5);
  });

  it('stops at the edges of the picture rather than running past them', () => {
    expect(focusAfterDrag(CENTRE, { dx: 0, dy: 9000 }, overflow).y).toBe(0);
    expect(focusAfterDrag(CENTRE, { dx: 0, dy: -9000 }, overflow).y).toBe(1);
  });

  it('an axis with nothing hidden does not move, however hard you pull', () => {
    const after = focusAfterDrag(CENTRE, { dx: 500, dy: 0 }, overflow);
    expect(after.x).toBe(0.5);
  });

  it('carries on from where the photo was left, not from the middle', () => {
    const after = focusAfterDrag({ x: 0.5, y: 0.2 }, { dx: 0, dy: -60 }, overflow);
    expect(after.y).toBeCloseTo(0.3, 5);
  });

  it('treats a missing focal point as the middle', () => {
    expect(focusAfterDrag(null, { dx: 0, dy: 0 }, overflow)).toEqual(CENTRE);
  });
});

describe('objectPosition', () => {
  it('is what the browser wants, and defaults to the middle', () => {
    expect(objectPosition({ x: 0.5, y: 0.2 })).toBe('50% 20%');
    expect(objectPosition(null)).toBe('50% 50%');
    // a stored value from a wilder era still renders somewhere sensible
    expect(objectPosition({ x: -1, y: 4 })).toBe('0% 100%');
  });
});

describe('canReframe', () => {
  it('is false when the photo already fits, so nothing offers to move it', () => {
    expect(canReframe({ x: 0, y: 0 })).toBe(false);
    expect(canReframe({ x: 0, y: 0.4 })).toBe(false); // sub-pixel, not worth a handle
    expect(canReframe({ x: 0, y: 597 })).toBe(true);
  });
});

describe('focusOf', () => {
  it('reads a focal point off an event, and shrugs at anything else', () => {
    expect(focusOf({ payload: { focal: { x: 0.5, y: 0.1 } } })).toEqual({ x: 0.5, y: 0.1 });
    expect(focusOf({ payload: {} })).toBeNull();
    expect(focusOf({ payload: { focal: { x: 'up', y: 0.1 } } })).toBeNull();
    expect(focusOf(undefined)).toBeNull();
  });
});
