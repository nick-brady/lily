import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import GuessForm from './GuessForm';

/**
 * The family pool: weight/length, an arrival-date call, and (for surprise
 * families) boy-or-girl. Guesses are SEALED until the parents record the
 * actuals — the server withholds other people's values pre-settle, so the
 * table shows who's in without spoiling the reveal or anchoring anyone.
 *
 * Guesses stay editable until the birth — no calendar freeze, because a due
 * date tells nobody what the baby will weigh. The settled board shows each
 * row's own provenance instead ("guessed Jul 12 · updated Aug 14"), so a
 * late change is visible rather than prevented. Settling crowns two winners:
 * closest size (🏆, the score) and closest date (📅, its own crown).
 *
 * Lives in the pool sheet (all roles) and on the parent stats tab — never
 * on the timeline. Pass `birthId` (parents) or `slug`, plus `status` and
 * `isParent` (parents get the settle form once born). `onBoardChange`
 * lets the pool pill refresh its label after a save.
 */
export default function Predictions({ birthId, slug, status, isParent = false, onBoardChange }) {
  const [board, setBoard] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const next = await api.listGuesses(birthId ? { birthId } : { slug });
      setBoard(next);
      setError('');
      onBoardChange?.(next);
    } catch (err) {
      setError(err.message || 'Could not load the family pool');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [birthId, slug]);

  useEffect(() => {
    load();
  }, [load]);

  if (board === null && !error) return null;

  const guesses = board?.guesses || [];
  const settled = Boolean(board?.settled);
  const born = status === 'born';
  const inLabor = status === 'in_labor';

  // A born birth with no pool and nothing for this viewer to do: stay quiet.
  if (born && guesses.length === 0 && !isParent) return null;

  const mine = guesses.find((g) => g.is_mine) || null;
  const scope = birthId ? { birthId } : { slug };
  const genderEnabled = Boolean(board?.gender_pool_enabled);
  const canWrite = !born;

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
          : inLabor && !mine
            ? 'Last call — the arrival is underway! Get your guess in before the baby does. 🎈'
            : 'How big will the baby be? When? Everyone gets one guess, sealed until the arrival.'}
      </p>

      {error && (
        <div className="p-3 mb-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {canWrite && (
        <div className="mb-4">
          <PoolFormToggle
            key={mine?.id || 'new'}
            mine={mine}
            scope={scope}
            status={status}
            genderEnabled={genderEnabled}
            dueDate={board?.due_date}
            onSaved={load}
          />
        </div>
      )}
      {born && !settled && isParent && birthId && (
        <ActualsForm birthId={birthId} genderEnabled={genderEnabled} onSaved={load} />
      )}

      {guesses.length > 0 && (
        <GuessTable
          guesses={guesses}
          board={board}
          settled={settled}
          genderEnabled={genderEnabled}
        />
      )}
      {guesses.length === 0 && !born && (
        <p className="text-xs text-center t-muted py-3">
          No guesses yet — be the first. 🎈
        </p>
      )}
    </div>
  );
}

// The "your guess is in — change it" collapse around the shared form.
function PoolFormToggle({ mine, scope, status, genderEnabled, dueDate, onSaved }) {
  const [open, setOpen] = useState(!mine);
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full px-3 py-2 text-xs t-muted hover:t-ink text-left transition-colors"
      >
        Your guess is in, sealed 🎈 — change it →
      </button>
    );
  }
  return (
    <GuessForm
      mine={mine}
      scope={scope}
      status={status}
      genderEnabled={genderEnabled}
      dueDate={dueDate}
      onSaved={async () => {
        setOpen(false);
        await onSaved();
      }}
    />
  );
}

