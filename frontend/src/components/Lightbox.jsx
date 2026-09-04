import { useEffect, useState } from 'react';
import useDialog from '../hooks/useDialog';

// Full-screen image view, shared by the timeline's photos and the keepsake
// designs. Takes either a single `url` or a set of `images` — a set gets
// arrow-key navigation and on-screen chevrons, so the mug's artwork and its
// angles are one gallery rather than four separate trips through a modal.
//
// Every handler stops propagation. This renders *inside* the design dialog,
// whose backdrop closes it on click — without this, dismissing the image
// would bubble up and close the dialog underneath it, which is never what
// someone flicking through angles meant.
export default function Lightbox({
  url,
  caption = '',
  images,
  startIndex = 0,
  onClose,
  // A smaller copy of the same picture, already in the browser's cache from
  // whatever the viewer clicked. Shown immediately so the screen is never
  // blank, and replaced by `url` — the full original — when that arrives.
  // Full screen is the one place the original earns its size.
  preview,
}) {
  const slides = images?.length ? images : url ? [{ url, caption }] : [];
  const [i, setI] = useState(() => Math.min(Math.max(startIndex, 0), Math.max(slides.length - 1, 0)));
  // whether the full-size image for the current slide has arrived
  const [loaded, setLoaded] = useState(false);
  useEffect(() => setLoaded(false), [i, url]);

  const many = slides.length > 1;

  useEffect(() => {
    if (!slides.length) return undefined;
    const onKey = (e) => {
      if (many && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) {
        // wraps: with four angles, stopping dead at either end just makes
        // you reverse over ground you've already seen
        const step = e.key === 'ArrowRight' ? 1 : -1;
        setI((n) => (n + step + slides.length) % slides.length);
      } else {
        return;
      }
      e.preventDefault();
      e.stopPropagation();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, many, slides.length]);

  if (!slides.length) return null;
  const slide = slides[Math.min(i, slides.length - 1)];

  const stop = (e) => e.stopPropagation();
  const panelRef = useDialog(onClose, { label: 'Photo' });
  const go = (step) => (e) => {
    e.stopPropagation();
    setI((n) => (n + step + slides.length) % slides.length);
  };

  return (
    <div
      ref={panelRef}
      className="fixed inset-0 bg-black/90 z-[60] flex items-center justify-center p-4 outline-none"
      onClick={(e) => {
        e.stopPropagation();
        onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Photo"
    >
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        aria-label="Close"
        className="absolute top-4 right-4 p-2 text-white/80 hover:text-white"
      >
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      {/* Arrow keys are the fast path, but a phone hasn't got any. */}
      {many && (
        <>
          <button
            type="button"
            onClick={go(-1)}
            aria-label="Previous image"
            className="absolute left-2 sm:left-4 p-3 text-white/70 hover:text-white"
          >
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <button
            type="button"
            onClick={go(1)}
            aria-label="Next image"
            className="absolute right-2 sm:right-4 p-3 text-white/70 hover:text-white"
          >
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </>
      )}

      <img
        src={slide.url}
        alt={slide.caption || 'Full size'}
        className="max-w-full max-h-[90vh] object-contain"
        onClick={stop}
        style={preview && !loaded ? { display: 'none' } : undefined}
        onLoad={() => setLoaded(true)}
      />
      {preview && !loaded && (
        <img
          src={preview}
          alt={slide.caption || 'Full size'}
          className="max-w-full max-h-[90vh] object-contain"
          onClick={stop}
        />
      )}

      {(slide.caption || many) && (
        <p className="absolute bottom-4 left-0 right-0 text-center text-white/80 text-sm px-4">
          {slide.caption}
          {slide.caption && many ? ' · ' : ''}
          {many ? `${i + 1} / ${slides.length}` : ''}
        </p>
      )}
    </div>
  );
}
