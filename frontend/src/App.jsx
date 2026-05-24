import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import AuthPage from './pages/AuthPage';
import AuthVerifyPage from './pages/AuthVerifyPage';
import BirthManagePage from './pages/BirthManagePage';
import InviteRedeemPage from './pages/InviteRedeemPage';
import PublicBirthPage from './pages/PublicBirthPage';

const DEFAULT_BIRTH_SLUG = import.meta.env.VITE_DEFAULT_BIRTH_SLUG || 'lily-wren';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to={`/b/${DEFAULT_BIRTH_SLUG}`} replace />} />
          <Route path="/login" element={<AuthPage />} />
          <Route path="/auth/verify" element={<AuthVerifyPage />} />
          <Route path="/invite/:token" element={<InviteRedeemPage />} />
          <Route path="/b/:slug" element={<PublicBirthPage />} />
          <Route path="/b/:slug/manage" element={<BirthManagePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
