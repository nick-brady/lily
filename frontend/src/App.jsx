import { useState, useEffect, useCallback, useMemo } from 'react';
import ContractionButton from './components/ContractionButton';
import Timeline from './components/Timeline';
import UpdateForm from './components/UpdateForm';
import TimeSeriesChart from './components/TimeSeriesChart';
import StatsPanel from './components/StatsPanel';
import Predictions from './components/Predictions';
import ConnectionStatus from './components/ConnectionStatus';
import LoginForm from './components/LoginForm';
import { useWebSocket } from './hooks/useWebSocket';
import { AuthProvider, useAuth } from './contexts/AuthContext';

const API_URL = import.meta.env.DEV ? 'http://localhost:8000' : '';

function AppContent() {
  const { isAdmin, logout, getAuthHeaders, loading: authLoading } = useAuth();
  const [showLoginForm, setShowLoginForm] = useState(false);
  const [feed, setFeed] = useState([]);
  const [contractions, setContractions] = useState([]);
  const [activeContraction, setActiveContraction] = useState(null);
  const [activeTab, setActiveTab] = useState('timeline'); // 'timeline' or 'stats'
  const [statsTimeRange, setStatsTimeRange] = useState('all'); // 'all', 'hour', or 'custom'
  const [customRange, setCustomRange] = useState({ start: 0, end: 100 }); // percentages of data range

  // Compute time bounds from contractions data
  const timeBounds = useMemo(() => {
    const completed = contractions.filter(c => c.end_time && c.duration_seconds);
    if (completed.length === 0) {
      const now = Date.now();
      return { min: now - 3600000, max: now }; // Default to last hour
    }
    const times = completed.map(c => new Date(c.start_time).getTime());
    return {
      min: Math.min(...times),
      max: Math.max(...times, Date.now())
    };
  }, [contractions]);

  // Convert percentage to timestamp
  const getCustomTimestamps = useCallback(() => {
    const range = timeBounds.max - timeBounds.min;
    return {
      start: new Date(timeBounds.min + (customRange.start / 100) * range),
      end: new Date(timeBounds.min + (customRange.end / 100) * range)
    };
  }, [timeBounds, customRange]);

  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('darkMode') === 'true' ||
        window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
  });
  const [loading, setLoading] = useState(true);

  // Fetch data from server
  const fetchData = useCallback(async () => {
    try {
      const [feedRes, contractionsRes] = await Promise.all([
        fetch(`${API_URL}/feed`),
        fetch(`${API_URL}/contractions`)
      ]);
      const feedData = await feedRes.json();
      const contractionsData = await contractionsRes.json();

      setFeed(feedData);
      setContractions(contractionsData);

      const active = contractionsData.find(c => !c.end_time);
      setActiveContraction(active || null);
    } catch (error) {
      console.error('Failed to fetch data:', error);
    }
  }, []);

  // Handle WebSocket messages
  const handleWsMessage = useCallback((message) => {
    if (message.type === 'contraction_new') {
      const contraction = message.data;
      setContractions(prev => {
        if (prev.some(c => c.id === contraction.id)) return prev;
        return [contraction, ...prev];
      });
      setFeed(prev => {
        const newItem = { feed_type: 'contraction', timestamp: contraction.start_time, ...contraction };
        if (prev.some(f => f.feed_type === 'contraction' && f.id === contraction.id)) return prev;
        return [newItem, ...prev].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      });
      if (!contraction.end_time) {
        setActiveContraction(contraction);
      }
    } else if (message.type === 'contraction_update') {
      const contraction = message.data;
      setContractions(prev => prev.map(c => c.id === contraction.id ? contraction : c));
      setFeed(prev => prev.map(f =>
        f.feed_type === 'contraction' && f.id === contraction.id
          ? { ...f, ...contraction }
          : f
      ));
      if (activeContraction?.id === contraction.id) {
        setActiveContraction(null);
      }
    } else if (message.type === 'contraction_delete') {
      setContractions(prev => prev.filter(c => c.id !== message.id));
      setFeed(prev => prev.filter(f => !(f.feed_type === 'contraction' && f.id === message.id)));
      if (activeContraction?.id === message.id) {
        setActiveContraction(null);
      }
    } else if (message.type === 'update_new') {
      const update = message.data;
      setFeed(prev => {
        if (prev.some(f => f.feed_type === update.type && f.id === update.id)) return prev;
        const newItem = { feed_type: update.type, timestamp: update.timestamp, ...update };
        return [newItem, ...prev].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      });
    } else if (message.type === 'update_edit') {
      const update = message.data;
      setFeed(prev => prev.map(f =>
        f.feed_type !== 'contraction' && f.id === update.id
          ? { ...f, content: update.content }
          : f
      ));
    } else if (message.type === 'update_delete') {
      setFeed(prev => prev.filter(f => !(f.feed_type !== 'contraction' && f.id === message.id)));
    }
  }, [activeContraction]);

  const { isConnected } = useWebSocket(handleWsMessage, fetchData);

  // Apply dark mode
  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode);
    localStorage.setItem('darkMode', darkMode);
  }, [darkMode]);

  // Fetch initial data
  useEffect(() => {
    const init = async () => {
      await fetchData();
      setLoading(false);
    };
    init();
  }, [fetchData]);

  const handleStart = async () => {
    const now = new Date().toISOString();
    try {
      const response = await fetch(`${API_URL}/contraction`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ start_time: now }),
      });
      const data = await response.json();
      setActiveContraction(data);
    } catch (error) {
      console.error('Failed to start contraction:', error);
    }
  };

  const handleStop = async () => {
    if (!activeContraction) return;
    const now = new Date().toISOString();
    try {
      await fetch(`${API_URL}/contraction/${activeContraction.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ end_time: now }),
      });
      setActiveContraction(null);
    } catch (error) {
      console.error('Failed to stop contraction:', error);
    }
  };

  const handleCancel = async () => {
    if (!activeContraction) return;
    try {
      await fetch(`${API_URL}/contraction/${activeContraction.id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      setActiveContraction(null);
    } catch (error) {
      console.error('Failed to cancel contraction:', error);
    }
  };

  const handleDelete = async (id, type) => {
    const endpoint = type === 'update' ? `/update/${id}` : `/contraction/${id}`;
    try {
      await fetch(`${API_URL}${endpoint}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
    } catch (error) {
      console.error('Failed to delete:', error);
    }
  };

  const handleToggleIgnore = async (id) => {
    try {
      await fetch(`${API_URL}/contraction/${id}/toggle-ignore`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
    } catch (error) {
      console.error('Failed to toggle ignore:', error);
    }
  };

  if (loading || authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100 dark:bg-gray-900">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900 transition-colors">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-2xl sm:text-3xl text-primary-600 dark:text-primary-400" style={{ fontFamily: "'Great Vibes', cursive" }}>
              Welcoming Lily Wren Brady
            </h1>
            <div className="flex items-center gap-2">
              {isAdmin ? (
                <button
                  onClick={logout}
                  className="px-3 py-2 text-sm rounded-lg bg-gray-100 dark:bg-gray-700
                            text-gray-600 dark:text-gray-300 hover:bg-gray-200
                            dark:hover:bg-gray-600 transition-colors"
                >
                  Logout
                </button>
              ) : (
                <button
                  onClick={() => setShowLoginForm(true)}
                  className="px-3 py-2 text-sm rounded-lg bg-gray-100 dark:bg-gray-700
                            text-gray-600 dark:text-gray-300 hover:bg-gray-200
                            dark:hover:bg-gray-600 transition-colors"
                >
                  Admin
                </button>
              )}
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
            </div>
          </div>
          <div className="flex items-center justify-between">
            <ConnectionStatus isConnected={isConnected} />
            {/* Tab switcher */}
            <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
              <button
                onClick={() => setActiveTab('timeline')}
                className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  activeTab === 'timeline'
                    ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400'
                }`}
              >
                Timeline
              </button>
              <button
                onClick={() => setActiveTab('stats')}
                className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  activeTab === 'stats'
                    ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400'
                }`}
              >
                Stats
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Login Modal */}
      {showLoginForm && (
        <div
          className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50"
          onClick={(e) => e.target === e.currentTarget && setShowLoginForm(false)}
        >
          <div className="bg-white dark:bg-gray-800 rounded-t-2xl sm:rounded-xl shadow-xl
                          w-full sm:max-w-sm sm:mx-4 p-6 pb-8 sm:pb-6 animate-slide-up sm:animate-none">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Admin Login</h2>
              <button
                onClick={() => setShowLoginForm(false)}
                className="p-2 -mr-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-full"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <LoginForm onSuccess={() => setShowLoginForm(false)} />
          </div>
        </div>
      )}

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {/* Contraction Button - Admin only */}
        {isAdmin && (
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
              activeContraction={activeContraction}
            />
          </section>
        )}

        {/* Update Form - Admin only */}
        {isAdmin && activeTab === 'timeline' && (
          <UpdateForm getAuthHeaders={getAuthHeaders} />
        )}

        {/* Timeline Tab */}
        {activeTab === 'timeline' && (
          <Timeline feed={feed} isAdmin={isAdmin} onDelete={handleDelete} onToggleIgnore={handleToggleIgnore} getAuthHeaders={getAuthHeaders} />
        )}

        {/* Stats Tab */}
        {activeTab === 'stats' && (
          <>
            {/* Time Range Toggle */}
            <div className="card">
              <div className="flex justify-center mb-3">
                <div className="flex bg-gray-200 dark:bg-gray-700 rounded-lg p-1">
                  <button
                    onClick={() => setStatsTimeRange('all')}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      statsTimeRange === 'all'
                        ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                        : 'text-gray-600 dark:text-gray-400'
                    }`}
                  >
                    All Time
                  </button>
                  <button
                    onClick={() => setStatsTimeRange('hour')}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      statsTimeRange === 'hour'
                        ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                        : 'text-gray-600 dark:text-gray-400'
                    }`}
                  >
                    Last Hour
                  </button>
                  <button
                    onClick={() => setStatsTimeRange('custom')}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      statsTimeRange === 'custom'
                        ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                        : 'text-gray-600 dark:text-gray-400'
                    }`}
                  >
                    Custom
                  </button>
                </div>
              </div>

              {/* Custom Range Sliders */}
              {statsTimeRange === 'custom' && (() => {
                const timestamps = getCustomTimestamps();
                const formatTime = (date) => date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                return (
                  <div className="flex flex-col items-center gap-3 pt-2">
                    <div className="w-full max-w-sm space-y-4">
                      <div>
                        <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                          <span>Start</span>
                          <span className="font-medium text-gray-700 dark:text-gray-300">{formatTime(timestamps.start)}</span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={customRange.start}
                          onChange={(e) => {
                            const val = Number(e.target.value);
                            setCustomRange(prev => ({ ...prev, start: Math.min(val, prev.end - 1) }));
                          }}
                          className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-primary-500"
                        />
                      </div>
                      <div>
                        <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                          <span>End</span>
                          <span className="font-medium text-gray-700 dark:text-gray-300">{formatTime(timestamps.end)}</span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={customRange.end}
                          onChange={(e) => {
                            const val = Number(e.target.value);
                            setCustomRange(prev => ({ ...prev, end: Math.max(val, prev.start + 1) }));
                          }}
                          className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-primary-500"
                        />
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>
            <StatsPanel contractions={contractions} timeRange={statsTimeRange} customTimestamps={getCustomTimestamps()} />
            <div className="grid md:grid-cols-2 gap-6">
              <TimeSeriesChart contractions={contractions} type="duration" timeRange={statsTimeRange} customTimestamps={getCustomTimestamps()} />
              <TimeSeriesChart contractions={contractions} type="interval" timeRange={statsTimeRange} customTimestamps={getCustomTimestamps()} />
            </div>
            <Predictions />
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="py-8 text-center text-sm text-gray-400 dark:text-gray-600">
        <span style={{ fontFamily: "'Great Vibes', cursive", fontSize: '1.25rem' }}>
          Made with love
        </span>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
