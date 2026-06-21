import { Link, Navigate, useNavigate } from 'react-router-dom';
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
        to={isParent ? `/b/${birth.slug}/manage` : `/b/${birth.slug}`}
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

export default function AccountPage() {
  const { isAuthenticated, loading, me, user, logout } = useAuth();
  const navigate = useNavigate();

  if (loading) return null;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  const births = (me?.families || []).flatMap((family) =>
    (family.births || []).map((birth) => ({ ...birth, role: family.role }))
  );

  // Families where you're a parent get a "Your family" block to manage
  // co-parents. Name the block only when there's more than one.
  const parentFamilies = (me?.families || []).filter((f) => PARENT_ROLES.includes(f.role));

  if (births.length === 0) return <Navigate to="/setup" replace />;

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
            lily
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
          <p className="text-sm text-gray-500 dark:text-gray-400">Your family's pages</p>
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

        {/* Birth cards */}
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
        </div>
      </div>
    </div>
  );
}
