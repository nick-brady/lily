import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

export default function InviteRedeemPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, acceptToken, refreshMe } = useAuth();

  const [context, setContext] = useState(null);
  const [contextError, setContextError] = useState('');
  // 'identifier' | 'code' | 'redeeming' | 'name'
  const [step, setStep] = useState('identifier');
  const [identifier, setIdentifier] = useState('');
  const [code, setCode] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const autoRedeemStarted = useRef(false);

  // After auth, send the user on — but pause to collect a name first if
  // they don't have one yet, so their comments are attributed.
  const finishOrAskName = (profile) => {
    if (profile?.user && !profile.user.display_name) {
      setDisplayName(context?.display_name_hint || '');
      setStep('name');
    } else {
      navigate(`/b/${context.birth_slug}`, { replace: true });
    }
  };

  useEffect(() => {
    let cancelled = false;
    api.lookupInvitation(token)
      .then((ctx) => {
        if (cancelled) return;
        setContext(ctx);
        if (ctx.email_hint && !identifier) setIdentifier(ctx.email_hint);
        else if (ctx.phone_hint && !identifier) setIdentifier(ctx.phone_hint);
      })
      .catch((err) => {
        if (!cancelled) setContextError(err.message || 'This invitation is invalid or expired.');
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // If the user is already signed in, just redeem against their session.
  // Guarded by a ref so it runs exactly once even as `step` changes.
  useEffect(() => {
    if (!isAuthenticated || !context || autoRedeemStarted.current) return;
    autoRedeemStarted.current = true;
    setStep('redeeming');
    (async () => {
      try {
        await api.redeemInvitationAuthed(token);
        const profile = await refreshMe();
        finishOrAskName(profile);
      } catch (err) {
        setError(err.message || 'Could not redeem invitation.');
        setStep('identifier');
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, context, token, refreshMe]);

  const submitIdentifier = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.requestChallenge(identifier);
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
      const result = await api.verifyChallenge({ identifier, code, inviteToken: token });
      const profile = await acceptToken(result.access_token);
      finishOrAskName(profile);
    } catch (err) {
      setError(err.message || 'Invalid code');
    } finally {
      setLoading(false);
    }
  };

  const submitName = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.updateMe({ displayName: displayName.trim() });
      await refreshMe();
      navigate(`/b/${context.birth_slug}`, { replace: true });
    } catch (err) {
      setError(err.message || 'Could not save your name');
    } finally {
      setLoading(false);
    }
  };

  if (contextError) {
    return (
      <Centered>
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
          Invitation unavailable
        </h1>
        <p className="text-sm text-gray-600 dark:text-gray-400">{contextError}</p>
      </Centered>
    );
  }
  if (!context) {
    return <Centered>Loading invitation…</Centered>;
  }

  const isCoParent = context.role === 'co_parent';
  const childPart = context.birth_child_name
    ? `${context.birth_child_name}'s birth`
    : 'a birth';

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 px-4">
      <div className="w-full max-w-sm bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6">
        <p className="text-sm text-gray-500 dark:text-gray-400 text-center mb-1">
          {context.family_display_name} invited you to
          {isCoParent ? ' help welcome' : ''}
        </p>
        <h1
          className="text-3xl text-center text-primary-600 dark:text-primary-400 mb-2"
          style={{ fontFamily: "'Great Vibes', cursive" }}
        >
          {isCoParent ? childPart : `Welcome ${childPart}`}
        </h1>
        {isCoParent && (
          <p className="text-sm text-gray-500 dark:text-gray-400 text-center mb-6">
            As a co-parent, you'll be able to post updates, time contractions, and run the page.
          </p>
        )}
        {!isCoParent && <div className="mb-4" />}

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        {step === 'redeeming' && (
          <p className="text-center text-gray-500 dark:text-gray-400">
            Joining…
          </p>
        )}

        {step === 'identifier' && (
          <form onSubmit={submitIdentifier} className="space-y-4">
            <label className="block">
              <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Verify your email or phone
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
              We'll text or email you a 6-digit code to confirm you're you.
            </p>
          </form>
        )}

        {step === 'code' && (
          <form onSubmit={submitCode} className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Enter the code sent to{' '}
              <span className="font-medium text-gray-900 dark:text-white">{identifier}</span>.
            </p>
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
            <button
              type="submit"
              disabled={loading || code.length !== 6}
              className="w-full py-3 rounded-lg bg-primary-600 hover:bg-primary-700
                         text-white font-medium transition-colors
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Joining…' : 'Accept invitation'}
            </button>
          </form>
        )}

        {step === 'name' && (
          <form onSubmit={submitName} className="space-y-4">
            <label className="block">
              <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                What should we call you?
              </span>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                autoFocus
                maxLength={80}
                placeholder="e.g. Grandma Rose"
                className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600
                           bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                           focus:ring-2 focus:ring-primary-500 focus:border-transparent
                           focus:outline-none transition-colors"
                required
              />
            </label>
            <button
              type="submit"
              disabled={loading || !displayName.trim()}
              className="w-full py-3 rounded-lg bg-primary-600 hover:bg-primary-700
                         text-white font-medium transition-colors
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Saving…' : 'Continue'}
            </button>
            <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
              This is the name friends and family see on your comments. You can change it later.
            </p>
          </form>
        )}
      </div>
    </div>
  );
}

function Centered({ children }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 px-4">
      <div className="text-center text-gray-500 dark:text-gray-400">{children}</div>
    </div>
  );
}
