import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

/**
 * The reaction palette. Three is intentional — see the personas doc.
 * Janet leaves "a heart on every milestone"; the curated set keeps the
 * vocabulary small and the keepsake dignified. If we ever feel the urge
 * to add fire / clap / cry, resist it: the comment unlock is for words.
 */
const REACTIONS = [
  { kind: 'love', emoji: '💖', label: 'Love' },
  { kind: 'wow', emoji: '✨', label: 'Wow' },
  { kind: 'pray', emoji: '🙏', label: 'Pray' },
];

export default function ReactionBar({ event, scope }) {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [pending, setPending] = useState(null);

  const reactions = event.reactions || {};

  async function toggle(kind) {
    if (!isAuthenticated) {
      const next = encodeURIComponent(location.pathname);
      navigate(`/login?next=${next}`);
      return;
    }
    if (pending) return;
    const wasMine = reactions[kind]?.mine ?? false;
    setPending(kind);
    try {
      if (wasMine) {
        await api.removeReaction({ ...scope, eventId: event.id, kind });
      } else {
        await api.addReaction({ ...scope, eventId: event.id, kind });
      }
      // The server response and the SSE round-trip will update event
      // state at the page level. No optimistic local mutation needed —
      // the keepsake brand is calm, no flicker, no shimmer.
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex items-center gap-1 mt-2">
      {REACTIONS.map(({ kind, emoji, label }) => {
        const summary = reactions[kind];
        const count = summary?.count ?? 0;
        const mine = summary?.mine ?? false;
        const isHot = count > 0;
        return (
          <button
            key={kind}
            type="button"
            onClick={() => toggle(kind)}
            disabled={pending === kind}
            aria-label={`${label} (${count})`}
            aria-pressed={mine}
            className={[
              'group inline-flex items-center gap-1 px-2 py-1 rounded-full text-sm',
              'transition-all duration-200 ease-out',
              mine
                ? 'bg-primary-50 dark:bg-primary-900/20 ring-1 ring-primary-200 dark:ring-primary-800'
                : 'hover:bg-gray-100 dark:hover:bg-gray-700/50',
              pending === kind ? 'opacity-60' : '',
            ].join(' ')}
          >
            <span
              className={`text-base ${
                mine ? 'scale-110' : 'opacity-70 group-hover:opacity-100'
              } transition-transform`}
            >
              {emoji}
            </span>
            {isHot && (
              <span
                className={`text-xs ${
                  mine
                    ? 'text-primary-700 dark:text-primary-300 font-medium'
                    : 'text-gray-500 dark:text-gray-400'
                }`}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
