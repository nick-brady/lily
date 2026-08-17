import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import Lightbox from './Lightbox';

function formatPrice(cents) {
  return `$${(cents / 100).toFixed(2)}`;
}

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
  const [familyHasAddress, setFamilyHasAddress] = useState(false);
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
      setFamilyHasAddress(gallery.family_has_shipping_address);
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
      setFamilyHasAddress(gallery.family_has_shipping_address);
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
            // once storage is forever there's nothing left to sell there
            .filter((item) => !(storageLifetime && item.kind === 'storage_gift'))
            .map((item) => (
              <GiftItemCard key={item.id} item={item} birthId={birthId} familyHasAddress={familyHasAddress} />
          ))}
        </div>
      )}
    </section>
  );
}

// Three beautiful designs reads "curated keepsakes"; nine reads "catalog".
const VISIBLE_DESIGNS = 3;

// Taste-ordered: what shows in each product's visible three, best first.
// Unlisted templates keep their generated order after these.
const DESIGN_ORDER = [
  'mug_hours',
  'mug_reel',
  'mug_pool',
  'card_story',
  'card_pool',
  'card_hours_photo',
  'card_welcome',
];

function GiftItemCard({ item, birthId, familyHasAddress }) {
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
              <RenderingTile key={r.id} rendering={r} birthId={birthId} item={item} familyHasAddress={familyHasAddress} />
            ))}
          </div>
          {usable.length > VISIBLE_DESIGNS && !showAll && (
            <button
              type="button"
              onClick={() => setShowAll(true)}
              className="mt-2 text-xs t-muted hover:t-ink transition-colors"
            >
              Show {usable.length - VISIBLE_DESIGNS} more design
              {usable.length - VISIBLE_DESIGNS === 1 ? '' : 's'} →
            </button>
          )}
        </>
      )}
    </div>
  );
}

