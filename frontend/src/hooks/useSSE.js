import { useEffect, useRef, useState } from 'react';

/**
 * Subscribe to a server-sent-events stream. Reconnects automatically; the
 * browser's `EventSource` handles the Last-Event-ID resume header on its
 * own, so we just track the highest sequence_id we've seen for debugging.
 *
 * `onEvent` is called with `(kind, data, sequenceId)` for every event.
 *
 * `status` distinguishes four states, because a boolean can't:
 *   idle          no url — we never subscribed (anonymous preview)
 *   connecting    opening, or retrying before we've ever been live
 *   live          open
 *   reconnecting  dropped after having been live — the only alarming one
 * Callers render nothing for `idle`: "not subscribed" is not an outage.
 */
export function useSSE(url, onEvent) {
  const [status, setStatus] = useState('idle');
  const onEventRef = useRef(onEvent);
  const lastSequenceIdRef = useRef(null);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!url) {
      setStatus('idle');
      return undefined;
    }
    const source = new EventSource(url);
    let everOpened = false;
    setStatus('connecting');

    const handle = (kind) => (evt) => {
      if (evt.lastEventId) lastSequenceIdRef.current = Number(evt.lastEventId);
      let data = null;
      try {
        data = evt.data ? JSON.parse(evt.data) : null;
      } catch {
        data = evt.data;
      }
      onEventRef.current?.(kind, data, evt.lastEventId ? Number(evt.lastEventId) : null);
    };

    source.addEventListener('open', () => {
      everOpened = true;
      setStatus('live');
    });
    // birth_update carries no id: line (negative sequence id server-side),
    // so evt.lastEventId is empty — the guard in handle() tolerates that.
    // This listener is what makes labor-start and "baby born" appear live
    // for viewers; without it the pages' birth_update branches never fire.
    source.addEventListener('birth_update', handle('birth_update'));
    source.addEventListener('appended', handle('appended'));
    source.addEventListener('updated', handle('updated'));
    source.addEventListener('deleted', handle('deleted'));
    source.addEventListener('reaction_added', handle('reaction_added'));
    source.addEventListener('reaction_removed', handle('reaction_removed'));
    source.addEventListener('comment_added', handle('comment_added'));
    source.addEventListener('comment_updated', handle('comment_updated'));
    source.addEventListener('comment_deleted', handle('comment_deleted'));
    source.onerror = () => {
      // EventSource retries on its own. Before the first successful open this
      // is still the opening handshake, not a dropped stream — saying
      // "Reconnecting" then would be crying wolf on every first paint.
      setStatus(everOpened ? 'reconnecting' : 'connecting');
    };

    return () => {
      source.close();
      setStatus('idle');
    };
  }, [url]);

  return { status, lastSequenceId: lastSequenceIdRef.current };
}
