// Categorical series palette (light mode), fixed slot order — the ordering
// is the colorblind-safety mechanism (validated adjacent-pair CVD ΔE ≥ 8),
// so slots are assigned in this order and never cycled or re-sorted.
export const SERIES_COLORS = [
  '#2a78d6', // blue
  '#008300', // green
  '#e87ba4', // magenta
  '#eda100', // yellow
  '#1baf7a', // aqua
  '#eb6834', // orange
  '#4a3aa7', // violet
  '#e34948', // red
];

// Chart chrome
export const GRID_COLOR = '#e1e0d9';
export const AXIS_TICK_COLOR = '#898781';
export const LEGEND_INK = '#52514e';

// Color follows the entity, never its rank: once a source gets a slot it
// keeps it for the whole session, even when a date-range change reshuffles
// which sources appear or how big they are.
const assigned = new Map();

export function colorForSource(source) {
  if (!assigned.has(source)) {
    assigned.set(source, SERIES_COLORS[assigned.size % SERIES_COLORS.length]);
  }
  return assigned.get(source);
}