function ActualsForm({ birthId, genderEnabled, onSaved }) {
  const [lbs, setLbs] = useState('');
  const [oz, setOz] = useState('');
  const [inches, setInches] = useState('');
  const [sex, setSex] = useState(null);
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
        ...(genderEnabled && sex ? { child_sex: sex } : {}),
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
        Record the measurements to settle the pool and crown the winners:
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
        {genderEnabled && ['boy', 'girl'].map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSex(sex === s ? null : s)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium capitalize ${
              sex === s ? 'text-white' : ''
            }`}
            style={sex === s
              ? { backgroundColor: 'var(--t-accent)' }
              : { backgroundColor: 'var(--t-card-bg)', color: 'var(--t-soft-text)', border: '1px solid var(--t-soft-ring)' }}
          >
            {s === 'boy' ? '💙' : '🩷'} {s}
          </button>
        ))}
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

export function formatWeight(lbs) {
  if (!lbs) return null;
  let pounds = Math.floor(lbs);
  let oz = Math.round((lbs - pounds) * 16);
  if (oz === 16) {
    pounds += 1;
    oz = 0;
  }
  return oz > 0 ? `${pounds} lbs ${oz} oz` : `${pounds} lbs`;
}

export function formatLength(inches) {
  return inches ? `${inches}"` : null;
}

// Three medals, one per dimension, because pounds, inches and days have no
// exchange rate. The labels live in a legend under the table rather than in
// each row — a medal on its own reads as 1st/2nd/3rd place, and then a silver
// sitting next to a worse weight than the bronze looks like a bug.
const MEDALS = [
  { flag: 'weight_winner', icon: '🏆', label: 'closest weight' },
  { flag: 'length_winner', icon: '🥈', label: 'closest length' },
  { flag: 'date_winner', icon: '🥉', label: 'closest day' },
];

// How far off, in the units people actually say. Absolute values: the board is
// about closeness, and "2 oz over" invites an argument about the rounding.
function offBy(value, render) {
  if (value == null) return null;
  return value === 0 ? 'exact' : render(value);
}

function weightOffBy(lbs) {
  return offBy(lbs, (v) => {
    const oz = Math.round(v * 16);
    return oz < 16 ? `${oz} oz off` : `${(v).toFixed(2).replace(/\.?0+$/, '')} lbs off`;
  });
}

function lengthOffBy(inches) {
  return offBy(inches, (v) => `${Number(v.toFixed(2))}" off`);
}

function dateOffBy(days) {
  return offBy(days, (v) => `${v} day${v === 1 ? '' : 's'} off`);
}

function OffBy({ text }) {
  if (!text) return null;
  return <div className="text-xs t-faint font-normal">{text}</div>;
}

export function formatDate(iso) {
  if (!iso) return null;
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

// Pre-settle, non-mine rows arrive from the server with values nulled —
// render the seal, not a dash, so "hidden" doesn't read as "empty".
function Sealed() {
  return <span title="Sealed until the arrival">🎈</span>;
}

function formatStamp(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  // Non-breaking space: the provenance line wraps inside a narrow modal, and
  // "Jul / 30" split across two lines reads as a typo.
  return d
    .toLocaleDateString([], { month: 'short', day: 'numeric' })
    .replace(' ', ' ');
}

// Guesses are editable until the birth, so the reveal carries its own
// provenance: when the guess went in, and whether it moved afterwards. A
// late change is shown rather than blocked — the family can do the ribbing.
function provenance(g) {
  const made = formatStamp(g.created_at);
  if (!made) return null;
  // Only a change on a LATER DAY is worth calling out. Same-day tweaks are
  // just finishing the form (and the upsert stamps both columns in one
  // transaction anyway), so they'd render a pointless duplicate date.
  const edited = formatStamp(g.updated_at);
  return edited && edited !== made
    ? `guessed ${made} · updated ${edited}`
    : `guessed ${made}`;
}

function GuessTable({ guesses, board, settled, genderEnabled }) {
  const sealedOr = (g, formatted) => {
    if (formatted != null) return formatted;
    return settled || g.is_mine ? '-' : <Sealed />;
  };
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
            <th className="text-right py-2 px-2 font-medium text-gray-500 dark:text-gray-400">Day</th>
            {genderEnabled && (
              <th className="text-right py-2 px-2 font-medium text-gray-500 dark:text-gray-400">Call</th>
            )}
          </tr>
        </thead>
        <tbody>
          {guesses.map((g) => (
            <tr
              key={g.id}
              className={`border-b border-gray-100 dark:border-gray-700/50 ${
                settled && g.weight_winner ? 'bg-amber-50 dark:bg-amber-900/20' : ''
              }`}
            >
              <td className="py-2 px-2 whitespace-nowrap">
                {settled
                  && MEDALS.filter((m) => g[m.flag]).map((m) => (
                    <span key={m.flag} className="text-lg" title={m.label}>
                      {m.icon}
                    </span>
                  ))}
              </td>
              <td className="py-2 px-2 font-medium text-gray-800 dark:text-gray-200">
                {g.display_name}
                {g.is_mine && <span className="text-xs t-muted"> (you)</span>}
                {settled && provenance(g) && (
                  <div className="text-xs t-faint font-normal">{provenance(g)}</div>
                )}
              </td>
              <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-400">
                {sealedOr(g, formatWeight(g.weight_lbs))}
                {settled && <OffBy text={weightOffBy(g.weight_delta_lbs)} />}
              </td>
              <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-400">
                {sealedOr(g, formatLength(g.length_in))}
                {settled && <OffBy text={lengthOffBy(g.length_delta_in)} />}
              </td>
              <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-400 whitespace-nowrap">
                {sealedOr(g, formatDate(g.date_guess))}
                {settled && <OffBy text={dateOffBy(g.date_delta_days)} />}
              </td>
              {genderEnabled && (
                <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-400 whitespace-nowrap">
                  {settled && g.sex_guess && board.actual_sex && (
                    <span className="mr-1">{g.sex_guess === board.actual_sex ? '✓' : '✗'}</span>
                  )}
                  {sealedOr(g, g.sex_guess ? (g.sex_guess === 'boy' ? '💙' : '🩷') : null)}
                </td>
              )}
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
                {formatWeight(board.actual_weight_lbs) || '-'}
              </td>
              <td className="py-2 px-2 text-right text-primary-700 dark:text-primary-300">
                {formatLength(board.actual_length_in) || '-'}
              </td>
              <td className="py-2 px-2 text-right text-primary-700 dark:text-primary-300">
                {formatDate(board.actual_date) || '-'}
              </td>
              {genderEnabled && (
                <td className="py-2 px-2 text-right text-primary-700 dark:text-primary-300">
                  {board.actual_sex ? (board.actual_sex === 'boy' ? '💙' : '🩷') : '-'}
                </td>
              )}
            </tr>
          </tfoot>
        )}
      </table>
      {settled && (
        <p className="mt-3 text-xs t-faint flex flex-wrap gap-x-3 gap-y-1">
          {MEDALS.map((m) => (
            <span key={m.flag}>
              {m.icon} {m.label}
            </span>
          ))}
        </p>
      )}
    </div>
  );
}
