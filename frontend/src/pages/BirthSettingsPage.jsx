import { useEffect, useMemo, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { getTheme, themeVars } from '../utils/themes';
import GiftGallery from '../components/GiftGallery';
import HeaderMenu from '../components/HeaderMenu';
import InviteManager from '../components/InviteManager';
import ThemePickerSheet from '../components/ThemePickerSheet';

const STATUS_LABELS = {
  preparing: 'Preparing',
  in_labor: 'In labor',
  born: 'Born',
  archived: 'Keepsake',
};

export default function BirthSettingsPage() {
  const { slug } = useParams();
  const { isAuthenticated, me, loading: authLoading, refreshMe } = useAuth();
  const [showThemePicker, setShowThemePicker] = useState(false);
  const [copied, setCopied] = useState(false);

  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window === 'undefined') return false;
    return (
      localStorage.getItem('darkMode') === 'true'
      || window.matchMedia('(prefers-color-scheme: dark)').matches
    );
  });

  const birth = useMemo(() => {
    if (!me) return null;
    for (const family of me.families) {
      for (const b of family.births) {
        if (b.slug === slug) return b;
      }
    }
    return null;
  }, [me, slug]);

  const isParent = useMemo(() => {
    if (!me) return false;
    return me.families.some(
      (f) =>
        ['owner', 'co_parent'].includes(f.role)
        && f.births.some((b) => b.slug === slug),
    );
  }, [me, slug]);

  // Deletion is owner-only (the backend enforces it too) — a co-parent
  // shouldn't see a button that would 403.
  const isOwner = useMemo(() => {
    if (!me) return false;
    return me.families.some(
      (f) => f.role === 'owner' && f.births.some((b) => b.slug === slug),
    );
  }, [me, slug]);

  const theme = getTheme(birth?.theme);
  const effectiveDark = darkMode || Boolean(theme.alwaysDark);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', effectiveDark);
    localStorage.setItem('darkMode', darkMode);
  }, [darkMode, effectiveDark]);

  if (authLoading || (isAuthenticated && !me)) {
    return <CenteredMessage>Loading…</CenteredMessage>;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (!birth || !isParent) {
    return (
      <CenteredMessage>
        You don't manage this birth.{' '}
        <Link to="/account" className="underline">Go home</Link>
      </CenteredMessage>
    );
  }

  const title = birth.child_name ? `${birth.child_name}'s settings` : 'Birth settings';
  const publicUrl = `${window.location.origin}/b/${birth.slug}`;

  const copyPublicUrl = async () => {
    try {
      await navigator.clipboard.writeText(publicUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt('Copy this link', publicUrl);
    }
  };

  return (
    <div
      className="min-h-screen transition-colors"
      style={{
        ...themeVars(theme, effectiveDark),
        backgroundColor: 'var(--t-page-bg)',
        backgroundImage: 'var(--t-page-pattern)',
        backgroundSize: 'var(--t-pattern-size)',
      }}
    >
      <header
        className="shadow-sm sticky top-0 z-10"
        style={{
          backgroundColor: 'var(--t-header-bg)',
          borderBottom: '1px solid var(--t-header-border)',
          backdropFilter: 'blur(10px)',
          WebkitBackdropFilter: 'blur(10px)',
        }}
      >
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className="t-display" style={{ fontSize: 'var(--t-title-size)' }}>
            {title}
          </h1>
          <div className="flex items-center gap-2">
            <Link
              to={`/b/${slug}`}
              className="px-3 py-2 text-sm rounded-lg transition-opacity hover:opacity-80"
              style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
            >
              View page
            </Link>
            <HeaderMenu
              items={[
                { label: 'Account', to: '/account' },
              ]}
            />
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {/* Theme */}
        <section className="card flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold t-ink">Theme</h3>
            <p className="text-sm t-muted">The look of {birth.child_name || 'this'}'s page.</p>
          </div>
          <button
            type="button"
            onClick={() => setShowThemePicker(true)}
            className="px-3 py-2 text-sm rounded-lg t-btn-accent font-medium"
          >
            Change theme
          </button>
        </section>

        {/* Family viewers */}
        <InviteManager birthId={birth.id} />

        {/* The guess pool */}
        <PoolSettingsCard birth={birth} onSaved={refreshMe} />

        {/* Keepsake gifts */}
        <ShippingAddressCard birthId={birth.id} />

        <GiftsReceivedCard birthId={birth.id} />

        {/* Gift artwork is generated from the finished story — nothing to
            manage until the birth is done. */}
        {birth.status === 'born' && <GiftGallery birthId={birth.id} isParent />}

        {/* Birth details */}
        <section className="card">
          <h3 className="text-lg font-semibold t-ink mb-3">Birth details</h3>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="t-muted">Name</dt>
              <dd className="t-ink">{birth.child_name || 'Baby'}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="t-muted">Status</dt>
              <dd className="t-ink">{STATUS_LABELS[birth.status] || birth.status}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="t-muted">Public link</dt>
              <dd className="flex items-center gap-2 min-w-0">
                <span className="font-mono text-xs t-faint truncate">/b/{birth.slug}</span>
                <button
                  type="button"
                  onClick={copyPublicUrl}
                  className="shrink-0 px-2 py-1 text-xs rounded"
                  style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
                >
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </dd>
            </div>
          </dl>
        </section>

        <DownloadDataCard birthId={birth.id} />

        {isOwner && <DangerZoneCard birth={birth} />}
      </main>

      {showThemePicker && (
        <ThemePickerSheet
          birth={birth}
          onClose={() => setShowThemePicker(false)}
          onSaved={refreshMe}
        />
      )}
    </div>
  );
}

// The danger zone: delete the whole page. Two-stage confirm — expand,
// then type the baby's name — because there is no undo on the other side.
function DangerZoneCard({ birth }) {
  const navigate = useNavigate();
  const { refreshMe } = useAuth();
  const [expanded, setExpanded] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');

  const confirmPhrase = birth.child_name || birth.slug;
  const matches =
    confirmText.trim().toLowerCase() === confirmPhrase.trim().toLowerCase();

  async function destroy() {
    if (!matches || deleting) return;
    setDeleting(true);
    setError('');
    try {
      await api.deleteBirth(birth.id);
      navigate('/account', { replace: true });
      refreshMe();
    } catch (err) {
      setError(err.message || 'Could not delete the page');
      setDeleting(false);
    }
  }

  return (
    <section
      className="card"
      style={{ border: '1px solid rgba(239, 68, 68, 0.45)' }}
    >
      <h3 className="text-lg font-semibold text-red-600 dark:text-red-400">
        Danger zone
      </h3>
      <p className="text-sm t-muted mt-1 mb-4">
        Deleting {birth.child_name ? `${birth.child_name}'s` : 'this'} page
        permanently erases the timeline, every photo and video, comments,
        guesses, and invites — for you and everyone following along. There is
        no undo. Download everything first if you want to keep it.
      </p>

      {!expanded ? (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="px-4 py-2 rounded-lg text-sm font-medium border border-red-400
                     text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
        >
          Delete this page…
        </button>
      ) : (
        <div className="space-y-3">
          <label className="block text-sm">
            <span className="t-muted">
              Type <span className="font-semibold t-ink">{confirmPhrase}</span> to
              confirm:
            </span>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              autoFocus
              autoComplete="off"
              className="mt-1 w-full max-w-xs px-3 py-2 rounded-lg border text-sm
                         bg-white dark:bg-gray-800 t-ink"
              style={{ borderColor: 'rgba(239, 68, 68, 0.45)' }}
            />
          </label>
          {error && <p className="text-xs text-red-500">{error}</p>}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={destroy}
              disabled={!matches || deleting}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-red-600
                         hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {deleting ? 'Deleting…' : 'Delete this page forever'}
            </button>
            <button
              type="button"
              onClick={() => {
                setExpanded(false);
                setConfirmText('');
                setError('');
              }}
              className="text-sm t-muted hover:opacity-80"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function CenteredMessage({ children }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900">
      <div className="text-gray-500 dark:text-gray-400 text-center px-4">{children}</div>
    </div>
  );
}


function DownloadDataCard({ birthId }) {
  const [preparing, setPreparing] = useState(false);

  function download() {
    setPreparing(true);
    // Anchor-click (not location.assign) so a failure can't navigate the
    // SPA; the attachment disposition keeps the page alive either way.
    const a = document.createElement('a');
    a.href = api.birthExportUrl(birthId);
    document.body.appendChild(a);
    a.click();
    a.remove();
    // The browser owns the download from here — there's no completion
    // event to listen for, so just re-enable after a beat.
    setTimeout(() => setPreparing(false), 8000);
  }

  return (
    <section className="card">
      <h3 className="text-lg font-semibold t-ink">Download everything</h3>
      <p className="text-sm t-muted mt-1 mb-4">
        One ZIP with every photo, video, and voice memo at full quality, plus
        spreadsheets of contractions, guesses, comments, and the whole
        timeline. Always free — your memories are yours.
      </p>
      <button
        type="button"
        onClick={download}
        disabled={preparing}
        className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
        style={{ backgroundColor: 'var(--t-accent)' }}
      >
        {preparing ? 'Preparing your download…' : 'Download all data (.zip)'}
      </button>
    </section>
  );
}


function ShippingAddressCard({ birthId }) {
  const empty = { name: '', line1: '', line2: '', city: '', state: '', postal_code: '', country: 'US' };
  const [addr, setAddr] = useState(empty);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .getShippingAddress(birthId)
      .then((res) => {
        if (res.address) {
          setAddr({ ...empty, ...res.address });
          setSaved(true);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [birthId]);

  const set = (k) => (e) => setAddr((a) => ({ ...a, [k]: e.target.value }));

  async function save() {
    setSaving(true);
    setError('');
    try {
      await api.putShippingAddress(birthId, addr);
      setSaved(true);
    } catch (err) {
      setError(err.message || "Couldn't save the address");
    } finally {
      setSaving(false);
    }
  }

  const input = (key, placeholder, extra = '') => (
    <input
      type="text"
      value={addr[key] || ''}
      onChange={set(key)}
      placeholder={placeholder}
      className={`px-3 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink ${extra}`}
      style={{ borderColor: 'var(--t-soft-ring)' }}
    />
  );

  return (
    <section className="card">
      <h3 className="text-lg font-semibold t-ink">Shipping address</h3>
      <p className="text-sm t-muted mb-3">
        Where gifts sent "to the family" ship. Family members never see this —
        their gift options just say it ships to your saved address.
      </p>
      {error && (
        <div className="mb-3 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {input('name', 'Recipient name', 'sm:col-span-2')}
        {input('line1', 'Address line 1', 'sm:col-span-2')}
        {input('line2', 'Address line 2 (optional)', 'sm:col-span-2')}
        {input('city', 'City')}
        {input('state', 'State')}
        {input('postal_code', 'ZIP')}
        {input('country', 'Country (US)')}
      </div>
      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
          style={{ backgroundColor: 'var(--t-accent)' }}
        >
          {saving ? 'Saving…' : 'Save address'}
        </button>
        {saved && <span className="text-xs t-muted">Saved 🤍</span>}
      </div>
    </section>
  );
}

function GiftsReceivedCard({ birthId }) {
  const [orders, setOrders] = useState(null);
  const [retrying, setRetrying] = useState('');

  const load = () =>
    api
      .listGiftOrders(birthId)
      .then(setOrders)
      .catch(() => setOrders([]));

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [birthId]);

  async function retry(orderId) {
    setRetrying(orderId);
    try {
      await api.retryGiftFulfillment(birthId, orderId);
      await load();
    } finally {
      setRetrying('');
    }
  }

  if (!orders || orders.length === 0) return null;

  return (
    <section className="card">
      <h3 className="text-lg font-semibold t-ink mb-3">Gifts received</h3>
      <ul className="space-y-3">
        {orders.map((o) => (
          <li
            key={o.id}
            className="p-3 rounded-lg border text-sm"
            style={{ borderColor: 'var(--t-soft-ring)' }}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="t-ink font-medium">
                {o.item_display_name}
                {o.recipient_kind === 'self' && (
                  <span className="text-xs t-muted"> (kept a copy)</span>
                )}
              </span>
              <span className="text-xs t-muted">
                {o.status === 'refunded'
                  ? 'refunded'
                  : o.fulfillment_status === 'submitted'
                    ? 'on its way'
                    : o.fulfillment_status === 'failed'
                      ? 'needs attention'
                      : 'processing'}
              </span>
            </div>
            {o.purchased_by && (
              <p className="text-xs t-muted mt-1">from {o.purchased_by}</p>
            )}
            {o.gift_message && (
              <p className="mt-2 text-sm t-ink italic">"{o.gift_message}"</p>
            )}
            {o.fulfillment_status === 'failed' && o.status === 'paid' && (
              <button
                type="button"
                onClick={() => retry(o.id)}
                disabled={retrying === o.id}
                className="mt-2 text-xs underline t-muted hover:t-ink disabled:opacity-50"
              >
                {retrying === o.id ? 'Retrying…' : `Retry fulfillment (${o.fulfillment_failure || 'failed'})`}
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}


// Pool controls: the due date (drives the 36-week guess-edit lock) and the
// gender-surprise toggle (opens boy/girl guessing — only sensible for
// families keeping it a surprise).
function PoolSettingsCard({ birth, onSaved }) {
  const [dueDate, setDueDate] = useState(birth.due_date || '');
  const [genderPool, setGenderPool] = useState(Boolean(birth.gender_pool_enabled));
  const [saving, setSaving] = useState(false);
  const [savedTick, setSavedTick] = useState(false);
  const [error, setError] = useState('');

  const lockDate = dueDate
    ? (() => {
        const [y, m, d] = dueDate.split('-').map(Number);
        const dt = new Date(y, m - 1, d);
        dt.setDate(dt.getDate() - 28);
        return dt.toLocaleDateString([], { month: 'long', day: 'numeric' });
      })()
    : null;

  const dirty =
    (dueDate || '') !== (birth.due_date || '')
    || genderPool !== Boolean(birth.gender_pool_enabled);

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      await api.updateBirth(birth.id, {
        ...(dueDate && dueDate !== birth.due_date ? { due_date: dueDate } : {}),
        gender_pool_enabled: genderPool,
      });
      await onSaved?.();
      setSavedTick(true);
      setTimeout(() => setSavedTick(false), 2000);
    } catch (err) {
      setError(err.message || 'Could not save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="card space-y-4">
      <div>
        <h3 className="text-lg font-semibold t-ink">The family pool 🎈</h3>
        <p className="text-sm t-muted">
          Everyone's guesses at the big stats — sealed until the arrival.
        </p>
      </div>

      <label className="block text-sm">
        <span className="t-muted">Due date</span>
        <div className="flex items-center gap-3 mt-1">
          <input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            className="t-date-input px-3 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink"
            style={{ borderColor: 'var(--t-soft-ring)' }}
          />
          {lockDate && (
            <span className="text-xs t-muted">
              guesses lock {lockDate} (36 weeks)
            </span>
          )}
        </div>
        {!dueDate && (
          <p className="text-xs t-faint mt-1">
            Without a due date, guesses stay editable until the birth.
          </p>
        )}
      </label>

      <label className="flex items-start gap-3 text-sm cursor-pointer">
        <input
          type="checkbox"
          checked={genderPool}
          onChange={(e) => setGenderPool(e.target.checked)}
          className="mt-0.5 h-4 w-4 accent-primary-600"
        />
        <span>
          <span className="t-ink font-medium">Keeping the gender a surprise?</span>
          <span className="block text-xs t-muted">
            Let family guess boy or girl in the pool. Leave this off if
            everyone already knows.
          </span>
        </span>
      </label>

      {error && <p className="text-xs text-red-500">{error}</p>}
      <button
        type="button"
        onClick={save}
        disabled={saving || !dirty}
        className="px-4 py-2 rounded-lg text-sm font-medium t-btn-accent disabled:opacity-50"
      >
        {saving ? 'Saving…' : savedTick ? 'Saved ✓' : 'Save pool settings'}
      </button>
    </section>
  );
}
