import { describe, it, expect } from 'vitest';
import { destinationLine, presentOrder, stillSettling } from './orderPresentation';

const paid = (fulfillment_status) => ({ status: 'paid', fulfillment_status, recipient_kind: 'self' });

describe('presentOrder', () => {
  it('never says "on its way" when the printer rejected it', () => {
    const p = presentOrder(paid('failed'));
    expect(p.tone).toBe('warn');
    expect(p.headline).toMatch(/problem/);
    expect(p.detail).toMatch(/nothing more for you to do/i);
  });

  it('thanks them and says nothing more until the printer has it', () => {
    for (const state of ['none', 'submitting']) {
      const p = presentOrder(paid(state));
      expect(p.headline).toMatch(/Thank you/);
      expect(p.detail).toBeNull();
      expect(p.tone).toBe('good');
    }
  });

  it('says where it stands: waiting on us, then being made', () => {
    expect(presentOrder(paid('submitted')).detail).toMatch(/waiting for us/);
    const made = presentOrder({ status: 'paid', fulfillment_status: 'confirmed', confirmed_at: '2026-09-05T12:00:00Z' });
    expect(made.headline).toMatch(/being made/);
    expect(made.detail).toMatch(/Sent to print on/);
  });

  it('waits before worrying about a pending payment', () => {
    expect(presentOrder({ status: 'pending' }, true).headline).toMatch(/Confirming/);
    expect(presentOrder({ status: 'pending' }, false).detail).toMatch(/wasn't charged/);
  });

  it('explains a refund as the claim race it is, unless we cancelled it', () => {
    expect(presentOrder({ status: 'refunded' }).headline).toMatch(/beat you/);
    expect(presentOrder({ status: 'refunded', fulfillment_status: 'canceled' }).headline).toMatch(/cancelled and refunded/);
  });
});

describe('presentOrder, once the parcel has left', () => {
  it('is the one time it says "on its way", and names the carrier', () => {
    const p = presentOrder({ status: 'paid', fulfillment_status: 'shipped', carrier: 'USPS', shipped_at: '2026-09-08T12:00:00Z' });
    expect(p.headline).toBe("It's on its way.");
    expect(p.detail).toMatch(/^Shipped with USPS on /);
    expect(p.tone).toBe('good');
  });

  it('says so when the printer put it on hold', () => {
    expect(presentOrder({ status: 'paid', fulfillment_status: 'on_hold' }).tone).toBe('warn');
  });
});

describe('destinationLine', () => {
  it('names who and where, and copes without a city', () => {
    expect(destinationLine({ recipient_kind: 'family', destination: 'Raleigh, NC' })).toBe('to the family, in Raleigh, NC');
    expect(destinationLine({ recipient_kind: 'self', destination: null })).toBe('to you');
  });
});

describe('stillSettling', () => {
  it('keeps asking while a payment is pending or the printer has not answered', () => {
    expect(stillSettling([{ status: 'paid', fulfillment_status: 'submitted' }, { status: 'pending' }])).toBe(true);
    expect(stillSettling([{ status: 'paid', fulfillment_status: 'none' }])).toBe(true);
    expect(stillSettling([{ status: 'paid', fulfillment_status: 'submitted' }, { status: 'refunded' }])).toBe(false);
    expect(stillSettling([{ status: 'paid', fulfillment_status: 'failed' }])).toBe(false);
  });
});
