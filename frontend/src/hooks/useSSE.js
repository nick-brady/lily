import { useEffect, useRef, useState } from 'react';

/**
 * Subscribe to a server-sent-events stream. Reconnects automatically; the
 * browser's `EventSource` handles the Last-Event-ID resume header on its
 * own, so we just track the highest sequence_id we've seen for debugging.
 *
 * `onEvent` is called with `(kind, data, sequenceId)` for every event.
 */
export function useSSE(url, onEvent) {
  const [isConnected, setIsConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  const lastSequenceIdRef = useRef(null);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!url) return undefined;
    const source = new EventSource(url);

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

    source.addEventListener('open', () => setIsConnected(true));
    source.addEventListener('appended', handle('appended'));
    source.addEventListener('updated', handle('updated'));
    source.addEventListener('deleted', handle('deleted'));
    source.addEventListener('reaction_added', handle('reaction_added'));
    source.addEventListener('reaction_removed', handle('reaction_removed'));
    source.addEventListener('comment_added', handle('comment_added'));
    source.addEventListener('comment_updated', handle('comment_updated'));
    source.addEventListener('comment_deleted', handle('comment_deleted'));
    source.onerror = () => {
      setIsConnected(false);
    };

    return () => {
      source.close();
      setIsConnected(false);
    };
  }, [url]);

  return { isConnected, lastSequenceId: lastSequenceIdRef.current };
}
