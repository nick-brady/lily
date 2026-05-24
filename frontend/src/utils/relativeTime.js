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
