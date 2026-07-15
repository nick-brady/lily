import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { PageTracking } from './hooks/usePageTracking';
import AccountPage from './pages/AccountPage';
import AuthPage from './pages/AuthPage';
import AuthVerifyPage from './pages/AuthVerifyPage';
import BirthManagePage from './pages/BirthManagePage';
import BirthSettingsPage from './pages/BirthSettingsPage';
import InviteRedeemPage from './pages/InviteRedeemPage';
import LandingPage from './pages/LandingPage';
import PrivacyPage from './pages/PrivacyPage';
import PublicBirthPage from './pages/PublicBirthPage';
import SetupPage from './pages/SetupPage';
import TermsPage from './pages/TermsPage';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <PageTracking />
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/account" element={<AccountPage />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/login" element={<AuthPage />} />
          <Route path="/auth/verify" element={<AuthVerifyPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/invite/:token" element={<InviteRedeemPage />} />
          <Route path="/b/:slug" element={<PublicBirthPage />} />
          <Route path="/b/:slug/manage" element={<BirthManagePage />} />
          <Route path="/b/:slug/settings" element={<BirthSettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
