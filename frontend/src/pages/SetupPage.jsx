import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../api/client';
import { THEMES, getTheme, themeVars } from '../utils/themes';
import ThemeCard from '../components/ThemeCard';
import GuessForm from '../components/GuessForm';

function toSlug(name) {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/[\s]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

function toDisplayName(raw) {
  return raw
    .split(' ')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}

export default function SetupPage() {
  const { isAuthenticated, loading, me, completeSignIn, refreshMe } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isAddingAnother = searchParams.get('new') === '1';

  const [step, setStep] = useState('name');
  // Set once the birth exists — from here the flow is post-create (guess,
  // invite) and the "existing users go home" redirect must stand down.
  const [createdBirth, setCreatedBirth] = useState(null);
  // Whether this run actually passed through the auth step — keeps the
  // auth progress dot from vanishing mid-flow once sign-in succeeds.
  const [wentToAuth, setWentToAuth] = useState(false);
  const [babyName, setBabyName] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [slug, setSlug] = useState('');
  const [slugStatus, setSlugStatus] = useState(null);
  const [slugSuggestion, setSlugSuggestion] = useState('');
  const slugCheckTimeout = useRef(null);

  const [selectedTheme, setSelectedTheme] = useState('blossom');

  // Second child, twins, etc. — offer joining an existing family (where
  // the user is already a parent) instead of always starting a new one.
  const parentFamilies = (me?.families || []).filter(
    (f) => f.role === 'owner' || f.role === 'co_parent',
  );
  const [selectedFamilyId, setSelectedFamilyId] = useState('new');
  useEffect(() => {
    if (parentFamilies.length === 0) return;
    setSelectedFamilyId((prev) => (prev === 'new' ? parentFamilies[0].id : prev));
    // Only re-run when `me` (re)loads — not on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me]);

  const [authStep, setAuthStep] = useState('identifier');
  const [identifier, setIdentifier] = useState('');
  const [code, setCode] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [error, setError] = useState('');

  // Redirect existing users home, unless they deliberately came to add a birth
  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated) return;
    if (isAddingAnother) return;
    // The refreshed `me` now includes the birth we just made — that's the
    // onboarding steps ahead, not an "existing user" to bounce home.
    if (createdBirth) return;
    const hasBirth = me?.families?.some((f) => f.births?.length > 0);
    if (hasBirth) navigate('/account', { replace: true });
  }, [isAuthenticated, loading, me, navigate, isAddingAnother, createdBirth]);

  // Debounced slug availability check
  useEffect(() => {
    const generated = toSlug(babyName);
    setSlug(generated);
    setSlugSuggestion('');
    if (!generated) { setSlugStatus(null); return; }
    setSlugStatus('checking');
    if (slugCheckTimeout.current) clearTimeout(slugCheckTimeout.current);
    slugCheckTimeout.current = setTimeout(async () => {
      try {
        const result = await api.checkSlugAvailable(generated);
        setSlugStatus(result.available ? 'available' : 'taken');
        if (!result.available && result.suggestion) setSlugSuggestion(result.suggestion);
      } catch { setSlugStatus(null); }
    }, 400);
    return () => { if (slugCheckTimeout.current) clearTimeout(slugCheckTimeout.current); };
  }, [babyName]);

  const theme = getTheme(selectedTheme);
  const displayName = babyName ? toDisplayName(babyName) : '';

  const adoptSuggestion = () => setBabyName(slugSuggestion.replace(/-/g, ' '));
  const familyIdToJoin = selectedFamilyId === 'new' ? null : selectedFamilyId;

  const goToAuth = async (e) => {
    e.preventDefault();
    if (slugStatus !== 'available') return;
    if (isAuthenticated) {
      setAuthLoading(true);
      setError('');
      try {
        const birth = await api.createBirth({
          babyName, slug, theme: selectedTheme, familyId: familyIdToJoin, dueDate,
        });
        // Mark the post-create flow BEFORE refreshing `me` — once `me`
        // carries the new birth, the redirect effect would bounce us to
        // /account if createdBirth weren't already set.
        setCreatedBirth(birth);
        setStep('invite');
        setAuthLoading(false);
        // The birth page derives parent tooling from `me`; refresh it so
        // we land there already wearing the parent hat.
        await refreshMe();
      } catch (err) {
        setError(err.message || 'Something went wrong');
        setAuthLoading(false);
      }
      return;
    }
    setWentToAuth(true);
    setStep('auth');
    setError('');
  };

  const submitIdentifier = async (e) => {
    e.preventDefault();
    setError('');
    setAuthLoading(true);
    try {
      await api.requestChallenge(identifier.trim().toLowerCase());
      setAuthStep('code');
    } catch (err) {
      setError(err.message || 'Could not send code');
    } finally { setAuthLoading(false); }
  };

  const submitCode = async (e) => {
    e.preventDefault();
    setError('');
    setAuthLoading(true);
    try {
      await api.verifyChallenge({
        identifier: identifier.trim().toLowerCase(),
        code,
      });
      await completeSignIn();
      const birth = await api.createBirth({
        babyName, slug, theme: selectedTheme, familyId: familyIdToJoin, dueDate,
      });
      // Mark the post-create flow before refreshing `me` (see goToAuth).
      setCreatedBirth(birth);
      setStep('invite');
      // completeSignIn fetched /me before the birth existed; refresh so
      // the birth page recognizes us as its parent on arrival.
      await refreshMe();
    } catch (err) {
      setError(err.message || 'Something went wrong');
    } finally { setAuthLoading(false); }
  };

  if (loading) return null;

  return (
    <div className="min-h-screen flex flex-col items-center justify-start bg-gradient-to-b from-primary-50 to-white dark:from-gray-900 dark:to-gray-950 px-4 py-12">
      {/* Logo */}
      <div
        className="text-4xl text-primary-600 dark:text-primary-400 mb-8"
        style={{ fontFamily: "'Great Vibes', cursive" }}
      >
        Arrival Story
      </div>

      {/* Progress dots — auth only appears for signed-out runs */}
      <div className="flex items-center gap-2 mb-8">
        {['name', ...(wentToAuth || !isAuthenticated ? ['auth'] : []), 'invite', 'guess'].map((s) => (
          <div
            key={s}
            className={`h-2 w-2 rounded-full transition-colors ${step === s ? 'bg-primary-500' : 'bg-primary-200 dark:bg-primary-700'}`}
          />
        ))}
      </div>

      <div className="w-full max-w-md">

        {/* ── Step 1: Name + Theme ── */}
        {step === 'name' && (
          <form onSubmit={goToAuth} className="space-y-8">

            {/* Family chooser — only when the user already parents a family */}
            {parentFamilies.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300 text-center">
                  Add this baby to
                </p>
                <div className="space-y-2">
                  {parentFamilies.map((f) => (
                    <label
                      key={f.id}
                      className="flex items-center gap-3 p-3 rounded-xl border border-gray-300 dark:border-gray-600
                                 bg-white dark:bg-gray-800 cursor-pointer"
                    >
                      <input
                        type="radio"
                        name="family"
                        checked={selectedFamilyId === f.id}
                        onChange={() => setSelectedFamilyId(f.id)}
                      />
                      <span className="text-sm text-gray-800 dark:text-gray-100">
                        {f.display_name}
                        <span className="block text-xs text-gray-400 dark:text-gray-500">
                          Co-parents and viewers from this family carry over
                        </span>
                      </span>
                    </label>
                  ))}
                  <label
                    className="flex items-center gap-3 p-3 rounded-xl border border-gray-300 dark:border-gray-600
                               bg-white dark:bg-gray-800 cursor-pointer"
                  >
                    <input
                      type="radio"
                      name="family"
                      checked={selectedFamilyId === 'new'}
                      onChange={() => setSelectedFamilyId('new')}
                    />
                    <span className="text-sm text-gray-800 dark:text-gray-100">A new family</span>
                  </label>
                </div>
              </div>
            )}

            {/* Name input */}
            <div className="space-y-2">
              <div className="text-center">
                <h1 className="text-xl font-semibold text-gray-800 dark:text-white mb-1">
                  What's your baby's name?
                </h1>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  You can always change this later.
                </p>
              </div>
              <input
                type="text"
                value={babyName}
                onChange={(e) => setBabyName(e.target.value)}
                placeholder="Lily Wren"
                autoFocus
                autoComplete="off"
                className="w-full px-4 py-4 text-xl rounded-xl border border-gray-300 dark:border-gray-600
                           bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-center
                           focus:ring-2 focus:ring-primary-500 focus:border-transparent
                           focus:outline-none transition-colors placeholder-gray-300 dark:placeholder-gray-600"
              />
              {slug && (
                <div className="flex items-center justify-between px-1">
                  <span className="text-xs text-gray-400 font-mono">/b/{slug}</span>
                  {slugStatus === 'checking' && <span className="text-xs text-gray-400">Checking…</span>}
                  {slugStatus === 'available' && <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">Available ✓</span>}
                  {slugStatus === 'taken' && <span className="text-xs text-red-500 dark:text-red-400 font-medium">Taken</span>}
                </div>
              )}
              {slugStatus === 'taken' && slugSuggestion && (
                <button
                  type="button"
                  onClick={adoptSuggestion}
                  className="text-xs text-primary-600 dark:text-primary-400 hover:underline px-1"
                >
                  Use /b/{slugSuggestion} instead →
                </button>
              )}
            </div>

            {/* Due date — optional, skippable; drives the family pool's
                36-week guess lock and can be set later in Birth settings */}
            <label className="block">
              <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                When are they due? <span className="font-normal text-gray-400">(optional)</span>
              </span>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="t-date-input px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600
                           bg-white dark:bg-gray-800 text-gray-900 dark:text-white
                           focus:ring-2 focus:ring-primary-500 focus:border-transparent
                           focus:outline-none transition-colors"
              />
            </label>

            {/* Theme picker */}
            <div className="space-y-4">
              <div className="text-center">
                <h2 className="text-base font-semibold text-gray-800 dark:text-white">
                  Pick a look for your page
                </h2>
              </div>

              {/* Theme cards — all 6 in a 3-column grid */}
              <div className="grid grid-cols-3 gap-2.5">
                {Object.values(THEMES).map((t) => (
                  <ThemeCard
                    key={t.id}
                    theme={t}
                    displayName={displayName || 'Baby'}
                    selected={selectedTheme === t.id}
                    onSelect={() => setSelectedTheme(t.id)}
                  />
                ))}
              </div>

              {/* Live preview */}
              {displayName && (
                <PagePreview theme={theme} displayName={displayName} />
              )}
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={!slug || slugStatus !== 'available' || authLoading}
              className="w-full py-3.5 rounded-xl font-medium transition-colors text-white
                         disabled:opacity-40 disabled:cursor-not-allowed"
              style={{
                background: slugStatus === 'available'
                  ? `linear-gradient(135deg, ${theme.modes.light.accent}, ${theme.modes.light.accentHover})`
                  : undefined,
                backgroundColor: slugStatus !== 'available' ? '#9ca3af' : undefined,
              }}
            >
              {authLoading ? 'Creating…' : isAuthenticated ? 'Create my page' : 'Next →'}
            </button>
          </form>
        )}

        {/* ── Step 2: Auth ── */}
        {step === 'auth' && (
          <div className="space-y-6">
            <div className="text-center">
              <h1 className="text-xl font-semibold text-gray-800 dark:text-white mb-1">
                Let's get you set up
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Sign in to create{' '}
                <span
                  style={{
                    fontFamily: theme.display.family,
                    fontWeight: theme.display.weight,
                    fontStyle: theme.display.style,
                    fontSize: '1.15em',
                    color: theme.modes.light.accent,
                  }}
                >
                  {displayName}
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
                    Email
                  </span>
                  <input
                    type="email"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    autoFocus
                    autoComplete="email"
                    autoCapitalize="none"
                    autoCorrect="off"
                    placeholder="you@example.com"
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
                  className="w-full py-3 rounded-xl text-white font-medium transition-colors
                             disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{ backgroundColor: theme.modes.light.accent }}
                >
                  {authLoading ? 'Sending…' : 'Send code'}
                </button>
                <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
                  We'll email you a 6-digit code — no password needed. By continuing, you agree
                  to our <Link to="/terms" className="underline hover:text-primary-600 dark:hover:text-primary-400">Terms</Link> and{' '}
                  <Link to="/privacy" className="underline hover:text-primary-600 dark:hover:text-primary-400">Privacy Policy</Link>.
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
                  <span className="font-medium text-gray-900 dark:text-white">
                    {identifier.trim()}
                  </span>
                  . Check your email.
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
                  className="w-full py-3 rounded-xl text-white font-medium transition-colors
                             disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{ backgroundColor: theme.modes.light.accent }}
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

        {/* ── Step 3: The page is live — share it ── */}
        {step === 'invite' && createdBirth && (
          <InviteStep
            birth={createdBirth}
            theme={theme}
            displayName={displayName}
            onDone={() => setStep('guess')}
          />
        )}

        {/* ── Step 4: The closer — the parents' own pool guess ── */}
        {step === 'guess' && createdBirth && (
          <div className="space-y-6">
            <div className="text-center">
              <h1 className="text-xl font-semibold text-gray-800 dark:text-white mb-1">
                One more thing — the family pool 🎈
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                How big will {displayName || 'the baby'} be, and when? Everyone's
                guess stays sealed until the arrival — closest wins bragging
                rights.
              </p>
            </div>
            <GuessForm
              scope={{ slug: createdBirth.slug }}
              mine={null}
              status={createdBirth.status}
              genderEnabled={createdBirth.gender_pool_enabled}
              dueDate={createdBirth.due_date}
              onSaved={() => navigate(`/b/${createdBirth.slug}`, { replace: true })}
              onSkip={() => navigate(`/b/${createdBirth.slug}`, { replace: true })}
              submitLabel="Lock in my guess"
            />
          </div>
        )}
      </div>
    </div>
  );
}

