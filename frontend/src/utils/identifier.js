// Shared handling for the "email or phone" identifier fields.
//
// The backend (`normalize_identifier` in backend/auth.py) is the source of
// truth: anything containing "@" is an email; otherwise digits are extracted
// and US numbers are stored as +1XXXXXXXXXX. These helpers mirror that logic
// so the UI can show the user what the server will see — `2099185557` and
// `12099185557` are the same number, and both render as (209) 918-5557.

// Mirrors EMAIL_RE in backend/auth.py.
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// Digits plus the punctuation people type in phone numbers.
const PHONE_SHAPE_RE = /^\+?[\d\s().-]+$/;

export function detectIdentifierKind(raw) {
  const trimmed = (raw || '').trim();
  if (!trimmed) return 'unknown';
  if (trimmed.includes('@')) return 'email';
  if (/\d/.test(trimmed) && PHONE_SHAPE_RE.test(trimmed)) return 'phone';
  return 'unknown';
}

// Mirrors backend normalize_identifier exactly. `invalid` keeps the raw trim
// so callers can still submit it and surface the backend's own 400 message.
export function normalizeIdentifier(raw) {
  const candidate = (raw || '').trim();
  if (candidate.includes('@')) {
    return { kind: 'email', value: candidate.toLowerCase() };
  }
  const digits = candidate.replace(/\D/g, '');
  if (digits.length === 10) return { kind: 'phone', value: `+1${digits}` };
  if (digits.length === 11 && digits.startsWith('1')) {
    return { kind: 'phone', value: `+${digits}` };
  }
  if (digits.length >= 8 && candidate.startsWith('+')) {
    return { kind: 'phone', value: `+${digits}` };
  }
  return { kind: 'invalid', value: candidate };
}

export function isValidEmail(raw) {
  return EMAIL_RE.test((raw || '').trim().toLowerCase());
}

function formatUsNational(national) {
  if (national.length <= 3) return national;
  if (national.length <= 6) return `(${national.slice(0, 3)}) ${national.slice(3)}`;
  return `(${national.slice(0, 3)}) ${national.slice(3, 6)}-${national.slice(6)}`;
}

function countDigits(str) {
  let n = 0;
  for (const ch of str) if (ch >= '0' && ch <= '9') n += 1;
  return n;
}

// Caret index that sits immediately after the Nth digit of `formatted`.
function caretAfterDigit(formatted, digitIndex) {
  if (digitIndex <= 0) return 0;
  let seen = 0;
  for (let i = 0; i < formatted.length; i += 1) {
    if (formatted[i] >= '0' && formatted[i] <= '9') {
      seen += 1;
      if (seen === digitIndex) return i + 1;
    }
  }
  return formatted.length;
}

// As-you-type formatter. `caret` is the selectionStart within `raw`; the
// returned caret is the position within the returned value, or null when the
// value passed through untouched (emails, international numbers) and the DOM
// caret should be left alone.
export function formatIdentifierInput(raw, caret = null) {
  const kind = detectIdentifierKind(raw);
  if (kind !== 'phone') return { value: raw, caret: null, kind };

  const trimmed = raw.replace(/^\s+/, '');
  const digits = trimmed.replace(/\D/g, '');

  // Non-US international numbers stay exactly as typed; the backend accepts
  // any "+" number with 8+ digits.
  if (trimmed.startsWith('+') && !digits.startsWith('1')) {
    return { value: trimmed, caret: null, kind };
  }

  // A bare country code ("1" or "+1") has nothing to format yet — leave it
  // so the keystroke doesn't visually vanish.
  if (digits === '1') return { value: trimmed, caret: null, kind };

  const absorbedOne = digits.startsWith('1');
  const national = absorbedOne ? digits.slice(1) : digits;

  // Overlong input renders as the raw digit string — never drop what the
  // user typed; the missing hint signals something is off.
  const overlong = national.length > 10;
  const value = overlong ? digits : formatUsNational(national);

  let nextCaret = null;
  if (caret != null) {
    let digitsBefore = countDigits(raw.slice(0, caret));
    if (absorbedOne && !overlong && digitsBefore > 0) digitsBefore -= 1;
    nextCaret = caretAfterDigit(value, digitsBefore);
  }
  return { value, caret: nextCaret, kind };
}

// Canonical human-readable form for hints and confirmation copy:
// "+12099185557" / "2099185557" / "(209) 918-5557" -> "+1 (209) 918-5557".
// Non-US numbers show their E.164 form; emails are trimmed and lowercased.
export function formatIdentifierDisplay(raw) {
  const norm = normalizeIdentifier(raw);
  if (norm.kind === 'phone' && /^\+1\d{10}$/.test(norm.value)) {
    const n = norm.value.slice(2);
    return `+1 (${n.slice(0, 3)}) ${n.slice(3, 6)}-${n.slice(6)}`;
  }
  return norm.value;
}
