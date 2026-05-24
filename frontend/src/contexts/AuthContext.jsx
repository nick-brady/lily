import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, getToken, setToken } from '../api/client';

const AuthContext = createContext(null);

function decodeJwtExp(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return typeof payload.exp === 'number' ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => getToken());
  const [user, setUser] = useState(null);
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    setToken(null);
    setTokenState(null);
    setUser(null);
    setMe(null);
  }, []);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    const exp = decodeJwtExp(token);
    if (!exp || exp < Date.now()) {
      logout();
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const profile = await api.me();
        if (cancelled) return;
        setUser(profile.user);
        setMe(profile);
      } catch (err) {
        if (err.status === 401) logout();
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, logout]);

  const acceptToken = useCallback(async (accessToken) => {
    setToken(accessToken);
    setTokenState(accessToken);
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

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        me,
        loading,
        isAuthenticated: Boolean(user),
        acceptToken,
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
