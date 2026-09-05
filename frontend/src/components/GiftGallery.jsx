import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import AddressForm, { addressComplete, emptyAddress } from './AddressForm';
import { formatPrice } from '../utils/money';
import GiftWizard from './GiftWizard';
import { PRODUCT_NOUN } from '../utils/products';
import useDialog from '../hooks/useDialog';

function formatDate(timestamp) {
  return new Date(timestamp).toLocaleDateString([], { dateStyle: 'long' });
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  });
}

export default function GiftGallery({ birthId, isParent = true }) {
  const [items, setItems] = useState(null);
  const [savedFamilyAddress, setSavedFamilyAddress] = useState(null);
  const [storagePaidUntil, setStoragePaidUntil] = useState(null);
  const [storageLifetime, setStorageLifetime] = useState(false);
  const [artworkReadyAt, setArtworkReadyAt] = useState(null);
  const [error, setError] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const gallery = await api.listGifts(birthId);
      setItems(gallery.items);
      setSavedFamilyAddress(gallery.family_shipping_address || null);
      setStoragePaidUntil(gallery.storage_paid_until);
      setStorageLifetime(gallery.storage_lifetime ?? false);
      setArtworkReadyAt(gallery.artwork_ready_at ?? null);
      setError('');
      return gallery.items;
    } catch (err) {
      setError(err.message || 'Could not load gifts');
      return null;
    }
  }, [birthId]);

  // Poll while any artwork is still rendering.
  useEffect(() => {
    load();
    return () => clearTimeout(pollRef.current);
  }, [load]);

  useEffect(() => {
    const pending = (items || []).some((it) =>
      it.renderings.some((r) => r.status === 'pending'),
    );
    if (!pending) return;
    pollRef.current = setTimeout(load, 2500);
    return () => clearTimeout(pollRef.current);
  }, [items, load]);

  // Artwork waits a few hours after the arrival; during that window there are
  // no renderings to show, only an explanation.
  const settling =
    artworkReadyAt != null
    && new Date(artworkReadyAt) > new Date()
    && !(items || []).some((it) => (it.renderings || []).length > 0);

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const gallery = await api.generateGifts(birthId);
      setItems(gallery.items);
      setSavedFamilyAddress(gallery.family_shipping_address || null);
      setStoragePaidUntil(gallery.storage_paid_until);
      setStorageLifetime(gallery.storage_lifetime ?? false);
      setArtworkReadyAt(gallery.artwork_ready_at ?? null);
    } catch (err) {
      setError(err.message || 'Could not regenerate');
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <section className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold t-ink">Keepsake gifts</h3>
          <p className="text-sm t-muted">
            Auto-designed from this birth's story — ready to send to family.
          </p>
        </div>
        {isParent && (
          <button
            onClick={handleRegenerate}
            disabled={regenerating || items === null}
            className="px-3 py-2 text-sm rounded-lg t-btn-accent font-medium disabled:opacity-50"
          >
            {regenerating ? 'Regenerating…' : 'Regenerate'}
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {storageLifetime ? (
        <p className="mb-4 text-sm t-muted">
          🤍 This page&rsquo;s storage is gifted — it&rsquo;s here forever.
        </p>
      ) : storagePaidUntil ? (
        <p className="mb-4 text-sm t-muted">
          🤍 This page&rsquo;s storage is gifted through {formatDate(storagePaidUntil)}.
        </p>
      ) : null}

      {items === null ? (
        <p className="text-sm t-muted">Loading gifts…</p>
      ) : settling ? (
        // Not a spinner: nothing is being worked on yet, and saying "loading"
        // for four hours would read as broken. The wait is the feature —
        // the arrival time and the measurements are usually still being
        // corrected in the first hour or two.
        <p className="text-sm t-muted">
          Your keepsake designs will be ready around{' '}
          <span className="font-medium t-ink">{formatTime(artworkReadyAt)}</span> — we
          give the birth time and the measurements a few hours to settle so the
          artwork matches the story.
          {isParent && ' Want them sooner? Tap Regenerate.'}
        </p>
      ) : (
        <div className="space-y-6">
          {items
            .filter((item) => item.kind === 'physical' && !PAIRED_KINDS.includes(item.product_kind))
            .map((item) => (
              <GiftItemCard
                key={item.id}
                item={item}
                birthId={birthId}
                savedFamilyAddress={savedFamilyAddress}
                onPhotoChanged={load}
              />
            ))}
          <PairedRow
            items={items.filter((item) => item.kind === 'physical' && PAIRED_KINDS.includes(item.product_kind))}
            birthId={birthId}
            savedFamilyAddress={savedFamilyAddress}
            onPhotoChanged={load}
          />
          <ComingNextSection />
          {items
            // once storage is forever there's nothing left to sell there
            .filter((item) => item.kind === 'storage_gift' && !storageLifetime)
            .map((item) => (
              <GiftItemCard
                key={item.id}
                item={item}
                birthId={birthId}
                savedFamilyAddress={savedFamilyAddress}
                onPhotoChanged={load}
              />
            ))}
        </div>
      )}
    </section>
  );
}

// The book and the ornament each have one design, so they share a row rather
// than each taking a section of their own — two small things side by side
// under the two big ones. Order here is display order.
const PAIRED_KINDS = ['photo_book', 'ornament'];

// Two designs lead each product; "see more" opens the third and the door to
// something custom. Two reads "curated keepsakes"; a wall of them reads
// "catalog", and this page is the former.
const VISIBLE_DESIGNS = 2;

// Taste-ordered: what shows in each product's visible pair, best first.
// Unlisted templates keep their generated order after these.
const DESIGN_ORDER = [
  'mug_hours',
  'mug_reel',
  'mug_pool',
  'frame_wall',
  'frame_story',
  'frame_pool',
  'book_8x8',
  'ornament_circle',
];


function GiftItemCard({ item, birthId, savedFamilyAddress, onPhotoChanged }) {
  const [showAll, setShowAll] = useState(false);
  const designRank = (r) => {
    const i = DESIGN_ORDER.indexOf(r.template_id);
    return i === -1 ? DESIGN_ORDER.length : i;
  };
  const usable = (item.renderings || [])
    .filter((r) => r.status !== 'failed')
    .sort((a, b) => designRank(a) - designRank(b));
  const visible = showAll ? usable : usable.slice(0, VISIBLE_DESIGNS);
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-sm font-medium t-ink">{item.display_name}</span>
        <span className="text-sm t-muted">
          {formatPrice(item.base_price_cents)}
          {item.kind === 'physical' && !item.is_purchasable && (
            <span className="ml-2 text-xs t-muted italic">coming soon</span>
          )}
          {item.is_claimed_for_family && (
            <span className="ml-2 text-xs" title="A family-bound copy has been gifted">
              Already gifted 🤍
            </span>
          )}
        </span>
      </div>

      {item.kind === 'storage_gift' ? (
        <StorageGiftCard item={item} birthId={birthId} />
      ) : usable.length === 0 ? (
        <p className="text-sm t-muted">No designs yet.</p>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {visible.map((r) => (
              <RenderingTile
                key={r.id}
                rendering={r}
                birthId={birthId}
                item={item}
                savedFamilyAddress={savedFamilyAddress}
                onPhotoChanged={onPhotoChanged}
              />
            ))}
            {showAll && <CustomDesignTile noun={PRODUCT_NOUN[item.product_kind] || 'design'} />}
          </div>
          <div className="mt-3 text-center">
            <button
              type="button"
              onClick={() => setShowAll((v) => !v)}
              className="text-xs underline t-muted hover:t-ink transition-colors"
            >
              {showAll ? 'See less' : 'See more'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// A place held for the design that isn't drawn yet — the one a family would
// describe if asked. Not a product: nothing to buy, no price, no editor. It
// sits behind "see more" with the third design so the visible pair stays a
// curated pair and the door is still there for anyone who looks.
function CustomDesignTile({ noun }) {
  return (
    <div
      className="rounded-lg border-2 border-dashed flex flex-col items-center justify-center text-center p-6 min-h-[180px]"
      style={{ borderColor: 'var(--t-soft-ring)' }}
    >
      <span className="text-2xl mb-2" aria-hidden="true">✦</span>
      <span className="text-sm font-medium t-ink">Something of your own</span>
      <span className="text-xs t-muted mt-1">
        A custom {noun} design, drawn for you — coming soon.
      </span>
    </div>
  );
}

// What's next on the shelf, shown honestly as next: real products we've
// priced from the catalogue but haven't drawn the artwork for yet.
const COMING_NEXT = [];

function ComingNextSection() {
  if (COMING_NEXT.length === 0) return null;
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-sm font-medium t-ink">Coming next</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {COMING_NEXT.map((p) => (
          <div
            key={p.key}
            className="rounded-lg border p-4 flex items-start gap-3"
            style={{ borderColor: 'var(--t-soft-ring)', backgroundColor: 'var(--t-soft-bg)' }}
          >
            <span className="text-2xl" aria-hidden="true">{p.icon}</span>
            <div>
              <div className="text-sm font-medium t-ink">{p.name}</div>
              <div className="text-xs t-muted mt-0.5">{p.blurb}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PairedRow({ items, birthId, savedFamilyAddress, onPhotoChanged }) {
  const ordered = PAIRED_KINDS.map((k) => items.find((it) => it.product_kind === k)).filter(Boolean);
  if (ordered.length === 0) return null;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
      {ordered.map((item) => {
        const usable = (item.renderings || []).filter((r) => r.status !== 'failed');
        return (
          <div key={item.id}>
            <div className="flex items-baseline justify-between mb-2">
              <span className="text-sm font-medium t-ink">{item.display_name}</span>
              <span className="text-sm t-muted">
                {formatPrice(item.base_price_cents)}
                {item.is_claimed_for_family && (
                  <span className="ml-2 text-xs" title="A family-bound copy has been gifted">
                    Already gifted 🤍
                  </span>
                )}
              </span>
            </div>
            {usable.length === 0 ? (
              <p className="text-sm t-muted">No designs yet.</p>
            ) : (
              <RenderingTile
                rendering={usable[0]}
                birthId={birthId}
                item={item}
                savedFamilyAddress={savedFamilyAddress}
                onPhotoChanged={onPhotoChanged}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function StorageGiftCard({ item, birthId }) {
  return (
    <div className="rounded-lg border overflow-hidden" style={{ borderColor: 'var(--t-soft-ring)' }}>
      <div
        className="p-4 text-sm t-ink flex items-center gap-3"
        style={{ backgroundColor: 'var(--t-soft-bg)' }}
      >
        <span className="text-2xl" aria-hidden="true">🎁</span>
        {item.storage_years_granted ? (
          <span>
            Gift {item.storage_years_granted} years of storage — less than
            the cost of one photo print per year.
          </span>
        ) : (
          <span>
            Keep this page safe forever — it&rsquo;ll still be here when
            they&rsquo;re 25. One gift, never a renewal.
          </span>
        )}
      </div>

      {item.is_purchasable && !item.is_claimed_for_family && (
        <button
          type="button"
          onClick={() => setWizardAt(0)}
          className="w-full px-3 py-2 text-sm font-medium text-left transition-colors t-btn-accent rounded-none"
        >
          Send this gift · {formatPrice(item.base_price_cents)}
        </button>
      )}

    </div>
  );
}

function StorageGiftCheckoutSheet({ birthId, item, onClose }) {
  const [note, setNote] = useState('');
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');

  async function startCheckout() {
    setStarting(true);
    setError('');
    try {
      const { url } = await api.createStorageGiftCheckout(birthId, item.id, {
        giftMessage: note.trim() || null,
      });
      window.location.assign(url);
    } catch (err) {
      if (err.status === 409) {
        setError('Someone already gifted storage for this family.');
      } else if (err.status === 503) {
        setError("Payments aren't available right now — try again soon.");
      } else {
        setError(err.message || "Couldn't start checkout");
      }
      setStarting(false);
    }
  }

  const panelRef = useDialog(onClose);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        className="animate-slide-up w-full sm:max-w-lg bg-white dark:bg-gray-900
                   rounded-t-2xl sm:rounded-2xl shadow-xl p-5 max-h-[85vh] overflow-y-auto outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center">
          <h2 className="text-base font-semibold text-gray-800 dark:text-white">
            {item.display_name} · {formatPrice(item.base_price_cents)}
          </h2>
          <p className="text-xs t-muted mt-1">
            A gift to the family — keeps this page live {item.storage_years_granted} more years.
          </p>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        <label className="block text-xs t-muted">
          A note for the family (optional)
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            maxLength={500}
            placeholder="I wanted you to have this. Love, Mom."
            className="mt-1 w-full px-3 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink resize-none"
            style={{ borderColor: 'var(--t-soft-ring)' }}
          />
        </label>

        <button
          type="button"
          onClick={startCheckout}
          disabled={starting}
          className="w-full py-3 rounded-xl text-sm font-medium text-white disabled:opacity-50"
          style={{ backgroundColor: 'var(--t-accent)' }}
        >
          {starting ? 'Opening checkout…' : 'Continue to checkout'}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="w-full py-2 rounded-xl text-sm text-gray-600 dark:text-gray-300"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function RenderingTile({
  rendering,
  birthId,
  item,
  savedFamilyAddress,
  onPhotoChanged,
}) {
  // Index into the gallery below, or null. One set of images, one viewer.
  // null, or the step to open the wizard at. The tile has two ways in: the
  // design itself (customise) and the buy button (straight to sending), so
  // someone happy with what they see doesn't have to click through.
  const [wizardAt, setWizardAt] = useState(null);

  // The artwork leads: a mug mockup renders the design an inch wide on a
  // white cylinder, and the clock face — the reason to want any of this —
  // arrives as a smudge. But the product shots still have to be *visible*,
  // not a tap away: "what will it be" is the second question everyone asks,
  // and answering it shouldn't cost a click. So the angles sit under the
  // artwork as thumbnails, and any of them opens the whole set full screen.
  const angles = rendering.mockup_url
    ? [
        { url: rendering.mockup_url, caption: 'Front' },
        ...(rendering.mockup_extras || []).map((v) => ({
          url: v.url,
          caption: v.title || '',
        })),
      ]
    : [];
  const hero = rendering.artwork_url || rendering.mockup_url;
  // A mug's artwork is a wide strip, so its product shots sit in a row
  // beneath it. A print is portrait; stacked over a row of landscape shots it
  // made a tile twice the height of the mug's. Side by side instead — the
  // artwork left, the two shots in a column on the right — and the tile
  // comes out about the mug's shape. The print file is a 12×16 sheet with
  // the mat's share of it blank, so the tile shows just the opening
  // (7.5×11.5 of it, centred): the mockup beside it shows the mat.
  // Anything that isn't a wide mug strip lays out sideways — artwork left,
  // the product shots stacked right — so tiles that share a row share a
  // height. The frame's art is cropped to its mat opening; the book's cover
  // face and the ornament are square.
  const kind = item?.product_kind;
  const portrait = kind === 'framed_print' || kind === 'ornament' || kind === 'photo_book';
  const cropToOpening = kind === 'framed_print';
  const artAspect = cropToOpening ? 'aspect-[15/23]' : 'aspect-square';   // the book's face and the ornament are both square

  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{ borderColor: 'var(--t-soft-ring)' }}
    >
      {rendering.status === 'ready' && hero ? (
        // One target, not four. Each image used to carry its own handler,
        // which left the padding and the gutters between them dead — a click
        // half a centimetre off did nothing, on a card whose whole job is to
        // be clicked. The button wraps the images instead of living inside
        // them, so anywhere in this region opens the editor, and it's one tab
        // stop rather than four.
        <button
          type="button"
          onClick={() => setWizardAt(0)}
          className="w-full block text-left"
          aria-label="Customise this design"
        >
          <span className={portrait ? 'grid grid-cols-[3fr_2fr] gap-1.5 p-1.5' : 'block'}>
            <span
              className={
                portrait
                  ? `block ${artAspect} overflow-hidden rounded flex items-center justify-center`
                  : 'block'
              }
              style={{ backgroundColor: 'var(--t-soft-bg)' }}
            >
              <img
                src={hero}
                alt={`${rendering.template_id} design`}
                className={portrait ? 'h-full w-auto max-w-none block' : 'w-full block'}
                // 1/0.719: the opening is 11.5 of the sheet's 16 inches tall
                style={cropToOpening ? { transform: 'scale(1.39)' } : undefined}
              />
            </span>

            {angles.length > 0 && rendering.artwork_url && (
              <span className={portrait ? 'flex flex-col gap-1.5' : 'flex gap-1.5 p-1.5'}>
                {angles.map((a) => (
                  <span key={a.url} className="flex-1 block rounded overflow-hidden">
                    <img
                      src={a.url}
                      alt={a.caption || `${rendering.template_id} view`}
                      className={`w-full object-cover block ${portrait ? 'h-full' : 'aspect-square'}`}
                      style={{ backgroundColor: 'var(--t-soft-bg)' }}
                    />
                  </span>
                ))}
              </span>
            )}
          </span>
        </button>
      ) : (
        <div className="aspect-[2/1] flex items-center justify-center text-xs t-muted gap-2">
          <span className="w-3 h-3 rounded-full animate-pulse" style={{ backgroundColor: 'var(--t-dot)' }} />
          Designing…
        </div>
      )}

      {rendering.status === 'ready' && item?.is_purchasable && (
        <button
          type="button"
          onClick={() => setWizardAt(0)}
          className="w-full px-3 py-2 text-sm font-medium text-left transition-colors t-btn-accent rounded-none"
        >
          Send this gift · {formatPrice(item.base_price_cents)}
        </button>
      )}

      {wizardAt !== null && (
        <GiftWizard
          birthId={birthId}
          rendering={rendering}
          item={item}
          savedFamilyAddress={savedFamilyAddress}
          onClose={() => setWizardAt(null)}
          onChanged={onPhotoChanged}
          renderCheckout={(current) => (
            <GiftCheckoutSheet
              embedded
              birthId={birthId}
              rendering={current}
              item={item}
              savedFamilyAddress={savedFamilyAddress}
              onClose={() => setWizardAt(null)}
            />
          )}
        />
      )}

    </div>
  );
}

function ProductOption({ product, onRequest }) {
  const clickable = product.status === 'none' || product.status === 'failed';
  return (
    <button
      type="button"
      onClick={clickable ? onRequest : undefined}
      disabled={!clickable}
      className="rounded-lg border overflow-hidden text-left disabled:cursor-default"
      style={{ borderColor: 'var(--t-soft-ring)' }}
    >
      {product.status === 'ready' && product.mockup_url ? (
        <img
          src={product.mockup_url}
          alt={`${product.display_name} preview`}
          className="w-full block aspect-square object-cover"
          style={{ backgroundColor: 'var(--t-soft-bg)' }}
        />
      ) : product.status === 'pending' ? (
        <div className="aspect-square flex items-center justify-center text-xs t-muted gap-2">
          <span className="w-3 h-3 rounded-full animate-pulse" style={{ backgroundColor: 'var(--t-dot)' }} />
          Designing…
        </div>
      ) : product.status === 'failed' ? (
        <div className="aspect-square flex flex-col items-center justify-center text-xs text-red-500 gap-1 px-2 text-center">
          Couldn't preview.
          <span className="t-muted">Tap to retry</span>
        </div>
      ) : (
        <div
          className="aspect-square flex items-center justify-center text-xs t-muted px-2 text-center"
          style={{ backgroundColor: 'var(--t-soft-bg)' }}
        >
          Tap to preview
        </div>
      )}
      <div className="px-2 py-2 text-xs font-medium t-ink">
        {product.display_name}
      </div>
    </button>
  );
}

// One recipient: the tick, and the address that belongs to it. The form used
// to sit in its own box further down the sheet, which left you to work out
// which box it answered — with two of them open at once, that's a real
// question. Ticking a box now opens the box.
//
// The grid 0fr→1fr transition animates to whatever height the form turns out
// to be, which max-height can't do without a magic number that's wrong the
// day a field is added.
function Recipient({ label, hint, checked, disabled = false, onChange, open, children }) {
  return (
    <div
      className={`rounded-lg border ${disabled ? 'opacity-50' : ''}`}
      style={{ borderColor: 'var(--t-soft-ring)' }}
    >
      <label
        className={`flex items-start gap-3 p-3 ${
          disabled ? 'cursor-default' : 'cursor-pointer'
        }`}
      >
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
          className="mt-1"
        />
        <span className="text-sm t-ink">
          {label}
          <span className="block text-xs t-muted mt-0.5">{hint}</span>
        </span>
      </label>
      <div
        className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
        style={{ gridTemplateRows: open ? '1fr' : '0fr' }}
        aria-hidden={!open}
        inert={open ? undefined : ''}
      >
        {/* the row is what animates; this is what gets clipped while it does */}
        <div className="overflow-hidden">
          <div
            className="px-3 pb-3 pt-1 border-t"
            style={{ borderColor: 'var(--t-soft-ring)' }}
          >
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}


// One parcel's postage, asked for once its address is whole and again when
// the address changes — a moment after the last keystroke, not on each one.
// Never a wall: if the quote fails the button still works, and the checkout
// prices the parcel itself.
function useShippingQuote(birthId, renderingId, recipientKind, ready, address) {
  const [state, setState] = useState({ loading: false, quote: null });
  const addressKey = address ? JSON.stringify(address) : '';
  useEffect(() => {
    if (!ready) {
      setState({ loading: false, quote: null });
      return undefined;
    }
    const controller = new AbortController();
    setState((s) => ({ ...s, loading: true }));
    const timer = setTimeout(async () => {
      try {
        const quote = await api.quoteShipping(
          birthId,
          renderingId,
          { recipientKind, address: address || null },
          { signal: controller.signal },
        );
        setState({ loading: false, quote });
      } catch (err) {
        if (err?.name !== 'AbortError') setState({ loading: false, quote: null });
      }
    }, 400);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
    // addressKey stands in for the address object, which is rebuilt on every edit
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [birthId, renderingId, recipientKind, ready, addressKey]);
  return state;
}

// Recipient, note, pay. Its own sheet from the tile's fast lane, or the last
// pane of the customise wizard — `embedded` drops the overlay and panel so it
// can sit inside one that already exists.
function GiftCheckoutSheet({
  birthId,
  rendering,
  item,
  savedFamilyAddress,
  onClose,
  embedded = false,
}) {
  // not either/or — both copies at once is a normal purchase (qty 2)
  const [toFamily, setToFamily] = useState(!item.is_claimed_for_family);
  const [toSelf, setToSelf] = useState(item.is_claimed_for_family);
  const [note, setNote] = useState('');
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');
  // The family's form starts filled with the parents' saved address, so the
  // buyer sees where it's going and can fix what's changed. The people on
  // this page were invited by the family; the address isn't a secret from
  // them, and "is this going to the right place" is the question anyone
  // buying a parcel wants answered.
  const [familyAddress, setFamilyAddress] = useState(() =>
    savedFamilyAddress ? { ...emptyAddress(), ...savedFamilyAddress } : emptyAddress(),
  );
  const [selfAddress, setSelfAddress] = useState(emptyAddress);

  const copies = (toFamily ? 1 : 0) + (toSelf ? 1 : 0);
  const recipientKind = toFamily && toSelf ? 'both' : toFamily ? 'family' : 'self';
  const missingAddress =
    (toFamily && !addressComplete(familyAddress)) ||
    (toSelf && !addressComplete(selfAddress));

  // Postage is quoted per parcel as soon as its address is whole — the same
  // quote the checkout takes, so the total here is the total Stripe shows.
  // Two quotes because two parcels to two places can cost differently.
  const familyQuote = useShippingQuote(
    birthId,
    rendering.id,
    'family',
    toFamily && addressComplete(familyAddress),
    familyAddress,
  );
  const selfQuote = useShippingQuote(
    birthId,
    rendering.id,
    'self',
    toSelf && addressComplete(selfAddress),
    selfAddress,
  );
  const quotes = [toFamily ? familyQuote : null, toSelf ? selfQuote : null].filter(Boolean);
  const quoting = quotes.some((q) => q.loading);
  const priced = copies > 0 && !missingAddress && quotes.every((q) => q.quote);
  const itemCents = quotes.find((q) => q.quote)?.quote.item_cents ?? item.base_price_cents;
  const shippingCents = quotes.reduce((sum, q) => sum + (q.quote?.shipping_cents || 0), 0);
  const totalCents = itemCents * copies + shippingCents;
  const estimated = quotes.some((q) => q.quote?.estimated);

  async function startCheckout() {
    setStarting(true);
    setError('');
    try {
      const { url } = await api.createGiftCheckout(birthId, rendering.id, {
        recipientKind,
        giftMessage: note.trim() || null,
        familyAddress: toFamily ? familyAddress : null,
        selfAddress: toSelf ? selfAddress : null,
      });
      window.location.assign(url);
    } catch (err) {
      if (err.status === 409) {
        setError(
          "Someone already gifted this to the family — you can still get one for yourself.",
        );
        setToFamily(false);
        setToSelf(true);
      } else if (err.status === 503) {
        setError("Payments aren't available right now — try again soon.");
      } else {
        setError(err.message || "Couldn't start checkout");
      }
      setStarting(false);
    }
  }

  const content = (
    <div className="space-y-4">
      <div className="text-center">
        <h2 className="text-base font-semibold text-gray-800 dark:text-white">
          {item.display_name}
        </h2>
        <p className="text-xs t-muted mt-1">Ships within the US.</p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      <div className="space-y-2">
        <Recipient
          label="Send to the family"
          hint={
            item.is_claimed_for_family
              ? 'Already gifted 🤍'
              : savedFamilyAddress
                ? "Their saved address, so you know it's going to the right place."
                : "They haven't saved an address, so you'll need theirs."
          }
          checked={toFamily}
          disabled={item.is_claimed_for_family}
          onChange={setToFamily}
          open={toFamily && !item.is_claimed_for_family}
        >
          <AddressForm
            birthId={birthId}
            value={familyAddress}
            onChange={setFamilyAddress}
          />
        </Recipient>

        <Recipient
          label="Get one for myself"
          hint="Ships to you."
          checked={toSelf}
          onChange={setToSelf}
          open={toSelf}
        >
          <AddressForm birthId={birthId} value={selfAddress} onChange={setSelfAddress} />
        </Recipient>
      </div>

      {toFamily && (
        <label className="block text-xs t-muted">
          A note for the family (printed on the packing slip)
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            maxLength={500}
            placeholder="With so much love…"
            className="mt-1 w-full px-3 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink resize-none"
            style={{ borderColor: 'var(--t-soft-ring)' }}
          />
        </label>
      )}

      {copies > 0 && (
        <dl className="text-xs t-muted space-y-1 px-1">
          <div className="flex justify-between">
            <dt>
              {item.display_name}
              {copies > 1 ? ` × ${copies}` : ''}
            </dt>
            <dd className="t-ink">{formatPrice(itemCents * copies)}</dd>
          </div>
          <div className="flex justify-between">
            <dt>
              Shipping{copies > 1 ? ' (2 parcels)' : ''}
              {estimated ? ' · estimated' : ''}
            </dt>
            <dd className="t-ink">
              {priced
                ? formatPrice(shippingCents)
                : quoting
                  ? 'Checking…'
                  : 'Add the address to see'}
            </dd>
          </div>
          <div
            className="flex justify-between pt-1 border-t font-medium t-ink"
            style={{ borderColor: 'var(--t-soft-ring)' }}
          >
            <dt>Total</dt>
            <dd>{priced ? formatPrice(totalCents) : '—'}</dd>
          </div>
        </dl>
      )}

      <button
        type="button"
        onClick={startCheckout}
        disabled={starting || copies === 0 || missingAddress}
        className="w-full py-3 rounded-xl text-sm font-medium text-white disabled:opacity-50"
        style={{ backgroundColor: 'var(--t-accent)' }}
      >
        {starting
          ? 'Opening checkout…'
          : copies === 0
            ? 'Pick who this is for'
            : missingAddress
              ? 'Add the address above to continue'
              : priced
                ? `Continue to checkout · ${formatPrice(totalCents)}`
                : 'Continue to checkout'}
      </button>
      <button
        type="button"
        onClick={onClose}
        className="w-full py-2 rounded-xl text-sm text-gray-600 dark:text-gray-300"
      >
        Cancel
      </button>
    </div>
  );

  // embedded (inside the gift editor) it is a panel, not a dialog: the ref
  // attaches to nothing and the hook does nothing
  const panelRef = useDialog(onClose);

  if (embedded) return content;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        className="animate-slide-up w-full sm:max-w-lg bg-white dark:bg-gray-900
                   rounded-t-2xl sm:rounded-2xl shadow-xl p-5 max-h-[85vh] overflow-y-auto outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        {content}
      </div>
    </div>
  );
}
