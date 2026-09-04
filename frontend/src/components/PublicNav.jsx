import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

// The header on the public pages (pricing, privacy, terms). The wordmark goes
// home; the right-hand link knows whether you're signed in. Until /me has
// answered it says "Log in" — that is also what the pre-rendered HTML says,
// so hydration matches — and then flips to your account if you have one.
export default function PublicNav() {
  const { isAuthenticated, loading } = useAuth();
  const signedIn = !loading && isAuthenticated;
  return (
    <nav className="flex items-center justify-between px-6 py-5 max-w-3xl mx-auto">
      <Link
        to="/"
        className="text-3xl text-primary-600 dark:text-primary-400"
        style={{ fontFamily: "'Great Vibes', cursive" }}
      >
        Arrival Story
      </Link>
      <Link
        to={signedIn ? '/account' : '/login'}
        className="text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors underline-offset-4 hover:underline"
      >
        {signedIn ? 'Your account →' : 'Log in'}
      </Link>
    </nav>
  );
}
