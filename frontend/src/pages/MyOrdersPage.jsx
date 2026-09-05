import { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { formatPrice } from '../utils/money';
import { presentOrder } from '../utils/orderPresentation';

// Everything you've bought, newest first, across every page. Each row is a
// door back to its receipt. Lives on its own page because /account is
// already full; /account only links here once there is something to show.
export default function MyOrdersPage() {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [orders, setOrders] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isAuthenticated) return undefined;
    let cancelled = false;
    api
      .myOrders()
      .then((rows) => !cancelled && setOrders(rows))
      .catch((err) => !cancelled && setError(err));
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  if (!authLoading && !isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen bg-gradient-to-b from-primary-50 to-white dark:from-gray-900 dark:to-gray-950 px-4 py-10">
      <main className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <Link
            to="/"
            className="text-3xl text-primary-600 dark:text-primary-400"
            style={{ fontFamily: "'Great Vibes', cursive" }}
          >
            Arrival Story
          </Link>
          <Link
            to="/account"
            className="text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
          >
            ← Your account
          </Link>
        </div>

        <h1 className="text-xl font-semibold text-gray-800 dark:text-white mb-6">Your orders</h1>

        {error && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {error.message || "We couldn't load your orders."}
          </p>
        )}
        {!orders && !error && <p className="text-sm text-gray-400">Loading…</p>}
        {orders && orders.length === 0 && (
          <p className="text-sm text-gray-500 dark:text-gray-400">Nothing yet.</p>
        )}

        {orders && orders.length > 0 && (
          <ul className="space-y-3">
            {orders.map((o) => {
              const says = presentOrder(o, false);
              return (
                <li key={o.id}>
                  <Link
                    to={`/b/${o.slug}/order/${o.id}`}
                    state={{ from: 'orders' }}
                    className="card flex gap-4 items-center hover:shadow-md transition-shadow"
                  >
                    {o.image_url ? (
                      <img
                        src={o.image_url}
                        alt=""
                        className="w-16 h-16 rounded-lg object-cover flex-shrink-0 bg-gray-100 dark:bg-gray-800"
                      />
                    ) : (
                      <div aria-hidden="true" className="w-16 h-16 rounded-lg flex-shrink-0 bg-gray-100 dark:bg-gray-800" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-800 dark:text-white truncate">
                        {o.item_display_name}
                        {o.child_name && (
                          <span className="text-gray-400 font-normal"> · for {o.child_name}</span>
                        )}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        {new Date(o.created_at).toLocaleDateString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                        })}
                        {' · '}
                        <span className="font-mono">{o.reference}</span>
                      </p>
                      <p
                        className="text-xs mt-1"
                        style={{ color: says.tone === 'warn' ? '#b45309' : undefined }}
                      >
                        {statusWord(o)}
                      </p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-sm font-medium text-gray-800 dark:text-white tabular-nums">
                        {formatPrice(o.amount_cents)}
                      </p>
                      <p className="text-xs text-gray-400">
                        {o.recipient_kind === 'family' ? 'to the family' : 'to you'}
                      </p>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </main>
    </div>
  );
}

// One word on the row; the receipt has the sentence.
function statusWord(o) {
  if (o.status === 'refunded') return o.fulfillment_status === 'canceled' ? 'Cancelled · refunded' : 'Refunded';
  if (o.status === 'pending') return 'Confirming payment';
  if (o.fulfillment_status === 'failed') return 'Problem — we are on it';
  if (o.fulfillment_status === 'on_hold') return 'On hold — we are on it';
  if (o.fulfillment_status === 'shipped') return `Shipped${o.carrier ? ` with ${o.carrier}` : ''}`;
  if (o.fulfillment_status === 'confirmed') return 'Being made';
  if (o.fulfillment_status === 'submitted') return 'Preparing your order';
  return 'Order received';
}
