import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import PhotoPickerSheet from './PhotoPickerSheet';

// Customise → see it on the mug → send.
//
// The split exists because the two halves cost wildly different things. The
// flat artwork re-renders in about half a second and costs us nothing, so you
// can try photos all day. The product shot comes from the fulfillment partner,
// which allows two mockups a minute for the *whole store* — so it's generated
// once per design automatically (that's the gallery you browse), and after
// that only when someone asks, for the design they actually settled on.
//
// Hiding that behind a live preview would either lie or run us out of budget.
// Making it a step is honest: this is the moment you ask to see the real thing.
const STEPS = ['Customise', 'See it', 'Send'];

export default function GiftWizard({
  birthId,
  rendering: initialRendering,
  item,
  familyHasAddress,
  startAt = 0,
  onClose,
  onChanged,
  renderCheckout,
}) {
  const [step, setStep] = useState(startAt);
  const [rendering, setRendering] = useState(initialRendering);
  const [photoOpen, setPhotoOpen] = useState(false);
  const [mockupBusy, setMockupBusy] = useState(false);
  const [error, setError] = useState('');
  const pollRef = useRef(null);

  const angles = rendering.mockup_url
    ? [
        { url: rendering.mockup_url, caption: 'Front' },
        ...(rendering.mockup_extras || []).map((v) => ({
          url: v.url,
          caption: v.title || '',
        })),
      ]
    : [];
  // A mockup made before the last edit still shows the old photo. It's a real
  // photograph of the product, so it's worth showing — but it has to say so.
  const stale = rendering.mockup_status === 'stale';
  const needsMockup = stale || !rendering.mockup_url;

  useEffect(() => () => clearTimeout(pollRef.current), []);

  const refetch = async () => {
    const gallery = await api.listGifts(birthId);
    const fresh = gallery.items
      .flatMap((it) => it.renderings || [])
      .find((r) => r.id === rendering.id);
    if (fresh) setRendering(fresh);
    onChanged?.();
    return fresh;
  };

  // Ask the partner for a product shot, then watch for it. Deliberately not
  // automatic on entering the step — see the note at the top of the file.
  const makeMockup = async () => {
    setMockupBusy(true);
    setError('');
    try {
      await api.refreshGiftMockup(birthId, rendering.id);
      const tick = async () => {
        const fresh = await refetch();
        if (fresh && fresh.mockup_status === 'pending') {
          pollRef.current = setTimeout(tick, 3000);
        } else {
          setMockupBusy(false);
          if (fresh && fresh.mockup_status === 'failed') {
            setError("The mockup didn't come back — the design itself is fine.");
          }
        }
      };
      pollRef.current = setTimeout(tick, 3000);
    } catch (err) {
      setError(err.message || 'Could not start the mockup');
      setMockupBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div
        className="animate-slide-up w-full sm:max-w-3xl bg-white dark:bg-gray-900
                   rounded-t-2xl sm:rounded-2xl shadow-xl max-h-[92vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-5 pt-5">
          {STEPS.map((label, i) => (
            <button
              key={label}
              type="button"
              // Going back is always allowed; skipping ahead isn't, because
              // step 2 is where the mockup gets asked for.
              onClick={() => i < step && setStep(i)}
              className={`text-xs tracking-wide uppercase px-2 py-1 rounded ${
                i === step ? 'font-semibold t-ink' : 't-muted'
              } ${i < step ? 'hover:t-ink' : ''}`}
            >
              {i + 1}. {label}
            </button>
          ))}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="ml-auto p-1 t-muted hover:t-ink"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="mx-5 mt-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        {step === 0 && (
          <div className="p-5 grid gap-5 sm:grid-cols-[1.6fr_1fr]">
            <div>
              {/* The artwork, with a hotspot over the photo itself. You click
                  her face on the design rather than a link in a list — the
                  template tells us where it sits. */}
              <div className="relative">
                <img
                  src={rendering.artwork_url}
                  alt="Your design"
                  className="w-full rounded-lg block"
                  style={{ backgroundColor: 'var(--t-soft-bg)' }}
                />
                {rendering.has_photo && rendering.photo_spot && (
                  <button
                    type="button"
                    onClick={() => setPhotoOpen(true)}
                    aria-label="Change the photo"
                    className="absolute rounded-full border-2 border-dashed opacity-0 hover:opacity-100
                               focus:opacity-100 transition-opacity flex items-center justify-center"
                    style={{
                      // Centre-anchored: the radius is a fraction of the
                      // artwork's *width*, so it can't be measured against
                      // height. Translate off the centre and let aspect-ratio
                      // keep it square whatever shape the canvas is.
                      left: `${rendering.photo_spot[0] * 100}%`,
                      top: `${rendering.photo_spot[1] * 100}%`,
                      transform: 'translate(-50%, -50%)',
                      width: `${rendering.photo_spot[2] * 200}%`,
                      aspectRatio: '1 / 1',
                      borderColor: 'var(--t-accent)',
                      backgroundColor: 'rgba(0,0,0,0.35)',
                    }}
                  >
                    <span className="text-[11px] font-medium text-white px-2 text-center leading-tight">
                      Change photo
                    </span>
                  </button>
                )}
              </div>
              {rendering.has_photo && (
                <p className="text-xs t-muted mt-2">
                  {rendering.photo_removed
                    ? 'No photo on this one.'
                    : rendering.photo_auto
                      ? 'Photo chosen for you — tap it to pick another.'
                      : 'Tap the photo to change it.'}
                </p>
              )}
            </div>

            <div className="space-y-3">
              <div>
                <h2 className="text-base font-semibold t-ink">{item.display_name}</h2>
                <p className="text-xs t-muted mt-1">
                  Everything else is drawn from the birth itself, so it stays true.
                </p>
              </div>

              {rendering.has_photo ? (
                <button
                  type="button"
                  onClick={() => setPhotoOpen(true)}
                  className="w-full py-2.5 rounded-xl text-sm font-medium border t-ink"
                  style={{ borderColor: 'var(--t-soft-ring)' }}
                >
                  {rendering.photo_removed ? 'Add a photo' : 'Change the photo'}
                </button>
              ) : (
                <p className="text-xs t-muted">This design has no photo to change.</p>
              )}

              <button
                type="button"
                onClick={() => setStep(1)}
                className="w-full py-3 rounded-xl text-sm font-medium t-btn-accent"
              >
                Next — see it on the {item.display_name.toLowerCase().includes('mug') ? 'mug' : 'product'}
              </button>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="p-5 space-y-4">
            {angles.length > 0 ? (
              <div className="grid grid-cols-3 gap-3">
                {angles.map((a) => (
                  <img
                    key={a.url}
                    src={a.url}
                    alt={a.caption || 'Product view'}
                    className="w-full aspect-square object-cover rounded-lg block"
                    style={{ backgroundColor: 'var(--t-soft-bg)' }}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm t-muted text-center py-10">
                No product photo yet.
              </p>
            )}

            {mockupBusy ? (
              <p className="text-sm t-muted text-center">
                Photographing your design… this takes about a minute.
              </p>
            ) : needsMockup ? (
              <div className="space-y-2">
                <p className="text-sm t-muted text-center">
                  {stale
                    ? 'These show the design before your last change.'
                    : 'We haven’t photographed this design yet.'}
                </p>
                <button
                  type="button"
                  onClick={makeMockup}
                  className="w-full py-2.5 rounded-xl text-sm font-medium border t-ink"
                  style={{ borderColor: 'var(--t-soft-ring)' }}
                >
                  {stale ? 'Refresh the photos' : 'Photograph it'}
                </button>
              </div>
            ) : null}

            <button
              type="button"
              onClick={() => setStep(2)}
              className="w-full py-3 rounded-xl text-sm font-medium t-btn-accent"
            >
              Next — send this gift
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="p-5">
            {renderCheckout?.(rendering)}
          </div>
        )}
      </div>

      {photoOpen && (
        <PhotoPickerSheet
          birthId={birthId}
          rendering={rendering}
          onClose={() => setPhotoOpen(false)}
          onChanged={(updated) => {
            setRendering(updated);
            onChanged?.();
          }}
        />
      )}
    </div>
  );
}