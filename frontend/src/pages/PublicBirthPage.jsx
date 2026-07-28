import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useSSE } from '../hooks/useSSE';
import { useDarkMode } from '../hooks/useDarkMode';
import CelebrationOverlay from '../components/CelebrationOverlay';
import ConnectionStatus from '../components/ConnectionStatus';
import ContractionButton from '../components/ContractionButton';
import DarkModeToggle from '../components/DarkModeToggle';
import GiftGallery from '../components/GiftGallery';
import HeaderMenu from '../components/HeaderMenu';
import PoolPill from '../components/PoolPill';
import StatsTab from '../components/StatsTab';
import Timeline from '../components/Timeline';
import UpdateForm from '../components/UpdateForm';
import { bumpCommentCount, updateReaction } from '../utils/engagement';
import { getTheme, themeVars } from '../utils/themes';

// THE birth page — one page for every role. Anonymous visitors get the
// preview; signed-in family sees the timeline; parents additionally get
// the labor tooling (contraction timer, composer, Baby Born, stats)
// rendered inline behind `canManageThisBirth`. Reads go through the slug
// endpoints for everyone (the server widens audience scopes by role);
// parent writes use the id endpoints, which enforce parenthood.
export default function PublicBirthPage() {
  const { slug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [giftBanner, setGiftBanner] = useState('');
  const { isAuthenticated, loading: authLoading, me, refreshMe } = useAuth();
  const [birth, setBirth] = useState(null);
  const [events, setEvents] = useState(() => new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [celebration, setCelebration] = useState(null);
  const [activeTab, setActiveTab] = useState('timeline');
  const [confirmingBorn, setConfirmingBorn] = useState(false);
  const [markingBorn, setMarkingBorn] = useState(false);

  const theme = getTheme(birth?.theme);
  const { darkMode, setDarkMode, effectiveDark } = useDarkMode(theme.alwaysDark);

  useEffect(() => {
    if (authLoading) return undefined;
    let cancelled = false;
    setLoading(true);
    // Viewing is auth-gated: `/b/{slug}` alone is the anonymous preview
    // (name, status, theme); the timeline needs a session.
    const loads = isAuthenticated
      ? Promise.all([api.getPublicBirth(slug), api.listPublicTimeline(slug)])
      : api.getPublicBirth(slug).then((b) => [b, []]);
    loads
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
  }, [slug, isAuthenticated, authLoading]);

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
      // The stream is already audience-filtered on the server. Preserve
      // engagement fields across updates — the broker payload drops them.
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
    if (!birth || !isAuthenticated) return null;
    // The httpOnly session cookie rides the same-origin EventSource on its
    // own — no token in the URL (or the access logs). One stream for every
    // role; the server filters events by the viewer's audience scopes.
    return new URL(`${api.apiUrl}/b/${slug}/stream`, window.location.origin).toString();
  }, [birth, slug, isAuthenticated]);
  const { isConnected } = useSSE(streamUrl, handleSSE);

  const sortedEvents = useMemo(
    () => [...events.values()].sort((a, b) => a.sequence_id - b.sequence_id),
    [events],
  );

  const activeContraction = useMemo(
    () => sortedEvents.find((e) => e.event_type === 'contraction' && !e.payload?.end_time),
    [sortedEvents],
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

  // ---- Parent actions (id endpoints; the server enforces parenthood) ----

  const handleStart = async () => {
    try {
      await api.startContraction(birth.id);
    } catch (err) {
      setError(err.message || 'Failed to start contraction');
    }
  };

  const handleStop = async () => {
    if (!activeContraction) return;
    try {
      await api.stopContraction(birth.id, activeContraction.id, new Date().toISOString());
    } catch (err) {
      setError(err.message || 'Failed to stop contraction');
    }
  };

  const handleCancel = async () => {
    if (!activeContraction) return;
    try {
      await api.deleteEvent(birth.id, activeContraction.id);
    } catch (err) {
      setError(err.message || 'Failed to cancel contraction');
    }
  };

  const handleBorn = async () => {
    setMarkingBorn(true);
    setError('');
    try {
      const updated = await api.markBorn(birth.id);
      // Celebrate immediately for the parent who tapped — don't rely on
      // our own SSE echo. Viewers get the moment via birth_update.
      setBirth((prev) => (prev ? { ...prev, ...updated } : prev));
      setCelebration({ name: updated.child_name || birth.child_name });
      // Keep the account page badge fresh; fire-and-forget on purpose —
      // page data is keyed on the slug, so this triggers no refetch.
      refreshMe().catch(() => {});
    } catch (err) {
      setError(err.message || 'Failed to mark baby born');
    } finally {
      setMarkingBorn(false);
      setConfirmingBorn(false);
    }
  };

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
              {!canManageThisBirth && (
                isAuthenticated ? (
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
                )
              )}
              <DarkModeToggle darkMode={darkMode} setDarkMode={setDarkMode} />
              {canManageThisBirth && (
                <HeaderMenu
                  items={[
                    { label: 'Account', to: '/account' },
                    { label: 'Birth settings', to: `/b/${slug}/settings` },
                  ]}
                />
              )}
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <ConnectionStatus isConnected={isConnected} />
              {!loading && birth && isAuthenticated && (
                <PoolPill
                  slug={slug}
                  birthId={canManageThisBirth ? birth.id : undefined}
                  status={birth.status}
                  isParent={canManageThisBirth}
                  themeStyle={themeVars(theme, effectiveDark)}
                />
              )}
            </div>
            {canManageThisBirth && (
              <TabSwitcher activeTab={activeTab} setActiveTab={setActiveTab} />
            )}
          </div>
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

        {/* Viewers get the ambient labor banner; parents get the timer
            itself instead. */}
        {!loading && !canManageThisBirth && birth?.status === 'in_labor' && (
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

        {!loading && !canManageThisBirth && birth?.status === 'born' && (
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

        {/* ---- Parent tooling ---- */}

        {/* The birth happened; the page steps back into keepsake mode — no
            labor tooling after "born". A contraction still running when the
            arrival was announced stays visible until it's stopped or
            cancelled, so it can't get stranded open. */}
        {!loading && canManageThisBirth
          && ((birth.status !== 'born' && birth.status !== 'archived') || activeContraction) ? (
          <section className="card relative flex justify-center py-8">
            {activeContraction && (
              <button
                onClick={handleCancel}
                className="absolute top-3 right-3 p-2 text-gray-400 hover:text-red-500
                           dark:text-gray-500 dark:hover:text-red-400 transition-colors"
                title="Cancel contraction"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
            <ContractionButton
              onStart={handleStart}
              onStop={handleStop}
              startTime={activeContraction?.occurred_at || null}
            />
          </section>
        ) : null}

        {!loading && canManageThisBirth && (
          birth.status !== 'born' ? (
            <section className="card flex flex-col items-center gap-3 py-5">
              {confirmingBorn ? (
                <>
                  <p className="text-sm t-ink text-center">
                    Announce the arrival to everyone watching?
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={handleBorn}
                      disabled={markingBorn}
                      className="px-5 py-2.5 rounded-full t-btn-accent font-medium disabled:opacity-50"
                    >
                      {markingBorn ? 'Announcing…' : '🎉 Baby Born!'}
                    </button>
                    <button
                      onClick={() => setConfirmingBorn(false)}
                      disabled={markingBorn}
                      className="px-4 py-2.5 rounded-full text-sm t-muted hover:opacity-80"
                    >
                      Not yet
                    </button>
                  </div>
                </>
              ) : (
                <button
                  onClick={() => setConfirmingBorn(true)}
                  className="px-6 py-3 rounded-full font-semibold text-base transition-opacity hover:opacity-90"
                  style={{ backgroundColor: 'var(--t-accent)', color: '#fff' }}
                >
                  👶 Baby Born!
                </button>
              )}
            </section>
          ) : (
            <section className="card text-center py-5">
              <p className="t-display" style={{ fontSize: '1.5rem' }}>
                {birth.child_name || 'Baby'} is here 🤍
              </p>
              {birth.birth_completed_at && (
                <p className="text-sm t-muted mt-1">
                  Born {new Date(birth.birth_completed_at).toLocaleString([], {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  })}
                </p>
              )}
            </section>
          )
        )}

        {/* ---- Shared page content (the pool lives in the header pill
            and on the parent stats tab — never on the timeline) ---- */}

        {loading ? (
          <p className="text-center t-muted py-12">
            Loading timeline…
          </p>
        ) : !isAuthenticated ? (
          <TimelinePreview slug={slug} childName={birth?.child_name} />
        ) : canManageThisBirth && activeTab === 'stats' ? (
          <StatsTab events={sortedEvents} birthId={birth.id} status={birth.status} />
        ) : canManageThisBirth ? (
          <>
            <UpdateForm birthId={birth.id} />
            <Timeline events={sortedEvents} canManage birthId={birth.id} />
          </>
        ) : (
          <Timeline events={sortedEvents} slug={slug} />
        )}

        {/* Keepsake gifts are made FROM the story — they exist only once
            the birth is done (Day Two is the moment), never as a shop on
            a page that's still waiting. */}
        {!loading && birth && isAuthenticated && activeTab === 'timeline'
          && birth.status === 'born' && (
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

function TabSwitcher({ activeTab, setActiveTab }) {
  return (
    <div className="flex rounded-lg p-1" style={{ backgroundColor: 'var(--t-soft-bg)' }}>
      {['timeline', 'stats'].map((tab) => (
        <button
          key={tab}
          onClick={() => setActiveTab(tab)}
          className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors capitalize ${
            activeTab === tab ? 'shadow-sm' : ''
          }`}
          style={activeTab === tab
            ? { backgroundColor: 'var(--t-card-bg)', color: 'var(--t-ink)' }
            : { color: 'var(--t-soft-text)' }}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}

// The unauthenticated preview (v1 requirement): the emotional hook —
// the name, the moment — before the email ask, never a login wall as the
// first thing a QR-scanning great-aunt sees. The blurred bars are
// decorative; no real content is fetched (the API enforces that).
function TimelinePreview({ slug, childName }) {
  const widths = [78, 92, 64, 85, 70];
  return (
    <section className="card relative overflow-hidden py-8">
      <div aria-hidden="true" className="space-y-5 px-6" style={{ filter: 'blur(6px)', opacity: 0.45 }}>
        {widths.map((w, i) => (
          <div key={i} className="flex items-start gap-3">
            <div
              className="w-8 h-8 rounded-full shrink-0"
              style={{ backgroundColor: 'var(--t-soft-bg)' }}
            />
            <div className="flex-1 space-y-2">
              <div
                className="h-3 rounded-full"
                style={{ width: `${w}%`, backgroundColor: 'var(--t-soft-bg)' }}
              />
              <div
                className="h-3 rounded-full"
                style={{ width: `${Math.max(30, w - 35)}%`, backgroundColor: 'var(--t-soft-bg)' }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-6">
        <p className="t-display mb-1" style={{ fontSize: '1.5rem' }}>
          {childName ? `Follow ${childName}'s story` : 'Follow the story'}
        </p>
        <p className="text-sm t-muted mb-4 max-w-xs">
          Photos, milestones, and the moments as they happen — shared with
          family and friends.
        </p>
        <Link
          to={`/login?next=/b/${slug}`}
          className="px-5 py-3 rounded-lg text-white font-medium transition-colors"
          style={{ backgroundColor: 'var(--t-accent)' }}
        >
          Sign in to follow along
        </Link>
      </div>
    </section>
  );
}

// Gifts are member-only (the API 403s non-members); probe once and render
// the gallery only for family members with actual artwork to show — a
// birth whose gifts haven't rendered yet gets no empty shop, and
// Aunt-Linda-before-joining sees nothing rather than an error.
function MemberGifts({ birthId, isParent }) {
  const [hasGifts, setHasGifts] = useState(null);
  useEffect(() => {
    let cancelled = false;
    api
      .listGifts(birthId)
      .then((gallery) => {
        if (cancelled) return;
        setHasGifts(
          (gallery.items || []).some((it) => (it.renderings || []).length > 0),
        );
      })
      .catch(() => !cancelled && setHasGifts(false));
    return () => {
      cancelled = true;
    };
  }, [birthId]);
  if (!hasGifts) return null;
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
