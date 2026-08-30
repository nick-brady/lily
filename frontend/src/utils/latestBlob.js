/**
 * Holds the object URL that is currently on screen, and decides what happens
 * to one that arrives late.
 *
 * The editor previews a draft on every keystroke, debounced. Each preview is
 * a fetch that comes back as a blob, and a blob URL has to be revoked or it
 * leaks. The trap is that two previews can be in flight and finish out of
 * order: aborting the older fetch doesn't help once its response has already
 * been read, so a slow render could come back last, revoke the URL the newer
 * one had just put on screen, and leave a broken-image icon behind.
 *
 * The rule, in one place: only the newest request may replace what's shown,
 * and a superseded one throws its own blob away without touching anything.
 *
 *     const slot = createLatestBlob();
 *     const token = slot.start();
 *     const url = await fetchPreview();
 *     if (slot.settle(token, url) === null) return;   // superseded
 */
export function createLatestBlob({ revoke } = {}) {
  const drop = revoke || ((url) => URL.revokeObjectURL(url));
  let shown = null;
  let newest = null;

  return {
    /** Claim to be the newest request. Keep the token; hand it back to settle. */
    start() {
      newest = {};
      return newest;
    },

    /** Whether `token` is still the newest request. */
    isCurrent(token) {
      return token === newest && token !== null;
    },

    /**
     * Finish a request. Adopts `url` and revokes whatever it replaces when
     * `token` is still the newest; otherwise revokes `url` itself and keeps
     * the screen as it is. Returns the URL now shown, or null if superseded.
     */
    settle(token, url) {
      if (token !== newest) {
        drop(url);
        return null;
      }
      if (shown && shown !== url) drop(shown);
      shown = url;
      return url;
    },

    /** Let go of what's on screen — a page switch, or unmounting. */
    clear() {
      if (shown) drop(shown);
      shown = null;
      newest = null;
    },

    /** What's on screen, or null. */
    current() {
      return shown;
    },
  };
}
