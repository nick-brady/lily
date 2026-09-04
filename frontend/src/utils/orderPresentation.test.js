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

  it('thanks them once the order is with the printer, and while it is being sent', () => {
    expect(presentOrder(paid('submitted')).headline).toMatch(/Thank you/);
    expect(presentOrder(paid('none')).detail).toMatch(/Sending/);
    expect(presentOrder(paid('submitting')).tone).toBe('good');
  });

  it('waits before worrying about a pending payment', () => {
    expect(presentOrder({ status: 'pending' }, true).headline).toMatch(/Confirming/);
    expect(presentOrder({ status: 'pending' }, false).detail).toMatch(/wasn't charged/);
  });

  it('explains a refund as the claim race it is', () => {
    expect(presentOrder({ status: 'refunded' }).headline).toMatch(/beat you/);
  });
});

describe('destinationLine', () => {
  it('names who and where, and copes without a city', () => {
    expect(destinationLine({ recipient_kind: 'family', destination: 'Raleigh, NC' })).toBe('to the family, in Raleigh, NC');
    expect(destinationLine({ recipient_kind: 'self', destination: null })).toBe('to you');
  });
});

describe('stillSettling', () => {
  it('is true while any order is pending', () => {
    expect(stillSettling([{ status: 'paid' }, { status: 'pending' }])).toBe(true);
    expect(stillSettling([{ status: 'paid' }, { status: 'refunded' }])).toBe(false);
  });
});
