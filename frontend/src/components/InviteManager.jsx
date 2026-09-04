import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { isValidEmail, normalizeIdentifier } from '../utils/identifier';

function formatRelative(timestamp) {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = date - now;
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays > 1) return `expires in ${diffDays} days`;
  if (diffDays === 1) return 'expires tomorrow';
  if (diffDays === 0) return 'expires today';
  return 'expired';
}

export default function InviteManager({ birthId }) {
  const [invitations, setInvitations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [lastCreated, setLastCreated] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [sentSummary, setSentSummary] = useState(null);
  // Bumped after a viewer is removed. Removal drops that person across
  // every link, so all rows' cached redemption lists go stale at once —
  // this forces each one to refetch.
  const [reloadKey, setReloadKey] = useState(0);

  const refresh = useCallback(async () => {
    setError('');
    try {
      const rows = await api.listInvitations(birthId);
      setInvitations(rows);
    } catch (err) {
      setError(err.message || 'Could not load invitations');
    } finally {
      setLoading(false);
    }
  }, [birthId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // The primary action: one tap → a share-it-yourself link. This is the
  // whole invite model (drop it in the family group text); sending on
  // people's behalf is the fallback pill form below.
  const createInvite = async () => {
    setCreating(true);
    setError('');
    setSentSummary(null);
    try {
      const created = await api.createInvitation(birthId, {});
      setLastCreated(created);
      await refresh();
    } catch (err) {
      setError(err.message || 'Could not create invitation');
    } finally {
      setCreating(false);
    }
  };

  // One invitation per contact — the backend delivers each (email or SMS).
  // Names aren't collected here on purpose: people name themselves when
  // they join.
  const sendInvites = async (contacts) => {
    setCreating(true);
    setError('');
    setLastCreated(null);
    const results = await Promise.allSettled(
      contacts.map((c) =>
        api.createInvitation(birthId, {
          emailHint: c.kind === 'email' ? c.value : undefined,
          phoneHint: c.kind !== 'email' ? c.value : undefined,
        }),
      ),
    );
    const sent = results.filter((r) => r.status === 'fulfilled').length;
    const failed = results.length - sent;
    setSentSummary({ sent, failed });
    if (failed > 0) {
      setError('Some invites could not be sent — check the list below.');
    } else {
      setShowForm(false);
    }
    await refresh();
    setCreating(false);
    return failed === 0;
  };

  const handleRevoke = async (invitationId) => {
    setError('');
    try {
      await api.revokeInvitation(birthId, invitationId);
      await refresh();
    } catch (err) {
      setError(err.message || 'Could not revoke invitation');
    }
  };

  const handleRemoveViewer = async (userId) => {
    setError('');
    try {
      await api.removeViewer(birthId, userId);
      // Refresh the link list (counts changed) and tell every row to
      // refetch who joined.
      await refresh();
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err.message || 'Could not remove viewer');
    }
  };

  const handleCopy = async (url, id) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedId(id);
      setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 2000);
    } catch {
      // Clipboard unavailable on insecure origins — fall back to selecting
      // the URL so the user can copy by hand. Browsers running on https
      // or localhost shouldn't hit this path.
      window.prompt('Copy this link', url);
    }
  };

  return (
    <section className="card">
      <div className="mb-4">
        <h3 className="text-lg font-semibold t-ink">
          Family viewers
        </h3>
        <p className="text-sm t-muted">
          Invite people to follow along. They see public + family posts; not parent-only.
        </p>
      </div>

      {/* Two ways to invite — equal billing, per the product call. The
          link is the native motion (family group text); direct send is
          for the relatives you'd rather not make forward things. */}
      <p className="text-xs font-medium uppercase tracking-wide t-muted mb-2">
        Two ways to invite
      </p>
      <div className="grid sm:grid-cols-2 gap-3 mb-4">
        <div
          className="p-3 rounded-lg border flex flex-col gap-2"
          style={{ borderColor: 'var(--t-soft-ring)' }}
        >
          <div>
            <p className="text-sm font-medium t-ink">Share a link</p>
            <p className="text-xs t-muted">
              Drop it in the family group text — anyone with it can join.
            </p>
          </div>
          <button
            onClick={() => { setShowForm(false); createInvite(); }}
            disabled={creating}
            className="mt-auto self-start px-3 py-2 text-sm rounded-lg t-btn-accent font-medium disabled:opacity-50"
          >
            {creating && !showForm ? 'Creating…' : 'Create invite link'}
          </button>
        </div>
        <div
          className="p-3 rounded-lg border flex flex-col gap-2"
          style={{ borderColor: 'var(--t-soft-ring)' }}
        >
          <div>
            <p className="text-sm font-medium t-ink">Enter contacts &amp; we&rsquo;ll send</p>
            <p className="text-xs t-muted">
              Paste emails or phone numbers — each gets an invite from us.
            </p>
          </div>
          <button
            onClick={() => { setShowForm(true); setSentSummary(null); setLastCreated(null); }}
            disabled={showForm}
            className="mt-auto self-start px-3 py-2 text-sm rounded-lg font-medium disabled:opacity-60"
            style={{ backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }}
          >
            Enter contacts
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {showForm && (
        <ContactPillForm
          creating={creating}
          onSend={sendInvites}
          onCancel={() => setShowForm(false)}
        />
      )}

      {sentSummary && (
        <div
          className="mb-4 p-3 rounded-lg border text-sm"
          style={{ backgroundColor: 'var(--t-soft-bg)', borderColor: 'var(--t-soft-ring)', color: 'var(--t-soft-text)' }}
        >
          {sentSummary.sent > 0
            ? `Invites sent to ${sentSummary.sent} ${sentSummary.sent === 1 ? 'person' : 'people'} 🤍`
            : 'No invites went out.'}
          {sentSummary.failed > 0 && ` (${sentSummary.failed} failed)`}
        </div>
      )}

      {lastCreated && (
        <div
          className="mb-4 p-3 rounded-lg border"
          style={{ backgroundColor: 'var(--t-soft-bg)', borderColor: 'var(--t-soft-ring)' }}
        >
          <p className="text-sm font-medium mb-2" style={{ color: 'var(--t-soft-text)' }}>
            {lastCreated.sent
              ? `Invite sent to ${lastCreated.email_hint || lastCreated.phone_hint}`
              : 'New invite link ready'}
          </p>
          <div className="flex gap-2">
            <input
              readOnly
              value={lastCreated.invite_url}
              className="flex-1 px-3 py-2 rounded border text-sm t-ink"
              style={{ backgroundColor: 'var(--t-card-bg)', borderColor: 'var(--t-soft-ring)' }}
              onFocus={(e) => e.target.select()}
            />
            <button
              onClick={() => handleCopy(lastCreated.invite_url, lastCreated.id)}
              className="px-3 py-2 text-sm rounded t-btn-accent"
            >
              {copiedId === lastCreated.id ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-sm t-muted">Loading invitations…</p>
      ) : invitations.length === 0 ? (
        <p className="text-sm t-muted">
          No invites yet. Create one to share.
        </p>
      ) : (
        <ul>
          {invitations.map((invite) => (
            <InviteRow
              key={invite.id}
              invite={invite}
              birthId={birthId}
              reloadKey={reloadKey}
              onRevoke={() => handleRevoke(invite.id)}
              onRemoveViewer={handleRemoveViewer}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

// Paste-friendly contact entry: emails and phones become removable pills.
// Comma / tab / newline / Enter always commit a pill; space commits only
// when the buffer is already a valid contact (so "555 123 4567" can still
// be typed). Pastes are split the same way. Invalid tokens become red
// pills — visible, removable, never sent.
function ContactPillForm({ creating, onSend, onCancel }) {
  const [pills, setPills] = useState([]);
  const [buffer, setBuffer] = useState('');
  const inputRef = useRef(null);

  const tokenize = (raw) => {
    const text = raw.trim();
    if (!text) return null;
    const norm = normalizeIdentifier(text);
    // normalizeIdentifier treats any "@" as an email, so shape-check
    // emails here; phones are already validated by digit count.
    const valid =
      norm.kind === 'phone' || (norm.kind === 'email' && isValidEmail(text));
    return { raw: text, value: norm.value, kind: norm.kind, valid };
  };

  const commitBuffer = () => {
    const pill = tokenize(buffer);
    if (pill) setPills((prev) => [...prev, pill]);
    setBuffer('');
    return Boolean(pill);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === 'Tab' || e.key === ',') {
      if (buffer.trim()) {
        e.preventDefault();
        commitBuffer();
      } else if (e.key !== 'Tab') {
        e.preventDefault();
      }
      return;
    }
    if (e.key === ' ') {
      // Space commits only a complete contact — otherwise it's part of a
      // phone number still being typed.
      const pill = tokenize(buffer);
      if (pill?.valid) {
        e.preventDefault();
        commitBuffer();
      }
      return;
    }
    if (e.key === 'Backspace' && buffer === '' && pills.length > 0) {
      e.preventDefault();
      setPills((prev) => prev.slice(0, -1));
    }
  };

  const handlePaste = (e) => {
    const text = e.clipboardData.getData('text');
    if (!text) return;
    e.preventDefault();
    // Split on hard delimiters first; then split space-separated fragments
    // unless the whole fragment is a single valid contact (a phone with
    // spaces stays whole).
    const fragments = (buffer + text)
      .split(/[,\n\t;]+/)
      .flatMap((frag) => {
        const trimmed = frag.trim();
        if (!trimmed) return [];
        const whole = tokenize(trimmed);
        if (whole?.valid) return [trimmed];
        return trimmed.split(/\s+/);
      });
    const next = fragments.map(tokenize).filter(Boolean);
    setPills((prev) => [...prev, ...next]);
    setBuffer('');
  };

  const removePill = (idx) => setPills((prev) => prev.filter((_, i) => i !== idx));

  const validPills = pills.filter((p) => p.valid);
  const hasInvalid = pills.some((p) => !p.valid);

  const send = async () => {
    // Whatever's still in the buffer counts too.
    let all = pills;
    const tail = tokenize(buffer);
    if (tail) {
      all = [...pills, tail];
      setPills(all);
      setBuffer('');
    }
    const valid = all.filter((p) => p.valid);
    if (valid.length === 0) return;
    const ok = await onSend(valid);
    if (ok) setPills([]);
  };

  return (
    <div className="mb-4 space-y-3 p-3 rounded-lg border" style={{ borderColor: 'var(--t-soft-ring)' }}>
      <div
        className="flex flex-wrap items-center gap-1.5 px-2 py-1.5 rounded-lg border cursor-text"
        style={{ borderColor: 'var(--t-soft-ring)', backgroundColor: 'var(--t-card-bg)' }}
        onClick={() => inputRef.current?.focus()}
      >
        {pills.map((p, i) => (
          <span
            key={`${p.raw}-${i}`}
            className={`inline-flex items-center gap-1 pl-2.5 pr-1.5 py-1 rounded-full text-xs font-medium ${
              p.valid
                ? ''
                : 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300'
            }`}
            style={p.valid
              ? { backgroundColor: 'var(--t-soft-bg)', color: 'var(--t-soft-text)' }
              : undefined}
            title={p.valid ? p.value : 'Not a valid email or phone'}
          >
            {p.raw}
            <button
              type="button"
              onClick={() => removePill(i)}
              className="p-0.5 rounded-full hover:opacity-70"
              aria-label={`Remove ${p.raw}`}
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={buffer}
          onChange={(e) => setBuffer(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          onBlur={() => buffer.trim() && commitBuffer()}
          autoFocus
          autoCapitalize="none"
          autoCorrect="off"
          placeholder={pills.length === 0 ? 'Paste or type emails and phone numbers' : ''}
          aria-label="Emails and phone numbers to invite"
          className="flex-1 min-w-[12ch] px-1 py-1 text-sm bg-transparent t-ink rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
        />
      </div>
      {hasInvalid && (
        <p className="text-xs text-red-500">
          Red entries aren&rsquo;t valid emails or phone numbers — they won&rsquo;t be sent.
        </p>
      )}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={send}
          disabled={creating || (validPills.length === 0 && !tokenize(buffer)?.valid)}
          className="px-4 py-2 text-sm rounded-lg t-btn-accent font-medium disabled:opacity-50"
        >
          {creating
            ? 'Sending…'
            : `Send ${validPills.length > 1 ? `${validPills.length} invites` : 'invite'}`}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm t-muted hover:opacity-80"
        >
          Cancel
        </button>
        <p className="ml-auto text-xs t-faint">
          They&rsquo;ll add their own name when they join.
        </p>
      </div>
    </div>
  );
}

function formatJoined(timestamp) {
  return new Date(timestamp).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function InviteRow({ invite, birthId, reloadKey, onRevoke, onRemoveViewer }) {
  const [expanded, setExpanded] = useState(false);
  const [redemptions, setRedemptions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [removingId, setRemovingId] = useState(null);

  const loadRedemptions = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setRedemptions(await api.listInvitationRedemptions(birthId, invite.id));
    } catch (err) {
      setError(err.message || 'Could not load who joined');
    } finally {
      setLoading(false);
    }
  }, [birthId, invite.id]);

  // A removal elsewhere invalidates this row's cached list. Drop the cache;
  // if we're open, refetch now so the change shows immediately.
  useEffect(() => {
    if (reloadKey === 0) return;
    setRedemptions(null);
    if (expanded) loadRedemptions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey]);

  const isRevoked = Boolean(invite.revoked_at);
  const isExpired = !isRevoked && new Date(invite.expires_at) < new Date();
  const count = invite.redemption_count;
  const canExpand = count > 0;
  const isActive = !isRevoked && !isExpired;

  const copyLink = async () => {
    if (!invite.invite_url) return;
    try {
      await navigator.clipboard.writeText(invite.invite_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt('Copy this link', invite.invite_url);
    }
  };

  const status = isRevoked
    ? 'Revoked'
    : isExpired
      ? 'Expired'
      : `${count} ${count === 1 ? 'redemption' : 'redemptions'}`;

  const toggle = async () => {
    if (!canExpand) return;
    const next = !expanded;
    setExpanded(next);
    if (next && redemptions === null && !loading) {
      await loadRedemptions();
    }
  };

  const handleRemove = async (userId) => {
    setRemovingId(userId);
    try {
      await onRemoveViewer(userId);
    } finally {
      setRemovingId(null);
    }
  };

  return (
    <li className="py-3 t-row">
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={toggle}
          disabled={!canExpand}
          className={`min-w-0 flex items-center gap-2 text-left ${canExpand ? '' : 'cursor-default'}`}
        >
          {canExpand && (
            <svg
              className={`w-3.5 h-3.5 t-muted shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          )}
          <span className="min-w-0">
            <span className="block text-sm t-ink truncate">
              {invite.display_name_hint || invite.email_hint || invite.phone_hint || 'Anyone with the link'}
            </span>
            <span className="block text-xs t-muted">
              {status} · {formatRelative(invite.expires_at)}
            </span>
          </span>
        </button>
        {isActive && (
          <div className="flex items-center gap-3 shrink-0">
            {invite.invite_url && (
              <button
                onClick={copyLink}
                className="text-xs font-medium hover:opacity-80"
                style={{ color: 'var(--t-soft-text)' }}
              >
                {copied ? 'Copied' : 'Copy link'}
              </button>
            )}
            <button
              onClick={onRevoke}
              className="text-xs t-muted hover:text-red-500 dark:hover:text-red-400"
            >
              Revoke
            </button>
          </div>
        )}
      </div>

      {expanded && (
        <div className="mt-2 ml-6">
          {loading && <p className="text-xs t-muted">Loading…</p>}
          {error && <p className="text-xs text-red-500">{error}</p>}
          {redemptions && redemptions.length === 0 && (
            <p className="text-xs t-muted">No one has joined through this link yet.</p>
          )}
          {redemptions && redemptions.length > 0 && (
            <ul className="space-y-2.5">
              {redemptions.map((r) => {
                const contacts = [r.email, r.phone].filter(Boolean);
                const hasName = Boolean(r.display_name);
                // If there's no display name we fall back to the first
                // contact as the title — so don't repeat it below.
                const title = hasName ? r.display_name : contacts[0] || 'Someone';
                const subContacts = hasName ? contacts : contacts.slice(1);
                const isViewer = r.role === 'family_viewer';
                return (
                  <li key={r.user_id} className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline gap-2">
                        <span className="text-sm t-ink truncate min-w-0">
                          {title}
                        </span>
                        <span
                          aria-hidden="true"
                          className="flex-1 border-b border-dotted opacity-40 -translate-y-0.5"
                          style={{ borderColor: 'var(--t-divider)' }}
                        />
                        <span className="text-xs t-muted shrink-0">
                          {formatJoined(r.redeemed_at)}
                        </span>
                      </div>
                      {subContacts.length > 0 && (
                        <div className="text-xs t-muted truncate">
                          {subContacts.join(' · ')}
                        </div>
                      )}
                    </div>
                    {isViewer ? (
                      <button
                        type="button"
                        onClick={() => handleRemove(r.user_id)}
                        disabled={removingId === r.user_id}
                        title="Remove this viewer's access"
                        aria-label={`Remove ${r.display_name || contacts[0] || 'viewer'}`}
                        className="shrink-0 mt-0.5 p-1 rounded t-muted hover:text-red-500 dark:hover:text-red-400 disabled:opacity-40"
                      >
                        {removingId === r.user_id ? (
                          <span className="text-xs">Removing…</span>
                        ) : (
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        )}
                      </button>
                    ) : (
                      <span className="shrink-0 mt-0.5 text-xs t-muted capitalize">
                        {r.role === 'co_parent' ? 'co-parent' : r.role}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}
