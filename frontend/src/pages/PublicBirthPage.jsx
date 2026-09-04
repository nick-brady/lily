import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import Modal from '../components/Modal';
import { NO_TAPS, recordSilentStop, secondsSince } from '../utils/stopTaps';
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

// Milestones that are only possible once the baby is out. Posting one of these
// while the birth isn't marked is proof the announcement got skipped.
const POST_BIRTH_MILESTONES = {
  first_hold: 'a First Hold',
  first_feed: 'a First Feed',
  name_announced: 'a Name Announced',
  going_home: 'a Going Home',
};

// THE birth page — one page for every role that can see it, and it's a
// private page: invited family sees the timeline, parents additionally get
// the labor tooling (contraction timer, composer, Baby Born, stats)
// rendered inline behind `canManageThisBirth`, and everyone else — signed
// in or not — gets a plain not-found. The preview that used to live here
// for strangers moved to the invite screen, where a token vouches for the
// person asking. Reads go through the slug endpoints (the server widens
// audience scopes by role); parent writes use the id endpoints, which
// enforce parenthood.
export default function PublicBirthPage() {
  const { slug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [giftBanner, setGiftBanner] = useState('');
  const { isAuthenticated, loading: authLoading, me, refreshMe } = useAuth();
  const [birth, setBirth] = useState(null);
  const [events, setEvents] = useState(() => new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notFound, setNotFound] = useState(false);
  const [celebration, setCelebration] = useState(null);
  const [activeTab, setActiveTab] = useState('timeline');
  // Set by the arrival nudge to pop the composer straight into born mode.
  const [markBornFromNudge, setMarkBornFromNudge] = useState(false);

  const theme = getTheme(birth?.theme);
  const { darkMode, setDarkMode, effectiveDark } = useDarkMode(theme.alwaysDark);

  useEffect(() => {
    if (authLoading) return undefined;
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    // The page is private: every one of these 404s unless you're a member,
    // whether or not you're signed in. There's no anonymous shape to load
    // — the preview a not-yet-member sees lives on the invite screen.
    Promise.all([api.getPublicBirth(slug), api.listPublicTimeline(slug)])
      .then(([b, rows]) => {
        if (cancelled) return;
        setBirth(b);
        setEvents(new Map(rows.map((e) => [e.id, e])));
      })
      .catch((err) => {
        if (cancelled) return;
        // A page you can't see is a page that isn't there, as far as this
        // screen knows — the API deliberately gives non-members the same
        // 404 as an unused slug, and we must not undo that by hinting
        // that signing in would help.
        if (err.status === 404 || err.status === 401) setNotFound(true);
        else setError(err.message || 'Could not load birth');
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
    // A loaded birth means a member: the API gives everyone else a 404.
    if (!birth) return null;
    // The httpOnly session cookie rides the same-origin EventSource on its
    // own — no token in the URL (or the access logs). One stream for every
    // role; the server filters events by the viewer's audience scopes.
    return new URL(`${api.apiUrl}/b/${slug}/stream`, window.location.origin).toString();
  }, [birth, slug]);
  const { status: syncStatus } = useSSE(streamUrl, handleSSE);

  const sortedEvents = useMemo(
    () => [...events.values()].sort((a, b) => a.sequence_id - b.sequence_id),
    [events],
  );

  const activeContraction = useMemo(
    () => sortedEvents.find((e) => e.event_type === 'contraction' && !e.payload?.end_time),
    [sortedEvents],
  );

  // The forget-to-tap safety net. Everything downstream of the birth hangs off
  // one flip that someone has to remember in the least rememberable hour of
  // their life: no artwork is generated, the guessing jar never settles, the
  // measurements form never appears, and nobody watching gets the moment.
  //
  // These milestones can't happen before the baby does, so posting one while
  // the birth still isn't marked is a contradiction the page can see. We ask
  // rather than flip on our own: a First Hold is *after* the arrival, and its
  // timestamp isn't the birth time — which is the number that ends up printed
  // on the keepsake. So the nudge opens the real form, with its real question.
  const arrivalHint = useMemo(() => {
    if (!birth || birth.status === 'born' || birth.status === 'archived') return null;
    const proof = sortedEvents.find(
      (e) => e.event_type === 'milestone' && POST_BIRTH_MILESTONES[(e.payload || {}).kind],
    );
    return proof ? POST_BIRTH_MILESTONES[proof.payload.kind] : null;
  }, [birth, sortedEvents]);

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

  // A tap, until the server has answered it. The button was the only one in
  // the app without this, and it is the one where it matters: both parents
  // are watching, and the answer used to arrive by way of the event stream,
  // leaving the button saying START to both of them for the whole round trip.
  const [contractionPending, setContractionPending] = useState(false);
  // Set when the server refuses a stop because the contraction has only just
  // begun: {startedSecondsAgo}. Holding it opens the dialog.
  const [justStarted, setJustStarted] = useState(null);
  // The cancel × used to delete a running contraction outright, from a 40px
  // target, with no confirmation.
  const [confirmCancel, setConfirmCancel] = useState(false);
  // STOP taps the server quietly declined (a contraction under five seconds
  // old). The third one on the same contraction opens the dialog above, so
  // someone who started it by accident isn't left hammering a button that
  // seems to do nothing. See utils/stopTaps.js.
  const silentStops = useRef(NO_TAPS);

  // The server's own answer, applied at once rather than waited for over the
  // event stream. Not an optimistic guess — the same object SSE would bring,
  // a few hundred milliseconds earlier.
  const applyEvent = (event) => {
    if (!event?.id) return;
    setEvents((prev) => {
      const next = new Map(prev);
      const existing = next.get(event.id);
      next.set(event.id, {
        reactions: existing?.reactions || {},
        comment_count: existing?.comment_count ?? 0,
        ...event,
      });
      return next;
    });
  };

  const handleStart = async () => {
    if (contractionPending) return;
    setContractionPending(true);
    try {
      // If their partner was a moment quicker, this returns that contraction
      // rather than opening a second one.
      applyEvent(await api.startContraction(birth.id));
    } catch (err) {
      setError(err.message || 'Failed to start contraction');
    } finally {
      setContractionPending(false);
    }
  };

  const handleStop = async () => {
    if (!activeContraction || contractionPending) return;
    setContractionPending(true);
    try {
      const result = await api.stopContraction(birth.id, activeContraction.id);
      applyEvent(result);
      if (!result?.payload?.end_time) {
        // still running: the server treated the tap as a no-op
        const next = recordSilentStop(silentStops.current, result.id);
        silentStops.current = next.tally;
        if (next.prompt) {
          setJustStarted({ startedSecondsAgo: secondsSince(result.occurred_at) });
        }
      }
    } catch (err) {
      if (err.code === 'just_started') {
        setJustStarted({ startedSecondsAgo: err.detail?.started_seconds_ago ?? 0 });
      } else {
        setError(err.message || 'Failed to stop contraction');
      }
    } finally {
      setContractionPending(false);
    }
  };

  const discardContraction = async () => {
    if (!activeContraction) return;
    setContractionPending(true);
    try {
      await api.deleteEvent(birth.id, activeContraction.id);
      setJustStarted(null);
      setConfirmCancel(false);
    } catch (err) {
      setError(err.message || 'Failed to discard contraction');
    } finally {
      setContractionPending(false);
    }
  };

  // Called by the composer's Baby Born! mode with the arrival time it
  // collected. Errors propagate: the composer keeps its form open and shows
  // why, rather than closing as if the family had been told.
  const handleBorn = async (occurredAtISO) => {
    const updated = await api.markBorn(
      birth.id,
      occurredAtISO ? { occurred_at: occurredAtISO } : {},
    );
    // Celebrate immediately for the parent who tapped — don't rely on
    // our own SSE echo. Viewers get the moment via birth_update.
    setBirth((prev) => (prev ? { ...prev, ...updated } : prev));
    setCelebration({ name: updated.child_name || birth.child_name });
    // Keep the account page badge fresh; fire-and-forget on purpose —
    // page data is keyed on the slug, so this triggers no refetch.
    refreshMe().catch(() => {});
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

  // Below every hook, so the early return can't change how many run.
  // Everything after this assumes a member looking at their own family's
  // page — nobody else gets here.
  if (notFound) return <PageNotFound />;

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
              {/* No "Sign in" variant: everyone who can see this page is
                  already signed in and on the family. */}
              {!canManageThisBirth && (
                <Link
                  to="/account"
                  className="px-3 py-2 text-sm rounded-lg transition-opacity hover:opacity-80"
                  style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
                  title="Back to your account"
                >
                  Home
                </Link>
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
              <ConnectionStatus status={syncStatus} />
              {!loading && birth && (
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
            role="status"
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
          <div role="alert" className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
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
                onClick={() => setConfirmCancel(true)}
                className="absolute top-2 right-2 p-3 text-gray-400 hover:text-red-500
                           dark:text-gray-500 dark:hover:text-red-400 transition-colors"
                aria-label="Cancel contraction"
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
              pending={contractionPending}
            />
          </section>
        ) : null}

        {/* Someone pressed stop moments after it began. Almost always it was
            a second thumb going for start — their partner was quicker, and
            nothing on their screen had said so yet. Under five seconds the
            server ignores it outright; this is the window just after, where
            it might have been meant. There is no "stop it here": the
            contractions recorded here run from fourteen seconds, so anything
            this short is a misfire, not a short contraction. */}
        {justStarted && (
          <Modal onClose={() => setJustStarted(null)}>
            <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-2">
              This contraction started {justStarted.startedSecondsAgo} seconds ago
            </h3>
            <p className="text-sm t-muted mb-5">
              If you both reached for the button, it&rsquo;s already being timed — keep
              going. Discard it only if it started by mistake.
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setJustStarted(null)}
                className="flex-1 py-2 rounded-lg t-btn-accent font-medium"
              >
                Keep timing
              </button>
              <button
                type="button"
                onClick={discardContraction}
                disabled={contractionPending}
                className="flex-1 py-2 rounded-lg bg-red-500 text-white font-medium
                           hover:bg-red-600 disabled:opacity-50"
              >
                Discard it
              </button>
            </div>
          </Modal>
        )}

        {confirmCancel && (
          <Modal onClose={() => setConfirmCancel(false)}>
            <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100 mb-2">
              Discard this contraction?
            </h3>
            <p className="text-sm t-muted mb-5">
              It won&rsquo;t be timed or counted. There&rsquo;s no undo.
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setConfirmCancel(false)}
                className="flex-1 py-2 rounded-lg border font-medium t-ink"
                style={{ borderColor: 'var(--t-soft-ring)' }}
              >
                Keep timing
              </button>
              <button
                type="button"
                onClick={discardContraction}
                disabled={contractionPending}
                className="flex-1 py-2 rounded-lg bg-red-500 text-white font-medium
                           hover:bg-red-600 disabled:opacity-50"
              >
                Discard it
              </button>
            </div>
          </Modal>
        )}

        {/* No card here for the birth. Announcing lives in the composer
            because it IS a timeline milestone, and the arrival reads as one
            too — the Born card in the story is the celebration. A banner up
            here only ever reflected `status`, so it had no controls of its
            own, and the undo it needed had to be a link parked on the happiest
            thing on the page. The milestone carries its own actions. */}

        {/* ---- Shared page content (the pool lives in the header pill
            and on the parent stats tab — never on the timeline) ---- */}

        {loading ? (
          <p className="text-center t-muted py-12">
            Loading timeline…
          </p>
        ) : canManageThisBirth && activeTab === 'stats' ? (
          <StatsTab events={sortedEvents} birthId={birth.id} status={birth.status} />
        ) : canManageThisBirth ? (
          <>
            {arrivalHint && (
              <ArrivalNudge
                hint={arrivalHint}
                onMark={() => setMarkBornFromNudge(true)}
              />
            )}
            {/* No gap: the composer and the story are one surface. It isn't a
                tool that happens to sit near the timeline — it's the top of
                the timeline, and what you write lands directly beneath it. */}
            <div>
              <UpdateForm
                birthId={birth.id}
                childName={birth.child_name}
                onBabyBorn={birth.status !== 'born' ? handleBorn : null}
                openBornMode={markBornFromNudge}
                onBornModeOpened={() => setMarkBornFromNudge(false)}
                joinedBelow
              />
              <Timeline
                events={sortedEvents}
                canManage
                birthId={birth.id}
                joinedAbove
                childName={birth.child_name}
              />
            </div>
          </>
        ) : (
          <Timeline events={sortedEvents} slug={slug} childName={birth.child_name} />
        )}

        {/* Keepsake gifts are made FROM the story — they exist only once
            the birth is done (Day Two is the moment), never as a shop on
            a page that's still waiting. */}
        {!loading && birth && activeTab === 'timeline'
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

// Deliberately not dismissible: the cost of ignoring it is the whole back half
// of the product silently not happening. It disappears the moment the birth is
// marked, which is the only thing that actually resolves it.
function ArrivalNudge({ hint, onMark }) {
  return (
    <div
      className="card flex flex-wrap items-center gap-3 py-4"
      style={{ backgroundColor: 'var(--t-soft-bg)', borderColor: 'var(--t-soft-ring)' }}
    >
      <span className="text-2xl leading-none">👶</span>
      <div className="flex-1 min-w-[16rem]">
        <p className="font-semibold t-ink">
          You posted {hint} — are they here?
        </p>
        <p className="text-sm t-muted">
          Marking the arrival tells everyone watching, settles the guessing jar,
          and starts the keepsake.
        </p>
      </div>
      <button
        type="button"
        onClick={onMark}
        className="px-5 py-2.5 rounded-full t-btn-accent font-semibold"
      >
        Mark it
      </button>
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

// What someone without a place on this page gets, and all they get.
//
// No baby's name, no "this is a private birth", no invitation to sign in,
// no suggestion to go ask the parents for access — the family invites who
// they want to invite, and anything warmer here would either confirm the
// page exists to a stranger who guessed a name, or send them knocking.
// Deliberately un-themed too: the theme belongs to a page they can't see.
function PageNotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900 px-4">
      <div className="text-center">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
          Page not found
        </h1>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          This link doesn't go anywhere.
        </p>
      </div>
    </div>
  );
}

// Gifts are member-only (the API 403s non-members); probe once and render
// the gallery only for family members with actual artwork to show — a
// birth whose gifts haven't rendered yet gets no empty shop, and
// Aunt-Linda-before-joining sees nothing rather than an error.
//
// The exception is the settling window: artwork deliberately waits a few
// hours after the arrival, so during it there's nothing to show but there IS
// something to say — and the parent's "make them now" escape hatch lives
// inside the gallery, so hiding the section would lock it away too.
function MemberGifts({ birthId, isParent }) {
  const [show, setShow] = useState(null);
  useEffect(() => {
    let cancelled = false;
    api
      .listGifts(birthId)
      .then((gallery) => {
        if (cancelled) return;
        const hasArtwork = (gallery.items || []).some(
          (it) => (it.renderings || []).length > 0,
        );
        const settling =
          gallery.artwork_ready_at != null
          && new Date(gallery.artwork_ready_at) > new Date();
        setShow(hasArtwork || settling);
      })
      .catch(() => !cancelled && setShow(false));
    return () => {
      cancelled = true;
    };
  }, [birthId]);
  if (!show) return null;
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
