import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { formatPrice } from '../utils/money';

// Customise → see it on the product → send.
//
// The split follows what the two halves cost. The flat artwork renders in
// ~107ms at preview size and costs us nothing, so step one updates as you
// type. The product shot comes from the fulfillment partner, which allows two
// mockups a minute for the *whole store* — so it's generated once per design
// automatically (that's the gallery you browse) and after that only when
// someone asks, for the design they actually settled on.
//
// Pretending the mug could update live would either lie or exhaust that
// budget. So the mug shots sit under the artwork, real but honest: the moment
// you change something they dim and say they're behind.
const STEPS = ['Customise', 'See it', 'Send'];
const DEBOUNCE_MS = 300;

const SLOT_LABELS = { child_name: 'Name', custom_line: 'Your own line' };
const SLOT_PLACEHOLDERS = { child_name: 'Lily Wren', custom_line: 'worth every hour' };
const SLOT_MAX = { child_name: 40, custom_line: 60 };

export default function GiftWizard({
  birthId,
  rendering: initialRendering,
  item,
  familyHasAddress,
  onClose,
  onChanged,
  renderCheckout,
}) {
  const [step, setStep] = useState(0);
  const [rendering, setRendering] = useState(initialRendering);

  // The draft lives here and nowhere else until Next. Previews don't persist,
  // so trying things costs nothing and backing out costs nothing either.
  const [draft, setDraft] = useState(() => ({
    mediaId: initialRendering.photo_media_id || null,
    removed: Boolean(initialRendering.photo_removed),
    text: { ...(initialRendering.text_overrides || {}) },
    productKey: initialRendering.product_key || null,
  }));
  const [products, setProducts] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [photos, setPhotos] = useState(null);
  const [saving, setSaving] = useState(false);
  const [mockupBusy, setMockupBusy] = useState(false);
  const [error, setError] = useState('');

  const fileRef = useRef(null);
  const abortRef = useRef(null);
  const timerRef = useRef(null);
  const pollRef = useRef(null);
  const urlRef = useRef(null);

  const angles = rendering.mockup_url
    ? [
        { url: rendering.mockup_url, caption: 'Front' },
        ...(rendering.mockup_extras || []).map((v) => ({ url: v.url, caption: v.title || '' })),
      ]
    : [];
  // Behind either because we've edited since it was taken, or because the
  // last save marked it so.
  const anglesBehind = dirty || rendering.mockup_status === 'stale';

  useEffect(() => {
    api.listGiftPhotos(birthId).then(setPhotos).catch(() => setPhotos([]));
    // Blank product photos, straight from the partner's catalogue. Choosing a
    // mug costs no mockups at all — only the one you settle on gets
    // photographed with your design on it, at the next step.
    api
      .listRenderingProducts(birthId, initialRendering.id)
      .then((res) => setProducts(res.products || []))
      .catch(() => setProducts([]));
  }, [birthId, initialRendering.id]);

  useEffect(
    () => () => {
      clearTimeout(timerRef.current);
      clearTimeout(pollRef.current);
      abortRef.current?.abort();
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    },
    [],
  );

  // Debounced preview. An in-flight render is abandoned the moment the draft
  // moves on — typing shouldn't queue a render per keystroke.
  const schedulePreview = useCallback(
    (next) => {
      setDirty(true);
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(async () => {
        abortRef.current?.abort();
        const controller = new AbortController();
        abortRef.current = controller;
        setPreviewing(true);
        try {
          const url = await api.previewGiftDesign(birthId, rendering.id, next, {
            signal: controller.signal,
          });
          if (urlRef.current) URL.revokeObjectURL(urlRef.current);
          urlRef.current = url;
          setPreviewUrl(url);
          setError('');
        } catch (err) {
          if (err.name !== 'AbortError') setError(err.message || 'Preview failed');
        } finally {
          if (abortRef.current === controller) setPreviewing(false);
        }
      }, DEBOUNCE_MS);
    },
    [birthId, rendering.id],
  );

  const edit = (patch) => {
    const next = { ...draft, ...patch, text: { ...draft.text, ...(patch.text || {}) } };
    setDraft(next);
    schedulePreview(next);
  };

  const uploadPhoto = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    try {
      const added = await api.uploadGiftPhoto(birthId, file);
      setPhotos((rows) => [...(rows || []), added]);
      edit({ mediaId: added.media_id, removed: false });
    } catch (err) {
      setError(err.message || "We couldn't add that photo");
    }
  };

  const refetch = async () => {
    const gallery = await api.listGifts(birthId);
    const fresh = gallery.items
      .flatMap((it) => it.renderings || [])
      .find((r) => r.id === rendering.id);
    if (fresh) setRendering(fresh);
    onChanged?.();
    return fresh;
  };

  const makeMockup = async () => {
    setMockupBusy(true);
    try {
      await api.refreshGiftMockup(birthId, rendering.id);
      const tick = async () => {
        const fresh = await refetch();
        if (fresh?.mockup_status === 'pending') {
          pollRef.current = setTimeout(tick, 3000);
        } else {
          setMockupBusy(false);
          if (fresh?.mockup_status === 'failed') {
            setError("The photo of the product didn't come back — your design is fine.");
          }
        }
      };
      pollRef.current = setTimeout(tick, 3000);
    } catch (err) {
      setError(err.message || 'Could not photograph the design');
      setMockupBusy(false);
    }
  };

  // Next commits the draft and re-renders at print resolution. Only then does
  // the mockup question arise — and only if something actually changed, so
  // someone who liked what they saw spends none of the partner's budget.
  const goToProduct = async () => {
    if (!dirty) {
      setStep(1);
      return;
    }
    setSaving(true);
    setError('');
    try {
      const saved = await api.saveGiftDesign(birthId, rendering.id, draft);
      setRendering(saved);
      setDirty(false);
      onChanged?.();
      setStep(1);
      makeMockup();
    } catch (err) {
      setError(err.message || 'Could not save the design');
    } finally {
      setSaving(false);
    }
  };

  const shown = previewUrl || rendering.artwork_url;
  const slots = rendering.editable_text || [];

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-end sm:items-center justify-center sm:p-6"
      onClick={onClose}
    >
      <div
        className="animate-slide-up w-full sm:max-w-6xl bg-white dark:bg-gray-900
                   rounded-t-2xl sm:rounded-2xl shadow-xl max-h-[94vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header
          className="flex items-center gap-3 px-5 py-4 border-b"
          style={{ borderColor: 'var(--t-soft-ring)' }}
        >
          {STEPS.map((label, i) => (
            <button
              key={label}
              type="button"
              onClick={() => i < step && setStep(i)}
              className={`text-xs tracking-wide uppercase ${
                i === step ? 'font-semibold t-ink' : 't-muted'
              }`}
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
        </header>

        {error && (
          <div className="mx-5 mt-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        {step === 0 && (
          <div className="flex-1 overflow-y-auto grid sm:grid-cols-[3fr_1fr]">
            {/* The artwork leads and updates as you type; the product shots sit
                beneath it, real but honest about being behind. */}
            <div
              className="flex flex-col justify-center items-center gap-5 p-6"
              style={{ backgroundColor: 'var(--t-soft-bg)' }}
            >
              <div className="relative w-full">
                <img src={shown} alt="Your design" className="w-full rounded-lg block shadow-sm bg-white" />
                {previewing && (
                  <span className="absolute top-3 right-3 text-[11px] px-2 py-1 rounded-full bg-black/60 text-white">
                    updating…
                  </span>
                )}
              </div>

              {angles.length > 0 && (
                <div className="w-full">
                  <div className={`grid grid-cols-3 gap-3 ${anglesBehind ? 'opacity-40' : ''}`}>
                    {angles.map((a) => (
                      <img
                        key={a.url}
                        src={a.url}
                        alt={a.caption || 'On the product'}
                        className="w-full aspect-square object-cover rounded-lg block bg-white"
                      />
                    ))}
                  </div>
                  <p className="text-[11px] t-muted text-center mt-2">
                    {anglesBehind
                      ? 'Shows your design before this change — refreshed at the next step.'
                      : 'On the mug.'}
                  </p>
                </div>
              )}
            </div>

            <div
              className="p-5 space-y-4 border-t sm:border-t-0 sm:border-l"
              style={{ borderColor: 'var(--t-soft-ring)' }}
            >
              <div>
                <h2 className="text-base font-semibold t-ink">{item.display_name}</h2>
                <p className="text-xs t-muted mt-1">
                  The rest is drawn from the birth itself, so it stays true.
                </p>
              </div>

              {slots.map((slot) => (
                <label key={slot} className="block">
                  <span className="text-xs font-medium t-muted">{SLOT_LABELS[slot] || slot}</span>
                  <input
                    type="text"
                    value={draft.text[slot] ?? ''}
                    maxLength={SLOT_MAX[slot] || 60}
                    placeholder={SLOT_PLACEHOLDERS[slot] || ''}
                    onChange={(e) => edit({ text: { [slot]: e.target.value } })}
                    className="mt-1 w-full px-3 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink"
                    style={{ borderColor: 'var(--t-soft-ring)' }}
                  />
                </label>
              ))}

              {(products || []).length > 1 && (
                <div>
                  <span className="text-xs font-medium t-muted">Mug</span>
                  <div className="mt-1 grid grid-cols-3 gap-1.5">
                    {products.map((product, i) => {
                      const chosen = (draft.productKey || products[0].product_key)
                        === product.product_key;
                      return (
                        <button
                          key={product.product_key}
                          type="button"
                          onClick={() => edit({ productKey: product.product_key })}
                          title={product.display_name}
                          className="block rounded border-2 overflow-hidden text-left"
                          style={{ borderColor: chosen ? 'var(--t-accent)' : 'transparent' }}
                        >
                          <img
                            src={product.blank_image_url}
                            alt={product.display_name}
                            className="w-full aspect-square object-contain block bg-white"
                          />
                          {product.surcharge_cents > 0 && (
                            <span className="block text-[10px] text-center py-0.5 t-faint">
                              +{formatPrice(product.surcharge_cents)}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {rendering.has_photo && (
                <div>
                  <span className="text-xs font-medium t-muted">Photo</span>
                  {/* These are the birth's photos — everything posted to the
                      story, plus anything uploaded here. Worth saying so:
                      an unlabelled grid of thumbnails reads as "some photos"
                      rather than "yours, pick one". */}
                  <p className="text-[11px] t-faint mt-0.5">
                    {(photos || []).length > 0
                      ? `From your story — ${photos.length} photo${photos.length === 1 ? '' : 's'}`
                      : 'No photos yet'}
                  </p>
                  <div className="mt-1.5 grid grid-cols-4 gap-1.5 max-h-56 overflow-y-auto">
                    {(photos || []).map((photo) => (
                      <button
                        key={photo.media_id}
                        type="button"
                        onClick={() => edit({ mediaId: photo.media_id, removed: false })}
                        className="block rounded overflow-hidden border-2"
                        style={{
                          borderColor:
                            draft.mediaId === photo.media_id && !draft.removed
                              ? 'var(--t-accent)'
                              : 'transparent',
                        }}
                      >
                        <img
                          src={api.mediaUrl(photo.media_id)}
                          alt=""
                          className="w-full aspect-square object-cover block"
                        />
                      </button>
                    ))}
                  </div>
                  <input type="file" ref={fileRef} accept="image/*" onChange={uploadPhoto} className="hidden" />
                  <div className="flex gap-2 mt-2">
                    <button
                      type="button"
                      onClick={() => fileRef.current?.click()}
                      className="flex-1 py-2 rounded-lg text-xs border t-ink"
                      style={{ borderColor: 'var(--t-soft-ring)' }}
                    >
                      Upload
                    </button>
                    {rendering.photo_removable && (
                      <button
                        type="button"
                        onClick={() => edit({ mediaId: null, removed: !draft.removed })}
                        className="flex-1 py-2 rounded-lg text-xs border t-muted"
                        style={{ borderColor: 'var(--t-soft-ring)' }}
                      >
                        {draft.removed ? 'Put it back' : 'No photo'}
                      </button>
                    )}
                  </div>
                </div>
              )}

              <button
                type="button"
                onClick={goToProduct}
                disabled={saving}
                className="w-full py-3 rounded-xl text-sm font-medium t-btn-accent disabled:opacity-50"
              >
                {saving ? 'Saving…' : 'Next — see it on the product'}
              </button>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="flex-1 overflow-y-auto p-6 space-y-5">
            {mockupBusy ? (
              <div className="py-12 flex flex-col items-center gap-4">
                <span
                  className="w-10 h-10 rounded-full border-2 animate-spin"
                  style={{ borderColor: 'var(--t-accent)', borderTopColor: 'transparent' }}
                />
                <p className="text-sm t-muted text-center">
                  Photographing your design on the mug — about a minute.
                </p>
              </div>
            ) : angles.length > 0 ? (
              <div className="grid grid-cols-3 gap-4">
                {angles.map((a) => (
                  <img
                    key={a.url}
                    src={a.url}
                    alt={a.caption || 'On the product'}
                    className="w-full aspect-square object-cover rounded-lg block"
                    style={{ backgroundColor: 'var(--t-soft-bg)' }}
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm t-muted text-center py-12">No product photo yet.</p>
            )}

            {!mockupBusy && rendering.mockup_status === 'stale' && (
              <button
                type="button"
                onClick={makeMockup}
                className="w-full py-2.5 rounded-xl text-sm border t-ink"
                style={{ borderColor: 'var(--t-soft-ring)' }}
              >
                Refresh these
              </button>
            )}

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
          <div className="flex-1 overflow-y-auto p-5">{renderCheckout?.(rendering)}</div>
        )}
      </div>
    </div>
  );
}
