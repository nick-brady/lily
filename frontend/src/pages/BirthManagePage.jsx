import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { api, getToken } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useSSE } from '../hooks/useSSE';
import { contractionsFromEvents } from '../utils/statistics';
import ConnectionStatus from '../components/ConnectionStatus';
import ContractionButton from '../components/ContractionButton';
import Predictions from '../components/Predictions';
import StatsPanel from '../components/StatsPanel';
import Timeline from '../components/Timeline';
import TimeSeriesChart from '../components/TimeSeriesChart';
import UpdateForm from '../components/UpdateForm';

export default function BirthManagePage() {
  const { slug } = useParams();
  const { isAuthenticated, me, logout, loading: authLoading } = useAuth();
  const [events, setEvents] = useState(() => new Map());
  const [birth, setBirth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('timeline');
  const [statsTimeRange, setStatsTimeRange] = useState('all');
  const [customRange, setCustomRange] = useState({ start: 0, end: 100 });

  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window === 'undefined') return false;
    return (
      localStorage.getItem('darkMode') === 'true'
      || window.matchMedia('(prefers-color-scheme: dark)').matches
    );
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode);
    localStorage.setItem('darkMode', darkMode);
  }, [darkMode]);

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

  const handleSSE = useCallback((kind, data) => {
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
        next.set(data.id, data);
        return next;
      });
    }
  }, []);

  // EventSource can't send Authorization headers, so we pass the JWT as a
  // query parameter on the private stream URL. The backend accepts both.
  const streamUrl = useMemo(() => {
    if (!birth) return null;
    const token = getToken();
    const url = new URL(`${api.apiUrl}/birth/${birth.id}/stream`);
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
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900 transition-colors">
      <header className="bg-white dark:bg-gray-800 shadow-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-2">
            <h1
              className="text-2xl sm:text-3xl text-primary-600 dark:text-primary-400"
              style={{ fontFamily: "'Great Vibes', cursive" }}
            >
              {title}
            </h1>
            <div className="flex items-center gap-2">
              <Link
                to={`/b/${slug}`}
                className="px-3 py-2 text-sm rounded-lg bg-gray-100 dark:bg-gray-700
                           text-gray-600 dark:text-gray-300 hover:bg-gray-200
                           dark:hover:bg-gray-600 transition-colors"
                title="Open public view"
              >
                Public view
              </Link>
              <button
                onClick={logout}
                className="px-3 py-2 text-sm rounded-lg bg-gray-100 dark:bg-gray-700
                           text-gray-600 dark:text-gray-300 hover:bg-gray-200
                           dark:hover:bg-gray-600 transition-colors"
              >
                Sign out
              </button>
              <DarkModeToggle darkMode={darkMode} setDarkMode={setDarkMode} />
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

        {activeTab === 'timeline' && (
          <>
            <UpdateForm birthId={birth.id} />
            <Timeline events={sortedEvents} canManage birthId={birth.id} />
          </>
        )}

        {activeTab === 'stats' && (
          <StatsTab
            contractions={contractions}
            statsTimeRange={statsTimeRange}
            setStatsTimeRange={setStatsTimeRange}
            customRange={customRange}
            setCustomRange={setCustomRange}
            getCustomTimestamps={getCustomTimestamps}
          />
        )}
      </main>

      <footer className="py-8 text-center text-sm text-gray-400 dark:text-gray-600">
        <span style={{ fontFamily: "'Great Vibes', cursive", fontSize: '1.25rem' }}>
          Made with love
        </span>
      </footer>
    </div>
  );
}

function StatsTab({
  contractions, statsTimeRange, setStatsTimeRange, customRange, setCustomRange, getCustomTimestamps,
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
      <Predictions />
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
    <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
      {['timeline', 'stats'].map((tab) => (
        <button
          key={tab}
          onClick={() => setActiveTab(tab)}
          className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors capitalize ${
            activeTab === tab
              ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
              : 'text-gray-600 dark:text-gray-400'
          }`}
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
      className="p-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300
                 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
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
