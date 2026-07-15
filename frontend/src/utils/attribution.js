// First-touch acquisition attribution. When a visitor lands with ?ref= or
// utm_* params we stash them once and never overwrite — a returning visitor
// who comes back through a different campaign stays credited to whatever
// brought them here first. Sent along with /track pings and attached to
// signup, where the backend also only records it for brand-new users.
const ATTRIBUTION_KEY = 'lily_attribution';
const PARAMS = ['ref', 'utm_source', 'utm_medium', 'utm_campaign'];

export function captureAttribution() {
  try {
    if (localStorage.getItem(ATTRIBUTION_KEY)) return;
    const search = new URLSearchParams(window.location.search);
    const captured = {};
    for (const param of PARAMS) {
      const value = search.get(param);
      if (value) captured[param] = value.slice(0, 128);
    }
    if (Object.keys(captured).length === 0) return;
    captured.captured_at = new Date().toISOString();
    localStorage.setItem(ATTRIBUTION_KEY, JSON.stringify(captured));
  } catch {
    // storage unavailable (private mode etc.) — attribution is best-effort
  }
}

export function getAttribution() {
  try {
    const raw = localStorage.getItem(ATTRIBUTION_KEY);
    if (!raw) return {};
    const { ref, utm_source, utm_medium, utm_campaign } = JSON.parse(raw);
    return { ref, utm_source, utm_medium, utm_campaign };
  } catch {
    return {};
  }
}
