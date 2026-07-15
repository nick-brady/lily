import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from '../api/client';
import { captureAttribution, getAttribution } from '../utils/attribution';

// Fires one /track ping per SPA route change (self-hosted analytics — no
// cookies, no third parties). document.referrer only means anything for the
// first hit of a session; after that it's just our own previous page.
export function usePageTracking() {
  const location = useLocation();
  const lastPath = useRef(null);

  useEffect(() => {
    captureAttribution();
  }, []);

  useEffect(() => {
    if (location.pathname === lastPath.current) return;
    const firstHit = lastPath.current === null;
    lastPath.current = location.pathname;
    api
      .track({
        path: location.pathname,
        referrer: firstHit && document.referrer ? document.referrer : undefined,
        ...getAttribution(),
      })
      .catch(() => {});
  }, [location.pathname]);
}

// Rendered inside <BrowserRouter> (useLocation needs router context);
// contributes nothing to the DOM.
export function PageTracking() {
  usePageTracking();
  return null;
}
