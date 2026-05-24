import { forwardRef, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { relativeTime } from '../utils/relativeTime';

/**
 * Comment thread on a single timeline event.
 *
 * Collapsed by default. Tapping "{n} comments" expands the list and the
 * composer. The brand is dignified, slow, forgiving — Janet types
 * slowly, makes typos, wants to edit; this UI must not punish that.
 *
 * Comments require `birth.is_unlocked`. The 402 response shape from the
 * server is rendered as a gentle "$12, anyone in the family can unlock
 * the comments for everyone — it's permanent for this baby" prompt.
 * Once Stripe lands in PR 5 the prompt becomes a real CTA; today it's
 * a stub that explains the model.
 */
export default function CommentThread({
  event,
  scope,
  isUnlocked,
  countOverride = null,
}) {
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [expanded, setExpanded] = useState(false);
  const [comments, setComments] = useState(null);
  const [loading, setLoading] = useState(false);
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [lockedPrompt, setLockedPrompt] = useState(false);
  const textareaRef = useRef(null);

  const displayedCount = countOverride ?? event.comment_count ?? 0;

  useEffect(() => {
    if (!expanded || comments !== null) return;
    let cancelled = false;
    setLoading(true);
    api
      .listComments({ ...scope, eventId: event.id })
      .then((rows) => {
        if (!cancelled) setComments(rows);
      })
      .catch(() => {
        if (!cancelled) setComments([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [expanded, comments, scope, event.id]);

  function handleToggle() {
    setExpanded((e) => !e);
    setLockedPrompt(false);
  }

  function promptSignIn() {
    const next = encodeURIComponent(location.pathname);
    navigate(`/login?next=${next}`);
  }

  async function submit() {
    if (!body.trim()) return;
    if (!isAuthenticated) {
      promptSignIn();
      return;
    }
    setSubmitting(true);
    try {
      const created = await api.createComment({
        ...scope,
        eventId: event.id,
        body: body.trim(),
      });
      setComments((prev) => [...(prev || []), created]);
      setBody('');
      setLockedPrompt(false);
    } catch (err) {
      if (err.status === 402) {
        setLockedPrompt(true);
      } else {
        // eslint-disable-next-line no-console
        console.error(err);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(commentId) {
    try {
      await api.deleteComment({
        ...scope,
        eventId: event.id,
        commentId,
      });
      setComments((prev) =>
        (prev || []).filter((c) => c.id !== commentId),
      );
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(err);
    }
  }

  const summary = displayedCount === 0
    ? 'Leave a note'
    : displayedCount === 1
      ? '1 comment'
      : `${displayedCount} comments`;

  return (
    <div className="mt-2 text-sm">
      <button
        type="button"
        onClick={handleToggle}
        className="text-xs text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-300"
      >
        {expanded ? 'Hide' : summary}
      </button>

      {expanded && (
        <div className="mt-3 space-y-3">
          {loading && (
            <p className="text-xs text-gray-400 dark:text-gray-500">Loading…</p>
          )}

          {comments &&
            comments.map((c) => (
              <Comment
                key={c.id}
                comment={c}
                canDelete={!!user && c.user_id === user.id}
                onDelete={() => handleDelete(c.id)}
              />
            ))}

          {comments && comments.length === 0 && !loading && (
            <p className="text-xs text-gray-400 dark:text-gray-500 italic">
              No comments yet.
            </p>
          )}

          <Composer
            body={body}
            setBody={setBody}
            onSubmit={submit}
            onSignIn={promptSignIn}
            submitting={submitting}
            ref={textareaRef}
            isAuthenticated={isAuthenticated}
            isUnlocked={isUnlocked}
            lockedPrompt={lockedPrompt}
          />
        </div>
      )}
    </div>
  );
}

function Comment({ comment, canDelete, onDelete }) {
  return (
    <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {relativeTime(comment.created_at)}
        </span>
        {canDelete && (
          <button
            type="button"
            onClick={onDelete}
            className="text-xs text-gray-300 dark:text-gray-600 hover:text-red-500 dark:hover:text-red-400"
          >
            Delete
          </button>
        )}
      </div>
      <p className="mt-1 text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
        {comment.body}
      </p>
    </div>
  );
}

const Composer = forwardRef(function Composer(
  {
    body,
    setBody,
    onSubmit,
    onSignIn,
    submitting,
    isAuthenticated,
    isUnlocked,
    lockedPrompt,
  },
  ref,
) {
  if (!isAuthenticated) {
    return (
      <div className="rounded-lg bg-primary-50 dark:bg-primary-900/10 p-3 text-sm text-gray-700 dark:text-gray-300">
        <p className="mb-2">Sign in to leave a note for the family.</p>
        <button
          type="button"
          onClick={onSignIn}
          className="text-primary-600 dark:text-primary-300 hover:underline text-sm font-medium"
        >
          Sign in →
        </button>
      </div>
    );
  }

  if (lockedPrompt || isUnlocked === false) {
    return <LockedPrompt />;
  }

  return (
    <div className="space-y-2">
      <textarea
        ref={ref}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={2}
        placeholder="Write a note…"
        className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700
                   bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100
                   text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-300"
      />
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onSubmit}
          disabled={!body.trim() || submitting}
          className="px-4 py-1.5 rounded-lg bg-primary-600 text-white text-sm font-medium
                     hover:bg-primary-700 disabled:opacity-50"
        >
          {submitting ? 'Sending…' : 'Send'}
        </button>
      </div>
    </div>
  );
});

function LockedPrompt() {
  return (
    <div className="rounded-lg border border-primary-100 dark:border-primary-900/30
                    bg-primary-50/40 dark:bg-primary-900/10 p-4 text-sm">
      <p className="text-gray-800 dark:text-gray-200 leading-relaxed">
        Family conversations and personal messages happen here.
      </p>
      <p className="mt-2 text-gray-600 dark:text-gray-400 leading-relaxed">
        Anyone in the family can unlock the comments for everyone — $12,
        one time. It's permanent for this baby.
      </p>
      <p className="mt-3 text-xs text-gray-500 dark:text-gray-500 italic">
        Payments are coming soon. For now, ask the parents to unlock from
        their dashboard.
      </p>
    </div>
  );
}
