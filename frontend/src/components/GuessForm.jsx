import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

/**
 * The guess entry form — weight/length, an arrival-date call, and (for
 * surprise families) boy-or-girl. Shared by the pool sheet and the invite
 * onboarding step.
 *
 * The date field disappears once labor starts (the server also rejects it
 * then — calling "today" from the live contraction timeline is cheating);
 * a date already on record is preserved because the request simply omits
 * the field. `onSkip` renders a skip button (onboarding only).
 */
export default function GuessForm({
  scope,
  mine,
  status,
  genderEnabled = false,
  dueDate = null,
  onSaved,
  onSkip,
  submitLabel,
}) {
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
  // Start the arrival-day guess at the official due date — most people
  // nudge from there rather than pick a date cold.
  const [dateGuess, setDateGuess] = useState(mine?.date_guess || dueDate || '');
  const [sexGuess, setSexGuess] = useState(mine?.sex_guess || null);
  const [saving, setSaving] = useState(false);
  const [needName, setNeedName] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [formError, setFormError] = useState('');

  const dateOpen = status !== 'in_labor' && status !== 'born';

  function promptSignIn() {
    const next = encodeURIComponent(location.pathname);
    navigate(`/login?next=${next}`);
  }

  async function save() {
    const l = lbs === '' ? 0 : Number(lbs);
    const o = oz === '' ? 0 : Number(oz);
    const weight_lbs = l || o ? l + o / 16 : null;
    const length_in = inches === '' ? null : Number(inches);
    const body = { weight_lbs, length_in };
    // Absent ≠ null server-side: only send the fields this form owns right
    // now, so a closed date field never clobbers a recorded date.
    if (dateOpen) body.date_guess = dateGuess === '' ? null : dateGuess;
    if (genderEnabled) body.sex_guess = sexGuess;
    const guessedAnything =
      weight_lbs != null || length_in != null
      || (dateOpen && dateGuess !== '') || (genderEnabled && sexGuess);
    if (!guessedAnything) {
      setFormError('Guess something — a size, a date, or both.');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      await api.putGuess(scope, body);
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

  return (
    <div
      className="rounded-lg p-3 space-y-3"
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
            {dateOpen ? (
              <label className="text-xs t-muted">
                Arrival day
                <div className="mt-1">
                  <input
                    type="date"
                    value={dateGuess}
                    onChange={(e) => setDateGuess(e.target.value)}
                    className="t-date-input px-2 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink"
                    style={{ borderColor: 'var(--t-soft-ring)' }}
                  />
                </div>
              </label>
            ) : (
              mine?.date_guess && (
                <p className="text-xs t-muted self-center">
                  Your date call: <span className="font-medium">{mine.date_guess}</span>{' '}
                  🔒 locked when labor began
                </p>
              )
            )}
          </div>

          {genderEnabled && (
            <div className="flex items-center gap-2">
              <span className="text-xs t-muted">Your call:</span>
              {['boy', 'girl'].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setSexGuess(sexGuess === s ? null : s)}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors capitalize ${
                    sexGuess === s ? 'text-white' : ''
                  }`}
                  style={sexGuess === s
                    ? { backgroundColor: 'var(--t-accent)' }
                    : { backgroundColor: 'var(--t-card-bg)', color: 'var(--t-soft-text)', border: '1px solid var(--t-soft-ring)' }}
                >
                  {s === 'boy' ? '💙 boy' : '🩷 girl'}
                </button>
              ))}
            </div>
          )}

          {/* Wizard convention: forward motion on the right of the pair,
              the escape hatch quiet to its left — centered in the card. */}
          <div className={`flex items-center gap-3 ${onSkip ? 'justify-center' : ''}`}>
            {onSkip && (
              <button
                type="button"
                onClick={onSkip}
                className="text-sm t-muted hover:opacity-80"
              >
                Skip for now
              </button>
            )}
            <button
              type="button"
              onClick={submit}
              disabled={saving}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ backgroundColor: 'var(--t-accent)' }}
            >
              {submitLabel
                || (mine ? 'Update my guess' : isAuthenticated ? 'Add my guess' : 'Sign in to guess')}
            </button>
          </div>
          {formError && <p className="text-xs text-red-500">{formError}</p>}
        </>
      )}
    </div>
  );
}
