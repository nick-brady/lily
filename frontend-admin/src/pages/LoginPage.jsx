import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../auth';
import GoogleSignInButton from '../components/GoogleSignInButton';

// Google or a 6-digit code. Not the magic LINK: it points at the main site
// (FRONTEND_URL is the apex domain), so on the admin domain the typed code
// is the email path.
export default function LoginPage() {
  const { acceptToken } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState('identifier');
  const [identifier, setIdentifier] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submitIdentifier = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.requestChallenge(identifier);
      setStep('code');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const submitCode = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      signedIn(await api.verifyChallenge({ identifier, code }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const signedIn = (result) => {
    acceptToken(result.access_token);
    navigate('/', { replace: true });
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="card w-full max-w-sm">
        <h1 className="text-xl font-bold text-gray-900 mb-1">Arrival Story Admin</h1>
        {step === 'identifier' ? (
          <form onSubmit={submitIdentifier} className="space-y-4 mt-4">
            <GoogleSignInButton onSuccess={signedIn} onError={(err) => setError(err.message)} />
            <p className="text-sm text-gray-500">
              Or sign in with your admin email. We&apos;ll send a 6-digit code.
            </p>
            <input
              type="email"
              required
              autoFocus
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="you@example.com"
              aria-label="Email address"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <button
              type="submit"
              disabled={busy || !identifier}
              className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white font-semibold py-2 rounded-lg"
            >
              {busy ? 'Sending…' : 'Send code'}
            </button>
          </form>
        ) : (
          <form onSubmit={submitCode} className="space-y-4 mt-4">
            <p className="text-sm text-gray-500">
              Enter the 6-digit code sent to <span className="font-medium">{identifier}</span>.
              (Type the code — the sign-in link in the email opens the main site, not this one.)
            </p>
            <input
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              required
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              placeholder="123456"
              aria-label="6-digit code"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-center text-2xl tracking-[0.5em] tabular focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <button
              type="submit"
              disabled={busy || code.length !== 6}
              className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white font-semibold py-2 rounded-lg"
            >
              {busy ? 'Verifying…' : 'Sign in'}
            </button>
            <button
              type="button"
              onClick={() => { setStep('identifier'); setCode(''); }}
              className="w-full text-sm text-gray-500 hover:text-gray-700"
            >
              Use a different email
            </button>
          </form>
        )}
        {error && <p role="alert" className="mt-4 text-sm text-red-600">{error}</p>}
      </div>
    </div>
  );
}
