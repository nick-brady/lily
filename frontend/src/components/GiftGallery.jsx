import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

function formatPrice(cents) {
  return `$${(cents / 100).toFixed(2)}`;
}

export default function GiftGallery({ birthId, isParent = true }) {
  const [items, setItems] = useState(null);
  const [familyHasAddress, setFamilyHasAddress] = useState(false);
  const [error, setError] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const gallery = await api.listGifts(birthId);
      setItems(gallery.items);
      setFamilyHasAddress(gallery.family_has_shipping_address);
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

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const gallery = await api.generateGifts(birthId);
      setItems(gallery.items);
      setFamilyHasAddress(gallery.family_has_shipping_address);
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

      {items === null ? (
        <p className="text-sm t-muted">Loading gifts…</p>
      ) : (
        <div className="space-y-6">
          {items.map((item) => (
            <GiftItemCard key={item.id} item={item} birthId={birthId} familyHasAddress={familyHasAddress} />
          ))}
        </div>
      )}
    </section>
  );
}

function GiftItemCard({ item, birthId, familyHasAddress }) {
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
        <div
          className="p-4 rounded-lg border text-sm t-ink flex items-center gap-3"
          style={{ backgroundColor: 'var(--t-soft-bg)', borderColor: 'var(--t-soft-ring)' }}
        >
          <span className="text-2xl" aria-hidden="true">🎁</span>
          <span>
            Gift {item.storage_years_granted} years of storage — keep this
            keepsake online for the family.
          </span>
        </div>
      ) : item.renderings.length === 0 ? (
        <p className="text-sm t-muted">No designs yet.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {item.renderings.map((r) => (
            <RenderingTile key={r.id} rendering={r} birthId={birthId} item={item} familyHasAddress={familyHasAddress} />
          ))}
        </div>
      )}
    </div>
  );
}

function RenderingTile({ rendering, birthId, item, familyHasAddress }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [buyOpen, setBuyOpen] = useState(false);
  // Prefer the product mockup (artwork on the real mug/card) when ready;
  // otherwise show the flat artwork.
  const src = rendering.mockup_url || rendering.artwork_url;
  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{ borderColor: 'var(--t-soft-ring)' }}
    >
      {rendering.status === 'ready' && src ? (
        <img
          src={src}
          alt={`${rendering.template_id} design`}
          className="w-full block"
          style={{ backgroundColor: 'var(--t-soft-bg)' }}
        />
      ) : rendering.status === 'failed' ? (
        <div className="aspect-[2/1] flex items-center justify-center text-xs text-red-500 px-3 text-center">
          Couldn't generate this design.
        </div>
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
  const [recipient, setRecipient] = useState(
    item.is_claimed_for_family ? 'self' : 'family',
  );
  const [note, setNote] = useState('');
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');

  async function startCheckout() {
    setStarting(true);
    setError('');
    try {
      const { url } = await api.createGiftCheckout(birthId, rendering.id, {
        recipientKind: recipient,
        giftMessage: note.trim() || null,
      });
      window.location.assign(url);
    } catch (err) {
      if (err.status === 409) {
        setError(
          "Someone already gifted this to the family — you can still get one for yourself.",
        );
        setRecipient('self');
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
              type="radio"
              name="recipient"
              value="family"
              checked={recipient === 'family'}
              disabled={item.is_claimed_for_family}
              onChange={() => setRecipient('family')}
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
              type="radio"
              name="recipient"
              value="self"
              checked={recipient === 'self'}
              onChange={() => setRecipient('self')}
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

        {recipient === 'family' && (
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
