import { useEffect, useMemo, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { getTheme, themeVars } from '../utils/themes';
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
              to={`/b/${slug}/manage`}
              className="px-3 py-2 text-sm rounded-lg transition-opacity hover:opacity-80"
              style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
            >
              Manage
            </Link>
            <HeaderMenu
              items={[
                { label: 'Account', to: '/account' },
                { label: 'Public view', to: `/b/${slug}` },
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

function CenteredMessage({ children }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900">
      <div className="text-gray-500 dark:text-gray-400 text-center px-4">{children}</div>
    </div>
  );
}
