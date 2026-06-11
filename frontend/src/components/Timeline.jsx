import { useState } from 'react';
import { api } from '../api/client';
import { formatDuration } from '../utils/statistics';
import ReactionBar from './ReactionBar';
import CommentThread from './CommentThread';

const AUDIENCE_LABELS = {
  public: { label: 'Public', tone: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300' },
  group_targeted: { label: 'Family', tone: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  parents_only: { label: 'Parents', tone: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300' },
};

function AudienceBadge({ scope }) {
  const meta = AUDIENCE_LABELS[scope] || AUDIENCE_LABELS.public;
  if (scope === 'public') return null;
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

function ContractionItem({ event, canManage, onDelete, onToggleIgnore, accentColor }) {
  const { duration_seconds, ignore_interval_before } = event.payload || {};
  return (
    <div className="flex gap-4 py-3 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
      <div className="w-16 text-right text-sm text-gray-400 dark:text-gray-500 pt-1">
        {formatTime(event.occurred_at)}
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ backgroundColor: accentColor || undefined }}
          />
          <span className="text-gray-700 dark:text-gray-300">Contraction</span>
          {duration_seconds && (
            <span className="text-sm text-gray-500 dark:text-gray-400">
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

function MilestoneItem({ event, canManage, onDelete, onEdit, engagementScope, isUnlocked }) {
  const { kind, title, body } = event.payload || {};
  const milestone = MILESTONES[kind] || MILESTONES.other;
  return (
    <div className="flex gap-4 py-4 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
      <div className="w-16 text-right text-sm text-gray-400 dark:text-gray-500 pt-1">
        {formatTime(event.occurred_at)}
      </div>
      <div className="flex-1">
        <div className="bg-gradient-to-r from-primary-100 to-primary-50 dark:from-primary-900/30 dark:to-primary-800/20
                        rounded-xl p-4 border border-primary-200 dark:border-primary-700/50">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-2xl">{milestone.icon}</span>
            <span className="font-semibold text-primary-700 dark:text-primary-300">
              {title || milestone.label}
            </span>
          </div>
          {body && <p className="text-gray-600 dark:text-gray-400 text-sm mt-2">{body}</p>}
        </div>
        {canManage && (
          <ItemActions onEdit={() => onEdit(event)} onDelete={() => onDelete(event)} audienceScope={event.audience_scope} />
        )}
        <EngagementFooter event={event} scope={engagementScope} isUnlocked={isUnlocked} />
      </div>
    </div>
  );
}

function MediaItem({ event, canManage, onDelete, onEdit, onPhotoClick, engagementScope, isUnlocked }) {
  const { media_id, caption } = event.payload || {};
  const url = api.mediaUrl(media_id);
  if (event.event_type === 'photo') {
    return (
      <div className="flex gap-4 py-4 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
        <div className="w-16 text-right text-sm text-gray-400 dark:text-gray-500 pt-1">
          {formatTime(event.occurred_at)}
        </div>
        <div className="flex-1">
          <div
            className="rounded-xl overflow-hidden bg-gray-100 dark:bg-gray-700 cursor-pointer"
            onClick={() => onPhotoClick(url, caption)}
          >
            <img src={url} alt={caption || 'Photo'} className="w-full max-h-96 object-cover hover:opacity-90 transition-opacity" />
          </div>
          {caption && <p className="text-gray-600 dark:text-gray-400 text-sm mt-2">{caption}</p>}
          {canManage && (
            <ItemActions onEdit={() => onEdit(event)} onDelete={() => onDelete(event)} audienceScope={event.audience_scope} />
          )}
          <EngagementFooter event={event} scope={engagementScope} isUnlocked={isUnlocked} />
        </div>
      </div>
    );
  }

  if (event.event_type === 'video') {
    return (
      <div className="flex gap-4 py-4 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
        <div className="w-16 text-right text-sm text-gray-400 dark:text-gray-500 pt-1">
          {formatTime(event.occurred_at)}
        </div>
        <div className="flex-1">
          <div className="rounded-xl overflow-hidden bg-black">
            <video src={url} controls className="w-full max-h-96" />
          </div>
          {caption && <p className="text-gray-600 dark:text-gray-400 text-sm mt-2">{caption}</p>}
          {canManage && (
            <ItemActions onEdit={() => onEdit(event)} onDelete={() => onDelete(event)} audienceScope={event.audience_scope} />
          )}
          <EngagementFooter event={event} scope={engagementScope} isUnlocked={isUnlocked} />
        </div>
      </div>
    );
  }

  // voice memo
  return (
    <div className="flex gap-4 py-4 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
      <div className="w-16 text-right text-sm text-gray-400 dark:text-gray-500 pt-1">
        {formatTime(event.occurred_at)}
      </div>
      <div className="flex-1">
        <div className="bg-rose-50 dark:bg-rose-900/20 rounded-xl p-4 border border-rose-200 dark:border-rose-800/50">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-rose-500">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            </span>
            <span className="font-medium text-rose-700 dark:text-rose-300">Voice Memo</span>
          </div>
          <audio src={url} controls className="w-full" />
          {caption && <p className="text-gray-600 dark:text-gray-400 text-sm mt-3">{caption}</p>}
        </div>
        {canManage && (
          <ItemActions onEdit={() => onEdit(event)} onDelete={() => onDelete(event)} audienceScope={event.audience_scope} />
        )}
        <EngagementFooter event={event} scope={engagementScope} isUnlocked={isUnlocked} />
      </div>
    </div>
  );
}

function TextNoteItem({ event, canManage, onDelete, onEdit, engagementScope, isUnlocked }) {
  const { body } = event.payload || {};
  return (
    <div className="flex gap-4 py-4 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
      <div className="w-16 text-right text-sm text-gray-400 dark:text-gray-500 pt-1">
        {formatTime(event.occurred_at)}
      </div>
      <div className="flex-1">
        <div className="bg-gray-50 dark:bg-gray-700/50 rounded-xl p-4">
          <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{body}</p>
        </div>
        {canManage && (
          <ItemActions onEdit={() => onEdit(event)} onDelete={() => onDelete(event)} audienceScope={event.audience_scope} />
        )}
        <EngagementFooter event={event} scope={engagementScope} isUnlocked={isUnlocked} />
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
function EngagementFooter({ event, scope, isUnlocked }) {
  if (!scope) return null;
  return (
    <div className="mt-3">
      <ReactionBar event={event} scope={scope} />
      <CommentThread event={event} scope={scope} isUnlocked={isUnlocked} />
    </div>
  );
}

function TimelineItem(props) {
  const { event } = props;
  switch (event.event_type) {
    case 'contraction':
      return <ContractionItem {...props} />;
    case 'milestone':
      return <MilestoneItem {...props} />;
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
  isUnlocked = true,
  accentColor = null,
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
  const [busy, setBusy] = useState(false);

  const openLightbox = (url, caption) => setLightbox({ open: true, url, caption: caption || '' });
  const closeLightbox = () => setLightbox({ open: false, url: '', caption: '' });

  const askDelete = (event) => setDeleteConfirm(event);
  const askEdit = (event) => {
    const editable = editableFieldFor(event);
    if (!editable) return;
    setEditValue(editable.value);
    setEditModal({ event, field: editable.field });
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
    try {
      await api.editEvent(birthId, editModal.event.id, { [editModal.field]: editValue });
    } finally {
      setBusy(false);
      setEditModal(null);
    }
  };

  const toggleIgnore = async (eventId) => {
    if (!birthId) return;
    await api.toggleIgnoreInterval(birthId, eventId);
  };

  if (!events || events.length === 0) {
    return (
      <div className="card text-center py-12">
        <p className="text-gray-500 dark:text-gray-400">
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

  return (
    <>
      {deleteConfirm && (
        <Modal onClose={() => setDeleteConfirm(null)}>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            Delete this {deleteConfirm.event_type === 'contraction' ? 'contraction' : 'post'}?
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            This can't be undone.
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
              Delete
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
        <div
          className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
          onClick={closeLightbox}
        >
          <button
            onClick={closeLightbox}
            className="absolute top-4 right-4 p-2 text-white/80 hover:text-white"
          >
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <img
            src={lightbox.url}
            alt={lightbox.caption || 'Photo'}
            className="max-w-full max-h-[90vh] object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          {lightbox.caption && (
            <p className="absolute bottom-4 left-0 right-0 text-center text-white/80 text-sm px-4">
              {lightbox.caption}
            </p>
          )}
        </div>
      )}

      <div className="space-y-6">
        {Object.entries(grouped).map(([date, items]) => (
          <div key={date} className="card">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-4 uppercase tracking-wide">
              {date}
            </h3>
            <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
              {items.map((event) => (
                <TimelineItem
                  key={event.id}
                  event={event}
                  canManage={canManage}
                  onDelete={askDelete}
                  onEdit={askEdit}
                  onPhotoClick={openLightbox}
                  onToggleIgnore={toggleIgnore}
                  engagementScope={engagementScope}
                  isUnlocked={isUnlocked}
                  accentColor={accentColor}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function Modal({ children, onClose }) {
  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-sm w-full p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

export { MILESTONES };
