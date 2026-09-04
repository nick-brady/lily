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
 * Free for every signed-in viewer — participation is the top of the gift
 * funnel, never a paywall (pricing thesis, 2026-07-19).
 *
 * Demo mode (`initialComments`): scripted threads on the landing page and
 * hero video render fixture comments without touching the API and hide the
 * composer — a scripted thread isn't interactive.
 */
export default function CommentThread({
  event,
  scope,
  countOverride = null,
  initialComments = null,
  defaultExpanded = false,
}) {
  const isDemo = initialComments !== null;
  const { isAuthenticated, user, refreshMe } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [comments, setComments] = useState(initialComments);
  const [loading, setLoading] = useState(false);
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [needName, setNeedName] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [savingName, setSavingName] = useState(false);
  const textareaRef = useRef(null);

  const displayedCount = countOverride ?? event.comment_count ?? 0;

  // Demo threads follow the script: when the cue delivers comments, show
  // them and open the thread.
  useEffect(() => {
    if (initialComments === null) return;
    setComments(initialComments);
    if (initialComments.length > 0) setExpanded(true);
  }, [initialComments]);

  useEffect(() => {
    if (isDemo || !expanded || comments !== null) return;
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
  }

  function promptSignIn() {
    const next = encodeURIComponent(location.pathname);
    navigate(`/login?next=${next}`);
  }

  async function postComment() {
    setSubmitting(true);
    try {
      const created = await api.createComment({
        ...scope,
        eventId: event.id,
        body: body.trim(),
      });
      setComments((prev) => [...(prev || []), created]);
      setBody('');
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  }

  async function submit() {
    if (!body.trim()) return;
    if (!isAuthenticated) {
      promptSignIn();
      return;
    }
    // Their words get attributed forever — make sure they have a name
    // before the first comment posts.
    if (!user?.display_name) {
      setNameValue(user?.display_name || '');
      setNeedName(true);
      return;
    }
    await postComment();
  }

  async function saveNameThenPost() {
    if (!nameValue.trim()) return;
    setSavingName(true);
    try {
      await api.updateMe({ displayName: nameValue.trim() });
      await refreshMe();
      setNeedName(false);
      await postComment();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error(err);
    } finally {
      setSavingName(false);
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

          {needName && (
            <div className="rounded-lg border border-primary-200 dark:border-primary-800 bg-primary-50 dark:bg-primary-900/20 p-3 space-y-2">
              <p className="text-xs text-primary-800 dark:text-primary-200">
                First, what should we call you? This is the name friends and family see on your note.
              </p>
              <div className="flex gap-2">
                <input
                  value={nameValue}
                  onChange={(e) => setNameValue(e.target.value)}
                  autoFocus
                  maxLength={80}
                  placeholder="e.g. Grandma Rose"
                  aria-label="Your name"
                  onKeyDown={(e) => e.key === 'Enter' && saveNameThenPost()}
                  className="flex-1 px-3 py-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100"
                />
                <button
                  type="button"
                  onClick={saveNameThenPost}
                  disabled={savingName || !nameValue.trim()}
                  className="px-3 py-2 text-sm rounded bg-primary-600 hover:bg-primary-700 text-white font-medium disabled:opacity-50"
                >
                  {savingName ? 'Saving…' : 'Save & post'}
                </button>
              </div>
            </div>
          )}

          {!isDemo && (
            <Composer
              body={body}
              setBody={setBody}
              onSubmit={submit}
              onSignIn={promptSignIn}
              submitting={submitting}
              ref={textareaRef}
              isAuthenticated={isAuthenticated}
            />
          )}
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
          <span className="font-medium text-gray-700 dark:text-gray-200">
            {comment.author_name || 'Someone'}
          </span>
          {' · '}
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
  { body, setBody, onSubmit, onSignIn, submitting, isAuthenticated },
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

  return (
    <div className="space-y-2">
      <textarea
        ref={ref}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={2}
        placeholder="Write a note…"
        aria-label="Your note"
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
