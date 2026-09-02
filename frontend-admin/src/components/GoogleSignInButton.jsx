import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

// A copy of the main site's button, not an import — the two Vite roots stay
// decoupled. Same Google Identity Services flow, same backend route; the
// admin allowlist is applied afterwards by every /admin/* endpoint, so
// signing in with Google proves the email, nothing more.
const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
const GSI_SRC = 'https://accounts.google.com/gsi/client';

let gsiLoader = null;
function loadGsi() {
  if (!gsiLoader) {
    gsiLoader = new Promise((resolve, reject) => {
      if (window.google?.accounts?.id) return resolve();
      const script = document.createElement('script');
      script.src = GSI_SRC;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Google sign-in failed to load'));
      document.head.appendChild(script);
    });
  }
  return gsiLoader;
}

// Renders nothing when no client id is configured, so the code form stays
// the one path that always works.
export default function GoogleSignInButton({ onSuccess, onError }) {
  const slotRef = useRef(null);
  const [failed, setFailed] = useState(false);
  const callbacksRef = useRef({ onSuccess, onError });
  callbacksRef.current = { onSuccess, onError };

  useEffect(() => {
    if (!CLIENT_ID) return undefined;
    let cancelled = false;
    (async () => {
      try {
        await loadGsi();
        if (cancelled || !slotRef.current) return;
        window.google.accounts.id.initialize({
          client_id: CLIENT_ID,
          callback: async ({ credential }) => {
            try {
              const result = await api.googleAuth({ credential });
              callbacksRef.current.onSuccess?.(result);
            } catch (err) {
              callbacksRef.current.onError?.(err);
            }
          },
        });
        window.google.accounts.id.renderButton(slotRef.current, {
          theme: 'outline',
          size: 'large',
          width: 320,
          text: 'continue_with',
        });
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!CLIENT_ID || failed) return null;

  return (
    <div className="space-y-3">
      <div ref={slotRef} className="flex justify-center" />
      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-gray-200" />
        <span className="text-xs text-gray-400">or</span>
        <div className="flex-1 h-px bg-gray-200" />
      </div>
    </div>
  );
}
