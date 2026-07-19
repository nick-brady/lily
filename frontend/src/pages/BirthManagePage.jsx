import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { api, getToken } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useSSE } from '../hooks/useSSE';
import { contractionsFromEvents } from '../utils/statistics';
import { bumpCommentCount, updateReaction } from '../utils/engagement';
import CelebrationOverlay from '../components/CelebrationOverlay';
import ConnectionStatus from '../components/ConnectionStatus';
import ContractionButton from '../components/ContractionButton';
import HeaderMenu from '../components/HeaderMenu';
import Predictions from '../components/Predictions';
import StatsPanel from '../components/StatsPanel';
import Timeline from '../components/Timeline';
import TimeSeriesChart from '../components/TimeSeriesChart';
import UpdateForm from '../components/UpdateForm';
import { getTheme, themeVars } from '../utils/themes';

export default function BirthManagePage() {
  const { slug } = useParams();
  const { isAuthenticated, me, loading: authLoading, refreshMe } = useAuth();
  const [events, setEvents] = useState(() => new Map());
  const [birth, setBirth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('timeline');
  const [celebration, setCelebration] = useState(null); // { name } when playing
  const [confirmingBorn, setConfirmingBorn] = useState(false);
  const [markingBorn, setMarkingBorn] = useState(false);
  const [statsTimeRange, setStatsTimeRange] = useState('all');
  const [customRange, setCustomRange] = useState({ start: 0, end: 100 });

  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window === 'undefined') return false;
    return (
      localStorage.getItem('darkMode') === 'true'
      || window.matchMedia('(prefers-color-scheme: dark)').matches
    );
  });

  // Resolve the birth_id for `slug` from `/me` (the user must be a parent
  // of this birth in PR 2; PR 3 will add invitations).
  const birthFromMe = useMemo(() => {
    if (!me) return null;
    for (const family of me.families) {
      for (const b of family.births) {
        if (b.slug === slug) return b;
      }
    }
    return null;
  }, [me, slug]);

  const theme = getTheme((birth ?? birthFromMe)?.theme);
  const effectiveDark = darkMode || Boolean(theme.alwaysDark);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', effectiveDark);
    localStorage.setItem('darkMode', darkMode);
  }, [darkMode, effectiveDark]);

  useEffect(() => {
    if (!birthFromMe) return;
    setBirth(birthFromMe);
    setLoading(true);
    setError('');
    api.listTimeline(birthFromMe.id)
      .then((rows) => {
        setEvents(new Map(rows.map((e) => [e.id, e])));
      })
      .catch((err) => setError(err.message || 'Failed to load timeline'))
      .finally(() => setLoading(false));
  }, [birthFromMe]);

  const currentUserId = me?.user?.id;

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
    if (kind === 'appended' || kind === 'updated') {
      if (!data?.id) return;
      setEvents((prev) => {
        const next = new Map(prev);
        // Preserve existing engagement fields when an update arrives —
        // the broker payload doesn't include them.
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

  // EventSource can't send Authorization headers, so we pass the JWT as a
  // query parameter on the private stream URL. The backend accepts both.
  const streamUrl = useMemo(() => {
    if (!birth) return null;
    const token = getToken();
    const url = new URL(`${api.apiUrl}/birth/${birth.id}/stream`, window.location.origin);
    if (token) url.searchParams.set('token', token);
    return url.toString();
  }, [birth]);
  const { isConnected } = useSSE(streamUrl, handleSSE);

  const sortedEvents = useMemo(
    () => [...events.values()].sort((a, b) => a.sequence_id - b.sequence_id),
    [events],
  );
  const contractions = useMemo(() => contractionsFromEvents(sortedEvents), [sortedEvents]);
  const activeContraction = useMemo(
    () => sortedEvents.find((e) => e.event_type === 'contraction' && !e.payload?.end_time),
    [sortedEvents],
  );

  const timeBounds = useMemo(() => {
    const completed = contractions.filter((c) => c.end_time && c.duration_seconds);
    if (completed.length === 0) {
      const now = Date.now();
      return { min: now - 3600000, max: now };
    }
    const times = completed.map((c) => new Date(c.start_time).getTime());
    return { min: Math.min(...times), max: Math.max(...times, Date.now()) };
  }, [contractions]);

  const getCustomTimestamps = useCallback(() => {
    const range = timeBounds.max - timeBounds.min;
    return {
      start: new Date(timeBounds.min + (customRange.start / 100) * range),
      end: new Date(timeBounds.min + (customRange.end / 100) * range),
    };
  }, [timeBounds, customRange]);

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
      // our own SSE echo, which can lose the race against refreshMe().
      // Viewers get the same moment via the birth_update broadcast.
      setBirth((prev) => (prev ? { ...prev, ...updated } : prev));
      setCelebration({ name: updated.child_name || birth.child_name });
      // Refresh /me so the account page badge updates too.
      await refreshMe();
    } catch (err) {
      setError(err.message || 'Failed to mark baby born');
    } finally {
      setMarkingBorn(false);
      setConfirmingBorn(false);
    }
  };

  if (authLoading || (isAuthenticated && !me)) {
    return <CenteredMessage>Loading…</CenteredMessage>;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (!birthFromMe) {
    return (
      <CenteredMessage>
        You don't have access to this birth.{' '}
        <Link to="/" className="text-primary-600 hover:underline">Go home</Link>
      </CenteredMessage>
    );
  }
  if (loading) {
    return <CenteredMessage>Loading timeline…</CenteredMessage>;
  }

  const title = birth?.child_name
    ? `Welcoming ${birth.child_name}`
    : 'Welcoming Baby';

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
              <Link
                to={`/b/${slug}`}
                className="px-3 py-2 text-sm rounded-lg transition-opacity hover:opacity-80"
                style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
                title="Open public view"
              >
                Public view
              </Link>
              <DarkModeToggle darkMode={darkMode} setDarkMode={setDarkMode} />
              <HeaderMenu
                items={[
                  { label: 'Account', to: '/account' },
                  { label: 'Birth settings', to: `/b/${slug}/settings` },
                ]}
              />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <ConnectionStatus isConnected={isConnected} />
            <TabSwitcher activeTab={activeTab} setActiveTab={setActiveTab} />
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {error && (
          <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

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

        {birth.status !== 'born' ? (
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
        )}

        {activeTab === 'timeline' && (
          <>
            <UpdateForm birthId={birth.id} />
            <Timeline events={sortedEvents} canManage birthId={birth.id} />
          </>
        )}

        {activeTab === 'stats' && (
          <StatsTab
            birth={birth}
            contractions={contractions}
            statsTimeRange={statsTimeRange}
            setStatsTimeRange={setStatsTimeRange}
            customRange={customRange}
            setCustomRange={setCustomRange}
            getCustomTimestamps={getCustomTimestamps}
          />
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

function StatsTab({
  birth, contractions, statsTimeRange, setStatsTimeRange, customRange, setCustomRange, getCustomTimestamps,
}) {
  const timestamps = getCustomTimestamps();
  const formatTime = (date) =>
    date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <>
      <div className="card">
        <div className="flex justify-center mb-3">
          <div className="flex bg-gray-200 dark:bg-gray-700 rounded-lg p-1">
            {[
              { value: 'all', label: 'All Time' },
              { value: 'hour', label: 'Last Hour' },
              { value: 'custom', label: 'Custom' },
            ].map((option) => (
              <button
                key={option.value}
                onClick={() => setStatsTimeRange(option.value)}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                  statsTimeRange === option.value
                    ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {statsTimeRange === 'custom' && (
          <div className="flex flex-col items-center gap-3 pt-2">
            <div className="w-full max-w-sm space-y-4">
              <RangeSlider
                label="Start"
                timeLabel={formatTime(timestamps.start)}
                value={customRange.start}
                onChange={(val) =>
                  setCustomRange((prev) => ({ ...prev, start: Math.min(val, prev.end - 1) }))
                }
              />
              <RangeSlider
                label="End"
                timeLabel={formatTime(timestamps.end)}
                value={customRange.end}
                onChange={(val) =>
                  setCustomRange((prev) => ({ ...prev, end: Math.max(val, prev.start + 1) }))
                }
              />
            </div>
          </div>
        )}
      </div>

      <StatsPanel
        contractions={contractions}
        timeRange={statsTimeRange}
        customTimestamps={timestamps}
      />
      <div className="grid md:grid-cols-2 gap-6">
        <TimeSeriesChart
          contractions={contractions}
          type="duration"
          timeRange={statsTimeRange}
          customTimestamps={timestamps}
        />
        <TimeSeriesChart
          contractions={contractions}
          type="interval"
          timeRange={statsTimeRange}
          customTimestamps={timestamps}
        />
      </div>
      <Predictions birthId={birth?.id} status={birth?.status} isParent />
    </>
  );
}

function RangeSlider({ label, timeLabel, value, onChange }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
        <span>{label}</span>
        <span className="font-medium text-gray-700 dark:text-gray-300">{timeLabel}</span>
      </div>
      <input
        type="range"
        min="0"
        max="100"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-primary-500"
      />
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

function CenteredMessage({ children }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900">
      <div className="text-gray-500 dark:text-gray-400 text-center px-4">{children}</div>
    </div>
  );
}
