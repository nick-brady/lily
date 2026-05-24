import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, getToken } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useSSE } from '../hooks/useSSE';
import ConnectionStatus from '../components/ConnectionStatus';
import Timeline from '../components/Timeline';
import { bumpCommentCount, updateReaction } from '../utils/engagement';

export default function PublicBirthPage() {
  const { slug } = useParams();
  const { isAuthenticated, me } = useAuth();
  const [birth, setBirth] = useState(null);
  const [events, setEvents] = useState(() => new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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
    const url = new URL(`${api.apiUrl}/b/${slug}/stream`);
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
              {canManageThisBirth && (
                <Link
                  to={`/b/${slug}/manage`}
                  className="px-3 py-2 text-sm rounded-lg bg-primary-600 text-white font-medium hover:bg-primary-700 transition-colors"
                >
                  Manage
                </Link>
              )}
              {!isAuthenticated && (
                <Link
                  to="/login"
                  className="px-3 py-2 text-sm rounded-lg bg-gray-100 dark:bg-gray-700
                             text-gray-600 dark:text-gray-300 hover:bg-gray-200
                             dark:hover:bg-gray-600 transition-colors"
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
        {error && (
          <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}
        {loading ? (
          <p className="text-center text-gray-500 dark:text-gray-400 py-12">
            Loading timeline…
          </p>
        ) : (
          <Timeline
            events={sortedEvents}
            slug={slug}
            isUnlocked={birth?.is_unlocked ?? false}
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
