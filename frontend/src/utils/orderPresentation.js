/**
 * What the confirmation page says about an order, from its state.
 *
 * Stripe's success screen is a flash; the page after it is the receipt the
 * buyer remembers, and it has to be honest. "On its way" when the printer
 * rejected it is worse than saying there was a problem.
 */

export const POLL_EVERY_MS = 2000;
export const POLL_TRIES = 6; // ~12s: Stripe can settle a couple of seconds after the redirect

/**
 * @param {object} line   one order from the receipt
 * @param {boolean} settling  still polling for the payment to clear
 */
export function presentOrder(line, settling = false) {
  if (!line) return null;
  if (line.status === 'refunded') {
    if (line.fulfillment_status === 'canceled') {
      return {
        tone: 'neutral',
        headline: 'This order was cancelled and refunded.',
        detail: 'The refund goes back to the card that paid and usually shows within a few days.',
      };
    }
    return {
      tone: 'warn',
      headline: 'Someone beat you to this gift.',
      detail: 'Another family member had already sent it. Your payment has been refunded and will show on your card in a few days.',
    };
  }
  if (line.status === 'pending') {
    return settling
      ? { tone: 'neutral', headline: 'Confirming your payment…', detail: 'This takes a moment.' }
      : {
          tone: 'neutral',
          headline: 'Your payment is still being confirmed.',
          detail: "If it doesn't clear in a few minutes, your card wasn't charged and you can try again.",
        };
  }
  // paid: the headline is the news; there is nothing to add until the
  // printer has refused it (say so plainly) or the parcel has left (the
  // one time "on its way" is true)
  if (line.fulfillment_status === 'shipped') {
    return {
      tone: 'good',
      headline: "It's on its way.",
      detail: `Shipped${line.carrier ? ` with ${line.carrier}` : ''}${line.shipped_at ? ` on ${shortDate(line.shipped_at)}` : ''}.`,
    };
  }
  if (line.fulfillment_status === 'on_hold') {
    return {
      tone: 'warn',
      headline: 'Your order is on hold at the printer.',
      detail: "We've been notified and will sort it out. There's nothing more for you to do.",
    };
  }
  if (line.fulfillment_status === 'failed') {
    return {
      tone: 'warn',
      headline: 'Your payment went through, but we hit a problem sending it to the printer.',
      detail: "We've been notified and will sort it out. There's nothing more for you to do.",
    };
  }
  return { tone: 'good', headline: 'Thank you — your order is in.', detail: null };
}

export function shortDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** "to the family" / "to you", with the city when we have it. */
export function destinationLine(line) {
  const who = line.recipient_kind === 'family' ? 'to the family' : 'to you';
  return line.destination ? `${who}, in ${line.destination}` : who;
}

/** Whether the page should keep asking: a payment not yet confirmed, or a
 * paid order the printer hasn't answered on yet. */
export function stillSettling(orders) {
  return orders.some(
    (o) => o.status === 'pending' || (o.status === 'paid' && ['none', 'submitting'].includes(o.fulfillment_status)),
  );
}

/** Only a pending payment is worth telling the buyer we're waiting on. */
export function paymentSettling(orders) {
  return orders.some((o) => o.status === 'pending');
}
