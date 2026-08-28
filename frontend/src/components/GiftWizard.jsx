import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { formatPrice } from '../utils/money';
import { PRODUCT_NOUN } from '../utils/products';
import Lightbox from './Lightbox';

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
// The name holds a floor of 46px so it never sets smaller than the date line
// beneath it, which means the field has to stop where that floor does. Your
// own line has no such duty — it shrinks as far as it needs to, so it takes
// as much as the design can hold at all: about eighty characters of prose.
const SLOT_MAX = { child_name: 36, custom_line: 80 };

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
    // Seeded from the photo the artwork *actually* used, not from "auto".
    // Auto is re-resolved on every render, so a draft that just said "auto"
    // let an unrelated edit — changing the mug, typing a letter — quietly
    // swap the picture. The draft has to mean what's on screen.
    mediaId:
      initialRendering.photo_media_id
      || initialRendering.photo_media_id_effective
      || null,
    removed: Boolean(initialRendering.photo_removed),
    // The filmstrip designs: one entry per panel, seeded from what each
    // panel actually showed — same reasoning as mediaId above.
    slots: Object.fromEntries(
      (initialRendering.photo_slots_effective || [])
        .map((id, i) => [i, id])
        .filter(([, id]) => id),
    ),
    text: { ...(initialRendering.text_overrides || {}) },
    productKey: initialRendering.product_key || null,
    // the book's middle section as the parent arranged it; null = automatic
    pages: initialRendering.layout_overrides?.pages ?? null,
    // the part of each placed photo that shows; absent = the centre fills the frame
    crop: { ...(initialRendering.photo_crop || {}) },
    // the story frame's ticks: {off: [...], on: [...]}; null = the thinning decides
    story: initialRendering.layout_overrides?.story ?? null,
  }));
  // The story frame's photo roll — every day photo, on or off the line, and
  // how many fit. Seeded from the saved render, refreshed after each tick.
  // Present only on the story frame; its presence is what switches the photo
  // section from a picker to a roll.
  const [roll, setRoll] = useState(initialRendering.story_roll || null);
  const isStory = Boolean(roll);
  // which roll photo the crop box is showing
  const [activeMedia, setActiveMedia] = useState(null);
  const slotCount = isStory ? 0 : initialRendering.photo_slot_count || 0;
  const noun = PRODUCT_NOUN[item.product_kind] || 'product';
  // Which panel the story grid is currently choosing for.
  const [activeSlot, setActiveSlot] = useState(0);
  // The book is many pages. The editor shows one at a time — the cover, then
  // page 1..24 — and only that page's photo slots. `pageIdx` 0 is the cover.
  const isBook = item.product_kind === 'photo_book';
  const [pageIdx, setPageIdx] = useState(0);
  const pageKeyRef = useRef('cover_front');
  // The plan the strip shows. The saved rendering's until the parent adds,
  // removes or moves a page; then the server's plan for the draft, fetched
  // without drawing anything.
  const [planPages, setPlanPages] = useState(null);
  const [products, setProducts] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [photos, setPhotos] = useState(null);
  const [photosError, setPhotosError] = useState('');
  // What each set line ended up at, and the size below which it stops
  // printing well. Seeded from the saved render, refreshed by each preview.
  const [fit, setFit] = useState(() => ({
    sizes: initialRendering.text_sizes || {},
    floor: initialRendering.text_print_floor || 0,
  }));
  const [saving, setSaving] = useState(false);
  const [mockupBusy, setMockupBusy] = useState(false);
  const [error, setError] = useState('');
  // Index into [artwork, ...angles] when the gallery is open, else null.
  const [galleryAt, setGalleryAt] = useState(null);
  // A print-resolution render of the *unsaved* draft, fetched only when
  // someone actually opens it full screen. The 900px live preview is right
  // for typing and wrong for looking closely.
  const [hiResUrl, setHiResUrl] = useState(null);
  const hiResRef = useRef(null);

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
  // Behind because we've edited since it was taken, because the last save
  // marked it so, or because the last attempt to retake it failed — in which
  // case what's on screen is still the older, real photograph.
  const anglesBehind =
    dirty || rendering.mockup_status === 'stale' || rendering.mockup_status === 'failed';

  useEffect(() => {
    // Don't swallow this. An empty grid and "no photos yet" is a claim about
    // the family's story, and getting it wrong because a request failed is
    // worse than saying the request failed.
    api
      .listGiftPhotos(birthId)
      .then((rows) => {
        setPhotos(rows);
        setPhotosError('');
      })
      .catch((err) => {
        setPhotos([]);
        setPhotosError(err.message || 'Could not load your photos');
      });
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
      if (hiResRef.current) URL.revokeObjectURL(hiResRef.current);
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
          const { url, fit: nextFit } = await api.previewGiftDesign(
            birthId,
            rendering.id,
            next,
            { signal: controller.signal, page: isBook ? pageKeyRef.current : undefined },
          );
          if (urlRef.current) URL.revokeObjectURL(urlRef.current);
          urlRef.current = url;
          setPreviewUrl(url);
          if (nextFit) setFit(nextFit);
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
    if (hiResRef.current) {
      URL.revokeObjectURL(hiResRef.current);
      hiResRef.current = null;
    }
    setHiResUrl(null);
    schedulePreview(next);
  };

  // Whether anything distinguishes this design from its untouched default —
  // saved overrides or unsaved edits. That's when "start over" earns a place.
  const customized =
    dirty
    || Boolean(rendering.photo_media_id)
    || Boolean(rendering.photo_removed)
    || Boolean(rendering.product_key)
    || Object.keys(rendering.text_overrides || {}).length > 0
    || Object.keys(rendering.photo_slots || {}).length > 0
    || Boolean(rendering.layout_overrides?.story);

  // Back to the design as it was before anyone touched it: auto photo, no
  // text, the standard mug. Deliberately re-resolves the photo guess — the
  // seeding above exists to stop *accidental* re-resolution; asking for the
  // default is the one time re-resolving is the point. Nothing is saved
  // until Next, so this too can be walked away from.
  const resetToDefault = () => {
    const next = { mediaId: null, removed: false, slots: {}, text: {}, productKey: null, pages: null, crop: {}, story: null };
    setDraft(next);
    setPlanPages(null);
    if (isStory) api.storyRoll(birthId, rendering.id, next).then(setRoll).catch(() => {});
    setActiveSlot(0);
    if (hiResRef.current) {
      URL.revokeObjectURL(hiResRef.current);
      hiResRef.current = null;
    }
    setHiResUrl(null);
    schedulePreview(next);
  };

  // The artwork is the one worth enlarging: it's a 2475px print file, where
  // the mug shots are 1000px photographs. So the gallery leads with it and
  // the angles come along; the viewer never scales past an image's own size,
  // so nothing is blown up into blur.
  const openGallery = async (index) => {
    setGalleryAt(index);
    if (index !== 0 || !dirty || hiResRef.current) return;
    try {
      const { url } = await api.previewGiftDesign(birthId, rendering.id, draft, {
        full: true,
      });
      hiResRef.current = url;
      setHiResUrl(url);
    } catch {
      // the live preview is already on screen; leave it
    }
  };

  const uploadPhoto = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    try {
      const added = await api.uploadGiftPhoto(birthId, file);
      setPhotos((rows) => [...(rows || []), added]);
      if (visibleSlots.length > 0) {
        edit({ slots: { ...draft.slots, [activeSlot]: added.media_id } });
      } else {
        edit({ mediaId: added.media_id, removed: false });
      }
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
      let saved = await api.saveGiftDesign(birthId, rendering.id, draft);
      // The book renders its twenty-six files in the background; wait for it
      // here rather than moving on with a design that isn't drawn yet.
      for (let i = 0; saved?.status === 'pending' && i < 60; i += 1) {
        await new Promise((r) => setTimeout(r, 2500));
        saved = (await refetch()) || saved;
      }
      if (saved?.status === 'failed') {
        throw new Error("The book couldn't be drawn — your changes are kept.");
      }
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

  // The book: its pages, and which one is on screen. `pages` is the saved
  // plan — kind and slots per page — with a URL once each has been drawn.
  const pages = isBook ? planPages || rendering.pages || [] : [];
  const pageKeys = isBook ? ['cover_front', ...pages.map((pg) => pg.key)] : [];
  const currentPage = isBook && pageIdx > 0 ? pages[pageIdx - 1] : null;
  const savedPageUrl = isBook
    ? pageIdx === 0
      ? rendering.artwork_url
      : currentPage?.url || null
    : rendering.artwork_url;
  const goToPage = (idx) => {
    const next = Math.max(0, Math.min(pageKeys.length - 1, idx));
    setPageIdx(next);
    pageKeyRef.current = pageKeys[next];
    const pg = next > 0 ? pages[next - 1] : null;
    if (pg?.slots?.length) setActiveSlot(pg.slots[0]);
    if (hiResRef.current) {
      URL.revokeObjectURL(hiResRef.current);
      hiResRef.current = null;
    }
    setHiResUrl(null);
    if (dirty) schedulePreview(draft);   // the draft, on the new page
    else setPreviewUrl(null);            // the saved page as drawn
  };
  // The book's middle section as the parent arranges it. Starting from the
  // plan on screen (its editable pages), each change is sent for a fresh
  // plan so the strip and the slots follow — nothing is drawn until Next.
  const arrangement = () =>
    draft.pages ?? pages.filter((pg) => pg.editable).map((pg) => ({ kind: pg.kind, count: pg.count }));
  const rearrange = async (next, focusKeyIdx = null) => {
    const draftNext = { ...draft, pages: next };
    setDraft(draftNext);
    setDirty(true);
    try {
      const { pages: fresh } = await api.bookPlan(birthId, rendering.id, draftNext);
      setPlanPages(fresh.map((pg) => ({ ...pg, url: null })));   // not drawn yet
      const keys = ['cover_front', ...fresh.map((pg) => pg.key)];
      const idx = focusKeyIdx == null ? Math.min(pageIdx, keys.length - 1) : Math.max(0, Math.min(keys.length - 1, focusKeyIdx));
      setPageIdx(idx);
      pageKeyRef.current = keys[idx];
      const pg = idx > 0 ? fresh[idx - 1] : null;
      if (pg?.slots?.length) setActiveSlot(pg.slots[0]);
      schedulePreview(draftNext);
    } catch (err) {
      setError(err.message || "Couldn't rearrange the pages");
    }
  };
  // index of the current page within the editable section, or -1
  const editableIdx = currentPage?.editable ? pages.filter((pg) => pg.editable).indexOf(currentPage) : -1;
  const addPage = (spec) => {
    const day = arrangement();
    const at = editableIdx >= 0 ? editableIdx + 1 : day.length;
    day.splice(at, 0, spec);
    // the first fixed page after the head is page_1 + head; the new page sits after the current one
    rearrange(day, editableIdx >= 0 ? pageIdx + 1 : pageIdx);
  };
  const removePage = () => {
    if (editableIdx < 0) return;
    const day = arrangement();
    day.splice(editableIdx, 1);
    rearrange(day, pageIdx);
  };
  const movePage = (dir) => {
    if (editableIdx < 0) return;
    const day = arrangement();
    const to = editableIdx + dir;
    if (to < 0 || to >= day.length) return;
    [day[editableIdx], day[to]] = [day[to], day[editableIdx]];
    rearrange(day, pageIdx + dir);
  };

  // A tick on the story's roll. Off → on pins the photo (safe from the
  // thinning); on → off keeps it away however much room there is. The
  // server then says which photos make the line now — untick one and the
  // room it frees brings back the next — so the roll never guesses.
  const onCount = roll ? roll.photos.filter((p) => p.on).length : 0;
  const rollFull = roll ? onCount >= roll.capacity : false;
  const toggleStoryPhoto = async (mediaId, currentlyOn) => {
    const cur = draft.story || { off: [], on: [] };
    const without = (xs) => (xs || []).filter((x) => x !== mediaId);
    const next = currentlyOn
      ? { off: [...without(cur.off), mediaId], on: without(cur.on) }
      : { off: without(cur.off), on: [...without(cur.on), mediaId] };
    const draftNext = { ...draft, story: next };
    edit({ story: next });
    try {
      setRoll(await api.storyRoll(birthId, rendering.id, draftNext));
    } catch {
      /* the preview still shows the truth; the ticks catch up on the next change */
    }
  };

  // Which photo slots the picker offers: the current page's on a book, all
  // of them on a filmstrip or the wall.
  const visibleSlots = isBook
    ? currentPage?.slots || []
    : Array.from({ length: slotCount }, (_, i) => i);

  const shown = previewUrl || savedPageUrl;
  const slots = rendering.editable_text || [];

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-end sm:items-center justify-center sm:p-6"
      onClick={onClose}
    >
      <div
        className="animate-slide-up w-full sm:max-w-6xl bg-white dark:bg-gray-900
                   rounded-t-2xl sm:rounded-2xl shadow-xl max-h-[94vh] sm:h-[94vh] flex flex-col"
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
          <div className="flex-1 min-h-0 flex flex-col">
          <div className="flex-1 min-h-0 overflow-y-auto sm:overflow-visible grid sm:grid-cols-[minmax(0,3fr)_minmax(0,1fr)]">
            {/* The artwork leads and updates as you type; the product shots sit
                beneath it, real but honest about being behind.

                On desktop this pane is sized to the modal, not to the artwork:
                a portrait print at full column width is taller than the
                screen, and the whole editor scrolled to fit it — options and
                all. So the artwork takes whatever height is left after the
                product strip, and the options column scrolls on its own. */}
            <div
              // min-w-0: a grid column's default min-width is its content's,
              // so a 25-thumbnail page strip would widen this column past the
              // modal rather than scroll inside it
              className="flex flex-col items-center gap-4 p-6 sm:min-h-0 min-w-0"
              style={{ backgroundColor: 'var(--t-soft-bg)' }}
            >
              <div className="relative w-full sm:flex-1 sm:min-h-0 flex items-center justify-center">
                <button
                  type="button"
                  onClick={() => openGallery(0)}
                  className="block w-full sm:w-auto sm:h-full sm:max-w-full"
                  style={{ cursor: 'zoom-in' }}
                  aria-label="See your design full screen"
                >
                  <img
                    src={shown}
                    alt="Your design"
                    className="w-full sm:w-auto sm:h-full sm:max-w-full object-contain rounded-lg block shadow-sm bg-white"
                  />
                </button>
                {previewing && (
                  <span className="absolute top-3 right-3 text-[11px] px-2 py-1 rounded-full bg-black/60 text-white">
                    updating…
                  </span>
                )}
              </div>

              {isBook && pageKeys.length > 1 && (
                <div className="w-full min-w-0 sm:flex-none">
                  <div className="flex items-center gap-2">
                    <button type="button" onClick={() => goToPage(pageIdx - 1)} disabled={pageIdx === 0}
                      className="px-2 py-1 text-sm t-muted disabled:opacity-30" aria-label="Previous page">‹</button>
                    <div className="flex-1 min-w-0 flex gap-1.5 overflow-x-auto py-1">
                      {pageKeys.map((key, idx) => {
                        const pg = idx > 0 ? pages[idx - 1] : null;
                        const url = idx === 0 ? rendering.artwork_url : pg?.url;
                        return (
                          <button
                            key={key}
                            type="button"
                            onClick={() => goToPage(idx)}
                            title={idx === 0 ? 'Cover' : `Page ${idx} · ${(pg?.kind || '').replace('_', ' ')}`}
                            className="flex-none w-12 h-12 rounded border-2 overflow-hidden bg-white text-[10px] t-muted"
                            style={{ borderColor: idx === pageIdx ? 'var(--t-accent)' : 'var(--t-soft-ring)' }}
                          >
                            {url ? <img src={url} alt="" className="w-full h-full object-cover" /> : idx === 0 ? 'cover' : idx}
                          </button>
                        );
                      })}
                    </div>
                    <button type="button" onClick={() => goToPage(pageIdx + 1)} disabled={pageIdx >= pageKeys.length - 1}
                      className="px-2 py-1 text-sm t-muted disabled:opacity-30" aria-label="Next page">›</button>
                  </div>
                  <p className="text-[11px] t-muted text-center mt-1">
                    {pageIdx === 0 ? 'The cover' : `Page ${pageIdx} of ${pages.length}`}
                    {currentPage?.kind === 'gallery' ? ` — ${currentPage.count} photo${currentPage.count === 1 ? '' : 's'}, pick below to fill` : ''}
                    {currentPage?.kind === 'write_in' ? ' — ruled, for a pen' : ''}
                    {currentPage?.kind === 'notes' ? " — the family's notes" : ''}
                  </p>
                  {/* Arranging the middle of the book. The title, clock, pool,
                      milestones, the two pages for a pen and the closing stay
                      where they are; everything between is the parent's. The
                      book is always 24 pages: a page added takes the place of
                      a ruled one, a page removed becomes one. */}
                  {(currentPage?.editable || pageIdx === 0) && (
                    <div className="flex flex-wrap items-center justify-center gap-2 mt-2 text-[11px]">
                      {currentPage?.editable && (
                        <>
                          <button type="button" onClick={() => movePage(-1)} className="px-2 py-1 rounded border t-muted" style={{ borderColor: 'var(--t-soft-ring)' }}>← Move</button>
                          <button type="button" onClick={() => movePage(1)} className="px-2 py-1 rounded border t-muted" style={{ borderColor: 'var(--t-soft-ring)' }}>Move →</button>
                          <button type="button" onClick={removePage} className="px-2 py-1 rounded border t-muted" style={{ borderColor: 'var(--t-soft-ring)' }}>Remove page</button>
                          <span className="t-faint">·</span>
                        </>
                      )}
                      <span className="t-faint">Add after this:</span>
                      {[1, 2, 3, 4].map((n) => (
                        <button key={n} type="button" onClick={() => addPage({ kind: 'gallery', count: n })}
                          className="px-2 py-1 rounded border t-ink" style={{ borderColor: 'var(--t-soft-ring)' }}>
                          {n} photo{n === 1 ? '' : 's'}
                        </button>
                      ))}
                      <button type="button" onClick={() => addPage({ kind: 'notes' })} className="px-2 py-1 rounded border t-ink" style={{ borderColor: 'var(--t-soft-ring)' }}>Notes</button>
                      <button type="button" onClick={() => addPage({ kind: 'write_in' })} className="px-2 py-1 rounded border t-ink" style={{ borderColor: 'var(--t-soft-ring)' }}>Ruled</button>
                    </div>
                  )}
                </div>
              )}

              {angles.length > 0 && (
                <div className="w-full sm:flex-none">
                  {/* a fixed-height strip, so it never competes with the artwork for room */}
                  <div className={`flex justify-center gap-3 ${anglesBehind ? 'opacity-40' : ''}`}>
                    {angles.map((a, i) => (
                      <button
                        key={a.url}
                        type="button"
                        onClick={() => openGallery(i + 1)}
                        className="block h-24 sm:h-28 aspect-square"
                        style={{ cursor: 'zoom-in' }}
                        aria-label={`See ${a.caption || 'this view'} full screen`}
                      >
                        <img
                          src={a.url}
                          alt={a.caption || 'On the product'}
                          className="w-full h-full object-cover rounded-lg block bg-white"
                        />
                      </button>
                    ))}
                  </div>
                  <p className="text-[11px] t-muted text-center mt-2">
                    {rendering.mockup_status === 'failed'
                      ? "Shows an earlier version — the new photo didn't come back."
                      : anglesBehind
                        ? 'Shows your design before this change — refreshed at the next step.'
                        : `On the ${noun}.`}
                  </p>
                </div>
              )}
            </div>

            {/* The controls scroll; Next doesn't. A long design — the frame
                with its strip, gallery and crop — used to push the button
                below the fold, where nothing said it was there. Pinned
                beneath the column on wide screens, beneath the whole modal
                on a phone, it's in view whatever the design's length. */}
            <div
              className="border-t sm:border-t-0 sm:border-l sm:min-h-0 flex flex-col"
              style={{ borderColor: 'var(--t-soft-ring)' }}
            >
            <div className="p-5 space-y-4 sm:flex-1 sm:min-h-0 sm:overflow-y-auto">
              <div>
                <div className="flex items-baseline justify-between gap-2">
                  <h2 className="text-base font-semibold t-ink">{item.display_name}</h2>
                  {customized && (
                    <button
                      type="button"
                      onClick={resetToDefault}
                      className="text-[11px] underline t-muted whitespace-nowrap"
                    >
                      Reset to default
                    </button>
                  )}
                </div>
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
                  {/* Two different things can be worth saying here, and only
                      one at a time. Running out of room is the common one —
                      with the cap where it is, normal prose hits it long
                      before the type shrinks. Type too small to print is rarer
                      but more serious, so it wins when both are true. */}
                  {(() => {
                    const max = SLOT_MAX[slot] || 60;
                    const used = (draft.text[slot] ?? '').length;
                    const size = fit.sizes[slot] || 0;
                    if (fit.floor > 0 && size > 0 && size < fit.floor) {
                      return (
                        <span className="mt-1 flex items-start gap-1.5 text-[11px] text-amber-700 dark:text-amber-400">
                          <svg className="w-3.5 h-3.5 flex-none mt-px" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                              d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                          </svg>
                          This has shrunk small enough that it may not print clearly.
                        </span>
                      );
                    }
                    if (used >= max) {
                      return (
                        <span className="mt-1 block text-[11px] t-faint">
                          Character limit reached — any longer would set too
                          small to print clearly.
                        </span>
                      );
                    }
                    if (max - used <= 10) {
                      return (
                        <span className="mt-1 block text-[11px] t-faint">
                          {max - used} character{max - used === 1 ? '' : 's'} left
                        </span>
                      );
                    }
                    return null;
                  })()}
                </label>
              ))}

              {(products || []).length > 1 && (
                <div>
                  <span className="text-xs font-medium t-muted">{({ framed_print: 'Frame', ornament: 'Shape', photo_book: 'Paper' })[item.product_kind] || 'Mug'}</span>
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
                          {/* two white books look the same at this size — say which is which */}
                          {(product.caption || product.surcharge_cents > 0) && (
                            <span className="block text-[11px] text-center py-0.5">
                              {product.caption && <span className="t-muted">{product.caption}</span>}
                              {product.caption && product.surcharge_cents > 0 && <span className="t-faint"> · </span>}
                              {product.surcharge_cents > 0 && (
                                <span className="t-faint">+{formatPrice(product.surcharge_cents)}</span>
                              )}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {isStory && (
                <div>
                  <span className="text-xs font-medium t-muted">Photos</span>
                  {/* Not a picker. A photo's place on the line is the moment
                      it was taken, so there is nothing to choose but whether
                      it goes. The roll is the day in order; the tick is the
                      whole decision. */}
                  <p className="text-[11px] t-faint mt-0.5">
                    The day's photos, in order. Each sits on the line at the moment it was taken — tick the ones that go on.
                  </p>
                  <p className="text-[11px] t-muted mt-1">
                    {onCount} of {roll.photos.length} on the frame
                    {roll.photos.length > roll.capacity ? ` · the line holds ${roll.capacity}` : ''}
                    {rollFull && roll.photos.length > onCount ? ' — untick one to make room' : ''}
                  </p>
                  <div className="mt-1.5 grid grid-cols-4 gap-1.5 max-h-56 overflow-y-auto">
                    {roll.photos.map((p, n) => {
                      const blocked = !p.on && rollFull;
                      return (
                        <div
                          key={p.media_id}
                          className={`relative rounded overflow-hidden border-2 aspect-square ${p.on ? '' : 'opacity-60'}`}
                          style={{
                            borderColor: activeMedia === p.media_id ? 'var(--t-accent)' : 'var(--t-soft-ring)',
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => setActiveMedia(p.media_id)}
                            aria-label={`Photo ${n + 1}`}
                            className="absolute inset-0"
                          >
                            <img
                              src={api.mediaUrl(p.media_id)}
                              alt=""
                              className={`absolute inset-0 w-full h-full object-cover ${p.on ? '' : 'grayscale'}`}
                            />
                          </button>
                          <button
                            type="button"
                            onClick={() => toggleStoryPhoto(p.media_id, p.on)}
                            disabled={blocked}
                            title={blocked ? 'The line is full — untick another first' : p.on ? 'Leave off the frame' : 'Put on the frame'}
                            aria-label={p.on ? 'On the frame' : 'Off the frame'}
                            aria-pressed={p.on}
                            className="absolute top-1 left-1 w-5 h-5 rounded-full text-[11px] leading-none flex items-center justify-center border disabled:opacity-40"
                            style={{
                              backgroundColor: p.on ? 'var(--t-accent)' : 'rgba(255,255,255,0.85)',
                              borderColor: p.on ? 'var(--t-accent)' : 'var(--t-soft-ring)',
                              color: p.on ? 'white' : 'var(--t-ink)',
                            }}
                          >
                            {p.on ? '✓' : ''}
                          </button>
                          <span className="absolute bottom-0.5 right-1 text-[10px] px-1 rounded bg-black/50 text-white">
                            {n + 1}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  {(() => {
                    const p = roll.photos.find((x) => x.media_id === activeMedia);
                    if (!p || !p.on) return null;
                    const idx = roll.photos.filter((x) => x.on).indexOf(p);
                    const aspect = (rendering.slot_frame_aspects || [])[idx] || 1;
                    return (
                      <CropBox
                        key={p.media_id}
                        src={api.mediaUrl(p.media_id)}
                        frameAspect={aspect}
                        value={draft.crop?.[p.media_id] || null}
                        onChange={(rect) => edit({ crop: { ...(draft.crop || {}), [p.media_id]: rect } })}
                      />
                    );
                  })()}
                </div>
              )}

              {!isStory && (rendering.has_photo || visibleSlots.length > 0) && (
                <div>
                  <span className="text-xs font-medium t-muted">
                    {visibleSlots.length > 0 ? 'Photos' : 'Photo'}
                  </span>
                  {visibleSlots.length > 0 && (
                    <>
                      <p className="text-[11px] t-faint mt-0.5">
                        {isBook
                          ? `This page holds ${visibleSlots.length} photo${visibleSlots.length === 1 ? '' : 's'} — pick a spot, then choose below. Upload more and more pages fill.`
                          : 'The strip plays the day in order — pick a panel, then choose its photo below.'}
                      </p>
                      <div className="mt-1.5 grid grid-cols-4 gap-1.5">
                        {visibleSlots.map((i, n) => (
                          <button
                            key={i}
                            type="button"
                            onClick={() => setActiveSlot(i)}
                            aria-label={`Photo ${n + 1}`}
                            className="relative rounded overflow-hidden border-2 aspect-square"
                            style={{
                              borderColor:
                                i === activeSlot
                                  ? 'var(--t-accent)'
                                  : 'var(--t-soft-ring)',
                            }}
                          >
                            {draft.slots?.[i] ? (
                              <img
                                src={api.mediaUrl(draft.slots[i])}
                                alt=""
                                className="absolute inset-0 w-full h-full object-cover"
                              />
                            ) : (
                              <span className="absolute inset-0 flex items-center justify-center text-[10px] t-faint">
                                auto
                              </span>
                            )}
                            <span className="absolute bottom-0.5 right-1 text-[10px] px-1 rounded bg-black/50 text-white">
                              {n + 1}
                            </span>
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                  {/* These are the birth's photos — everything posted to the
                      story, plus anything uploaded here. Worth saying so:
                      an unlabelled grid of thumbnails reads as "some photos"
                      rather than "yours, pick one". */}
                  <p className="text-[11px] t-faint mt-0.5">
                    {photosError
                      ? photosError
                      : photos === null
                        ? 'Loading your photos…'
                        : photos.length > 0
                          ? `From your story — ${photos.length} photo${photos.length === 1 ? '' : 's'}`
                          : 'No photos yet'}
                  </p>
                  <div className="mt-1.5 grid grid-cols-4 gap-1.5 max-h-56 overflow-y-auto">
                    {(photos || []).map((photo) => (
                      <button
                        key={photo.media_id}
                        type="button"
                        onClick={() => {
                          if (visibleSlots.length > 0) {
                            edit({
                              slots: { ...draft.slots, [activeSlot]: photo.media_id },
                            });
                            // filling in order is the common case
                            setActiveSlot((cur) => {
                              const k = visibleSlots.indexOf(cur);
                              return visibleSlots[Math.min(k + 1, visibleSlots.length - 1)] ?? cur;
                            });
                          } else {
                            edit({ mediaId: photo.media_id, removed: false });
                          }
                        }}
                        className="block rounded overflow-hidden border-2"
                        style={{
                          borderColor: (
                            visibleSlots.length > 0
                              ? draft.slots?.[activeSlot] === photo.media_id
                              : draft.mediaId === photo.media_id && !draft.removed
                          )
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
                  {/* The crop. The whole photo shows; the rectangle on it is
                      the part that prints, in the shape of the frame it's
                      going into. Drag it to move; zoom in to shrink it, out
                      until it's as large as the photo allows. */}
                  {(() => {
                    const key = visibleSlots.length > 0 ? String(activeSlot) : 'hero';
                    const mediaId = visibleSlots.length > 0 ? draft.slots?.[activeSlot] : (draft.mediaId && !draft.removed ? draft.mediaId : null);
                    if (!mediaId) return null;
                    const aspect = visibleSlots.length > 0
                      ? (rendering.slot_frame_aspects || [])[activeSlot] || 1
                      : rendering.hero_frame_aspect || 1;
                    return (
                      <CropBox
                        key={`${key}-${mediaId}`}
                        src={api.mediaUrl(mediaId)}
                        frameAspect={aspect}
                        value={draft.crop?.[key] || null}
                        onChange={(rect) => edit({ crop: { ...(draft.crop || {}), [key]: rect } })}
                      />
                    );
                  })()}
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

            </div>
            <div
              className="hidden sm:block p-4 border-t shadow-[0_-6px_12px_-8px_rgba(0,0,0,0.25)]"
              style={{ borderColor: 'var(--t-soft-ring)' }}
            >
              <NextButton saving={saving} onClick={goToProduct} />
            </div>
            </div>
          </div>
          <div
            className="sm:hidden p-4 border-t shadow-[0_-6px_12px_-8px_rgba(0,0,0,0.25)]"
            style={{ borderColor: 'var(--t-soft-ring)' }}
          >
            <NextButton saving={saving} onClick={goToProduct} />
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
                  Photographing your design on the {noun} — about a minute.
                </p>
              </div>
            ) : angles.length > 0 ? (
              <div className="grid grid-cols-3 gap-4">
                {angles.map((a, i) => (
                  <button
                    key={a.url}
                    type="button"
                    onClick={() => openGallery(i + 1)}
                    className="block w-full"
                    style={{ cursor: 'zoom-in' }}
                    aria-label={`See ${a.caption || 'this view'} full screen`}
                  >
                    <img
                      src={a.url}
                      alt={a.caption || 'On the product'}
                      className="w-full aspect-square object-cover rounded-lg block"
                      style={{ backgroundColor: 'var(--t-soft-bg)' }}
                    />
                  </button>
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
          <div className="flex-1 overflow-y-auto p-6">
            {/* The editor is as wide as the artwork needs; a form isn't. Held
                to the same column the standalone checkout sheet uses, so a
                checkbox and its label aren't a foot apart. */}
            <div className="max-w-lg mx-auto">{renderCheckout?.(rendering)}</div>
          </div>
        )}

        {galleryAt !== null && (
          <Lightbox
            images={[
              { url: hiResUrl || shown, caption: 'Your design' },
              ...angles,
            ]}
            startIndex={galleryAt}
            onClose={() => setGalleryAt(null)}
          />
        )}
      </div>
    </div>
  );
}


// The crop control: the whole photo, with a draggable rectangle over it in
// the shape of its frame. Coordinates are fractions of the photo — [x, y,
// width] of the rectangle's top-left and width; its height follows the frame.
// The same numbers the renderer reads, so what's dragged here is what prints.
function CropBox({ src, frameAspect, value, onChange }) {
  const [nat, setNat] = useState(null);            // the photo's own width/height
  const boxRef = useRef(null);
  const dragRef = useRef(null);
  const BOX = 240;
  // the widest rectangle of the frame's shape that fits the photo
  const maxW = nat ? Math.min(1, frameAspect * nat.h / nat.w) : 1;
  const heightFor = (w) => (nat ? (w * nat.w) / (nat.h * frameAspect) : w);
  const clamp = (r) => {
    const w = Math.min(maxW, Math.max(0.1, r[2]));
    const h = heightFor(w);
    return [Math.min(1 - w, Math.max(0, r[0])), Math.min(1 - h, Math.max(0, r[1])), w];
  };
  const rect = nat ? clamp(value || [(1 - maxW) / 2, (1 - heightFor(maxW)) / 2, maxW]) : null;
  // the photo drawn to fit the box
  const scale = nat ? Math.min(BOX / nat.w, BOX / nat.h) : 1;
  const dw = nat ? nat.w * scale : BOX;
  const dh = nat ? nat.h * scale : BOX;
  // Zoom is "how much closer than the whole photo": 1 shows as much as fits,
  // 5 shows a fifth of that width. Set from the slider, the wheel, or ±.
  const MAX_ZOOM = 5;
  const level = rect ? maxW / rect[2] : 1;
  const setLevel = (z) => {
    if (!rect) return;
    const zoomTo = Math.min(MAX_ZOOM, Math.max(1, z));
    const w = maxW / zoomTo;
    const h = heightFor(w);
    const cx = rect[0] + rect[2] / 2;
    const cy = rect[1] + heightFor(rect[2]) / 2;
    onChange(clamp([cx - w / 2, cy - h / 2, w]));
  };
  const onWheel = (e) => {
    e.preventDefault();
    setLevel(level * (e.deltaY < 0 ? 1.1 : 1 / 1.1));
  };
  const onPointerDown = (e) => {
    if (!rect) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = { x: e.clientX, y: e.clientY, rect };
  };
  const onPointerMove = (e) => {
    const d = dragRef.current;
    if (!d) return;
    const dx = (e.clientX - d.x) / dw;
    const dy = (e.clientY - d.y) / dh;
    onChange(clamp([d.rect[0] + dx, d.rect[1] + dy, d.rect[2]]));
  };
  const onPointerUp = () => { dragRef.current = null; };
  return (
    <div className="mt-2">
      <p className="text-[11px] t-faint mb-1">Drag the picture to choose what shows · scroll to zoom</p>
      <div
        ref={boxRef}
        className="relative mx-auto select-none touch-none"
        style={{ width: dw, height: dh, cursor: rect ? 'grab' : 'default' }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onWheel={onWheel}
      >
        <img
          src={src}
          alt=""
          draggable={false}
          className="block w-full h-full"
          onLoad={(e) => setNat({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
        />
        {rect && (
          <>
            {/* dim what won't print; leave the rectangle clear */}
            <div className="absolute inset-0 pointer-events-none" style={{ background: 'rgba(0,0,0,0.45)', clipPath: `polygon(0 0, 100% 0, 100% 100%, 0 100%, 0 0, ${rect[0] * 100}% ${rect[1] * 100}%, ${rect[0] * 100}% ${(rect[1] + heightFor(rect[2])) * 100}%, ${(rect[0] + rect[2]) * 100}% ${(rect[1] + heightFor(rect[2])) * 100}%, ${(rect[0] + rect[2]) * 100}% ${rect[1] * 100}%, ${rect[0] * 100}% ${rect[1] * 100}%)` }} />
            <div
              className="absolute border-2 pointer-events-none"
              style={{
                left: `${rect[0] * 100}%`, top: `${rect[1] * 100}%`,
                width: `${rect[2] * 100}%`, height: `${heightFor(rect[2]) * 100}%`,
                borderColor: 'var(--t-accent)', boxShadow: '0 0 0 1px rgba(255,255,255,0.6) inset',
              }}
            />
          </>
        )}
      </div>
      {rect && (
        <div className="mt-2 flex items-center gap-2 mx-auto" style={{ width: dw }}>
          <button type="button" onClick={() => setLevel(level / 1.25)} disabled={level <= 1.001}
            className="w-7 h-7 flex-none rounded-full border text-sm t-ink disabled:opacity-30" style={{ borderColor: 'var(--t-soft-ring)' }} aria-label="Show more of the photo">−</button>
          <input
            type="range"
            min={1}
            max={MAX_ZOOM}
            step={0.01}
            value={level}
            onChange={(e) => setLevel(Number(e.target.value))}
            className="flex-1 accent-[var(--t-accent)]"
            aria-label="Zoom"
          />
          <button type="button" onClick={() => setLevel(level * 1.25)} disabled={level >= MAX_ZOOM - 0.001}
            className="w-7 h-7 flex-none rounded-full border text-sm t-ink disabled:opacity-30" style={{ borderColor: 'var(--t-soft-ring)' }} aria-label="Zoom in closer">+</button>
        </div>
      )}
      {rect && (
        <div className="flex justify-between text-[10px] t-faint mx-auto" style={{ width: dw }}>
          <span>whole photo</span>
          <span>closer</span>
        </div>
      )}
    </div>
  );
}

function NextButton({ saving, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={saving}
      className="w-full py-3 rounded-xl text-sm font-medium t-btn-accent disabled:opacity-50"
    >
      {saving ? 'Saving…' : 'Next — see it on the product'}
    </button>
  );
}
