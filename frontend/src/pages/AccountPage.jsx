import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { getTheme, themeVars } from '../utils/themes';
import CoParentManager from '../components/CoParentManager';

const STATUS_LABELS = {
  preparing: 'Preparing',
  in_labor: 'In labor',
  born: 'Born',
  archived: 'Keepsake',
};

function formatBornDate(birth) {
  const raw = birth.child_dob || birth.birth_completed_at;
  if (!raw) return null;
  return new Date(raw).toLocaleDateString(undefined, {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

function BirthCard({ birth }) {
  const theme = getTheme(birth.theme);
  const isParent = birth.role === 'owner' || birth.role === 'co_parent';
  const bornDate = birth.status === 'born' ? formatBornDate(birth) : null;

  return (
    <div
      className="rounded-2xl overflow-hidden shadow-md hover:shadow-lg transition-shadow flex flex-col"
      style={{
        ...themeVars(theme, false),
        backgroundColor: 'var(--t-page-bg)',
        backgroundImage: 'var(--t-page-pattern)',
        backgroundSize: 'var(--t-pattern-size)',
        border: '1px solid var(--t-card-border)',
      }}
    >
      <Link
        to={`/b/${birth.slug}`}
        className="flex-1 flex flex-col items-center justify-center gap-3 px-5 py-8 text-center"
      >
        <span className="t-display leading-tight" style={{ fontSize: 'var(--t-title-size)' }}>
          {birth.child_name || 'Baby'}
        </span>
        <span
          className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
          style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
        >
          {birth.status === 'in_labor' && (
            <span
              className="h-2 w-2 rounded-full animate-pulse"
              style={{ backgroundColor: 'var(--t-dot)' }}
            />
          )}
          {STATUS_LABELS[birth.status] || birth.status}
          {bornDate && ` · ${bornDate}`}
        </span>
        {!isParent && <span className="text-xs t-faint">Following</span>}
      </Link>

      {isParent && (
        <div
          className="flex items-center justify-between px-4 py-2.5"
          style={{ borderTop: '1px solid var(--t-divider)' }}
        >
          <span className="text-xs font-mono t-faint">/b/{birth.slug}</span>
          <Link
            to={`/b/${birth.slug}/settings`}
            className="text-xs font-medium hover:underline"
            style={{ color: 'var(--t-soft-text)' }}
          >
            Settings
          </Link>
        </div>
      )}
    </div>
  );
}

const PARENT_ROLES = ['owner', 'co_parent'];

// Leaving is family-wide, because membership is — so name every page it
// covers rather than saying "family", which sounds like one page and isn't.
function FollowedPages({ family, onLeft }) {
  const [confirming, setConfirming] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [error, setError] = useState('');
  const names = (family.births || []).map((b) => b.child_name).filter(Boolean);
  const label = names.length === 1
    ? `${names[0]}'s page`
    : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}'s pages`;

  const leave = async () => {
    setLeaving(true);
    setError('');
    try {
      await api.leaveFamily(family.id);
      await onLeft();
    } catch (err) {
      setError(err.message || 'Could not leave');
      setLeaving(false);
    }
  };

  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-gray-700 dark:text-gray-300">{label}</span>
      {confirming ? (
        <span className="flex items-center gap-3 shrink-0">
          <button
            type="button"
            onClick={leave}
            disabled={leaving}
            className="text-red-600 dark:text-red-400 hover:underline disabled:opacity-50"
          >
            {leaving ? 'Leaving…' : 'Yes, stop following'}
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            className="text-gray-500 dark:text-gray-400 hover:underline"
          >
            Cancel
          </button>
        </span>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="shrink-0 text-gray-500 dark:text-gray-400 hover:underline"
        >
          Stop following
        </button>
      )}
      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}

function NameField({ user, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(user?.display_name || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const save = async () => {
    if (!value.trim()) return;
    setSaving(true);
    setError('');
    try {
      await api.updateMe({ displayName: value.trim() });
      await onSaved?.();
      setEditing(false);
    } catch (err) {
      setError(err.message || 'Could not save your name');
    } finally {
      setSaving(false);
    }
  };

  if (!editing) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400">
        {user?.display_name ? (
          <>
            Friends and family see you as{' '}
            <span className="font-medium text-gray-700 dark:text-gray-200">{user.display_name}</span>
          </>
        ) : (
          <span className="text-amber-600 dark:text-amber-400">No name set — friends and family won't know who you are</span>
        )}
        <button
          type="button"
          onClick={() => { setValue(user?.display_name || ''); setEditing(true); }}
          className="ml-2 text-primary-600 dark:text-primary-400 hover:underline"
        >
          {user?.display_name ? 'Edit' : 'Add your name'}
        </button>
      </p>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoFocus
        maxLength={80}
        placeholder="Your name"
        onKeyDown={(e) => e.key === 'Enter' && save()}
        className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white"
      />
      <button
        type="button"
        onClick={save}
        disabled={saving || !value.trim()}
        className="px-3 py-1.5 text-sm rounded-lg bg-primary-600 hover:bg-primary-700 text-white font-medium disabled:opacity-50"
      >
        {saving ? 'Saving…' : 'Save'}
      </button>
      <button
        type="button"
        onClick={() => setEditing(false)}
        className="px-2 py-1.5 text-sm text-gray-500 dark:text-gray-400 hover:opacity-80"
      >
        Cancel
      </button>
      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  );
}

function NotifyPhoneField({ user, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const save = async () => {
    if (!value.trim()) return;
    setBusy(true);
    setError('');
    try {
      await api.setNotifyPhone(value.trim());
      await onSaved?.();
      setEditing(false);
      setValue('');
    } catch (err) {
      setError(err.message || "We couldn't text that number");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    setError('');
    try {
      await api.clearNotifyPhone();
      await onSaved?.();
    } catch (err) {
      setError(err.message || 'Could not update');
    } finally {
      setBusy(false);
    }
  };

  if (!editing) {
    return (
      <div className="mt-1">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {user?.notify_phone ? (
            <>
              We'll text{' '}
              <span className="font-medium text-gray-700 dark:text-gray-200">
                {user.notify_phone}
              </span>{' '}
              the moment labor begins — birth updates only, ever.
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="ml-2 text-primary-600 dark:text-primary-400 hover:underline"
              >
                Change
              </button>
              <button
                type="button"
                onClick={remove}
                disabled={busy}
                className="ml-2 text-gray-400 dark:text-gray-500 hover:underline"
              >
                Turn off
              </button>
            </>
          ) : (
            <>
              Want a text the moment labor begins? Birth updates only, ever.
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="ml-2 text-primary-600 dark:text-primary-400 hover:underline"
              >
                Add your number
              </button>
            </>
          )}
        </p>
        {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
      </div>
    );
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <input
        type="tel"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoFocus
        inputMode="tel"
        autoComplete="tel"
        placeholder="(555) 555-5555"
        onKeyDown={(e) => e.key === 'Enter' && save()}
        className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white"
      />
      <button
        type="button"
        onClick={save}
        disabled={busy || !value.trim()}
        className="px-3 py-1.5 text-sm rounded-lg bg-primary-600 hover:bg-primary-700 text-white font-medium disabled:opacity-50"
      >
        {busy ? 'Sending…' : 'Save'}
      </button>
      <button
        type="button"
        onClick={() => { setEditing(false); setError(''); }}
        className="px-2 py-1.5 text-sm text-gray-500 dark:text-gray-400 hover:opacity-80"
      >
        Cancel
      </button>
      {error && <span className="text-xs text-red-500">{error}</span>}
      <p className="w-full text-xs text-gray-400 dark:text-gray-500">
        We'll send one confirmation text. Msg &amp; data rates may apply. Reply STOP anytime.
      </p>
    </div>
  );
}

export default function AccountPage() {
  const { isAuthenticated, loading, me, user, logout, refreshMe } = useAuth();
  const navigate = useNavigate();
  const [showDelete, setShowDelete] = useState(false);

  if (loading) return null;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const births = (me?.families || []).flatMap((family) =>
    (family.births || []).map((birth) => ({ ...birth, role: family.role }))
  );

  // Families where you're a parent get a "Your family" block to manage
  // co-parents. Name the block only when there's more than one.
  const parentFamilies = (me?.families || []).filter((f) => PARENT_ROLES.includes(f.role));
  // Pages you follow but don't run. Until now there was no way to stop —
  // redeeming an invite attached you permanently, and the only copy that
  // mentioned leaving lived inside the account-deletion preview.
  const followedFamilies = (me?.families || []).filter(
    (f) => !PARENT_ROLES.includes(f.role) && (f.births || []).length > 0,
  );

  // No redirect to /setup here on purpose. New parents never reach this page
  // empty — AuthPage and LandingPage both route `hasBirth ? '/account' :
  // '/setup'`, so the wizard is already the sign-in destination for anyone
  // without a page. The only people who arrive here with nothing are a viewer
  // who just stopped following their last page and a parent who just deleted
  // theirs, and shoving either into "name your baby" is the wrong ending —
  // especially seconds after a destructive confirm. After leaving, a viewer's
  // data is indistinguishable from a new signup's, so there's no intent to
  // detect: say what's true and let them choose.
  const isEmpty = births.length === 0;

  const signOut = () => {
    logout();
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-primary-50 to-white dark:from-gray-900 dark:to-gray-950 px-4 py-10">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <Link
            to="/"
            className="text-3xl text-primary-600 dark:text-primary-400"
            style={{ fontFamily: "'Great Vibes', cursive" }}
          >
            Arrival Story
          </Link>
          <button
            type="button"
            onClick={signOut}
            className="text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
          >
            Sign out
          </button>
        </div>

        {/* Greeting */}
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-gray-800 dark:text-white">
            Welcome back{user?.display_name ? `, ${user.display_name}` : ''}
          </h1>
          <NameField user={user} onSaved={refreshMe} />
        </div>

        {/* Family / co-parent management */}
        {parentFamilies.length > 0 && (
          <div className="mb-6 space-y-4">
            {parentFamilies.map((family) => (
              <CoParentManager
                key={family.id}
                familyId={family.id}
                familyName={parentFamilies.length > 1 ? family.display_name : undefined}
              />
            ))}
          </div>
        )}

        {/* Birth cards, or an explanation of why there aren't any. Doubles as
            the confirmation that leaving worked: the section you just used is
            replaced by the reason the page is empty. */}
        {isEmpty ? (
          <div className="rounded-2xl border border-gray-200 dark:border-gray-700 p-6 text-center">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              You&rsquo;re not following any pages right now.
            </p>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              When someone shares a page with you, it&rsquo;ll show up here.
            </p>
            <Link
              to="/setup?new=1"
              className="mt-4 inline-block text-sm font-medium text-primary-600 dark:text-primary-400 hover:underline"
            >
              Create a page for your own baby →
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {births.map((birth) => (
              <BirthCard key={birth.id} birth={birth} />
            ))}

            <Link
              to="/setup?new=1"
              className="rounded-2xl border-2 border-dashed border-primary-200 dark:border-primary-800
                         flex items-center justify-center min-h-[10rem] text-primary-600 dark:text-primary-400
                         font-medium text-sm hover:border-primary-400 dark:hover:border-primary-600
                         hover:bg-primary-50/50 dark:hover:bg-primary-900/10 transition-colors"
            >
              + Add another birth
            </Link>
          </div>
        )}

        {/* Pages you follow — with a way out */}
        {followedFamilies.length > 0 && (
          <div className="mt-10 pt-6 border-t border-gray-200 dark:border-gray-800">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
              Pages you follow
            </h2>
            <div className="space-y-2">
              {followedFamilies.map((family) => (
                <FollowedPages key={family.id} family={family} onLeft={refreshMe} />
              ))}
            </div>
          </div>
        )}

        {/* Birth alerts (the birth-events-only text opt-in) */}
        <div className="mt-10 pt-6 border-t border-gray-200 dark:border-gray-800">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
            Text alerts
          </h2>
          <NotifyPhoneField user={user} onSaved={refreshMe} />
        </div>

        {/* Identity footer */}
        <div className="mt-10 pt-6 border-t border-gray-200 dark:border-gray-800 text-center">
          <p className="text-xs text-gray-400 dark:text-gray-500">
            Signed in as{' '}
            <span className="text-gray-500 dark:text-gray-400">
              {user?.display_name || user?.email || user?.phone}
            </span>
            {user?.display_name && (user?.email || user?.phone) && (
              <span> · {user.email || user.phone}</span>
            )}
          </p>
          <button
            type="button"
            onClick={() => setShowDelete(true)}
            className="mt-2 text-xs text-gray-400 dark:text-gray-500 underline underline-offset-2
                       hover:text-red-600 dark:hover:text-red-400 transition-colors"
          >
            Delete account…
          </button>
        </div>
      </div>

      {showDelete && (
        <DeleteAccountModal
          me={me}
          onClose={() => setShowDelete(false)}
          onDeleted={signOut}
        />
      )}
    </div>
  );
}

function DeleteAccountModal({ me, onClose, onDeleted }) {
  const [parentCounts, setParentCounts] = useState(null); // familyId -> # of parents
  const [removeContributions, setRemoveContributions] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const families = me?.families || [];
  const parentFamilyIds = families
    .filter((f) => PARENT_ROLES.includes(f.role))
    .map((f) => f.id);

  // Sole-parent vs shared decides whether a family's pages are erased or
  // handed to the co-parent — fetch the parent rosters to tell them apart.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const counts = {};
      await Promise.all(
        parentFamilyIds.map(async (familyId) => {
          try {
            const data = await api.listCoParents(familyId);
            counts[familyId] = (data.members || []).length;
          } catch {
            counts[familyId] = null; // unknown — show cautious copy
          }
        })
      );
      if (!cancelled) setParentCounts(counts);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const consequence = (family) => {
    const names = (family.births || [])
      .map((b) => b.child_name || 'Baby')
      .join(', ');
    if (family.role === 'owner') {
      const count = parentCounts?.[family.id];
      if (count === undefined || parentCounts === null) return { names, text: 'Checking…' };
      if (count !== null && count > 1) {
        return {
          names,
          text: 'Ownership transfers to your co-parent. Everything you posted stays, with your name removed.',
        };
      }
      return {
        names,
        erased: true,
        text: 'Permanently erased for everyone — every photo, video, contraction, and comment.',
        births: family.births || [],
      };
    }
    if (family.role === 'co_parent') {
      return {
        names,
        text: "You'll leave this family. Everything you posted stays, with your name removed.",
      };
    }
    return { names, text: "You'll stop following this page." };
  };

  const confirm = async () => {
    setBusy(true);
    setError('');
    try {
      await api.deleteAccount({ removeContributions });
      onDeleted();
    } catch (err) {
      setError(err.message || 'Could not delete your account. Nothing was changed.');
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl max-w-md w-full p-6 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Delete your account?
        </h3>

        <ul className="mt-4 space-y-3">
          {families.map((family) => {
            const c = consequence(family);
            return (
              <li key={family.id} className="text-sm">
                <span className="font-medium text-gray-800 dark:text-gray-100">
                  {c.names}
                </span>
                <span className="block text-gray-500 dark:text-gray-400">
                  {c.text}
                </span>
                {c.erased && (
                  <span className="block mt-1 text-xs text-primary-700 dark:text-primary-300">
                    Download everything first — it's free:{' '}
                    {c.births.map((birth, i) => (
                      <span key={birth.id}>
                        {i > 0 && ' · '}
                        <Link
                          to={`/b/${birth.slug}/settings`}
                          className="underline hover:opacity-80"
                        >
                          {birth.child_name || 'Baby'}'s settings
                        </Link>
                      </span>
                    ))}
                  </span>
                )}
              </li>
            );
          })}
        </ul>

        <label className="mt-4 flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
          <input
            type="checkbox"
            checked={removeContributions}
            onChange={(e) => setRemoveContributions(e.target.checked)}
            className="mt-0.5"
          />
          Also delete my comments, reactions, and guesses on other families' pages
        </label>

        <div className="mt-5">
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
            Type <span className="font-mono font-semibold">DELETE</span> to confirm
          </label>
          <input
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-white"
          />
        </div>

        {error && <p className="mt-3 text-sm text-red-500">{error}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={confirm}
            disabled={busy || confirmText !== 'DELETE'}
            className="px-4 py-2 text-sm rounded-lg bg-red-500 hover:bg-red-600 text-white font-medium disabled:opacity-50"
          >
            {busy ? 'Deleting…' : 'Delete my account'}
          </button>
        </div>
      </div>
    </div>
  );
}