function StorageGiftCard({ item, birthId }) {
  const [buyOpen, setBuyOpen] = useState(false);
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
          onClick={() => setBuyOpen(true)}
          className="w-full px-3 py-2 text-sm font-medium text-left transition-colors t-btn-accent rounded-none"
        >
          Send this gift · {formatPrice(item.base_price_cents)}
        </button>
      )}

      {buyOpen && (
        <StorageGiftCheckoutSheet
          birthId={birthId}
          item={item}
          onClose={() => setBuyOpen(false)}
        />
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

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div
        className="animate-slide-up w-full sm:max-w-lg bg-white dark:bg-gray-900
                   rounded-t-2xl sm:rounded-2xl shadow-xl p-5 space-y-4 max-h-[85vh] overflow-y-auto"
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

function RenderingTile({ rendering, birthId, item, familyHasAddress }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [buyOpen, setBuyOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  // Lead with the artwork, not the product shot. A mug mockup renders the
  // design an inch wide on a white cylinder — the clock face, which is the
  // reason to want any of this, arrives as a smudge. The mockup answers
  // "what will it be", which only matters once you've wanted the thing;
  // it's a tap away in the detail view, with every angle.
  const src = rendering.artwork_url || rendering.mockup_url;
  // A modal earns itself when there's more to show than the tile already
  // does — the product shots. With nothing but the artwork, the modal would
  // be a box around the same image, so those go straight to full screen.
  const hasDetail = Boolean(
    rendering.mockup_url || (rendering.mockup_extras || []).length > 0,
  );
  const [zoomOpen, setZoomOpen] = useState(false);
  const canOpen = hasDetail || Boolean(rendering.artwork_url);
  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{ borderColor: 'var(--t-soft-ring)' }}
    >
      {rendering.status === 'ready' && src ? (
        <button
          type="button"
          onClick={() => (hasDetail ? setDetailOpen(true) : setZoomOpen(true))}
          disabled={!canOpen}
          className="w-full block"
          style={{ cursor: canOpen ? 'zoom-in' : 'default' }}
          aria-label={
            hasDetail ? 'See the full design and more views' : 'See the design full screen'
          }
        >
          <img
            src={src}
            alt={`${rendering.template_id} design`}
            className="w-full block"
            style={{ backgroundColor: 'var(--t-soft-bg)' }}
          />
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
          onClick={() => setBuyOpen(true)}
          className="w-full px-3 py-2 text-sm font-medium text-left transition-colors t-btn-accent rounded-none"
        >
          Send this gift · {formatPrice(item.base_price_cents)}
        </button>
      )}

      {rendering.status === 'ready' && (
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="w-full px-3 py-2 text-xs t-muted hover:t-ink text-left transition-colors"
        >
          See this design on another product →
        </button>
      )}

      {buyOpen && (
        <GiftCheckoutSheet
          birthId={birthId}
          rendering={rendering}
          item={item}
          familyHasAddress={familyHasAddress}
          onClose={() => setBuyOpen(false)}
        />
      )}

      {pickerOpen && (
        <ProductPickerDialog
          birthId={birthId}
          rendering={rendering}
          onClose={() => setPickerOpen(false)}
        />
      )}

      {detailOpen && (
        <GiftDetailDialog rendering={rendering} onClose={() => setDetailOpen(false)} />
      )}

      {zoomOpen && (
        <Lightbox url={rendering.artwork_url} onClose={() => setZoomOpen(false)} />
      )}
    </div>
  );
}

// The full flat artwork (so you can actually read the design), plus the
// product mockup and any extra angle shots the partner returned — as a
// small tile gallery underneath.
function GiftDetailDialog({ rendering, onClose }) {
  const views = rendering.mockup_url
    ? [{ title: 'Front', url: rendering.mockup_url }, ...(rendering.mockup_extras || [])]
    : [];
  // Which image is blown up, if any. The artwork is the one you actually want
  // to read — at dialog width the clock face is a couple of hundred pixels
  // across, which is smaller than it prints.
  const [zoom, setZoom] = useState(null);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div
        className="animate-slide-up w-full sm:max-w-2xl bg-white dark:bg-gray-900
                   rounded-t-2xl sm:rounded-2xl shadow-xl p-6 space-y-5 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-white">
            The full design
          </h2>
          <p className="text-sm t-muted mt-1">
            {views.length > 1
              ? 'The artwork, and the mug from every angle.'
              : 'The artwork this design is printed from.'}
          </p>
        </div>

        {rendering.artwork_url && (
          <img
            src={rendering.artwork_url}
            alt={`${rendering.template_id} full design`}
            onClick={() => setZoom({ url: rendering.artwork_url, caption: 'The artwork' })}
            className="w-full rounded-lg cursor-zoom-in"
            style={{ backgroundColor: 'var(--t-soft-bg)' }}
          />
        )}

        {views.length > 1 ? (
          <div className="grid grid-cols-3 gap-3">
            {views.map((v, i) => (
              <img
                key={i}
                src={v.url}
                alt={v.title ? `${rendering.template_id} — ${v.title}` : `${rendering.template_id} view`}
                onClick={() => setZoom({ url: v.url, caption: v.title || '' })}
                className="w-full aspect-square object-cover rounded-lg cursor-zoom-in"
                style={{ backgroundColor: 'var(--t-soft-bg)' }}
              />
            ))}
          </div>
        ) : views.length === 1 && !rendering.artwork_url ? (
          <img
            src={views[0].url}
            alt={`${rendering.template_id} design`}
            onClick={() => setZoom({ url: views[0].url, caption: views[0].title || '' })}
            className="w-full rounded-lg cursor-zoom-in"
            style={{ backgroundColor: 'var(--t-soft-bg)' }}
          />
        ) : null}

        <button
          type="button"
          onClick={onClose}
          className="w-full py-3 rounded-xl text-sm font-medium text-gray-600 dark:text-gray-300
                     bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
          Close
        </button>
      </div>

      {/* Closes only itself — the design dialog stays open behind it, so you
          can go straight from one angle to the next. */}
      {zoom && (
        <Lightbox url={zoom.url} caption={zoom.caption} onClose={() => setZoom(null)} />
      )}
    </div>
  );
}

