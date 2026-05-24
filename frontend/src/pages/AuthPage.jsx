import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../api/client';

const DEFAULT_BIRTH_SLUG = import.meta.env.VITE_DEFAULT_BIRTH_SLUG || 'lily-wren';

export default function AuthPage() {
  const { acceptToken } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState('identifier'); // 'identifier' | 'code'
  const [identifier, setIdentifier] = useState('');
  const [code, setCode] = useState('');
  const [identifierKind, setIdentifierKind] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submitIdentifier = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = await api.requestChallenge(identifier);
      setIdentifierKind(result.identifier_kind);
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
      const result = await api.verifyChallenge({ identifier, code });
      await acceptToken(result.access_token);
      navigate(`/b/${DEFAULT_BIRTH_SLUG}/manage`, { replace: true });
    } catch (err) {
      setError(err.message || 'Invalid code');
    } finally {
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
          Lily
        </h1>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        {step === 'identifier' && (
          <form onSubmit={submitIdentifier} className="space-y-4">
            <label className="block">
              <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Email or phone
              </span>
              <input
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                autoComplete="email"
                autoCapitalize="none"
                autoCorrect="off"
                placeholder="you@example.com or 555-555-5555"
                className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600
                           bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                           focus:ring-2 focus:ring-primary-500 focus:border-transparent
                           focus:outline-none transition-colors"
                required
              />
            </label>
            <button
              type="submit"
              disabled={loading || !identifier.trim()}
              className="w-full py-3 rounded-lg bg-primary-600 hover:bg-primary-700
                         text-white font-medium transition-colors
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Sending…' : 'Send code'}
            </button>
            <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
              We'll send you a 6-digit code and a magic link.
            </p>
          </form>
        )}

        {step === 'code' && (
          <form onSubmit={submitCode} className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              We sent a code to{' '}
              <span className="font-medium text-gray-900 dark:text-white">{identifier}</span>
              {identifierKind === 'email' && '. Check your email — or paste the 6-digit code below.'}
              {identifierKind === 'phone' && '. Check your texts — enter the 6-digit code below.'}
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
                setStep('identifier');
                setCode('');
                setError('');
              }}
              className="w-full text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400"
            >
              Use a different address
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
