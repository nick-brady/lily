import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../api/client';

function toSlug(name) {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/[\s]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

export default function SetupPage() {
  const { isAuthenticated, loading, me, acceptToken } = useAuth();
  const navigate = useNavigate();

  const [step, setStep] = useState('name'); // 'name' | 'auth'
  const [babyName, setBabyName] = useState('');
  const [slug, setSlug] = useState('');
  const [slugStatus, setSlugStatus] = useState(null); // null | 'checking' | 'available' | 'taken'
  const [slugSuggestion, setSlugSuggestion] = useState('');
  const slugCheckTimeout = useRef(null);

  // Auth step state
  const [authStep, setAuthStep] = useState('identifier'); // 'identifier' | 'code'
  const [identifier, setIdentifier] = useState('');
  const [identifierKind, setIdentifierKind] = useState(null);
  const [code, setCode] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [error, setError] = useState('');

  // If already logged in with a birth, redirect away
  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated) return;
    const firstFamily = me?.families?.[0];
    const firstBirth = firstFamily?.births?.[0];
    if (firstBirth) {
      const isParent = firstFamily.role === 'owner' || firstFamily.role === 'co_parent';
      navigate(isParent ? `/b/${firstBirth.slug}/manage` : `/b/${firstBirth.slug}`, { replace: true });
    }
  }, [isAuthenticated, loading, me, navigate]);

  // Debounced slug availability check
  useEffect(() => {
    const generated = toSlug(babyName);
    setSlug(generated);
    setSlugSuggestion('');
    if (!generated) {
      setSlugStatus(null);
      return;
    }
    setSlugStatus('checking');
    if (slugCheckTimeout.current) clearTimeout(slugCheckTimeout.current);
    slugCheckTimeout.current = setTimeout(async () => {
      try {
        const result = await api.checkSlugAvailable(generated);
        setSlugStatus(result.available ? 'available' : 'taken');
        if (!result.available && result.suggestion) {
          setSlugSuggestion(result.suggestion);
        }
      } catch {
        setSlugStatus(null);
      }
    }, 400);
    return () => {
      if (slugCheckTimeout.current) clearTimeout(slugCheckTimeout.current);
    };
  }, [babyName]);

  const adoptSuggestion = () => {
    setBabyName(slugSuggestion.replace(/-/g, ' '));
  };

  const goToAuth = async (e) => {
    e.preventDefault();
    if (slugStatus !== 'available') return;
    // If already authenticated, skip auth and create directly
    if (isAuthenticated) {
      setAuthLoading(true);
      setError('');
      try {
        const birth = await api.createBirth({ babyName, slug });
        navigate(`/b/${birth.slug}/manage`, { replace: true });
      } catch (err) {
        setError(err.message || 'Something went wrong');
        setAuthLoading(false);
      }
      return;
    }
    setStep('auth');
    setError('');
  };

  const submitIdentifier = async (e) => {
    e.preventDefault();
    setError('');
    setAuthLoading(true);
    try {
      const result = await api.requestChallenge(identifier);
      setIdentifierKind(result.identifier_kind);
      setAuthStep('code');
    } catch (err) {
      setError(err.message || 'Could not send code');
    } finally {
      setAuthLoading(false);
    }
  };

  const submitCode = async (e) => {
    e.preventDefault();
    setError('');
    setAuthLoading(true);
    try {
      const authResult = await api.verifyChallenge({ identifier, code });
      await acceptToken(authResult.access_token);
      const birth = await api.createBirth({ babyName, slug });
      navigate(`/b/${birth.slug}/manage`, { replace: true });
    } catch (err) {
      setError(err.message || 'Something went wrong');
    } finally {
      setAuthLoading(false);
    }
  };

  if (loading) return null;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-primary-50 to-white dark:from-gray-900 dark:to-gray-950 px-4 py-12">
      {/* Logo */}
      <div
        className="text-4xl text-primary-600 dark:text-primary-400 mb-8"
        style={{ fontFamily: "'Great Vibes', cursive" }}
      >
        lily
      </div>

      {/* Progress dots */}
      <div className="flex items-center gap-2 mb-8">
        <div className={`h-2 w-2 rounded-full transition-colors ${step === 'name' ? 'bg-primary-500' : 'bg-primary-200 dark:bg-primary-700'}`} />
        <div className={`h-2 w-2 rounded-full transition-colors ${step === 'auth' ? 'bg-primary-500' : 'bg-primary-200 dark:bg-primary-700'}`} />
      </div>

      <div className="w-full max-w-sm">
        {/* Step 1: Baby's name */}
        {step === 'name' && (
          <form onSubmit={goToAuth} className="space-y-6">
            <div className="text-center mb-2">
              <h1 className="text-xl font-semibold text-gray-800 dark:text-white mb-1">
                What's your baby's name?
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                You can always change this later.
              </p>
            </div>

            <div>
              <input
                type="text"
                value={babyName}
                onChange={(e) => setBabyName(e.target.value)}
                placeholder="Lily Rose"
                autoFocus
                autoComplete="off"
                className="w-full px-4 py-4 text-xl rounded-xl border border-gray-300 dark:border-gray-600
                           bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-center
                           focus:ring-2 focus:ring-primary-500 focus:border-transparent
                           focus:outline-none transition-colors placeholder-gray-300 dark:placeholder-gray-600"
              />
            </div>

            {/* Slug preview */}
            {slug && (
              <div className="space-y-3">
                <div className="flex items-center justify-between px-1">
                  <span className="text-xs text-gray-400 font-mono">/b/{slug}</span>
                  {slugStatus === 'checking' && (
                    <span className="text-xs text-gray-400">Checking…</span>
                  )}
                  {slugStatus === 'available' && (
                    <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">Available</span>
                  )}
                  {slugStatus === 'taken' && (
                    <span className="text-xs text-red-500 dark:text-red-400 font-medium">Taken</span>
                  )}
                </div>

                {slugStatus === 'taken' && slugSuggestion && (
                  <button
                    type="button"
                    onClick={adoptSuggestion}
                    className="w-full text-xs text-primary-600 dark:text-primary-400 hover:underline text-left px-1"
                  >
                    Use /b/{slugSuggestion} instead →
                  </button>
                )}

                {/* Mini page preview */}
                <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-md border border-primary-100 dark:border-primary-900/40 p-4 text-center">
                  <p
                    className="text-2xl text-primary-600 dark:text-primary-400"
                    style={{ fontFamily: "'Great Vibes', cursive" }}
                  >
                    Welcoming{' '}
                    {babyName
                      .split(' ')
                      .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
                      .join(' ')}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">Your page will look something like this</p>
                </div>
              </div>
            )}

            {error && (
              <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={!slug || slugStatus !== 'available' || authLoading}
              className="w-full py-3 rounded-xl bg-primary-600 hover:bg-primary-700
                         text-white font-medium transition-colors
                         disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {authLoading ? 'Creating…' : isAuthenticated ? 'Create my page' : 'Next →'}
            </button>
          </form>
        )}

        {/* Step 2: Auth */}
        {step === 'auth' && (
          <div className="space-y-6">
            <div className="text-center">
              <h1 className="text-xl font-semibold text-gray-800 dark:text-white mb-1">
                Let's get you set up
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Sign in to create{' '}
                <span
                  className="text-primary-600 dark:text-primary-400"
                  style={{ fontFamily: "'Great Vibes', cursive", fontSize: '1.1em' }}
                >
                  {babyName
                    .split(' ')
                    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
                    .join(' ')}
                </span>
                's page.
              </p>
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
                {error}
              </div>
            )}

            {authStep === 'identifier' && (
              <form onSubmit={submitIdentifier} className="space-y-4">
                <label className="block">
                  <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Email or phone
                  </span>
                  <input
                    type="text"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    autoFocus
                    autoComplete="email"
                    autoCapitalize="none"
                    autoCorrect="off"
                    placeholder="you@example.com or 555-555-5555"
                    className="w-full px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600
                               bg-white dark:bg-gray-800 text-gray-900 dark:text-white
                               focus:ring-2 focus:ring-primary-500 focus:border-transparent
                               focus:outline-none transition-colors"
                    required
                  />
                </label>
                <button
                  type="submit"
                  disabled={authLoading || !identifier.trim()}
                  className="w-full py-3 rounded-xl bg-primary-600 hover:bg-primary-700
                             text-white font-medium transition-colors
                             disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {authLoading ? 'Sending…' : 'Send code'}
                </button>
                <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
                  We'll send you a 6-digit code and a magic link.
                </p>
                <button
                  type="button"
                  onClick={() => { setStep('name'); setError(''); }}
                  className="w-full text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400"
                >
                  ← Back
                </button>
              </form>
            )}

            {authStep === 'code' && (
              <form onSubmit={submitCode} className="space-y-4">
                <p className="text-sm text-gray-600 dark:text-gray-300">
                  We sent a code to{' '}
                  <span className="font-medium text-gray-900 dark:text-white">{identifier}</span>
                  {identifierKind === 'email' && '. Check your email.'}
                  {identifierKind === 'phone' && '. Check your texts.'}
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
                    autoFocus
                    placeholder="000000"
                    className="w-full px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600
                               bg-white dark:bg-gray-800 text-gray-900 dark:text-white
                               text-center text-2xl font-mono tracking-widest
                               focus:ring-2 focus:ring-primary-500 focus:border-transparent
                               focus:outline-none transition-colors"
                    required
                  />
                </label>
                <button
                  type="submit"
                  disabled={authLoading || code.length !== 6}
                  className="w-full py-3 rounded-xl bg-primary-600 hover:bg-primary-700
                             text-white font-medium transition-colors
                             disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {authLoading ? 'Creating your page…' : 'Create my page'}
                </button>
                <button
                  type="button"
                  onClick={() => { setAuthStep('identifier'); setCode(''); setError(''); }}
                  className="w-full text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400"
                >
                  Use a different address
                </button>
              </form>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
