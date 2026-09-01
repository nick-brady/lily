import { useLayoutEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import Modal from './Modal';
import {
  coverOverflow, focusAfterDrag, objectPosition, canReframe, focusOf,
} from '../utils/photoFocus';
import { formatDuration } from '../utils/statistics';
import { toLocalInputValue } from '../utils/relativeTime';
import ReactionBar from './ReactionBar';
import CommentThread from './CommentThread';
import Lightbox from './Lightbox';

const AUDIENCE_LABELS = {
  parents_only: { label: 'Parents', tone: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300' },
};

// The badge marks the exception, never the rule. Family is where posts go
// by default, so badging it would put a label on nearly every row and stop
// meaning anything — the one worth calling out is the post the parents kept
// to themselves. (`public` is retired; old rows in that scope are Family to
// everyone who can see them, so they get no badge either.)
function AudienceBadge({ scope }) {
  const meta = AUDIENCE_LABELS[scope];
  if (!meta) return null;
  return (
    <span className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded ${meta.tone}`}>
      {meta.label}
    </span>
  );
}

const MILESTONES = {
  water_broke: { label: 'Water Broke', icon: '💧' },
  arrived: { label: 'Arrived at Birth Center', icon: '🏠' },
  active_labor: { label: 'Active Labor', icon: '✨' },
  transition: { label: 'Transition', icon: '🌊' },
  pushing: { label: 'Started Pushing', icon: '💪' },
  born: { label: 'Baby Born!', icon: '👶' },
  first_hold: { label: 'First Hold', icon: '🤱' },
  first_feed: { label: 'First Feed', icon: '🍼' },
  name_announced: { label: 'Name Announced', icon: '📝' },
  going_home: { label: 'Going Home', icon: '🏡' },
  other: { label: 'Milestone', icon: '⭐' },
};

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDate(timestamp) {
  const date = new Date(timestamp);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.toDateString() === today.toDateString()) return 'Today';
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
}

function ContractionItem({ event, canManage, onDelete, onToggleIgnore }) {
  const { duration_seconds, ignore_interval_before } = event.payload || {};
  return (
    <div className="flex gap-4 py-3 t-row">
      <div className="w-16 text-right text-sm t-faint pt-1">
        {formatTime(event.occurred_at)}
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ backgroundColor: 'var(--t-dot)' }}
          />
          <span className="t-ink">Contraction</span>
          {duration_seconds && (
            <span className="text-sm t-muted">
              {formatDuration(duration_seconds)}
            </span>
          )}
          {ignore_interval_before && (
            <span className="text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 px-2 py-0.5 rounded">
              gap before
            </span>
          )}
          {canManage && (
            <>
              <button
                onClick={() => onToggleIgnore(event.id)}
                className={`ml-auto p-1 transition-colors ${
                  ignore_interval_before
                    ? 'text-amber-500 hover:text-amber-600'
                    : 'text-gray-300 hover:text-amber-500 dark:text-gray-600 dark:hover:text-amber-400'
                }`}
                title={ignore_interval_before ? 'Remove gap marker' : 'Mark gap before this'}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </button>
              <button
                onClick={() => onDelete(event)}
                className="p-1 text-gray-300 hover:text-red-500 dark:text-gray-600 dark:hover:text-red-400 transition-colors"
                title="Delete contraction"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function MilestoneItem({ event, canManage, onDelete, onEdit, engagementScope }) {
  const { kind, title, body } = event.payload || {};
  const milestone = MILESTONES[kind] || MILESTONES.other;
  return (
    <div className="flex gap-4 py-4 t-row">
      <div className="w-16 text-right text-sm t-faint pt-1">
        {formatTime(event.occurred_at)}
      </div>
      <div className="flex-1">
        <div
          className="rounded-xl p-4 border"
          style={{ backgroundColor: 'var(--t-milestone-bg)', borderColor: 'var(--t-milestone-border)' }}
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-2xl">{milestone.icon}</span>
            <span className="font-semibold" style={{ color: 'var(--t-milestone-text)' }}>
              {title || milestone.label}
            </span>
          </div>
          {body && <p className="t-muted text-sm mt-2">{body}</p>}
        </div>
        {canManage && (
          <ItemActions onEdit={() => onEdit(event)} onDelete={() => onDelete(event)} audienceScope={event.audience_scope} />
        )}
        <EngagementFooter event={event} scope={engagementScope} />
      </div>
    </div>
  );
}

// The birth isn't one milestone among the others. Water Broke and First Feed
// are things that happened on the way; this is the thing they were on the way
// to, and drawing it as another chip in the same soft box said otherwise.
//
// It takes the display face and drops the time gutter every other row keeps,
// so the story visibly arrives somewhere — and it carries its own actions like
// any other post, which is the whole point: undoing the announcement is
// deleting the announcement, right here, rather than a link parked on a
// separate card that only reflected this one.
function BornMilestoneItem({ event, canManage, onDelete, onEdit, engagementScope, childName }) {
  const { body } = event.payload || {};
  return (
    <div className="py-4 t-row">
      <div
        className="rounded-2xl px-6 py-7 text-center border"
        style={{
          backgroundColor: 'var(--t-soft-bg)',
          borderColor: 'var(--t-accent)',
        }}
      >
        <div className="text-3xl mb-2">👶</div>
        <p className="t-display" style={{ fontSize: '1.75rem', lineHeight: 1.2 }}>
          {childName ? `${childName} is here` : 'Baby is here'} 🤍
        </p>
        {/* Time only — the day header sits directly above, and this row gave up
            the gutter that would otherwise have carried the clock. */}
        <p className="text-sm t-muted mt-1">Born {formatTime(event.occurred_at)}</p>
        {body && <p className="t-ink text-sm mt-3">{body}</p>}
      </div>
      {canManage && (
        <ItemActions onEdit={() => onEdit(event)} onDelete={() => onDelete(event)} audienceScope={event.audience_scope} />
      )}
      <EngagementFooter event={event} scope={engagementScope} />
    </div>
  );
}

function MediaItem({ event, canManage, onDelete, onEdit, onPhotoClick, onReframe, engagementScope }) {
  // Scripted fixtures (landing demo, hero video) ride a demo_url on the
  // payload; real events always carry a media_id.
  const { media_id, caption, demo_url } = event.payload || {};
  // The original, for the lightbox and for anything that isn't a photo
  // (a variant of a video is not a thing).
  const url = demo_url || api.mediaUrl(media_id);
  // What the timeline itself draws: 736x384 CSS, so 1600px covers a 2x
  // screen and costs a fifteenth of the original.
  const displayUrl = demo_url || api.mediaUrl(media_id, 'display');
  if (event.event_type === 'photo') {
    return (
      <div className="flex gap-4 py-4 t-row">
        <div className="w-16 text-right text-sm t-faint pt-1">
          {formatTime(event.occurred_at)}
        </div>
        <div className="flex-1">
          <TimelinePhoto
            src={displayUrl}
            caption={caption}
            focus={focusOf(event)}
            onOpen={() => onPhotoClick(url, caption, displayUrl)}
            onReframe={canManage && onReframe ? (focus) => onReframe(event, focus) : null}
          />
          {caption && <p className="t-muted text-sm mt-2">{caption}</p>}
          {canManage && (
            <ItemActions onEdit={() => onEdit(event)} onDelete={() => onDelete(event)} audienceScope={event.audience_scope} />
          )}
          <EngagementFooter event={event} scope={engagementScope} />
        </div>
      </div>
    );
  }

  if (event.event_type === 'video') {
    return (
      <div className="flex gap-4 py-4 t-row">
        <div className="w-16 text-right text-sm t-faint pt-1">
          {formatTime(event.occurred_at)}
        </div>
        <div className="flex-1">
          <div className="rounded-xl overflow-hidden bg-black">
            <video src={url} controls className="w-full max-h-96" />
          </div>
          {caption && <p className="t-muted text-sm mt-2">{caption}</p>}
          {canManage && (
            <ItemActions onEdit={() => onEdit(event)} onDelete={() => onDelete(event)} audienceScope={event.audience_scope} />
          )}
          <EngagementFooter event={event} scope={engagementScope} />
        </div>
      </div>
    );
  }

  // voice memo
  return (
    <div className="flex gap-4 py-4 t-row">
      <div className="w-16 text-right text-sm t-faint pt-1">
        {formatTime(event.occurred_at)}
      </div>
      <div className="flex-1">
        <div
          className="rounded-xl p-4 border"
          style={{ backgroundColor: 'var(--t-memo-bg)', borderColor: 'var(--t-memo-border)' }}
        >
          <div className="flex items-center gap-2 mb-3" style={{ color: 'var(--t-memo-text)' }}>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
            </svg>
            <span className="font-medium">Voice Memo</span>
          </div>
          <audio src={url} controls className="w-full" />
          {caption && <p className="t-muted text-sm mt-3">{caption}</p>}
        </div>
        {canManage && (
          <ItemActions onEdit={() => onEdit(event)} onDelete={() => onDelete(event)} audienceScope={event.audience_scope} />
        )}
        <EngagementFooter event={event} scope={engagementScope} />
      </div>
    </div>
  );
}

function TextNoteItem({ event, canManage, onDelete, onEdit, engagementScope }) {
  const { body } = event.payload || {};
  return (
    <div className="flex gap-4 py-4 t-row">
      <div className="w-16 text-right text-sm t-faint pt-1">
        {formatTime(event.occurred_at)}
      </div>
      <div className="flex-1">
        <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--t-note-bg)' }}>
          <p className="t-ink whitespace-pre-wrap">{body}</p>
        </div>
        {canManage && (
          <ItemActions onEdit={() => onEdit(event)} onDelete={() => onDelete(event)} audienceScope={event.audience_scope} />
        )}
        <EngagementFooter event={event} scope={engagementScope} />
      </div>
    </div>
  );
}

function ItemActions({ onEdit, onDelete, audienceScope }) {
  return (
    <div className="flex items-center gap-3 mt-2">
      <button onClick={onEdit} className="text-xs text-gray-400 hover:text-primary-500">
        Edit
      </button>
      <button onClick={onDelete} className="text-xs text-gray-400 hover:text-red-500">
        Delete
      </button>
      <AudienceBadge scope={audienceScope} />
    </div>
  );
}

/**
 * Engagement footer rendered under everything except contractions.
 * Contractions are high-frequency timing data; reacting to one feels
 * weird. The persona doc explicitly describes "hearts on every
 * milestone" — engagement lives on the stories, not the metrics.
 */
function EngagementFooter({ event, scope }) {
  if (!scope) return null;
  return (
    <div className="mt-3">
      <ReactionBar event={event} scope={scope} />
      <CommentThread
        event={event}
        scope={scope}
        // Scripted fixtures (landing demo, hero video) ride their comments
        // on the event itself; real events never carry demo_comments.
        initialComments={event.demo_comments ?? null}
        defaultExpanded={Boolean(event.demo_comments?.length)}
      />
    </div>
  );
}

/**
 * A photo in the timeline, and the means to say which part of it shows.
 *
 * Every photo gets the same width and a capped height, filled `object-cover`,
 * so a tall one is cropped from its middle — and on a newborn the middle is a
 * torso. "Reposition" turns the picture into something you can drag: pull it
 * down to bring the face into the frame.
 *
 * Only offered when there is something hidden to drag towards, which is why a
 * photo that already fits shows no handle at all.
 */
function TimelinePhoto({ src, caption, focus, onOpen, onReframe }) {
  const [natural, setNatural] = useState(null);
  const [box, setBox] = useState(null);
  const [draft, setDraft] = useState(null);      // the focus while adjusting
  const [saving, setSaving] = useState(false);
  const frameRef = useRef(null);
  const dragRef = useRef(null);

  const adjusting = draft !== null;
  const shown = adjusting ? draft : focus;
  const overflow = coverOverflow(natural, box);
  const movable = canReframe(overflow);

  // Measure the frame after layout, not during render, and only record a
  // size that actually differs.
  //
  // This was a ref callback that called setBox. A ref callback declared in the
  // body is a new function every render, so React detaches and re-attaches the
  // ref each time — and because setBox was handed a fresh object, every
  // attach counted as a change, re-rendered, and re-attached. React caught it
  // as "Maximum update depth exceeded" and took the page down with it.
  //
  // The frame's height depends on the image having loaded, so the observer
  // does the real work: at mount it is often still zero.
  useLayoutEffect(() => {
    const node = frameRef.current;
    if (!node || typeof ResizeObserver === 'undefined') return undefined;
    const read = () => {
      const { clientWidth: width, clientHeight: height } = node;
      setBox((prev) =>
        prev && prev.width === width && prev.height === height ? prev : { width, height },
      );
    };
    read();
    const observer = new ResizeObserver(read);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const onPointerDown = (e) => {
    if (!adjusting) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY, from: shown };
  };
  const onPointerMove = (e) => {
    const d = dragRef.current;
    if (!d) return;
    setDraft(
      focusAfterDrag(d.from, { dx: e.clientX - d.x, dy: e.clientY - d.y }, overflow),
    );
  };
  const endDrag = () => {
    dragRef.current = null;
  };

  const save = async () => {
    setSaving(true);
    try {
      await onReframe(draft);
      setDraft(null);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div
        ref={frameRef}
        className={`group rounded-xl overflow-hidden relative ${adjusting ? 'cursor-grab active:cursor-grabbing touch-none ring-2' : 'cursor-pointer'}`}
        style={{
          backgroundColor: 'var(--t-note-bg)',
          ...(adjusting ? { '--tw-ring-color': 'var(--t-accent)' } : {}),
        }}
        onClick={adjusting ? undefined : onOpen}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <img
          src={src}
          alt={caption || 'Photo'}
          loading="lazy"
          draggable={false}
          onLoad={(e) =>
            setNatural({
              width: e.currentTarget.naturalWidth,
              height: e.currentTarget.naturalHeight,
            })
          }
          className={`w-full max-h-96 object-cover select-none ${
            adjusting ? '' : 'hover:opacity-90 transition-opacity'
          }`}
          style={{ objectPosition: objectPosition(shown) }}
        />
        {adjusting && (
          <span className="absolute inset-x-0 bottom-0 py-1.5 text-center text-[11px]
                           text-white bg-black/50 pointer-events-none">
            Drag the photo to choose what shows
          </span>
        )}
        {/* Quiet enough to ignore, in the corner of the thing it acts on —
            a word under the photo read as part of the post. */}
        {!adjusting && onReframe && movable && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();     // not a click on the photo
              setDraft(focus || { x: 0.5, y: 0.5 });
            }}
            aria-label="Reposition this photo"
            title="Reposition"
            className="absolute bottom-2 right-2 p-1.5 rounded-full
                       bg-black/35 text-white/80 backdrop-blur-sm
                       opacity-0 group-hover:opacity-100 focus:opacity-100
                       hover:bg-black/55 hover:text-white transition-opacity"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 4v16M4 12h16" />
              <path d="M9.5 6.5 12 4l2.5 2.5M9.5 17.5 12 20l2.5-2.5" />
              <path d="M6.5 9.5 4 12l2.5 2.5M17.5 9.5 20 12l-2.5 2.5" />
            </svg>
          </button>
        )}
      </div>

      {adjusting && (
        <div className="flex gap-2 mt-2">
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="px-3 py-1.5 rounded-lg text-xs font-medium t-btn-accent disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Done'}
          </button>
          <button
            type="button"
            onClick={() => setDraft(null)}
            className="px-3 py-1.5 rounded-lg text-xs t-muted"
          >
            Cancel
          </button>
        </div>
      )}

    </>
  );
}

function TimelineItem(props) {
  const { event } = props;
  switch (event.event_type) {
    case 'contraction':
      return <ContractionItem {...props} />;
    case 'milestone':
      return event.payload?.kind === 'born'
        ? <BornMilestoneItem {...props} />
        : <MilestoneItem {...props} />;
    case 'photo':
    case 'video':
    case 'voice_memo':
      return <MediaItem {...props} />;
    case 'text_note':
      return <TextNoteItem {...props} />;
    default:
      return null;
  }
}

function editableFieldFor(event) {
  switch (event.event_type) {
    case 'text_note':
      return { field: 'body', value: event.payload?.body || '' };
    case 'milestone':
      return { field: 'body', value: event.payload?.body || '' };
    case 'photo':
    case 'video':
    case 'voice_memo':
      return { field: 'caption', value: event.payload?.caption || '' };
    default:
      return null;
  }
}

export default function Timeline({
  events,
  canManage = false,
  birthId = null,
  slug = null,
  joinedAbove = false,
  // Only the Born card uses it — the announcement says the name, because the
  // name is the news. Falls back to "Baby is here" for the landing demos.
  childName = null,
}) {
  const engagementScope = birthId
    ? { birthId }
    : slug
      ? { slug }
      : null;
  const [lightbox, setLightbox] = useState({ open: false, url: '', caption: '' });
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [editModal, setEditModal] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [editTime, setEditTime] = useState('');
  const [editError, setEditError] = useState('');
  const [busy, setBusy] = useState(false);

  // `preview` is the copy the timeline already drew — shown instantly while
  // the original loads behind it.
  const openLightbox = (url, caption, preview) =>
    setLightbox({ open: true, url, caption: caption || '', preview });
  const closeLightbox = () => setLightbox({ open: false, url: '', caption: '', preview: undefined });

  // Save which part of a photo shows. The event's own payload carries it, so
  // it reaches every other device the same way a caption does.
  const reframePhoto = birthId
    ? async (event, focus) => {
        await api.editEvent(birthId, event.id, { focal: focus });
      }
    : null;

  const askDelete = (event) => setDeleteConfirm(event);
  const askEdit = (event) => {
    const editable = editableFieldFor(event);
    if (!editable) return;
    setEditValue(editable.value);
    const initialTime = toLocalInputValue(event.occurred_at);
    setEditTime(initialTime);
    setEditError('');
    setEditModal({ event, field: editable.field, initialTime });
  };

  const confirmDelete = async () => {
    if (!deleteConfirm || !birthId) return;
    setBusy(true);
    try {
      await api.deleteEvent(birthId, deleteConfirm.id);
    } finally {
      setBusy(false);
      setDeleteConfirm(null);
    }
  };

  const submitEdit = async () => {
    if (!editModal || !birthId) return;
    setBusy(true);
    setEditError('');
    try {
      const patch = { [editModal.field]: editValue };
      if (editTime && editTime !== editModal.initialTime) {
        patch.occurred_at = new Date(editTime).toISOString();
      }
      await api.editEvent(birthId, editModal.event.id, patch);
      setEditModal(null);
    } catch (err) {
      // Stay open and say why. This used to close on `finally` regardless, so
      // a rejected correction looked exactly like a saved one — the worst
      // possible outcome for someone fixing their baby's arrival time.
      setEditError(err.message || 'Could not save that change');
    } finally {
      setBusy(false);
    }
  };

  const toggleIgnore = async (eventId) => {
    if (!birthId) return;
    await api.toggleIgnoreInterval(birthId, eventId);
  };

  if (!events || events.length === 0) {
    return (
      <div className={`card text-center py-12 ${joinedAbove ? 'rounded-t-none' : ''}`}>
        <p className="t-muted">
          No updates yet. The journey is about to begin!
        </p>
      </div>
    );
  }

  // Group by date, newest first.
  const sorted = [...events].sort(
    (a, b) => new Date(b.occurred_at) - new Date(a.occurred_at),
  );
  const grouped = sorted.reduce((groups, event) => {
    const date = formatDate(event.occurred_at);
    if (!groups[date]) groups[date] = [];
    groups[date].push(event);
    return groups;
  }, {});

  const isBornConfirm =
    deleteConfirm?.event_type === 'milestone' &&
    deleteConfirm?.payload?.kind === 'born';

  return (
    <>
      {deleteConfirm && (
        <Modal onClose={() => setDeleteConfirm(null)}>
          {/* Removing the Born milestone takes the announcement back with it —
              say so plainly. Calling it "this post" and warning it can't be
              undone got both facts backwards: it's the birth record, and it's
              the only way back from a mistaken tap. */}
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            {isBornConfirm
              ? 'Undo the announcement?'
              : `Delete this ${deleteConfirm.event_type === 'contraction' ? 'contraction' : 'post'}?`}
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            {isBornConfirm
              ? "The page goes back to waiting and the arrival time is cleared. Anyone watching sees it return. You can announce again whenever you're ready."
              : "This can't be undone."}
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => setDeleteConfirm(null)}
              className="flex-1 py-2 rounded-lg border border-gray-200 dark:border-gray-700
                         text-gray-600 dark:text-gray-400 font-medium hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Cancel
            </button>
            <button
              onClick={confirmDelete}
              disabled={busy}
              className="flex-1 py-2 rounded-lg bg-red-500 text-white font-medium hover:bg-red-600 disabled:opacity-50"
            >
              {isBornConfirm ? 'Undo' : 'Delete'}
            </button>
          </div>
        </Modal>
      )}

      {editModal && (
        <Modal onClose={() => setEditModal(null)}>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Edit</h3>
          <textarea
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700
                       bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 resize-none"
            rows={3}
          />
          <label className="block mt-3">
            <span className="text-xs text-gray-500 dark:text-gray-400">When it happened</span>
            {/* Same bound as the composer and the Baby Born field: nothing on
                a birth timeline has happened yet in the future. */}
            <input
              type="datetime-local"
              value={editTime}
              onChange={(e) => setEditTime(e.target.value)}
              max={toLocalInputValue()}
              className="mt-1 w-full px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-700
                         bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 text-sm"
            />
          </label>
          {editError && (
            <p className="mt-3 text-sm text-red-600 dark:text-red-400">{editError}</p>
          )}
          <div className="flex gap-3 mt-4">
            <button
              onClick={() => setEditModal(null)}
              className="flex-1 py-2 rounded-lg border border-gray-200 dark:border-gray-700
                         text-gray-600 dark:text-gray-400 font-medium hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Cancel
            </button>
            <button
              onClick={submitEdit}
              disabled={busy}
              className="flex-1 py-2 rounded-lg bg-primary-600 text-white font-medium hover:bg-primary-700 disabled:opacity-50"
            >
              {busy ? 'Saving…' : 'Save'}
            </button>
          </div>
        </Modal>
      )}

      {lightbox.open && (
        <Lightbox
          url={lightbox.url}
          preview={lightbox.preview}
          caption={lightbox.caption}
          onClose={closeLightbox}
        />
      )}

      <div className="space-y-6">
        {Object.entries(grouped).map(([date, items], groupIndex) => (
          // The first group squares its top edge when a composer sits directly
          // above it, so the two share one surface instead of floating apart.
          <div
            key={date}
            className={`card ${joinedAbove && groupIndex === 0 ? 'rounded-t-none' : ''}`}
          >
            <h3 className="text-sm font-medium t-muted mb-4 uppercase tracking-wide">
              {date}
            </h3>
            <div>
              {items.map((event) => (
                <TimelineItem
                  key={event.id}
                  event={event}
                  canManage={canManage}
                  onDelete={askDelete}
                  onEdit={askEdit}
                  onPhotoClick={openLightbox}
                  onReframe={reframePhoto}
                  onToggleIgnore={toggleIgnore}
                  engagementScope={engagementScope}
                  childName={childName}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}


export { MILESTONES };
