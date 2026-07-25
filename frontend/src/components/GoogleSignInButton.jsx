import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

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

// "Continue with Google" — a convenience layer over the same email-keyed
// identity, not a separate account type. Renders nothing when no client id
// is configured, and the email-code form must always remain the visually
// primary path: in-app browsers (Facebook/Instagram webviews, where family
// invite links often open) block Google OAuth entirely.
export default function GoogleSignInButton({ inviteToken, onSuccess, onError }) {
  const slotRef = useRef(null);
  const [failed, setFailed] = useState(false);
  const callbacksRef = useRef({ onSuccess, onError });
  callbacksRef.current = { onSuccess, onError };
  const inviteTokenRef = useRef(inviteToken);
  inviteTokenRef.current = inviteToken;

  useEffect(() => {
    if (!CLIENT_ID) return;
    let cancelled = false;
    (async () => {
      try {
        await loadGsi();
        if (cancelled || !slotRef.current) return;
        window.google.accounts.id.initialize({
          client_id: CLIENT_ID,
          callback: async ({ credential }) => {
            try {
              await api.googleAuth({
                credential,
                inviteToken: inviteTokenRef.current,
              });
              callbacksRef.current.onSuccess?.();
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
        <div className="flex-1 h-px bg-gray-200 dark:bg-gray-600" />
        <span className="text-xs text-gray-400 dark:text-gray-500">or</span>
        <div className="flex-1 h-px bg-gray-200 dark:bg-gray-600" />
      </div>
    </div>
  );
}
