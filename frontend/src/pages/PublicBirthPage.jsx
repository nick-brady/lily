import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api, getToken } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useSSE } from '../hooks/useSSE';
import CelebrationOverlay from '../components/CelebrationOverlay';
import ConnectionStatus from '../components/ConnectionStatus';
import Timeline from '../components/Timeline';
import Predictions from '../components/Predictions';
import GiftGallery from '../components/GiftGallery';
import { bumpCommentCount, updateReaction } from '../utils/engagement';
import { getTheme, themeVars } from '../utils/themes';

export default function PublicBirthPage() {
  const { slug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [giftBanner, setGiftBanner] = useState('');
  const { isAuthenticated, me } = useAuth();
  const [birth, setBirth] = useState(null);
  const [events, setEvents] = useState(() => new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [celebration, setCelebration] = useState(null);

  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window === 'undefined') return false;
    return (
      localStorage.getItem('darkMode') === 'true'
      || window.matchMedia('(prefers-color-scheme: dark)').matches
    );
  });

  const theme = getTheme(birth?.theme);
  const effectiveDark = darkMode || Boolean(theme.alwaysDark);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', effectiveDark);
    localStorage.setItem('darkMode', darkMode);
  }, [darkMode, effectiveDark]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([api.getPublicBirth(slug), api.listPublicTimeline(slug)])
      .then(([b, rows]) => {
        if (cancelled) return;
        setBirth(b);
        setEvents(new Map(rows.map((e) => [e.id, e])));
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load birth');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // Re-fetch when the user signs in / out so the audience-widened
    // timeline is reloaded with the new role.
  }, [slug, isAuthenticated]);

  const currentUserId = me?.user?.id;

  // Returning from a gift checkout: confirm server-side (dev path; the
  // webhook is the prod source of truth) and strip the param.
  useEffect(() => {
    const sessionId = searchParams.get('gift_session');
    if (!sessionId) return;
    const next = new URLSearchParams(searchParams);
    next.delete('gift_session');
    setSearchParams(next, { replace: true });
    api
      .confirmGift(slug, sessionId)
      .then((res) => {
        if (res.status === 'fulfilled' || res.status === 'already_processed') {
          setGiftBanner('Your gift is on its way — thank you 🤍');
        } else if (res.status === 'refunded') {
          setGiftBanner(
            'Someone beat you to this gift — your payment has been refunded.',
          );
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, searchParams]);

  const handleSSE = useCallback((kind, data) => {
    if (kind === 'birth_update') {
      setBirth((prev) => {
        if (!prev) return prev;
        if (data.status === 'born' && prev.status !== 'born') {
          setCelebration({ name: data.child_name || prev.child_name });
        }
        return {
          ...prev,
          status: data.status,
          birth_started_at: data.birth_started_at,
          birth_completed_at: data.birth_completed_at,
        };
      });
      return;
    }
    if (kind === 'deleted') {
      const id = data?.id;
      setEvents((prev) => {
        if (!id || !prev.has(id)) return prev;
        const next = new Map(prev);
        next.delete(id);
        return next;
      });
      return;
    }
    if ((kind === 'appended' || kind === 'updated') && data?.id) {
      // Public stream is already audience-filtered on the server.
      setEvents((prev) => {
        const next = new Map(prev);
        const existing = next.get(data.id);
        next.set(data.id, {
          reactions: existing?.reactions || {},
          comment_count: existing?.comment_count ?? 0,
          ...data,
        });
        return next;
      });
      return;
    }
    if (kind === 'reaction_added' || kind === 'reaction_removed') {
      const { event_id, kind: reactionKind, user_id } = data || {};
      if (!event_id || !reactionKind) return;
      const delta = kind === 'reaction_added' ? 1 : -1;
      const isMyAction = !!currentUserId && user_id === currentUserId;
      setEvents((prev) => updateReaction(prev, event_id, reactionKind, delta, isMyAction));
      return;
    }
    if (kind === 'comment_added') {
      const eventId = data?.event_id;
      if (!eventId) return;
      setEvents((prev) => bumpCommentCount(prev, eventId, 1));
      return;
    }
    if (kind === 'comment_deleted') {
      const eventId = data?.event_id;
      if (!eventId) return;
      setEvents((prev) => bumpCommentCount(prev, eventId, -1));
    }
  }, [currentUserId]);

  const streamUrl = useMemo(() => {
    if (!birth) return null;
    const url = new URL(`${api.apiUrl}/b/${slug}/stream`, window.location.origin);
    const token = getToken();
    if (token) url.searchParams.set('token', token);
    return url.toString();
  }, [birth, slug, isAuthenticated]);
  const { isConnected } = useSSE(streamUrl, handleSSE);

  const sortedEvents = useMemo(
    () => [...events.values()].sort((a, b) => a.sequence_id - b.sequence_id),
    [events],
  );

  const canManageThisBirth = useMemo(() => {
    if (!me || !birth) return false;
    for (const family of me.families) {
      if (family.role === 'owner' || family.role === 'co_parent') {
        for (const b of family.births) {
          if (b.id === birth.id) return true;
        }
      }
    }
    return false;
  }, [me, birth]);

  const title = birth?.child_name
    ? `Welcoming ${birth.child_name}`
    : 'Welcoming Baby';

  useEffect(() => {
    if (birth?.child_name) {
      document.title = `Welcoming ${birth.child_name}`;
    }
    return () => { document.title = 'Arrival Story'; };
  }, [birth?.child_name]);

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
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-2">
            <h1 className="t-display" style={{ fontSize: 'var(--t-title-size)' }}>
              {title}
            </h1>
            <div className="flex items-center gap-2">
              {canManageThisBirth && (
                <Link
                  to={`/b/${slug}/manage`}
                  className="px-3 py-2 text-sm rounded-lg text-white font-medium transition-colors"
                  style={{ backgroundColor: 'var(--t-accent)' }}
                >
                  Manage
                </Link>
              )}
              {isAuthenticated ? (
                <Link
                  to="/account"
                  className="px-3 py-2 text-sm rounded-lg transition-opacity hover:opacity-80"
                  style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
                  title="Back to your account"
                >
                  Home
                </Link>
              ) : (
                <Link
                  to="/login"
                  className="px-3 py-2 text-sm rounded-lg transition-opacity hover:opacity-80"
                  style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
                >
                  Sign in
                </Link>
              )}
              <DarkModeToggle darkMode={darkMode} setDarkMode={setDarkMode} />
            </div>
          </div>
          <ConnectionStatus isConnected={isConnected} />
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {giftBanner && (
          <div
            className="card flex items-center gap-3 py-3"
            style={{ backgroundColor: 'var(--t-soft-bg)' }}
          >
            <span className="text-lg">🎁</span>
            <p className="text-sm" style={{ color: 'var(--t-soft-text)' }}>
              {giftBanner}
            </p>
          </div>
        )}
        {error && (
          <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}
        {!loading && birth?.status === 'in_labor' && (
          <div
            className="card flex items-center gap-3 py-3"
            style={{ backgroundColor: 'var(--t-soft-bg)' }}
          >
            <span className="h-2.5 w-2.5 rounded-full animate-pulse" style={{ backgroundColor: 'var(--t-dot)' }} />
            <p className="text-sm" style={{ color: 'var(--t-soft-text)' }}>
              Something's happening — {birth.child_name ? `${birth.child_name}'s` : 'the'} family is timing contractions. Following along 🤍
            </p>
          </div>
        )}

        {!loading && birth?.status === 'born' && (
          <section className="card text-center py-8">
            <div className="text-4xl mb-2">👶</div>
            <h2 className="t-display" style={{ fontSize: '2rem', lineHeight: 1.15 }}>
              {birth.child_name ? `${birth.child_name} is here` : 'Baby is here'} 🤍
            </h2>
            {birth.birth_completed_at && (
              <p className="text-sm t-muted mt-2">
                Born {new Date(birth.birth_completed_at).toLocaleString([], {
                  dateStyle: 'long',
                  timeStyle: 'short',
                })}
              </p>
            )}
          </section>
        )}

        {!loading && birth && (
          <Predictions
            slug={slug}
            status={birth.status}
            isParent={canManageThisBirth}
          />
        )}

        {loading ? (
          <p className="text-center t-muted py-12">
            Loading timeline…
          </p>
        ) : (
          <Timeline events={sortedEvents} slug={slug} />
        )}

        {!loading && birth && isAuthenticated && (
          <MemberGifts birthId={birth.id} isParent={canManageThisBirth} />
        )}
      </main>

      <footer
        className="py-8 text-center text-sm"
        style={{ borderTop: '1px solid var(--t-divider)' }}
      >
        <span className="t-display" style={{ fontSize: '1.25rem', opacity: 0.75 }}>
          Made with love
        </span>
      </footer>

      {celebration && (
        <CelebrationOverlay
          childName={celebration.name}
          onDone={() => setCelebration(null)}
        />
      )}
    </div>
  );
}

function DarkModeToggle({ darkMode, setDarkMode }) {
  return (
    <button
      onClick={() => setDarkMode(!darkMode)}
      className="p-2 rounded-lg transition-opacity hover:opacity-80"
      style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
    >
      {darkMode ? (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
      ) : (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
        </svg>
      )}
    </button>
  );
}


// Gifts are member-only (the API 403s non-members); probe once and render
// the gallery only for family members, so Aunt-Linda-before-joining sees
// nothing rather than an error.
function MemberGifts({ birthId, isParent }) {
  const [isMember, setIsMember] = useState(null);
  useEffect(() => {
    let cancelled = false;
    api
      .listGifts(birthId)
      .then(() => !cancelled && setIsMember(true))
      .catch(() => !cancelled && setIsMember(false));
    return () => {
      cancelled = true;
    };
  }, [birthId]);
  if (!isMember) return null;
  return (
    <>
      {/* a quiet seam where the story ends and the keepsakes begin */}
      <div className="flex items-center gap-4 px-10 pt-2" aria-hidden="true">
        <div className="flex-1" style={{ borderTop: '1px solid var(--t-divider)' }} />
        <span
          className="w-1.5 h-1.5 rounded-full"
          style={{ backgroundColor: 'var(--t-dot)' }}
        />
        <div className="flex-1" style={{ borderTop: '1px solid var(--t-divider)' }} />
      </div>
      <GiftGallery birthId={birthId} isParent={isParent} />
    </>
  );
}
