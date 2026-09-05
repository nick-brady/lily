import { useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import useDialog from '../hooks/useDialog';
import { formatPrice } from '../utils/money';
import {
  POLL_EVERY_MS,
  POLL_TRIES,
  destinationLine,
  paymentSettling,
  presentOrder,
  stillSettling,
} from '../utils/orderPresentation';
import { SUPPORT_EMAIL } from '../utils/support';

// The page after Stripe. Stripe's success screen is a flash; this is the
// receipt the buyer remembers. It confirms the checkout session on load (the
// "dev path" fulfillment, the webhook being the source of truth), then shows
// the order honestly: what, where to, what it cost, where it stands.
//
// Unauthenticated, like the confirm route: the order id is the key, and
// nothing here is a secret — no email, no street, no payment or partner ids.
// The one action, cancelling, is offered only to the signed-in buyer and
// only until we send the order to print — the Terms' window.
export default function OrderConfirmationPage() {
  const { slug, orderId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isAuthenticated } = useAuth();
  const [receipt, setReceipt] = useState(null);
  const [error, setError] = useState(null);
  const [tries, setTries] = useState(0);
  const [cancelling, setCancelling] = useState(null); // the line being cancelled
  const confirmed = useRef(false);

  const replaceLine = (line) =>
    setReceipt((prev) => prev && { ...prev, orders: prev.orders.map((o) => (o.id === line.id ? line : o)) });

  // Confirm the session once, then strip the param so a reload doesn't.
  useEffect(() => {
    const sessionId = searchParams.get('gift_session');
    if (!sessionId || confirmed.current) return;
    confirmed.current = true;
    const next = new URLSearchParams(searchParams);
    next.delete('gift_session');
    setSearchParams(next, { replace: true });
    api.confirmGift(slug, sessionId).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, searchParams]);

  // Load, and keep asking while a payment is still settling.
  useEffect(() => {
    let cancelled = false;
    let timer;
    const load = (attempt) => {
      api
        .getOrderReceipt(slug, orderId)
        .then((res) => {
          if (cancelled) return;
          setReceipt(res);
          setTries(attempt);
          if (stillSettling(res.orders) && attempt < POLL_TRIES) {
            timer = setTimeout(() => load(attempt + 1), POLL_EVERY_MS);
          }
        })
        .catch((err) => {
          if (!cancelled) setError(err);
        });
    };
    load(0);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, orderId, isAuthenticated]);

  const settling = receipt ? paymentSettling(receipt.orders) && tries < POLL_TRIES : false;
  const childName = receipt?.child_name;
  const pageName = childName ? `${childName}'s page` : 'the page';

  return (
    // The plain Arrival Story gradient, like /account — a receipt is ours,
    // not the family's page, so it doesn't wear the birth's theme.
    <div className="min-h-screen bg-gradient-to-b from-primary-50 to-white dark:from-gray-900 dark:to-gray-950">
      <main className="max-w-lg mx-auto px-4 py-10 space-y-4">
        {error && (
          <div role="alert" className="card">
            <h1 className="text-xl font-semibold text-gray-800 dark:text-white">We couldn't find that order.</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              If you just paid, your receipt is on its way by email and nothing is lost.
              Email <a href={`mailto:${SUPPORT_EMAIL}`} className="underline underline-offset-2">{SUPPORT_EMAIL}</a> if it doesn't arrive.
            </p>
            <Link to={`/b/${slug}`} className="btn-primary inline-block mt-5 px-6 py-3">
              Back to {pageName}
            </Link>
          </div>
        )}

        {!receipt && !error && (
          <div className="card" role="status">
            <p className="text-gray-500 dark:text-gray-400">Loading your order…</p>
          </div>
        )}

        {receipt && (
          <>
            {receipt.orders.map((line, i) => (
              <OrderCard
                key={line.id}
                line={line}
                settling={settling}
                first={i === 0}
                childName={childName}
                onCancel={receipt.yours && line.can_cancel ? () => setCancelling(line) : null}
              />
            ))}

            <div className="card text-sm text-gray-500 dark:text-gray-400 space-y-2">
              {receipt.orders.some((o) => o.status === 'paid' && !['failed', 'on_hold', 'shipped'].includes(o.fulfillment_status)) && (
                <p>
                  It's made to order and usually ships within a few business days.
                </p>
              )}
              {receipt.yours && receipt.orders.some((o) => o.status === 'paid' && o.fulfillment_status === 'confirmed') && (
                <p>It's already being made, so it can't be cancelled from here.</p>
              )}
              <p>Your receipt is on its way by email.</p>
              <p>
                Questions? Email{' '}
                <a href={`mailto:${SUPPORT_EMAIL}?subject=Order%20${receipt.orders[0]?.reference ?? ''}`} className="underline underline-offset-2 text-gray-800 dark:text-white">
                  {SUPPORT_EMAIL}
                </a>{' '}
                and quote the reference above.
              </p>
            </div>

            <div className="pt-2 text-center">
              <Link to={`/b/${slug}`} className="btn-primary inline-block px-8 py-4 text-base">
                Back to {pageName} →
              </Link>
            </div>
          </>
        )}
      </main>

      {cancelling && (
        <CancelDialog
          line={cancelling}
          onDone={(updated) => {
            replaceLine(updated);
            setCancelling(null);
          }}
          onClose={() => setCancelling(null)}
        />
      )}
    </div>
  );
}

// Asks once, says what happens, then does it. The refund is automatic —
// nothing has been made yet — so this is a cancel, not a request to cancel.
function CancelDialog({ line, onDone, onClose }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const panelRef = useDialog(() => !busy && onClose());

  const cancel = () => {
    setBusy(true);
    setError(null);
    api
      .cancelMyOrder(line.id)
      .then(onDone)
      .catch((err) => {
        setError(err.message || "We couldn't cancel it just now.");
        setBusy(false);
      });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => !busy && onClose()}>
      <div ref={panelRef} className="card max-w-sm w-full space-y-4" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-gray-800 dark:text-white">Cancel this order?</h2>
        <p className="text-sm text-gray-600 dark:text-gray-300">
          The {line.item_display_name.toLowerCase()} won't be made, and {formatPrice(line.amount_cents)} goes back to
          the card you paid with, usually within a few days.
        </p>
        {error && (
          <p role="alert" className="text-sm text-amber-700 dark:text-amber-400">
            {error} Email <a href={`mailto:${SUPPORT_EMAIL}`} className="underline underline-offset-2">{SUPPORT_EMAIL}</a> and we'll sort it out.
          </p>
        )}
        <div className="flex gap-3 justify-end">
          <button type="button" onClick={onClose} disabled={busy} className="px-4 py-2 text-sm rounded-xl text-gray-600 dark:text-gray-300 hover:bg-black/5 disabled:opacity-50">
            Keep it
          </button>
          <button type="button" onClick={cancel} disabled={busy} className="btn-primary px-4 py-2 text-sm disabled:opacity-50">
            {busy ? 'Cancelling…' : 'Cancel and refund'}
          </button>
        </div>
      </div>
    </div>
  );
}

