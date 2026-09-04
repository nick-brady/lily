import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useAuth } from '../auth';
import Header from '../components/Header';
import { levelColor } from '../palette';

// Every order, newest first: who bought what for which page, the money in
// and out, where the printer has it, and the doors into Stripe's and
// Printful's dashboards. The one place to stand when a buyer writes in
// quoting a reference.

const PRINTFUL_ORDERS = 'https://www.printful.com/dashboard/default/orders';

function usd(cents) {
  if (cents == null) return '—';
  return (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

function when(iso) {
  return iso ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—';
}

// One word per order, and a colour: red for anything the operator must act on.
function state(o) {
  if (o.status === 'pending') return { word: 'unpaid', tone: 'INFO' };
  if (o.status === 'refunded') return { word: o.fulfillment_status === 'canceled' ? 'cancelled' : 'refunded', tone: 'INFO' };
  switch (o.fulfillment_status) {
    case 'shipped':
      return { word: 'shipped', tone: null };
    case 'confirmed':
      return { word: 'in production', tone: null };
    case 'submitted':
      return { word: 'draft — approve?', tone: 'WARNING' };
    case 'failed':
      return { word: 'failed', tone: 'ERROR' };
    case 'on_hold':
      return { word: 'on hold', tone: 'WARNING' };
    default:
      return { word: 'submitting', tone: 'INFO' };
  }
}

export default function OrdersPage() {
  const { logout } = useAuth();
  const [orders, setOrders] = useState(null);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(null);
  const [acting, setActing] = useState(null); // { id, kind: 'approve' | 'cancel' }
  const [busy, setBusy] = useState(false);
  const [actError, setActError] = useState(null);

  const replaceRow = (row) => setOrders((prev) => prev.map((o) => (o.id === row.id ? row : o)));
  const perform = async () => {
    if (!acting) return;
    setBusy(true);
    setActError(null);
    try {
      const row = acting.kind === 'approve' ? await api.approveOrder(acting.id) : await api.cancelOrder(acting.id);
      replaceRow(row);
      setActing(null);
    } catch (err) {
      setActError(err.message || 'That did not go through.');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    api
      .getOrders()
      .then((rows) => !cancelled && setOrders(rows))
      .catch((err) => !cancelled && setError(err));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error?.status === 403) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="card max-w-sm text-center">
          <p className="text-gray-800 font-medium">This account is not an administrator.</p>
          <button onClick={logout} className="mt-4 text-sm text-primary-700 hover:text-primary-800 font-semibold">
            Sign out
          </button>
        </div>
      </div>
    );
  }
  if (error?.status === 401) {
    logout();
    return null;
  }

  const paid = (orders || []).filter((o) => o.status === 'paid');
  const kept = paid.reduce((sum, o) => sum + (o.margin_cents ?? 0), 0);
  const needsAttention = paid.filter((o) => ['failed', 'on_hold'].includes(o.fulfillment_status)).length;

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-4">
      <Header>
        <a
          href={PRINTFUL_ORDERS}
          target="_blank"
          rel="noreferrer"
          className="px-3 py-1.5 text-sm font-medium rounded-lg border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
        >
          Printful orders ↗
        </a>
      </Header>

      {error && <div role="alert" className="card text-red-600 text-sm">{error.message}</div>}

      {orders && (
        <div className="card py-3 px-5 flex items-center gap-x-5 gap-y-1 flex-wrap text-sm">
          <span className="text-gray-700">
            <span className="tabular font-semibold">{paid.length}</span> paid
          </span>
          <span className="text-gray-700">
            <span className="tabular font-semibold">{usd(kept)}</span> kept
          </span>
          {needsAttention > 0 && (
            <span className="font-semibold" style={{ color: levelColor('ERROR') }}>
              {needsAttention} need{needsAttention === 1 ? 's' : ''} attention
            </span>
          )}
        </div>
      )}

      <div className="card p-0 overflow-hidden">
        {!orders && !error && <p className="p-6 text-gray-400 text-sm">Loading…</p>}
        {orders && orders.length === 0 && <p className="p-6 text-gray-400 text-sm">No orders yet.</p>}
        {orders && orders.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-100 text-xs uppercase tracking-wide">
                  <th className="py-2 pl-4 pr-2 font-medium">When</th>
                  <th className="py-2 px-2 font-medium">Ref</th>
                  <th className="py-2 px-2 font-medium">Item</th>
                  <th className="py-2 px-2 font-medium">For</th>
                  <th className="py-2 px-2 font-medium">Buyer</th>
                  <th className="py-2 px-2 font-medium text-right">Charged</th>
                  <th className="py-2 px-2 font-medium text-right">Kept</th>
                  <th className="py-2 px-2 font-medium">State</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => {
                  const st = state(o);
                  const isOpen = open === o.id;
                  return (
                    <OrderRow
                      key={o.id}
                      o={o}
                      st={st}
                      isOpen={isOpen}
                      onToggle={() => setOpen(isOpen ? null : o.id)}
                      onApprove={() => setActing({ id: o.id, kind: 'approve' })}
                      onCancel={() => setActing({ id: o.id, kind: 'cancel' })}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {acting && (
        <ActionDialog
          o={orders.find((x) => x.id === acting.id)}
          kind={acting.kind}
          busy={busy}
          error={actError}
          onConfirm={perform}
          onClose={() => !busy && setActing(null)}
        />
      )}
    </div>
  );
}

// The moment money moves (approve) or comes back (cancel). Says exactly what
// will happen, shows the design and the destination, and asks once.
function ActionDialog({ o, kind, busy, error, onConfirm, onClose }) {
  if (!o) return null;
  const approve = kind === 'approve';
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="order-action-title"
        className="card max-w-md w-full space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="order-action-title" className="text-lg font-semibold text-gray-900">
          {approve ? 'Send this to print?' : 'Cancel and refund this order?'}
        </h2>
        <div className="flex gap-4 items-start text-sm">
          {o.image_url && <img src={o.image_url} alt="" className="w-20 h-20 rounded-lg object-cover bg-gray-100" />}
          <div className="space-y-1 text-gray-700">
            <p className="font-medium text-gray-900">
              {o.item_display_name}
              {o.product_display_name && <span className="text-gray-500 font-normal"> · {o.product_display_name}</span>}
            </p>
            <p>{o.recipient_kind === 'family' ? 'To the family' : 'To the buyer'}{o.destination ? `, ${o.destination}` : ''}</p>
            <p className="text-gray-500">Ref {o.reference} · Printful {o.printful_order_id || '—'}</p>
          </div>
        </div>
        <p className="text-sm text-gray-700">
          {approve ? (
            <>
              Printful will charge <strong>{usd(o.total_cost_cents)}</strong> to your account and start production.
              The buyer paid {usd(o.amount_cents)}; you keep about {usd((o.amount_cents || 0) - (o.payment_fee_cents || 0) - (o.total_cost_cents || 0))}.
              This can't be undone from here.
            </>
          ) : (
            <>
              The Printful draft is deleted and <strong>{usd(o.amount_cents)}</strong> goes back to the buyer's card.
              Stripe keeps its {usd(o.payment_fee_cents)} fee. A family-bound gift becomes available again.
            </>
          )}
        </p>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <div className="flex gap-3 justify-end">
          <button type="button" onClick={onClose} disabled={busy} className="px-4 py-2 text-sm rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50">
            Keep as is
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={`px-4 py-2 text-sm rounded-lg font-medium text-white disabled:opacity-50 ${approve ? 'bg-primary-600 hover:bg-primary-700' : 'bg-red-600 hover:bg-red-700'}`}
          >
            {busy ? 'Working…' : approve ? 'Send to print' : 'Cancel & refund'}
          </button>
        </div>
      </div>
    </div>
  );
}

function OrderRow({ o, st, isOpen, onToggle, onApprove, onCancel }) {
  return (
    <>
      <tr
        onClick={onToggle}
        tabIndex={0}
        aria-expanded={isOpen}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle();
          }
        }}
        className={`border-b border-gray-50 cursor-pointer hover:bg-gray-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary-500 ${isOpen ? 'bg-gray-50' : ''}`}
      >
        <td className="py-2 pl-4 pr-2 text-gray-500 whitespace-nowrap tabular">{when(o.paid_at || o.created_at)}</td>
        <td className="py-2 px-2 font-mono text-xs text-gray-700">{o.reference}</td>
        <td className="py-2 px-2 text-gray-800">
          {o.item_display_name}
          {o.recipient_kind === 'self' && <span className="text-gray-400"> · for themselves</span>}
        </td>
        <td className="py-2 px-2 text-gray-600">{o.child_name || o.slug}</td>
        <td className="py-2 px-2 text-gray-600 truncate max-w-[12rem]" title={o.buyer_email || ''}>
          {o.buyer_name || o.buyer_email || '—'}
        </td>
        <td className="py-2 px-2 text-right tabular text-gray-800">{usd(o.amount_cents)}</td>
        <td className="py-2 px-2 text-right tabular text-gray-800">{usd(o.margin_cents)}</td>
        <td className="py-2 px-2">
          <span
            className="inline-block rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide"
            style={
              st.tone
                ? { backgroundColor: levelColor(st.tone), color: st.tone === 'WARNING' ? '#3b2a00' : '#fff' }
                : { backgroundColor: '#e1e0d9', color: '#52514e' }
            }
          >
            {st.word}
          </span>
        </td>
      </tr>
      {isOpen && (
        <tr className="border-b border-gray-100 bg-gray-50">
          <td colSpan={8} className="px-4 py-4">
            <Detail o={o} onApprove={onApprove} onCancel={onCancel} />
          </td>
        </tr>
      )}
    </>
  );
}

