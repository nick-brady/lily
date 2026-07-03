import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

/**
 * The family pool: everyone guesses the baby's weight and length before
 * the birth; the board settles once the parents record the actual
 * measurements. Guessing is free-tier engagement (like reactions — no
 * unlock), one guess per signed-in user, editable until the baby arrives.
 *
 * Works on both surfaces: pass `birthId` (manage page) or `slug`
 * (public page), plus the birth `status` and whether the viewer
 * `isParent` (parents get the record-measurements form once born).
 */
export default function Predictions({ birthId, slug, status, isParent = false }) {
  const [board, setBoard] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setBoard(await api.listGuesses(birthId ? { birthId } : { slug }));
      setError('');
    } catch (err) {
      setError(err.message || 'Could not load the family pool');
    }
  }, [birthId, slug]);

  useEffect(() => {
    load();
  }, [load]);

  if (board === null && !error) return null;

  const guesses = board?.guesses || [];
  const settled = Boolean(board?.settled);
  const born = status === 'born';

  // A born birth with no pool and nothing for this viewer to do: stay quiet.
  if (born && guesses.length === 0 && !isParent) return null;

  const mine = guesses.find((g) => g.is_mine) || null;
  const scope = birthId ? { birthId } : { slug };

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-1">
        The family pool
      </h3>
      <p className="text-xs t-muted mb-4">
        {born
          ? settled
            ? 'Everyone guessed before they met the baby — here’s how close you all came.'
            : 'The baby is here! The board settles once the measurements are in.'
          : 'How big will the baby be? Everyone gets one guess — change it any time before the big arrival.'}
      </p>

      {error && (
        <div className="p-3 mb-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {!born && <GuessForm key={mine?.id || 'new'} mine={mine} scope={scope} onSaved={load} />}
      {born && !settled && isParent && birthId && (
        <ActualsForm birthId={birthId} onSaved={load} />
      )}

      {guesses.length > 0 && (
        <GuessTable guesses={guesses} board={board} settled={settled} />
      )}
      {guesses.length === 0 && !born && (
        <p className="text-xs text-center t-muted py-3">
          No guesses yet — be the first.
        </p>
      )}
    </div>
  );
}

function GuessForm({ mine, scope, onSaved }) {
  const { isAuthenticated, user, refreshMe } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [lbs, setLbs] = useState(
    mine?.weight_lbs != null ? String(Math.floor(mine.weight_lbs)) : '',
  );
  const [oz, setOz] = useState(
    mine?.weight_lbs != null
      ? String(Math.round((mine.weight_lbs - Math.floor(mine.weight_lbs)) * 16))
      : '',
  );
  const [inches, setInches] = useState(mine?.length_in != null ? String(mine.length_in) : '');
  const [openForm, setOpenForm] = useState(!mine);
  const [saving, setSaving] = useState(false);
  const [needName, setNeedName] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [formError, setFormError] = useState('');

  function promptSignIn() {
    const next = encodeURIComponent(location.pathname);
    navigate(`/login?next=${next}`);
  }

  async function save() {
    const l = lbs === '' ? 0 : Number(lbs);
    const o = oz === '' ? 0 : Number(oz);
    const weight_lbs = l || o ? l + o / 16 : null;
    const length_in = inches === '' ? null : Number(inches);
    if (weight_lbs == null && length_in == null) {
      setFormError('Guess a weight, a length, or both.');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      await api.putGuess(scope, { weight_lbs, length_in });
      setOpenForm(false);
      setNeedName(false);
      await onSaved();
    } catch (err) {
      setFormError(err.message || 'Could not save your guess');
    } finally {
      setSaving(false);
    }
  }

  async function submit() {
    if (!isAuthenticated) {
      promptSignIn();
      return;
    }
    // Guesses are attributed forever — capture a name first (same flow as
    // comments).
    if (!user?.display_name) {
      setNameValue(user?.display_name || '');
      setNeedName(true);
      return;
    }
    await save();
  }

  async function saveNameThenSubmit() {
    if (!nameValue.trim()) return;
    setSaving(true);
    try {
      await api.updateMe({ displayName: nameValue.trim() });
      await refreshMe();
      setNeedName(false);
      await save();
    } catch (err) {
      setFormError(err.message || 'Could not save your name');
      setSaving(false);
    }
  }

  if (!openForm) {
    return (
      <button
        type="button"
        onClick={() => setOpenForm(true)}
        className="w-full mb-4 px-3 py-2 text-xs t-muted hover:t-ink text-left transition-colors"
      >
        Your guess is in — change it →
      </button>
    );
  }

  return (
    <div
      className="rounded-lg p-3 mb-4 space-y-3"
      style={{ backgroundColor: 'var(--t-soft-bg)' }}
    >
      {needName ? (
        <div className="space-y-2">
          <p className="text-xs t-muted">
            Add your name so the family knows whose guess this is:
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              value={nameValue}
              onChange={(e) => setNameValue(e.target.value)}
              placeholder="Your name"
              className="flex-1 px-3 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink"
              style={{ borderColor: 'var(--t-soft-ring)' }}
            />
            <button
              type="button"
              onClick={saveNameThenSubmit}
              disabled={saving || !nameValue.trim()}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ backgroundColor: 'var(--t-accent)' }}
            >
              Save
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs t-muted">
              Weight
              <div className="flex items-center gap-1 mt-1">
                <input
                  type="number"
                  min="0"
                  max="20"
                  value={lbs}
                  onChange={(e) => setLbs(e.target.value)}
                  className="w-16 px-2 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink"
                  style={{ borderColor: 'var(--t-soft-ring)' }}
                />
                <span className="text-xs t-muted">lbs</span>
                <input
                  type="number"
                  min="0"
                  max="15"
                  value={oz}
                  onChange={(e) => setOz(e.target.value)}
                  className="w-16 px-2 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink"
                  style={{ borderColor: 'var(--t-soft-ring)' }}
                />
                <span className="text-xs t-muted">oz</span>
              </div>
            </label>
            <label className="text-xs t-muted">
              Length
              <div className="flex items-center gap-1 mt-1">
                <input
                  type="number"
                  min="0"
                  max="30"
                  step="0.25"
                  value={inches}
                  onChange={(e) => setInches(e.target.value)}
                  className="w-20 px-2 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink"
                  style={{ borderColor: 'var(--t-soft-ring)' }}
                />
                <span className="text-xs t-muted">in</span>
              </div>
            </label>
            <button
              type="button"
              onClick={submit}
              disabled={saving}
              className="ml-auto px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ backgroundColor: 'var(--t-accent)' }}
            >
              {mine ? 'Update my guess' : isAuthenticated ? 'Add my guess' : 'Sign in to guess'}
            </button>
          </div>
          {formError && <p className="text-xs text-red-500">{formError}</p>}
        </>
      )}
    </div>
  );
}

