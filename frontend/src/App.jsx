import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import AuthPage from './pages/AuthPage';
import AuthVerifyPage from './pages/AuthVerifyPage';
import BirthManagePage from './pages/BirthManagePage';
import InviteRedeemPage from './pages/InviteRedeemPage';
import LandingPage from './pages/LandingPage';
import PublicBirthPage from './pages/PublicBirthPage';
import SetupPage from './pages/SetupPage';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/setup" element={<SetupPage />} />
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
