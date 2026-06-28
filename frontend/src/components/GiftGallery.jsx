import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

function formatPrice(cents) {
  return `$${(cents / 100).toFixed(2)}`;
}

export default function GiftGallery({ birthId }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const rows = await api.listGifts(birthId);
      setItems(rows);
      setError('');
      return rows;
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
      const rows = await api.generateGifts(birthId);
      setItems(rows);
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
        <button
          onClick={handleRegenerate}
          disabled={regenerating || items === null}
          className="px-3 py-2 text-sm rounded-lg t-btn-accent font-medium disabled:opacity-50"
        >
          {regenerating ? 'Regenerating…' : 'Regenerate'}
        </button>
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
            <GiftItemCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </section>
  );
}

function GiftItemCard({ item }) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-sm font-medium t-ink">{item.display_name}</span>
        <span className="text-sm t-muted">{formatPrice(item.base_price_cents)}</span>
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
            <RenderingTile key={r.id} rendering={r} />
          ))}
        </div>
      )}
    </div>
  );
}

function RenderingTile({ rendering }) {
  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{ borderColor: 'var(--t-soft-ring)' }}
    >
      {rendering.status === 'ready' && rendering.artwork_url ? (
        <img
          src={rendering.artwork_url}
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
    </div>
  );
}
