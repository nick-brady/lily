import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { PageMeta } from './hooks/usePageMeta';
import { PageTracking } from './hooks/usePageTracking';
import AccountPage from './pages/AccountPage';
import AuthPage from './pages/AuthPage';
import BirthSettingsPage from './pages/BirthSettingsPage';
import InviteRedeemPage from './pages/InviteRedeemPage';
import LandingPage from './pages/LandingPage';
import PricingPage from './pages/PricingPage';
import PrivacyPage from './pages/PrivacyPage';
import PublicBirthPage from './pages/PublicBirthPage';
import SetupPage from './pages/SetupPage';
import TermsPage from './pages/TermsPage';

function ManageRedirect() {
  const { slug } = useParams();
  return <Navigate to={`/b/${slug}`} replace />;
}

// The route table, without a router around it. The browser wraps it in
// BrowserRouter (below); the build-time pre-render of the public pages wraps
// it in StaticRouter (entry-server.jsx). Anything that needs router context
// but nothing else — the page titles — lives here so both get it.
export function AppRoutes() {
  return (
    <>
      <PageMeta />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/setup" element={<SetupPage />} />
        <Route path="/login" element={<AuthPage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/invite/:token" element={<InviteRedeemPage />} />
        <Route path="/b/:slug" element={<PublicBirthPage />} />
        {/* The manage page merged into the birth page (parent tooling
            renders by role); keep old bookmarks working. */}
        <Route path="/b/:slug/manage" element={<ManageRedirect />} />
        <Route path="/b/:slug/settings" element={<BirthSettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <PageTracking />
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
