import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import GoogleSignInButton from '../components/GoogleSignInButton';
import GuessForm from '../components/GuessForm';
import PhoneOptIn from '../components/PhoneOptIn';

// Janet's eleven-calm-minutes flow: tap the invite link, type an email and
// a 6-digit code (or one-tap Google), confirm a name, "want a text the
// moment labor begins?", and the fun closer — "how big do you think the
// baby will be? 🎈" This is the only auth event she ever sees; her session
// slides forever after, and she arrives at the page already invested.
export default function InviteRedeemPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, completeSignIn, refreshMe } = useAuth();

  const [context, setContext] = useState(null);
  const [contextError, setContextError] = useState('');
  // 'email' | 'code' | 'redeeming' | 'name' | 'notify' | 'guess'
  const [step, setStep] = useState('email');
  const [poolBirth, setPoolBirth] = useState(null);
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const autoRedeemStarted = useRef(false);

  const goToPage = () => navigate(`/b/${context.birth_slug}`, { replace: true });

  // The fun closer: offer a pool guess if the pool is open and this user
  // hasn't guessed. Any hiccup skips straight to the page — onboarding
  // must never be blockable by a nicety.
  const maybeGuessStep = async (profile) => {
    try {
      const birth = (profile?.families || [])
        .flatMap((f) => f.births || [])
        .find((b) => b.id === context.birth_id);
      if (!birth || birth.status === 'born') {
        goToPage();
        return;
      }
      const board = await api.listGuesses({ slug: context.birth_slug });
      if (board.settled || board.guesses.some((g) => g.is_mine)) {
        goToPage();
        return;
      }
      setPoolBirth(birth);
      setStep('guess');
    } catch {
      goToPage();
    }
  };

  // After auth: collect a display name if missing (so comments are
  // attributed — and the pool needs it), then the birth-alerts opt-in,
  // then the pool guess, then the page.
  const nextStepFor = (profile) => {
    if (profile?.user && !profile.user.display_name) {
      setDisplayName(context?.display_name_hint || '');
      setStep('name');
    } else if (profile?.user && !profile.user.notify_phone) {
      setStep('notify');
    } else {
      maybeGuessStep(profile);
    }
  };

  useEffect(() => {
    let cancelled = false;
    api.lookupInvitation(token)
      .then((ctx) => {
        if (cancelled) return;
        setContext(ctx);
        if (ctx.email_hint) setEmail((prev) => prev || ctx.email_hint);
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
        nextStepFor(profile);
      } catch (err) {
        setError(err.message || 'Could not redeem invitation.');
        setStep('email');
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, context, token, refreshMe]);

  const handleSignedIn = async () => {
    autoRedeemStarted.current = true; // the invite rode along with the auth
    const profile = await completeSignIn();
    nextStepFor(profile);
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
      await api.verifyChallenge({
        identifier: email.trim().toLowerCase(),
        code,
        inviteToken: token,
      });
      await handleSignedIn();
    } catch (err) {
      setError(err.message || 'Invalid code');
      setLoading(false);
    }
  };

  const submitName = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.updateMe({ displayName: displayName.trim() });
      const profile = await refreshMe();
      setLoading(false);
      if (profile?.user && !profile.user.notify_phone) {
        setStep('notify');
      } else {
        await maybeGuessStep(profile);
      }
    } catch (err) {
      setError(err.message || 'Could not save your name');
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

        {step === 'email' && (
          <div className="space-y-4">
            <GoogleSignInButton
              inviteToken={token}
              onSuccess={handleSignedIn}
              onError={(err) => setError(err.message || 'Google sign-in failed')}
            />
            <form onSubmit={submitEmail} className="space-y-4">
              <label className="block">
                <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Your email
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
                We'll email you a 6-digit code to confirm you're you — no password needed.
                By continuing, you agree to our{' '}
                <Link to="/terms" className="underline hover:text-primary-600 dark:hover:text-primary-400">Terms</Link> and{' '}
                <Link to="/privacy" className="underline hover:text-primary-600 dark:hover:text-primary-400">Privacy Policy</Link>.
              </p>
            </form>
          </div>
        )}

        {step === 'code' && (
          <form onSubmit={submitCode} className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Enter the code sent to{' '}
              <span className="font-medium text-gray-900 dark:text-white">
                {email.trim()}
              </span>.
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

        {step === 'notify' && (
          <PhoneOptIn
            babyName={context.birth_child_name}
            onDone={async () => {
              const profile = await refreshMe().catch(() => null);
              await maybeGuessStep(profile);
            }}
          />
        )}

        {step === 'guess' && poolBirth && (
          <div className="space-y-4">
            <div>
              {/* The viewer's counterpart to the setup step's "mother's
                  intuition" — grandma, aunts and friends are guessing at
                  someone they haven't met either. */}
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                One last thing — hunches before hellos 🎈
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                How big will {context.birth_child_name || 'the baby'} be? When?
                Everyone's guess is sealed until the arrival — closest wins bragging rights.
              </p>
            </div>
            <GuessForm
              scope={{ slug: context.birth_slug }}
              mine={null}
              status={poolBirth.status}
              genderEnabled={poolBirth.gender_pool_enabled}
              dueDate={poolBirth.due_date}
              onSaved={goToPage}
              onSkip={goToPage}
            />
          </div>
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
