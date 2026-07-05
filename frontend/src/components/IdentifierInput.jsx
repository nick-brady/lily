import { useLayoutEffect, useRef } from 'react';
import {
  detectIdentifierKind,
  formatIdentifierDisplay,
  formatIdentifierInput,
  isValidEmail,
  normalizeIdentifier,
} from '../utils/identifier';

function buildHint(value, action) {
  const kind = detectIdentifierKind(value);
  if (kind === 'email') {
    if (!isValidEmail(value)) return null;
    return `We'll email ${action} to ${formatIdentifierDisplay(value)}`;
  }
  if (kind === 'phone') {
    const norm = normalizeIdentifier(value);
    if (norm.kind === 'phone') {
      return `We'll text ${action} to ${formatIdentifierDisplay(value)}`;
    }
    // Too many digits to be a US number and no "+" — nudge, but leave real
    // errors to the backend's error banner.
    if (value.replace(/\D/g, '').length > 11 && !value.trim().startsWith('+')) {
      return 'Enter a 10-digit US number, or start with + for international.';
    }
  }
  return null;
}

// A controlled "email or phone" input that live-formats US phone numbers as
// you type and shows what the code will be sent to. Visual styling comes
// from the caller via className/style so each surface keeps its own look.
export default function IdentifierInput({
  value,
  onChange,
  hintAction = 'a code',
  hintClassName = 'mt-1 text-xs text-gray-500 dark:text-gray-400',
  ...inputProps
}) {
  const inputRef = useRef(null);
  const pendingCaret = useRef(null);

  const handleChange = (e) => {
    const { value: next, caret } = formatIdentifierInput(
      e.target.value,
      e.target.selectionStart,
    );
    pendingCaret.current = caret;
    onChange(next);
  };

  // React resets the caret to the end whenever the value it renders differs
  // from what's in the DOM (i.e. whenever formatting changed the string), so
  // restore the mapped position after the commit.
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (pendingCaret.current != null && el && document.activeElement === el) {
      el.setSelectionRange(pendingCaret.current, pendingCaret.current);
    }
    pendingCaret.current = null;
  }, [value]);

  const hint = buildHint(value, hintAction);

  return (
    <>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={handleChange}
        autoCapitalize="none"
        autoCorrect="off"
        {...inputProps}
      />
      {hint && <p className={hintClassName}>{hint}</p>}
    </>
  );
}
