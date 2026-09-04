import { useState } from 'react';
import { api } from '../api/client';
import { formatIdentifierInput } from '../utils/identifier';

// The birth-events text opt-in — shown once, right after signup, at peak
// intent ("Want a text the moment labor begins?"). Explicit and skippable:
// this consent is what lets the labor text be sent at all, and its scope
// (birth events only, forever) is stated in the UI, not buried in terms.
export default function PhoneOptIn({ babyName, onDone }) {
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const digits = phone.replace(/\D/g, '');
  const plausible = digits.length >= 10;

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.setNotifyPhone(phone);
      onDone(true);
    } catch (err) {
      setError(err.message || "We couldn't text that number");
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
          Want a text the moment labor begins?
        </h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          {babyName ? `Don't miss ${babyName}'s arrival.` : "Don't miss the moment."}{' '}
          We text for birth updates only — never anything else.
        </p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      <input
        type="tel"
        value={phone}
        onChange={(e) => setPhone(formatIdentifierInput(e.target.value).value)}
        autoComplete="tel"
        inputMode="tel"
        placeholder="(555) 555-5555"
        aria-label="Phone number"
        className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600
                   bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                   focus:ring-2 focus:ring-primary-500 focus:border-transparent
                   focus:outline-none transition-colors"
      />

      <button
        type="submit"
        disabled={loading || !plausible}
        className="w-full py-3 rounded-lg bg-primary-600 hover:bg-primary-700
                   text-white font-medium transition-colors
                   disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Sending confirmation…' : 'Text me when it starts'}
      </button>
      <button
        type="button"
        onClick={() => onDone(false)}
        className="w-full text-sm text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400"
      >
        Skip for now
      </button>
      <p className="text-xs text-gray-400 dark:text-gray-500 text-center">
        Birth updates only, ever. Msg &amp; data rates may apply. Reply STOP anytime.
      </p>
    </form>
  );
}