// The celebration step: the page they just made, in their theme, plus the
// fastest path to the family group text — one tap → a shareable link. The
// full invite tooling (contact sending, revoking, viewer management) lives
// in Birth settings.
function InviteStep({ birth, theme, displayName, onDone }) {
  const [creating, setCreating] = useState(false);
  const [invite, setInvite] = useState(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  const createLink = async () => {
    setCreating(true);
    setError('');
    try {
      setInvite(await api.createInvitation(birth.id, {}));
    } catch (err) {
      setError(err.message || 'Could not create the link');
    } finally {
      setCreating(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(invite.invite_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable on insecure origins — same fallback as
      // InviteManager.
      window.prompt('Copy this link', invite.invite_url);
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h1 className="text-xl font-semibold text-gray-800 dark:text-white mb-1">
          {displayName ? `${displayName}'s page is live 🎉` : 'Your page is live 🎉'}
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Now share it — grab a link and drop it in the family group text.
          Anyone with it can follow along and join the pool.
        </p>
      </div>

      <PagePreview
        theme={theme}
        displayName={displayName || birth.child_name || 'Baby'}
      />

      {error && (
        <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {invite ? (
        <div
          className="p-3 rounded-xl border border-gray-300 dark:border-gray-600
                     bg-white dark:bg-gray-800 space-y-2"
        >
          <p className="text-sm font-medium text-gray-800 dark:text-gray-100">
            Your invite link is ready
          </p>
          <div className="flex gap-2">
            <input
              readOnly
              value={invite.invite_url}
              onFocus={(e) => e.target.select()}
              className="flex-1 min-w-0 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600
                         bg-gray-50 dark:bg-gray-900 text-sm text-gray-900 dark:text-white"
            />
            <button
              type="button"
              onClick={copy}
              className="px-3 py-2 rounded-lg text-sm font-medium text-white"
              style={{ backgroundColor: theme.modes.light.accent }}
            >
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={createLink}
          disabled={creating}
          className="w-full py-3.5 rounded-xl text-white font-medium transition-colors
                     disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ backgroundColor: theme.modes.light.accent }}
        >
          {creating ? 'Creating…' : 'Create invite link'}
        </button>
      )}

      {/* Forward motion on the right; the quiet escape hatch only before
          a link exists (once it does, Next is the natural continue). */}
      <div className="flex items-center justify-end">
        {invite ? (
          <button
            type="button"
            onClick={onDone}
            className="px-5 py-2.5 rounded-xl text-white font-medium transition-colors"
            style={{
              background: `linear-gradient(135deg, ${theme.modes.light.accent}, ${theme.modes.light.accentHover})`,
            }}
          >
            Next →
          </button>
        ) : (
          <button
            type="button"
            onClick={onDone}
            className="text-sm text-gray-500 dark:text-gray-400
                       hover:text-primary-600 dark:hover:text-primary-400"
          >
            Skip for now
          </button>
        )}
      </div>
      <p className="text-xs text-gray-400 dark:text-gray-500 text-center">
        You can invite people anytime from Birth settings.
      </p>
    </div>
  );
}

function PagePreview({ theme, displayName }) {
  return (
    <div
      className="rounded-2xl overflow-hidden shadow-md"
      style={{ ...themeVars(theme, false), border: '1px solid var(--t-header-border)' }}
    >
      {/* Mock page: themed background with pattern */}
      <div
        style={{
          backgroundColor: 'var(--t-page-bg)',
          backgroundImage: 'var(--t-page-pattern)',
          backgroundSize: 'var(--t-pattern-size)',
        }}
      >
        {/* Mock header */}
        <div
          className="px-4 py-2.5"
          style={{
            backgroundColor: 'var(--t-header-bg)',
            borderBottom: '1px solid var(--t-header-border)',
          }}
        >
          <p className="t-display" style={{ fontSize: 'calc(var(--t-title-size) * 0.8)' }}>
            Welcoming {displayName}
          </p>
        </div>

        {/* Mock timeline card */}
        <div className="px-3 py-3">
          <div
            className="rounded-xl shadow-sm px-3 py-3 space-y-2"
            style={{
              backgroundColor: 'var(--t-card-bg)',
              border: '1px solid var(--t-card-border)',
            }}
          >
            <div className="flex items-center gap-2">
              <div
                className="h-2 w-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: 'var(--t-dot)' }}
              />
              <span className="text-xs t-faint">Contraction in progress · 0:42</span>
            </div>
            <div
              className="rounded-lg px-2.5 py-1.5 inline-flex items-center gap-1.5"
              style={{
                backgroundColor: 'var(--t-milestone-bg)',
                border: '1px solid var(--t-milestone-border)',
              }}
            >
              <span className="text-sm">👶</span>
              <span className="text-xs font-semibold" style={{ color: 'var(--t-milestone-text)' }}>
                Baby Born!
              </span>
            </div>
            <p className="text-xs t-ink">
              Contractions are 5 minutes apart 💪
            </p>
            <div className="flex gap-1.5 pt-0.5">
              {['💖 14', '🙏 8', '✨ 5'].map((r) => (
                <span
                  key={r}
                  className="text-xs rounded-full px-2 py-0.5"
                  style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
                >
                  {r}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