function Detail({ o, onApprove, onCancel }) {
  const isDraft = o.status === 'paid' && o.fulfillment_status === 'submitted' && o.printful_order_id;
  const canCancel = o.status === 'paid' && ['none', 'submitting', 'submitted', 'failed', 'on_hold'].includes(o.fulfillment_status);
  const rows = [
    ['destination', o.destination && `${o.recipient_kind === 'family' ? 'family' : 'buyer'} · ${o.destination}`],
    ['product', o.product_display_name],
    ['item / postage', `${usd(o.product_price_cents)} / ${usd(o.shipping_cents)}`],
    ['Stripe fee', usd(o.payment_fee_cents)],
    ['Printful cost', usd(o.total_cost_cents)],
    ['printer state', o.fulfillment_status + (o.fulfillment_failure ? ` — ${o.fulfillment_failure}` : '')],
    ['shipped', o.shipped_at && `${when(o.shipped_at)}${o.carrier ? ` · ${o.carrier}` : ''}`],
    ['gift message', o.gift_message],
    ['receipt emailed', o.receipt_emailed_at && when(o.receipt_emailed_at)],
    ['approved', o.confirmed_at && when(o.confirmed_at)],
    ['cancelled', o.canceled_at && when(o.canceled_at)],
    ['buyer email', o.buyer_email],
    ['order id', o.id],
  ].filter(([, v]) => v != null && v !== '');

  return (
    <div className="space-y-3 text-sm">
      <div className="flex gap-4 items-start">
        {o.image_url && <img src={o.image_url} alt="" className="w-20 h-20 rounded-lg object-cover bg-gray-100" />}
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs flex-1">
          {rows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-gray-500">{k}</dt>
              <dd className="text-gray-800 break-all">{v}</dd>
            </div>
          ))}
        </dl>
      </div>
      {(isDraft || canCancel) && (
        <div className="flex gap-3">
          {isDraft && (
            <button type="button" onClick={onApprove} className="px-3 py-1.5 text-sm rounded-lg bg-primary-600 text-white font-medium hover:bg-primary-700">
              Approve · send to print
            </button>
          )}
          {canCancel && (
            <button type="button" onClick={onCancel} className="px-3 py-1.5 text-sm rounded-lg border border-red-200 text-red-700 hover:bg-red-50">
              Cancel &amp; refund
            </button>
          )}
        </div>
      )}
      <div className="flex gap-4 text-xs">
        {o.stripe_url && (
          <a href={o.stripe_url} target="_blank" rel="noreferrer" className="text-gray-700 underline underline-offset-2">
            Stripe payment ↗
          </a>
        )}
        {o.printful_order_id && (
          <a href={PRINTFUL_ORDERS} target="_blank" rel="noreferrer" className="text-gray-700 underline underline-offset-2">
            Printful order {o.printful_order_id} ↗
          </a>
        )}
        {o.tracking_url && (
          <a href={o.tracking_url} target="_blank" rel="noreferrer" className="text-gray-700 underline underline-offset-2">
            Track parcel ↗
          </a>
        )}
        <a href={`/api/b/${o.slug}/orders/${o.id}`} className="text-gray-400 underline underline-offset-2" target="_blank" rel="noreferrer">
          receipt JSON
        </a>
      </div>
    </div>
  );
}
