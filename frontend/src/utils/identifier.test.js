import { describe, expect, it } from 'vitest';
import {
  detectIdentifierKind,
  formatIdentifierDisplay,
  formatIdentifierInput,
  isValidEmail,
  normalizeIdentifier,
} from './identifier';

describe('detectIdentifierKind', () => {
  it.each([
    ['', 'unknown'],
    ['   ', 'unknown'],
    ['nick@natrx.io', 'email'],
    ['nick@', 'email'], // backend treats any "@" as the email path
    ['2099185557', 'phone'],
    ['(209) 918-5557', 'phone'],
    ['+44 7911 123456', 'phone'],
    ['209-918', 'phone'],
    ['+', 'unknown'], // no digit yet
    ['nick', 'unknown'],
    ['555 call me', 'unknown'],
  ])('%j -> %s', (input, expected) => {
    expect(detectIdentifierKind(input)).toBe(expected);
  });
});

describe('normalizeIdentifier (mirrors backend normalize_identifier)', () => {
  it.each([
    ['2099185557', 'phone', '+12099185557'],
    ['12099185557', 'phone', '+12099185557'],
    ['+12099185557', 'phone', '+12099185557'],
    ['(209) 918-5557', 'phone', '+12099185557'],
    ['1 (209) 918-5557', 'phone', '+12099185557'],
    ['+44 20 7123 4567', 'phone', '+442071234567'],
    ['Nick@NATRX.io', 'email', 'nick@natrx.io'],
    ['  nick@natrx.io  ', 'email', 'nick@natrx.io'],
    ['209918', 'invalid', '209918'],
    ['20991855571', 'invalid', '20991855571'], // 11 digits, no leading 1
    ['garbage', 'invalid', 'garbage'],
  ])('%j -> %s %j', (input, kind, value) => {
    const result = normalizeIdentifier(input);
    expect(result.kind).toBe(kind);
    expect(result.value).toBe(value);
  });
});

describe('formatIdentifierInput', () => {
  const fmt = (raw) => formatIdentifierInput(raw).value;

  it('formats each length bucket', () => {
    expect(fmt('2')).toBe('2');
    expect(fmt('209')).toBe('209');
    expect(fmt('2099')).toBe('(209) 9');
    expect(fmt('209918')).toBe('(209) 918');
    expect(fmt('2099185')).toBe('(209) 918-5');
    expect(fmt('2099185557')).toBe('(209) 918-5557');
  });

  it('absorbs a leading 1 so both spellings render identically', () => {
    expect(fmt('12099185557')).toBe('(209) 918-5557');
    expect(fmt('2099185557')).toBe('(209) 918-5557');
    expect(fmt('+1 209 918 5557')).toBe('(209) 918-5557');
  });

  it('converges pasted punctuation variants', () => {
    expect(fmt('209-918-5557')).toBe('(209) 918-5557');
    expect(fmt('1.209.918.5557')).toBe('(209) 918-5557');
    expect(fmt('+1 (209) 918-5557')).toBe('(209) 918-5557');
  });

  it('keeps a bare country code visible while typing', () => {
    expect(fmt('1')).toBe('1');
    expect(fmt('+1')).toBe('+1');
  });

  it('leaves non-US international numbers as typed', () => {
    const result = formatIdentifierInput('+44 7911 123456', 5);
    expect(result.value).toBe('+44 7911 123456');
    expect(result.caret).toBe(null);
  });

  it('never touches emails or partial emails', () => {
    for (const input of ['nick', 'nick@', 'nick@natrx.io']) {
      const result = formatIdentifierInput(input, 2);
      expect(result.value).toBe(input);
      expect(result.caret).toBe(null);
    }
  });

  it('renders overlong input as the raw digit string', () => {
    expect(fmt('20991855573333')).toBe('20991855573333');
  });

  it('places the caret at the end after appending a digit', () => {
    const result = formatIdentifierInput('2099185557', 10);
    expect(result.value).toBe('(209) 918-5557');
    expect(result.caret).toBe(14);
  });

  it('maps the caret through inserted formatting chars', () => {
    // User typed "2099" (caret after 4th digit) -> "(209) 9" caret after the 9.
    const result = formatIdentifierInput('2099', 4);
    expect(result.value).toBe('(209) 9');
    expect(result.caret).toBe(7);
  });

  it('keeps the caret adjacent on a mid-string insert', () => {
    // "(209) 918-557" with "5" inserted after "918-5": "(209) 918-55|57"
    const raw = '(209) 918-5557';
    const result = formatIdentifierInput(raw, 12);
    expect(result.value).toBe('(209) 918-5557');
    expect(result.caret).toBe(12);
  });

  it('accounts for an absorbed leading 1 in the caret math', () => {
    const result = formatIdentifierInput('12099185557', 11);
    expect(result.value).toBe('(209) 918-5557');
    expect(result.caret).toBe(14);
  });

  it('repositions the caret before separators after deleting one', () => {
    // Backspacing the ")" of "(209) 918" gives raw "(209 918", caret 4.
    // Digits are unchanged, so the value re-formats and the caret lands
    // after the 3rd digit — the next backspace removes a real digit.
    const result = formatIdentifierInput('(209 918', 4);
    expect(result.value).toBe('(209) 918');
    expect(result.caret).toBe(4);
  });
});

describe('formatIdentifierDisplay', () => {
  it.each([
    ['2099185557', '+1 (209) 918-5557'],
    ['12099185557', '+1 (209) 918-5557'],
    ['(209) 918-5557', '+1 (209) 918-5557'],
    ['+442071234567', '+442071234567'],
    ['Nick@NATRX.io', 'nick@natrx.io'],
    ['garbage', 'garbage'],
  ])('%j -> %j', (input, expected) => {
    expect(formatIdentifierDisplay(input)).toBe(expected);
  });
});

describe('isValidEmail', () => {
  it.each([
    ['nick@natrx.io', true],
    ['Nick@NATRX.io', true],
    ['nick@', false],
    ['nick@natrx', false],
    ['@natrx.io', false],
    ['ni ck@natrx.io', false],
  ])('%j -> %s', (input, expected) => {
    expect(isValidEmail(input)).toBe(expected);
  });
});