function ProductPickerDialog({ birthId, rendering, onClose }) {
  const [products, setProducts] = useState(null);
  const [error, setError] = useState('');
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const data = await api.listRenderingProducts(birthId, rendering.id);
      setProducts(data.products);
      setError('');
      return data.products;
    } catch (err) {
      setError(err.message || 'Could not load products');
      return null;
    }
  }, [birthId, rendering.id]);

  useEffect(() => {
    load();
    return () => clearTimeout(pollRef.current);
  }, [load]);

  // Poll while any requested mockup is still generating.
  useEffect(() => {
    const pending = (products || []).some((p) => p.status === 'pending');
    if (!pending) return undefined;
    pollRef.current = setTimeout(load, 2500);
    return () => clearTimeout(pollRef.current);
  }, [products, load]);

  const requestMockup = async (productKey) => {
    // Optimistically flip to pending so the tile shows the designing state.
    setProducts((prev) =>
      (prev || []).map((p) =>
        p.product_key === productKey ? { ...p, status: 'pending' } : p,
      ),
    );
    try {
      const updated = await api.requestRenderingProductMockup(
        birthId,
        rendering.id,
        productKey,
      );
      setProducts((prev) =>
        (prev || []).map((p) => (p.product_key === productKey ? updated : p)),
      );
    } catch (err) {
      setError(err.message || 'Could not start the preview');
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div
        className="animate-slide-up w-full sm:max-w-lg bg-white dark:bg-gray-900
                   rounded-t-2xl sm:rounded-2xl shadow-xl p-5 space-y-4 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center">
          <h2 className="text-base font-semibold text-gray-800 dark:text-white">
            Put this design on another product
          </h2>
          <p className="text-xs t-muted mt-1">
            Tap a product to preview this design on it.
          </p>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        {products === null ? (
          <p className="text-sm t-muted text-center py-6">Loading products…</p>
        ) : products.length === 0 ? (
          <p className="text-sm t-muted text-center py-6">
            No other products available for this design yet.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {products.map((p) => (
              <ProductOption
                key={p.product_key}
                product={p}
                onRequest={() => requestMockup(p.product_key)}
              />
            ))}
          </div>
        )}

        <button
          type="button"
          onClick={onClose}
          className="w-full py-3 rounded-xl text-sm font-medium text-gray-600 dark:text-gray-300
                     bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
          Done
        </button>
      </div>
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

function GiftCheckoutSheet({ birthId, rendering, item, familyHasAddress, onClose }) {
  // not either/or — both copies at once is a normal purchase (qty 2)
  const [toFamily, setToFamily] = useState(!item.is_claimed_for_family);
  const [toSelf, setToSelf] = useState(item.is_claimed_for_family);
  const [note, setNote] = useState('');
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');

  const copies = (toFamily ? 1 : 0) + (toSelf ? 1 : 0);
  // Stripe collects one address per checkout (the buyer's, for the self
  // copy) — both copies together need the family's saved address.
  const bothBlocked = toFamily && toSelf && !familyHasAddress;
  const recipientKind = toFamily && toSelf ? 'both' : toFamily ? 'family' : 'self';

  async function startCheckout() {
    setStarting(true);
    setError('');
    try {
      const { url } = await api.createGiftCheckout(birthId, rendering.id, {
        recipientKind,
        giftMessage: note.trim() || null,
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

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center"
      onClick={onClose}
    >
      <div
        className="animate-slide-up w-full sm:max-w-lg bg-white dark:bg-gray-900
                   rounded-t-2xl sm:rounded-2xl shadow-xl p-5 space-y-4 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-center">
          <h2 className="text-base font-semibold text-gray-800 dark:text-white">
            {item.display_name} · {formatPrice(item.base_price_cents)}
          </h2>
          <p className="text-xs t-muted mt-1">Shipping included.</p>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}

        <div className="space-y-2">
          <label
            className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer ${
              item.is_claimed_for_family ? 'opacity-50 cursor-default' : ''
            }`}
            style={{ borderColor: 'var(--t-soft-ring)' }}
          >
            <input
              type="checkbox"
              checked={toFamily}
              disabled={item.is_claimed_for_family}
              onChange={(e) => setToFamily(e.target.checked)}
              className="mt-1"
            />
            <span className="text-sm t-ink">
              Send to the family
              <span className="block text-xs t-muted mt-0.5">
                {item.is_claimed_for_family
                  ? 'Already gifted 🤍'
                  : familyHasAddress
                    ? "Ships to the family's saved address."
                    : "You'll enter their address at checkout."}
              </span>
            </span>
          </label>
          <label
            className="flex items-start gap-3 p-3 rounded-lg border cursor-pointer"
            style={{ borderColor: 'var(--t-soft-ring)' }}
          >
            <input
              type="checkbox"
              checked={toSelf}
              onChange={(e) => setToSelf(e.target.checked)}
              className="mt-1"
            />
            <span className="text-sm t-ink">
              Get one for myself
              <span className="block text-xs t-muted mt-0.5">
                Ships to you — you'll enter your address at checkout.
              </span>
            </span>
          </label>
        </div>

        {bothBlocked && (
          <div
            className="p-3 rounded-lg text-sm t-ink flex items-start gap-2"
            style={{ backgroundColor: 'var(--t-soft-bg)' }}
          >
            <span aria-hidden="true">✋</span>
            <span>
              Both at once needs the family&rsquo;s saved shipping address, and
              they haven&rsquo;t added one yet — uncheck one to continue, and
              send the other separately.
            </span>
          </div>
        )}

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

        <button
          type="button"
          onClick={startCheckout}
          disabled={starting || copies === 0 || bothBlocked}
          className="w-full py-3 rounded-xl text-sm font-medium text-white disabled:opacity-50"
          style={{ backgroundColor: 'var(--t-accent)' }}
        >
          {starting
            ? 'Opening checkout…'
            : `Continue to checkout · ${formatPrice(item.base_price_cents * Math.max(copies, 1))}`}
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
