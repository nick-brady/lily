import { useState } from 'react';
import { formatDuration } from '../utils/statistics';

const API_URL = import.meta.env.DEV ? 'http://localhost:8000' : '';

// Milestone icons/labels
const MILESTONES = {
  'water_broke': { label: 'Water Broke', icon: '💧' },
  'arrived': { label: 'Arrived at Birth Center', icon: '🏠' },
  'active_labor': { label: 'Active Labor', icon: '✨' },
  'transition': { label: 'Transition', icon: '🌊' },
  'pushing': { label: 'Started Pushing', icon: '💪' },
  'born': { label: 'Baby Born!', icon: '👶' },
  'first_hold': { label: 'First Hold', icon: '🤱' },
  'first_feed': { label: 'First Feed', icon: '🍼' },
  'name_announced': { label: 'Name Announced', icon: '📝' },
  'going_home': { label: 'Going Home', icon: '🏡' },
  'other': { label: 'Milestone', icon: '⭐' },
};

function formatTime(timestamp) {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDate(timestamp) {
  const date = new Date(timestamp);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.toDateString() === today.toDateString()) {
    return 'Today';
  } else if (date.toDateString() === yesterday.toDateString()) {
    return 'Yesterday';
  }
  return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
}

function TimelineItem({ item, isAdmin, onDelete, onPhotoClick }) {
  const time = formatTime(item.timestamp);

  if (item.feed_type === 'contraction') {
    return (
      <div className="flex gap-4 py-3 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
        <div className="w-16 text-right text-sm text-gray-400 dark:text-gray-500 pt-1">
          {time}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary-500 animate-pulse" />
            <span className="text-gray-700 dark:text-gray-300">Contraction</span>
            {item.duration_seconds && (
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {formatDuration(item.duration_seconds)}
              </span>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (item.feed_type === 'milestone') {
    const milestone = MILESTONES[item.milestone] || MILESTONES.other;
    return (
      <div className="flex gap-4 py-4 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
        <div className="w-16 text-right text-sm text-gray-400 dark:text-gray-500 pt-1">
          {time}
        </div>
        <div className="flex-1">
          <div className="bg-gradient-to-r from-primary-100 to-primary-50 dark:from-primary-900/30 dark:to-primary-800/20
                          rounded-xl p-4 border border-primary-200 dark:border-primary-700/50">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-2xl">{milestone.icon}</span>
              <span className="font-semibold text-primary-700 dark:text-primary-300">
                {milestone.label}
              </span>
            </div>
            {item.content && (
              <p className="text-gray-600 dark:text-gray-400 text-sm mt-2">{item.content}</p>
            )}
          </div>
          {isAdmin && (
            <button
              onClick={() => onDelete(item.id, 'update')}
              className="text-xs text-gray-400 hover:text-red-500 mt-2"
            >
              Delete
            </button>
          )}
        </div>
      </div>
    );
  }

  if (item.feed_type === 'photo') {
    const photoUrl = `${API_URL}/uploads/${item.photo_filename}`;
    return (
      <div className="flex gap-4 py-4 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
        <div className="w-16 text-right text-sm text-gray-400 dark:text-gray-500 pt-1">
          {time}
        </div>
        <div className="flex-1">
          <div
            className="rounded-xl overflow-hidden bg-gray-100 dark:bg-gray-700 cursor-pointer"
            onClick={() => onPhotoClick(photoUrl, item.content)}
          >
            <img
              src={photoUrl}
              alt={item.content || 'Photo'}
              className="w-full max-h-96 object-cover hover:opacity-90 transition-opacity"
            />
          </div>
          {item.content && (
            <p className="text-gray-600 dark:text-gray-400 text-sm mt-2">{item.content}</p>
          )}
          {isAdmin && (
            <button
              onClick={() => onDelete(item.id, 'update')}
              className="text-xs text-gray-400 hover:text-red-500 mt-2"
            >
              Delete
            </button>
          )}
        </div>
      </div>
    );
  }

  if (item.feed_type === 'note') {
    return (
      <div className="flex gap-4 py-4 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
        <div className="w-16 text-right text-sm text-gray-400 dark:text-gray-500 pt-1">
          {time}
        </div>
        <div className="flex-1">
          <div className="bg-gray-50 dark:bg-gray-700/50 rounded-xl p-4">
            <p className="text-gray-700 dark:text-gray-300">{item.content}</p>
          </div>
          {isAdmin && (
            <button
              onClick={() => onDelete(item.id, 'update')}
              className="text-xs text-gray-400 hover:text-red-500 mt-2"
            >
              Delete
            </button>
          )}
        </div>
      </div>
    );
  }

  if (item.feed_type === 'audio') {
    return (
      <div className="flex gap-4 py-4 border-b border-gray-100 dark:border-gray-700/50 last:border-0">
        <div className="w-16 text-right text-sm text-gray-400 dark:text-gray-500 pt-1">
          {time}
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
            <audio
              src={`${API_URL}/uploads/${item.audio_filename}`}
              controls
              className="w-full"
            />
            {item.content && (
              <p className="text-gray-600 dark:text-gray-400 text-sm mt-3">{item.content}</p>
            )}
          </div>
          {isAdmin && (
            <button
              onClick={() => onDelete(item.id, 'update')}
              className="text-xs text-gray-400 hover:text-red-500 mt-2"
            >
              Delete
            </button>
          )}
        </div>
      </div>
    );
  }

  return null;
}

export default function Timeline({ feed, isAdmin, onDelete }) {
  const [lightbox, setLightbox] = useState({ open: false, url: '', caption: '' });

  const openLightbox = (url, caption) => {
    setLightbox({ open: true, url, caption: caption || '' });
  };

  const closeLightbox = () => {
    setLightbox({ open: false, url: '', caption: '' });
  };

  if (!feed || feed.length === 0) {
    return (
      <div className="card text-center py-12">
        <p className="text-gray-500 dark:text-gray-400">
          No updates yet. The journey is about to begin!
        </p>
      </div>
    );
  }

  // Group items by date
  const groupedByDate = feed.reduce((groups, item) => {
    const date = formatDate(item.timestamp);
    if (!groups[date]) {
      groups[date] = [];
    }
    groups[date].push(item);
    return groups;
  }, {});

  return (
    <>
      {/* Lightbox Modal */}
      {lightbox.open && (
        <div
          className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
          onClick={closeLightbox}
        >
          <button
            onClick={closeLightbox}
            className="absolute top-4 right-4 p-2 text-white/80 hover:text-white transition-colors"
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
        {Object.entries(groupedByDate).map(([date, items]) => (
          <div key={date} className="card">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-4 uppercase tracking-wide">
              {date}
            </h3>
            <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
              {items.map((item) => (
                <TimelineItem
                  key={`${item.feed_type}-${item.id}`}
                  item={item}
                  isAdmin={isAdmin}
                  onDelete={onDelete}
                  onPhotoClick={openLightbox}
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
