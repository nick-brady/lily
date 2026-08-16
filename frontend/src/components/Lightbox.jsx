import { useEffect } from 'react';

// Full-screen image view, shared by the timeline's photos and the keepsake
// design dialog. Both had the same job — get a small image out of its box so
// it can actually be looked at — and only one of them had an implementation.
//
// `z-[60]` rather than `z-50`: the design dialog is itself a z-50 overlay, and
// a lightbox opened from inside it has to land on top of the thing that opened
// it. Escape closes it, which matters more here than in a dialog with a
// visible Close button — full-screen with a dark ground gives you nothing else
// to reach for.
export default function Lightbox({ url, caption = '', onClose }) {
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!url) return null;

  return (
    <div
      className="fixed inset-0 bg-black/90 z-[60] flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        className="absolute top-4 right-4 p-2 text-white/80 hover:text-white"
      >
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
      <img
        src={url}
        alt={caption || 'Full size'}
        className="max-w-full max-h-[90vh] object-contain"
        onClick={(e) => e.stopPropagation()}
      />
      {caption && (
        <p className="absolute bottom-4 left-0 right-0 text-center text-white/80 text-sm px-4">
          {caption}
        </p>
      )}
    </div>
  );
}
