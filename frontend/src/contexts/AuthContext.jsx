import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api } from '../api/client';

const AuthContext = createContext(null);

// The session is an httpOnly cookie — invisible to JS by design, so "am I
// signed in?" is answered by asking the backend, not by inspecting storage.
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const profile = await api.me();
        if (cancelled) return;
        setUser(profile.user);
        setMe(profile);
      } catch {
        // 401 → anonymous visitor; anything else → treat the same and let
        // the next explicit sign-in sort it out.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Called after /auth/verify or /auth/google succeeds — the server has
  // already set the session cookie; we just load the profile it unlocked.
  const completeSignIn = useCallback(async () => {
    const profile = await api.me();
    setUser(profile.user);
    setMe(profile);
    return profile;
  }, []);

  const refreshMe = useCallback(async () => {
    const profile = await api.me();
    setUser(profile.user);
    setMe(profile);
    return profile;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Clearing local state matters more than the server ack.
    }
    setUser(null);
    setMe(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        me,
        loading,
        isAuthenticated: Boolean(user),
        completeSignIn,
        refreshMe,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