function OrderCard({ line, settling, first, childName, onCancel }) {
  const says = presentOrder(line, settling);
  const tone = {
    good: '#a21caf',
    warn: '#b45309',
    neutral: '#6b7280',
  }[says.tone];

  return (
    <section className="card space-y-5" aria-live={first ? 'polite' : undefined}>
      <header>
        {first ? (
          <h1 className="text-2xl font-semibold text-gray-800 dark:text-white leading-snug">{says.headline}</h1>
        ) : (
          <h2 className="text-xl font-semibold text-gray-800 dark:text-white leading-snug">{says.headline}</h2>
        )}
        {says.detail && (
          <p className="mt-2 text-sm" style={{ color: tone }}>
            {says.detail}
          </p>
        )}
      </header>

      <div className="flex gap-4 items-start">
        {line.image_url ? (
          <img
            src={line.image_url}
            alt={`${line.item_display_name} design`}
            className="w-24 h-24 rounded-xl object-cover flex-shrink-0"
            style={{ backgroundColor: 'rgb(0 0 0 / 0.04)' }}
          />
        ) : (
          <div
            aria-hidden="true"
            className="w-24 h-24 rounded-xl flex-shrink-0"
            style={{ backgroundColor: 'rgb(0 0 0 / 0.04)' }}
          />
        )}
        <dl className="flex-1 text-sm space-y-1.5">
          <div>
            <dt className="sr-only">Item</dt>
            <dd className="font-medium text-gray-800 dark:text-white">
              {line.item_display_name}
              {line.product_display_name && (
                <span className="text-gray-500 dark:text-gray-400 font-normal"> · {line.product_display_name}</span>
              )}
            </dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-gray-500 dark:text-gray-400">Going</dt>
            <dd className="text-gray-800 dark:text-white">
              {line.address ? (
                // the whole address, because this is the buyer's own view
                <>
                  {line.recipient_kind === 'family' ? 'to the family:' : 'to you:'}
                  <span className="block mt-0.5 leading-snug">
                    {line.address.map((part) => (
                      <span key={part} className="block">{part}</span>
                    ))}
                  </span>
                </>
              ) : (
                destinationLine(line)
              )}
            </dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-gray-500 dark:text-gray-400">Reference</dt>
            <dd className="text-gray-800 dark:text-white font-mono tracking-wider">{line.reference}</dd>
          </div>
          {line.tracking_url && (
            <div className="flex gap-2">
              <dt className="text-gray-500 dark:text-gray-400">Tracking</dt>
              <dd>
                <a href={line.tracking_url} target="_blank" rel="noreferrer" className="underline underline-offset-2 text-gray-800 dark:text-white">
                  Track the parcel{line.carrier ? ` with ${line.carrier}` : ''}
                </a>
              </dd>
            </div>
          )}
        </dl>
      </div>

      <dl className="text-sm border-t pt-4 space-y-1" >
        <div className="flex justify-between">
          <dt className="text-gray-500 dark:text-gray-400">{line.item_display_name}</dt>
          <dd className="text-gray-800 dark:text-white tabular-nums">{formatPrice(line.product_price_cents)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500 dark:text-gray-400">Postage</dt>
          <dd className="text-gray-800 dark:text-white tabular-nums">{formatPrice(line.shipping_cents)}</dd>
        </div>
        <div className="flex justify-between font-medium pt-1">
          <dt className="text-gray-800 dark:text-white">Total</dt>
          <dd className="text-gray-800 dark:text-white tabular-nums">{formatPrice(line.amount_cents)}</dd>
        </div>
      </dl>

      {line.gift_message && (
        <blockquote
          className="text-sm italic text-gray-800 dark:text-white rounded-xl px-4 py-3"
          style={{ backgroundColor: 'rgb(0 0 0 / 0.04)' }}
        >
          “{line.gift_message}”
          <footer className="not-italic text-gray-500 dark:text-gray-400 text-xs mt-1">
            printed on the packing slip{childName ? ` for ${childName}'s family` : ''}
          </footer>
        </blockquote>
      )}

      {onCancel && (
        <p className="text-sm text-gray-500 dark:text-gray-400 border-t pt-4">
          Changed your mind?{' '}
          <button type="button" onClick={onCancel} className="underline underline-offset-2 text-gray-800 dark:text-white hover:text-primary-600">
            Cancel this order
          </button>{' '}
          for a full refund — you can until we send it to print.
        </p>
      )}
    </section>
  );
}
