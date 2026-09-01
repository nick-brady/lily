/**
 * Which part of a photo stays in view when the frame has to crop it.
 *
 * The timeline gives every photo the same width and a fixed maximum height,
 * and fills that box with `object-cover`. A tall photo therefore loses its
 * top and bottom — and on a newborn, the top is the face.
 *
 * A focal point says which point of the picture to keep centred. It is a pair
 * of fractions so it survives whatever size the photo is drawn at: (0, 0) is
 * the top-left corner, (0.5, 0.5) the middle — which is what a browser does
 * on its own, and so what "no focal point" means.
 *
 * `object-position` takes exactly this, and the browser does the arithmetic
 * for drawing. What is here is the arithmetic for *dragging*: turning a
 * gesture across the box into a movement of the point.
 */

export const CENTRE = { x: 0.5, y: 0.5 };

const clamp01 = (n) => Math.min(1, Math.max(0, n));

/**
 * How many pixels of the photo are hidden on each axis.
 *
 * `object-cover` scales the picture up until it covers the box, so exactly
 * one axis overflows (or neither, when the shapes match). The overflow is how
 * far the picture can travel — an axis with none cannot be dragged, which is
 * why a wide photo in a wide box does not move vertically however hard you
 * pull it.
 */
export function coverOverflow(natural, box) {
  if (!natural?.width || !natural?.height || !box?.width || !box?.height) {
    return { x: 0, y: 0 };
  }
  const scale = Math.max(box.width / natural.width, box.height / natural.height);
  return {
    x: Math.max(0, natural.width * scale - box.width),
    y: Math.max(0, natural.height * scale - box.height),
  };
}

/**
 * The focal point after dragging the picture by (dx, dy) pixels.
 *
 * Dragging the picture down should reveal what is above it, so a positive dy
 * moves the point *up* the picture — the gesture moves the photo, not the
 * window onto it, which is what a hand on a photograph expects.
 */
export function focusAfterDrag(focus, drag, overflow) {
  const from = focus || CENTRE;
  return {
    x: overflow.x ? clamp01(from.x - drag.dx / overflow.x) : from.x,
    y: overflow.y ? clamp01(from.y - drag.dy / overflow.y) : from.y,
  };
}

/** `object-position` for a focal point. Absent means the middle. */
export function objectPosition(focus) {
  const { x, y } = focus || CENTRE;
  return `${clamp01(x) * 100}% ${clamp01(y) * 100}%`;
}

/** Whether there is anything hidden to drag towards. */
export function canReframe(overflow) {
  return overflow.x > 1 || overflow.y > 1;
}

/** A focal point read off an event payload, or null for the middle. */
export function focusOf(event) {
  const focal = event?.payload?.focal;
  if (typeof focal?.x !== 'number' || typeof focal?.y !== 'number') return null;
  return { x: clamp01(focal.x), y: clamp01(focal.y) };
}
