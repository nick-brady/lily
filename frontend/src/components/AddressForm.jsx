import { useState } from 'react';
import { api } from '../api/client';

// Where a parcel goes. Stripe used to ask this on its own page, which meant
// it could only ever ask once — fine for one mug, useless for two going to
// two different houses. So we ask, and Stripe is left to do the one thing it
// was needed for.
//
// Every field carries an `autocomplete` token, which is what lets the browser
// fill the whole thing from a saved address in one tap. Losing that was the
// only real cost of moving off Stripe's form, and this is most of it back.

const EMPTY = {
  name: '',
  line1: '',
  line2: '',
  city: '',
  state: '',
  postal_code: '',
  country: 'US',
};

export function emptyAddress() {
  return { ...EMPTY };
}

// US only, deliberately. The server is the authority on where we ship
// (GIFT_SHIPPING_COUNTRIES, "US"), and until that says otherwise a country
// picker would offer choices the checkout would refuse. Printful won't take a
// US order without a state code, so it's required here too.
export function addressComplete(address) {
  if (!address) return false;
  const has = (k) => (address[k] || '').trim().length > 0;
  return ['name', 'line1', 'city', 'state', 'postal_code'].every(has);
}

function Field({ label, value, onChange, autoComplete, required = true, className = '' }) {
  return (
    <label className={`block text-xs t-muted ${className}`}>
      {label}
      <input
        type="text"
        value={value}
        required={required}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full px-3 py-2 rounded-lg border text-sm bg-white dark:bg-gray-800 t-ink"
        style={{ borderColor: 'var(--t-soft-ring)' }}
      />
    </label>
  );
}

export default function AddressForm({ birthId, title, hint, value, onChange }) {
  const [review, setReview] = useState(null);
  const [checking, setChecking] = useState(false);
  const set = (patch) => {
    onChange({ ...value, ...patch });
    setReview(null); // any edit makes the last verdict a statement about the past
  };

  // Asked for once the address is whole, not on every keystroke — it's a
  // paid call to Google and half an address has nothing to say.
  const check = async () => {
    if (!addressComplete(value) || checking) return;
    setChecking(true);
    try {
      setReview(await api.reviewShippingAddress(birthId, value));
    } catch {
      setReview(null); // advisory only; never stand between them and the mug
    } finally {
      setChecking(false);
    }
  };

  const suggestion = review?.suggestion;

  return (
    <div
      className="p-3 rounded-lg border space-y-3"
      style={{ borderColor: 'var(--t-soft-ring)' }}
    >
      <div>
        <p className="text-sm t-ink font-medium">{title}</p>
        {hint && <p className="text-xs t-muted mt-0.5">{hint}</p>}
      </div>

      <Field
        label="Full name"
        value={value.name}
        onChange={(v) => set({ name: v })}
        autoComplete="shipping name"
      />
      <Field
        label="Street address"
        value={value.line1}
        onChange={(v) => set({ line1: v })}
        autoComplete="shipping address-line1"
      />
      <Field
        label="Apartment, suite (optional)"
        value={value.line2}
        onChange={(v) => set({ line2: v })}
        autoComplete="shipping address-line2"
        required={false}
      />
      <div className="grid grid-cols-2 gap-3">
        <Field
          label="City"
          value={value.city}
          onChange={(v) => set({ city: v })}
          autoComplete="shipping address-level2"
        />
        <Field
          label="State"
          value={value.state}
          onChange={(v) => set({ state: v })}
          autoComplete="shipping address-level1"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field
          label="ZIP code"
          value={value.postal_code}
          onChange={(v) => set({ postal_code: v })}
          autoComplete="shipping postal-code"
        />
        <div className="flex items-end">
          <p className="text-xs t-muted pb-2">United States</p>
        </div>
      </div>

      <button
        type="button"
        onClick={check}
        disabled={!addressComplete(value) || checking}
        className="text-xs underline t-muted disabled:opacity-40 disabled:no-underline"
      >
        {checking ? 'Checking…' : 'Check this address'}
      </button>

      {/* Advice, never a wall. A real address the postal file hasn't caught
          up with is still a real address, and the person typing it knows
          where their sister lives. */}
      {review?.verdict === 'confirmed' && (
        <p className="text-xs t-muted">✓ This address checks out.</p>
      )}
      {review?.verdict === 'corrected' && suggestion && (
        <div className="text-xs t-ink space-y-1">
          <p className="t-muted">The postal service writes it like this:</p>
          <p>
            {suggestion.line1}
            {suggestion.line2 ? `, ${suggestion.line2}` : ''}, {suggestion.city}{' '}
            {suggestion.state} {suggestion.postal_code}
          </p>
          <button
            type="button"
            onClick={() => {
              onChange({ ...value, ...suggestion, name: value.name });
              setReview(null);
            }}
            className="underline"
          >
            Use that instead
          </button>
        </div>
      )}
      {review?.verdict === 'unconfirmed' && (
        <p className="text-xs t-ink">
          We couldn&rsquo;t confirm this one — worth a second look, though you
          can send it as it is.
        </p>
      )}
      {review?.structure_error && (
        <p className="text-xs text-red-600 dark:text-red-400">{review.structure_error}</p>
      )}
    </div>
  );
}
