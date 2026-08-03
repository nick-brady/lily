import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../api/client';
import GoogleSignInButton from '../components/GoogleSignInButton';
import PhoneOptIn from '../components/PhoneOptIn';

// Identity is email — one auth path (email code or Continue-with-Google,
// both resolving to the same email-keyed user). Phones are collected on the
// next screen as an explicit birth-alerts opt-in, never as a login.
export default function AuthPage() {
  const { completeSignIn } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const nextPath = searchParams.get('next');
  const [step, setStep] = useState('email'); // 'email' | 'code' | 'notify'
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // After sign-in we land in this order:
  // 1. `?next=` if the user was redirected here from a guarded action
  //    (e.g. opening a birth page while anonymous).
  // 2. The account page if they have any births.
  // 3. Setup for brand-new users.
  //
  // This is why /account no longer redirects the empty case to /setup — the
  // wizard is already the sign-in destination for anyone without a page, so
  // that redirect only ever caught people who had just left or deleted their
  // last one. One edge survives on purpose: a viewer who stopped following
  // everything and then signs back in has no births either, so they land in
  // the wizard. Optimising for the new parent is the right call on the main
  // path, and that's an edge of an edge.
  const finish = (loadedProfile) => {
    if (nextPath) {
      navigate(nextPath, { replace: true });
      return;
    }
    const hasBirth = loadedProfile?.families?.some((f) => f.births?.length > 0);
    navigate(hasBirth ? '/account' : '/setup', { replace: true });
  };

  // Sign-in succeeded (code or Google) → offer the birth-alerts opt-in
  // once, at peak intent, unless they've already opted in before.
  const handleSignedIn = async () => {
    const loaded = await completeSignIn();
    if (loaded?.user?.notify_phone) {
      finish(loaded);
      return;
    }
    setProfile(loaded);
    setStep('notify');
  };

  const submitEmail = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.requestChallenge(email.trim().toLowerCase());
      setStep('code');
    } catch (err) {
      setError(err.message || 'Could not send code');
    } finally {
      setLoading(false);
    }
  };

  const submitCode = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.verifyChallenge({ identifier: email.trim().toLowerCase(), code });
      await handleSignedIn();
    } catch (err) {
      setError(err.message || 'Invalid code');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 px-4">
      <div className="w-full max-w-sm bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6">
        <h1
          className="text-3xl text-center text-primary-600 dark:text-primary-400 mb-6"
          style={{ fontFamily: "'Great Vibes', cursive" }}
        >
          Arrival Story
        </h1>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        {step === 'email' && (
          <div className="space-y-4">
            <GoogleSignInButton
              onSuccess={handleSignedIn}
              onError={(err) => setError(err.message || 'Google sign-in failed')}
            />
            <form onSubmit={submitEmail} className="space-y-4">
              <label className="block">
                <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Email
                </span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  autoCapitalize="none"
                  autoCorrect="off"
                  placeholder="you@example.com"
                  className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600
                             bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                             focus:ring-2 focus:ring-primary-500 focus:border-transparent
                             focus:outline-none transition-colors"
                  required
                />
              </label>
              <button
                type="submit"
                disabled={loading || !email.trim()}
                className="w-full py-3 rounded-lg bg-primary-600 hover:bg-primary-700
                           text-white font-medium transition-colors
                           disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Sending…' : 'Send code'}
              </button>
              <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
                We'll email you a 6-digit code — no password needed. By continuing, you agree to
                our <Link to="/terms" className="underline hover:text-primary-600 dark:hover:text-primary-400">Terms</Link> and{' '}
                <Link to="/privacy" className="underline hover:text-primary-600 dark:hover:text-primary-400">Privacy Policy</Link>.
              </p>
            </form>
          </div>
        )}

        {step === 'code' && (
          <form onSubmit={submitCode} className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              We sent a code to{' '}
              <span className="font-medium text-gray-900 dark:text-white">{email.trim()}</span>.
              Check your email — enter the 6-digit code below.
            </p>

            <label className="block">
              <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                6-digit code
              </span>
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="000000"
                className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600
                           bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                           text-center text-2xl font-mono tracking-widest
                           focus:ring-2 focus:ring-primary-500 focus:border-transparent
                           focus:outline-none transition-colors"
                required
              />
            </label>

            <button
              type="submit"
              disabled={loading || code.length !== 6}
              className="w-full py-3 rounded-lg bg-primary-600 hover:bg-primary-700
                         text-white font-medium transition-colors
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Verifying…' : 'Sign in'}
            </button>
            <button
              type="button"
              onClick={() => {
                setStep('email');
                setCode('');
                setError('');
              }}
              className="w-full text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400"
            >
              Use a different email
            </button>
          </form>
        )}

        {step === 'notify' && <PhoneOptIn onDone={() => finish(profile)} />}
      </div>
    </div>
  );
}
