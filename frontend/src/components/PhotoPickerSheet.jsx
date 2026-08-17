import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

// Choosing the photo on one keepsake. Per design on purpose: you're changing
// this mug, not every keepsake at once — so nothing here says "this will
// affect your other designs", because it won't.
//
// Uploads here never reach the timeline. Picking a nicer photo for a mug
// isn't an announcement, and it shouldn't notify everyone the family invited.
export default function PhotoPickerSheet({
  birthId,
  rendering,
  onClose,
  onChanged,
}) {
  const [photos, setPhotos] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listGiftPhotos(birthId)
      .then((rows) => !cancelled && setPhotos(rows))
      .catch((err) => !cancelled && setError(err.message || 'Could not load photos'));
    return () => {
      cancelled = true;
    };
  }, [birthId]);

  // Every path out of here is the same: tell the server, let it re-render
  // this one design, and hand the updated row back so the tile can start
  // polling. Failures keep the sheet open and say why.
  const apply = async (choice) => {
    setBusy(true);
    setError('');
    try {
      const updated = await api.setGiftPhoto(birthId, rendering.id, choice);
      onChanged?.(updated);
      onClose();
    } catch (err) {
      setError(err.message || 'Could not update the photo');
      setBusy(false);
    }
  };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError('');
    try {
      const added = await api.uploadGiftPhoto(birthId, file);
      await apply({ mediaId: added.media_id });
    } catch (err) {
      setError(err.message || "We couldn't add that photo");
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[70] bg-black/40 flex items-end sm:items-center justify-center"
      onClick={(e) => {
        e.stopPropagation();
        onClose();
      }}
    >
      <div
        className="animate-slide-up w-full sm:max-w-lg bg-white dark:bg-gray-900
                   rounded-t-2xl sm:rounded-2xl shadow-xl p-6 space-y-4 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-white">
            Choose the photo
          </h2>
          <p className="text-sm t-muted mt-1">
            Just for this design. Your other keepsakes stay as they are.
          </p>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        {photos === null ? (
          <p className="text-sm t-muted text-center py-6">Loading photos…</p>
        ) : photos.length === 0 ? (
          <p className="text-sm t-muted text-center py-6">
            No photos yet — upload one below.
          </p>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            {photos.map((photo) => {
              const chosen = rendering.photo_media_id === photo.media_id;
              return (
                <button
                  key={photo.media_id}
                  type="button"
                  disabled={busy}
                  onClick={() => apply({ mediaId: photo.media_id })}
                  className="relative block rounded-lg overflow-hidden border-2 disabled:opacity-50"
                  style={{
                    borderColor: chosen ? 'var(--t-accent)' : 'transparent',
                  }}
                >
                  <img
                    src={api.mediaUrl(photo.media_id)}
                    alt={photo.caption || 'Photo'}
                    className="w-full aspect-square object-cover block"
                    style={{ backgroundColor: 'var(--t-soft-bg)' }}
                  />
                </button>
              );
            })}
          </div>
        )}

        <input
          type="file"
          ref={fileRef}
          accept="image/*"
          onChange={upload}
          className="hidden"
        />

        <div className="space-y-2 pt-1">
          <button
            type="button"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
            className="w-full py-3 rounded-xl text-sm font-medium t-btn-accent disabled:opacity-50"
          >
            Upload a photo
          </button>

          {/* Only offered where the design survives without one — on a
              photo-first card, removing it would leave an empty frame. */}
          {rendering.photo_removable && !rendering.photo_removed && (
            <button
              type="button"
              disabled={busy}
              onClick={() => apply({ removed: true })}
              className="w-full py-3 rounded-xl text-sm t-muted hover:t-ink border disabled:opacity-50"
              style={{ borderColor: 'var(--t-soft-ring)' }}
            >
              Use no photo
            </button>
          )}

          {/* There's always a way back to "just pick something for me". */}
          {!rendering.photo_auto && (
            <button
              type="button"
              disabled={busy}
              onClick={() => apply({})}
              className="w-full py-3 rounded-xl text-sm t-muted hover:t-ink border disabled:opacity-50"
              style={{ borderColor: 'var(--t-soft-ring)' }}
            >
              Use the suggested photo
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            className="w-full py-3 rounded-xl text-sm font-medium text-gray-600 dark:text-gray-300
                       bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
