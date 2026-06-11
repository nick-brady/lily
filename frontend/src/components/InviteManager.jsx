import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';

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

  const handleCreate = async () => {
    setCreating(true);
    setError('');
    try {
      const created = await api.createInvitation(birthId);
      setLastCreated(created);
      await refresh();
    } catch (err) {
      setError(err.message || 'Could not create invitation');
    } finally {
      setCreating(false);
    }
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
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold t-ink">
            Family viewers
          </h3>
          <p className="text-sm t-muted">
            Invite people to follow along. They see public + family posts; not parent-only.
          </p>
        </div>
        <button
          onClick={handleCreate}
          disabled={creating}
          className="px-3 py-2 text-sm rounded-lg t-btn-accent font-medium disabled:opacity-50"
        >
          {creating ? 'Creating…' : 'New invite link'}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {lastCreated && (
        <div
          className="mb-4 p-3 rounded-lg border"
          style={{ backgroundColor: 'var(--t-soft-bg)', borderColor: 'var(--t-soft-ring)' }}
        >
          <p className="text-sm font-medium mb-2" style={{ color: 'var(--t-soft-text)' }}>
            New invite link ready
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
          {invitations.map((invite) => {
            const isRevoked = Boolean(invite.revoked_at);
            const isExpired = !isRevoked && new Date(invite.expires_at) < new Date();
            const status = isRevoked
              ? 'Revoked'
              : isExpired
                ? 'Expired'
                : `${invite.redemption_count} ${invite.redemption_count === 1 ? 'redemption' : 'redemptions'}`;
            return (
              <li key={invite.id} className="py-3 flex items-center justify-between gap-3 t-row">
                <div className="min-w-0">
                  <div className="text-sm t-ink truncate">
                    {invite.display_name_hint || invite.email_hint || invite.phone_hint || 'Anyone with the link'}
                  </div>
                  <div className="text-xs t-muted">
                    {status} · {formatRelative(invite.expires_at)}
                  </div>
                </div>
                {!isRevoked && !isExpired && (
                  <button
                    onClick={() => handleRevoke(invite.id)}
                    className="text-xs t-muted hover:text-red-500 dark:hover:text-red-400"
                  >
                    Revoke
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
