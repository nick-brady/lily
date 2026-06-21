import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';

function formatExpiry(timestamp) {
  const date = new Date(timestamp);
  const diffDays = Math.round((date - new Date()) / (1000 * 60 * 60 * 24));
  if (diffDays > 1) return `expires in ${diffDays} days`;
  if (diffDays === 1) return 'expires tomorrow';
  if (diffDays === 0) return 'expires today';
  return 'expired';
}

const ROLE_LABELS = {
  owner: 'Owner',
  co_parent: 'Co-parent',
};

export default function CoParentManager({ familyId, familyName }) {
  const [members, setMembers] = useState([]);
  const [pending, setPending] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [contact, setContact] = useState('');
  const [creating, setCreating] = useState(false);
  const [lastCreated, setLastCreated] = useState(null);
  const [copied, setCopied] = useState(false);

  const refresh = useCallback(async () => {
    setError('');
    try {
      const data = await api.listCoParents(familyId);
      setMembers(data.members || []);
      setPending(data.pending || []);
    } catch (err) {
      setError(err.message || 'Could not load your family');
    } finally {
      setLoading(false);
    }
  }, [familyId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleInvite = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError('');
    try {
      // A single contact field — route it by shape. An email if it looks
      // like one, otherwise treat it as a phone number.
      const isEmail = contact.includes('@');
      const created = await api.inviteCoParent(familyId, {
        displayNameHint: name.trim() || undefined,
        emailHint: isEmail ? contact.trim() : undefined,
        phoneHint: !isEmail && contact.trim() ? contact.trim() : undefined,
      });
      setLastCreated(created);
      setName('');
      setContact('');
      await refresh();
    } catch (err) {
      setError(err.message || 'Could not create invite');
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (invitationId) => {
    setError('');
    try {
      await api.revokeCoParentInvite(familyId, invitationId);
      await refresh();
    } catch (err) {
      setError(err.message || 'Could not revoke invite');
    }
  };

  const handleCopy = async () => {
    if (!lastCreated) return;
    try {
      await navigator.clipboard.writeText(lastCreated.invite_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt('Copy this link', lastCreated.invite_url);
    }
  };

  return (
    <section className="rounded-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-5">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-base font-semibold text-gray-800 dark:text-white">
          {familyName || 'Your family'}
        </h2>
        {!showForm && (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="text-sm font-medium text-primary-600 dark:text-primary-400 hover:underline"
          >
            + Invite a co-parent
          </button>
        )}
      </div>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        Co-parents can post updates, time contractions, and run the page during labor.
      </p>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading…</p>
      ) : (
        <ul className="divide-y divide-gray-100 dark:divide-gray-700">
          {members.map((m) => (
            <li key={m.user_id} className="py-2.5 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm text-gray-800 dark:text-gray-100 truncate">
                  {m.display_name || m.contact || 'Member'}
                  {m.is_self && (
                    <span className="text-gray-400 dark:text-gray-500"> · you</span>
                  )}
                </div>
                {m.display_name && m.contact && (
                  <div className="text-xs text-gray-400 dark:text-gray-500 truncate">{m.contact}</div>
                )}
              </div>
              <span className="shrink-0 text-xs font-medium rounded-full px-2.5 py-0.5 bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300">
                {ROLE_LABELS[m.role] || m.role}
              </span>
            </li>
          ))}

          {pending.map((p) => (
            <li key={p.id} className="py-2.5 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm text-gray-600 dark:text-gray-300 truncate">
                  {p.display_name_hint || p.email_hint || p.phone_hint || 'Pending invite'}
                </div>
                <div className="text-xs text-gray-400 dark:text-gray-500">
                  Invited · {formatExpiry(p.expires_at)}
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleRevoke(p.id)}
                className="shrink-0 text-xs text-gray-400 hover:text-red-500 dark:hover:text-red-400"
              >
                Revoke
              </button>
            </li>
          ))}
        </ul>
      )}

      {lastCreated && (
        <div className="mt-4 p-3 rounded-lg bg-primary-50 dark:bg-primary-900/20 border border-primary-100 dark:border-primary-800">
          <p className="text-sm font-medium text-primary-800 dark:text-primary-200 mb-2">
            Invite link ready — send it to your co-parent
          </p>
          <div className="flex gap-2">
            <input
              readOnly
              value={lastCreated.invite_url}
              onFocus={(e) => e.target.select()}
              className="flex-1 px-3 py-2 rounded border border-primary-200 dark:border-primary-700 bg-white dark:bg-gray-900 text-sm text-gray-800 dark:text-gray-100"
            />
            <button
              type="button"
              onClick={handleCopy}
              className="px-3 py-2 text-sm rounded bg-primary-600 hover:bg-primary-700 text-white font-medium"
            >
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>
      )}

      {showForm && (
        <form onSubmit={handleInvite} className="mt-4 space-y-3 border-t border-gray-100 dark:border-gray-700 pt-4">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Their name (e.g. Marco)"
            className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent focus:outline-none"
          />
          <input
            type="text"
            value={contact}
            onChange={(e) => setContact(e.target.value)}
            autoCapitalize="none"
            autoCorrect="off"
            placeholder="Their email or phone (optional)"
            className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent focus:outline-none"
          />
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={creating}
              className="px-4 py-2 text-sm rounded-lg bg-primary-600 hover:bg-primary-700 text-white font-medium disabled:opacity-50"
            >
              {creating ? 'Creating…' : 'Create invite link'}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 text-sm rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            >
              Cancel
            </button>
          </div>
          <p className="text-xs text-gray-400 dark:text-gray-500">
            We'll generate a link to send them. They confirm with a code and join as a co-parent.
          </p>
        </form>
      )}
    </section>
  );
}