function ActualsForm({ birthId, onSaved }) {
  const [lbs, setLbs] = useState('');
  const [oz, setOz] = useState('');
  const [inches, setInches] = useState('');
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  async function save() {
    const l = lbs === '' ? 0 : Number(lbs);
    const o = oz === '' ? 0 : Number(oz);
    const weight = l + o / 16;
    if (!weight) {
      setFormError('Weight is what settles the pool.');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      await api.updateBirth(birthId, {
        child_weight_lbs: weight,
        child_length_in: inches === '' ? null : Number(inches),
      });
      await onSaved();
    } catch (err) {
      setFormError(err.message || 'Could not save the measurements');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="rounded-lg p-3 mb-4 space-y-2"
      style={{ backgroundColor: 'var(--t-soft-bg)' }}
    >
      <p className="text-xs t-muted">
        Record the measurements to settle the pool and crown the winner:
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="number" min="0" max="20" placeholder="lbs" value={lbs}
          onChange={(e) => setLbs(e.target.value)}
          className="w-16 px-2 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink"
          style={{ borderColor: 'var(--t-soft-ring)' }}
        />
        <input
          type="number" min="0" max="15" placeholder="oz" value={oz}
          onChange={(e) => setOz(e.target.value)}
          className="w-16 px-2 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink"
          style={{ borderColor: 'var(--t-soft-ring)' }}
        />
        <input
          type="number" min="0" max="30" step="0.25" placeholder="inches" value={inches}
          onChange={(e) => setInches(e.target.value)}
          className="w-20 px-2 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink"
          style={{ borderColor: 'var(--t-soft-ring)' }}
        />
        <button
          type="button" onClick={save} disabled={saving}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
          style={{ backgroundColor: 'var(--t-accent)' }}
        >
          Settle the pool
        </button>
      </div>
      {formError && <p className="text-xs text-red-500">{formError}</p>}
    </div>
  );
}

function formatWeight(lbs) {
  if (!lbs) return '-';
  let pounds = Math.floor(lbs);
  let oz = Math.round((lbs - pounds) * 16);
  if (oz === 16) {
    pounds += 1;
    oz = 0;
  }
  return oz > 0 ? `${pounds} lbs ${oz} oz` : `${pounds} lbs`;
}

function formatLength(inches) {
  return inches ? `${inches}"` : '-';
}

function GuessTable({ guesses, board, settled }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700">
            <th className="text-left py-2 px-2 font-medium text-gray-500 dark:text-gray-400">
              {settled && '#'}
            </th>
            <th className="text-left py-2 px-2 font-medium text-gray-500 dark:text-gray-400">Name</th>
            <th className="text-right py-2 px-2 font-medium text-gray-500 dark:text-gray-400">Weight</th>
            <th className="text-right py-2 px-2 font-medium text-gray-500 dark:text-gray-400">Length</th>
          </tr>
        </thead>
        <tbody>
          {guesses.map((g) => (
            <tr
              key={g.id}
              className={`border-b border-gray-100 dark:border-gray-700/50 ${
                settled && g.rank === 1 ? 'bg-amber-50 dark:bg-amber-900/20' : ''
              }`}
            >
              <td className="py-2 px-2">
                {settled && g.rank === 1 && <span className="text-xl">🏆</span>}
                {settled && g.rank === 2 && <span className="text-lg">🥈</span>}
                {settled && g.rank === 3 && <span className="text-lg">🥉</span>}
              </td>
              <td className="py-2 px-2 font-medium text-gray-800 dark:text-gray-200">
                {g.display_name}
                {g.is_mine && <span className="text-xs t-muted"> (you)</span>}
              </td>
              <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-400">
                {formatWeight(g.weight_lbs)}
              </td>
              <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-400">
                {formatLength(g.length_in)}
              </td>
            </tr>
          ))}
        </tbody>
        {settled && (
          <tfoot>
            <tr className="bg-primary-50 dark:bg-primary-900/20 font-semibold">
              <td className="py-2 px-2">
                <span className="text-xl">👶</span>
              </td>
              <td className="py-2 px-2 text-primary-700 dark:text-primary-300">Actual</td>
              <td className="py-2 px-2 text-right text-primary-700 dark:text-primary-300">
                {formatWeight(board.actual_weight_lbs)}
              </td>
              <td className="py-2 px-2 text-right text-primary-700 dark:text-primary-300">
                {formatLength(board.actual_length_in)}
              </td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}
