import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import Predictions from './Predictions';

/**
 * The pool's one piece of page chrome: a tiny balloon chip in the sticky
 * header. It carries the state a visitor needs ("add yours", "you're in",
 * last-call during labor, results after settle) and opens the pool as a
 * bottom sheet — the timeline itself never shows the pool.
 */
export default function PoolPill({ slug, birthId, status, isParent }) {
  const [board, setBoard] = useState(null);
  const [open, setOpen] = useState(false);

  const loadBoard = useCallback(async () => {
    try {
      setBoard(await api.listGuesses(birthId ? { birthId } : { slug }));
    } catch {
      // No board, no pill — the pool is decoration, never an error state.
    }
  }, [birthId, slug]);

  useEffect(() => {
    loadBoard();
  }, [loadBoard]);

  if (!board) return null;

  const guesses = board.guesses || [];
  const mine = guesses.some((g) => g.is_mine);
  const settled = Boolean(board.settled);
  const born = status === 'born';
  const lastCall = status === 'in_labor' && !mine && !settled;

  // Nothing to say: born, nobody ever guessed, and no reveal coming.
  if (born && guesses.length === 0) return null;

  // Before you've guessed, "the pool" means nothing — say what the game
  // is. After you're in (or it's over), shorthand is earned.
  let label;
  if (settled) {
    label = '🏆 see who guessed best';
  } else if (born) {
    label = `🎈 ${guesses.length} ${guesses.length === 1 ? 'guess' : 'guesses'} sealed`;
  } else if (lastCall) {
    label = '🎈 last call — guess before the baby comes!';
  } else if (mine) {
    label = `🎈 you're in · ${guesses.length}`;
  } else {
    label = "🎈 guess the baby's size & arrival day";
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="px-3 py-1 text-xs rounded-full transition-opacity hover:opacity-80 whitespace-nowrap"
        style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
      >
        {lastCall && (
          <span
            className="inline-block h-1.5 w-1.5 rounded-full animate-pulse mr-1.5 align-middle"
            style={{ backgroundColor: 'var(--t-dot)' }}
          />
        )}
        {label}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center"
          onClick={() => setOpen(false)}
        >
          <div
            className="animate-slide-up w-full sm:max-w-lg max-h-[85vh] overflow-y-auto
                       bg-white dark:bg-gray-900 rounded-t-2xl sm:rounded-2xl shadow-xl p-2"
            onClick={(e) => e.stopPropagation()}
          >
            <Predictions
              slug={slug}
              birthId={birthId}
              status={status}
              isParent={isParent}
              onBoardChange={setBoard}
            />
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="w-full py-3 text-sm t-muted hover:opacity-80"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </>
  );
}
