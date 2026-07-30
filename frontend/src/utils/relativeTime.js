/**
 * Format a timestamp as a relative-time string. Tone is gentle and
 * unobtrusive — comments on a baby's birth page live forever, so the
 * "X minutes ago" should never feel like a timer.
 */
export function relativeTime(iso) {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diff = Math.max(0, now - then);

  const seconds = Math.floor(diff / 1000);
  if (seconds < 45) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Value for an <input type="datetime-local"> — the viewer's local time at
 * minute precision. Defaults to now.
 */
export function toLocalInputValue(timestamp = new Date()) {
  const d = new Date(timestamp);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
