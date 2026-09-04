import { useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { formatPrice } from '../utils/money';
import {
  POLL_EVERY_MS,
  POLL_TRIES,
  destinationLine,
  presentOrder,
  stillSettling,
} from '../utils/orderPresentation';
import { getTheme, themeVars } from '../utils/themes';

// The page after Stripe. Stripe's success screen is a flash; this is the
// receipt the buyer remembers. It confirms the checkout session on load (the
// "dev path" fulfillment, the webhook being the source of truth), then shows
// the order honestly: what, where to, what it cost, where it stands.
//
// Unauthenticated, like the confirm route: the order id is the key, and
// nothing here is a secret — no email, no street, no payment or partner ids.
export default function OrderConfirmationPage() {
  const { slug, orderId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [receipt, setReceipt] = useState(null);
  const [error, setError] = useState(null);
  const [tries, setTries] = useState(0);
  const confirmed = useRef(false);

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
  }, [slug, orderId]);

  const theme = getTheme(receipt?.theme);
  const settling = receipt ? stillSettling(receipt.orders) && tries < POLL_TRIES : false;
  const childName = receipt?.child_name;
  const pageName = childName ? `${childName}'s page` : 'the page';

  return (
    <div
      className="min-h-screen transition-colors"
      style={{
        ...themeVars(theme, false),
        backgroundColor: 'var(--t-page-bg)',
        backgroundImage: 'var(--t-page-pattern)',
        backgroundSize: 'var(--t-pattern-size)',
      }}
    >
      <main className="max-w-lg mx-auto px-4 py-10 space-y-4">
        {error && (
          <div role="alert" className="card">
            <h1 className="text-xl font-semibold t-ink">We couldn't find that order.</h1>
            <p className="text-sm t-muted mt-2">
              If you just paid, the receipt from Stripe is in your email. Nothing is lost.
            </p>
            <Link to={`/b/${slug}`} className="btn-primary inline-block mt-5 px-6 py-3">
              Back to {pageName}
            </Link>
          </div>
        )}

        {!receipt && !error && (
          <div className="card" role="status">
            <p className="t-muted">Loading your order…</p>
          </div>
        )}

        {receipt && (
          <>
            {receipt.orders.map((line, i) => (
              <OrderCard key={line.id} line={line} settling={settling} first={i === 0} childName={childName} />
            ))}

            <div className="card text-sm t-muted space-y-2">
              {receipt.orders.some((o) => o.status === 'paid' && o.fulfillment_status !== 'failed') && (
                <p>
                  It's made to order and usually ships within a few business days.
                </p>
              )}
              <p>Your receipt from Stripe is on its way by email.</p>
              <p>Questions? Quote the reference above.</p>
            </div>

            <div className="pt-2 text-center">
              <Link to={`/b/${slug}`} className="btn-primary inline-block px-8 py-4 text-base">
                Back to {pageName} →
              </Link>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function OrderCard({ line, settling, first, childName }) {
  const says = presentOrder(line, settling);
  const tone = {
    good: 'var(--t-accent)',
    warn: '#b45309',
    neutral: 'var(--t-ink-muted)',
  }[says.tone];

  return (
    <section className="card space-y-5" aria-live={first ? 'polite' : undefined}>
      <header>
        {first ? (
          <h1 className="text-2xl font-semibold t-ink leading-snug">{says.headline}</h1>
        ) : (
          <h2 className="text-xl font-semibold t-ink leading-snug">{says.headline}</h2>
        )}
        <p className="mt-2 text-sm" style={{ color: tone }}>
          {says.detail}
        </p>
      </header>

      <div className="flex gap-4 items-start">
        {line.image_url ? (
          <img
            src={line.image_url}
            alt={`${line.item_display_name} design`}
            className="w-24 h-24 rounded-xl object-cover flex-shrink-0"
            style={{ backgroundColor: 'var(--t-note-bg)' }}
          />
        ) : (
          <div
            aria-hidden="true"
            className="w-24 h-24 rounded-xl flex-shrink-0"
            style={{ backgroundColor: 'var(--t-note-bg)' }}
          />
        )}
        <dl className="flex-1 text-sm space-y-1.5">
          <div>
            <dt className="sr-only">Item</dt>
            <dd className="font-medium t-ink">
              {line.item_display_name}
              {line.product_display_name && (
                <span className="t-muted font-normal"> · {line.product_display_name}</span>
              )}
            </dd>
          </div>
          <div className="flex gap-2">
            <dt className="t-muted">Going</dt>
            <dd className="t-ink">{destinationLine(line)}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="t-muted">Reference</dt>
            <dd className="t-ink font-mono tracking-wider">{line.reference}</dd>
          </div>
        </dl>
      </div>

      <dl className="text-sm border-t pt-4 space-y-1" style={{ borderColor: 'var(--t-soft-ring)' }}>
        <div className="flex justify-between">
          <dt className="t-muted">{line.item_display_name}</dt>
          <dd className="t-ink tabular-nums">{formatPrice(line.product_price_cents)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="t-muted">Postage</dt>
          <dd className="t-ink tabular-nums">{formatPrice(line.shipping_cents)}</dd>
        </div>
        <div className="flex justify-between font-medium pt-1">
          <dt className="t-ink">Total</dt>
          <dd className="t-ink tabular-nums">{formatPrice(line.amount_cents)}</dd>
        </div>
      </dl>

      {line.gift_message && (
        <blockquote
          className="text-sm italic t-ink rounded-xl px-4 py-3"
          style={{ backgroundColor: 'var(--t-note-bg)' }}
        >
          “{line.gift_message}”
          <footer className="not-italic t-muted text-xs mt-1">
            printed on the packing slip{childName ? ` for ${childName}'s family` : ''}
          </footer>
        </blockquote>
      )}
    </section>
  );
}
