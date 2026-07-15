import { createContext, useContext, useState } from 'react';
import { getToken, setToken } from './api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(getToken());

  const acceptToken = (accessToken) => {
    setToken(accessToken);
    setTokenState(accessToken);
  };

  const logout = () => {
    setToken(null);
    setTokenState(null);
  };

  return (
    <AuthContext.Provider value={{ token, isAuthenticated: !!token, acceptToken, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
