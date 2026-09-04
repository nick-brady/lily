import { describe, it, expect } from 'vitest';
import { NO_TAPS, PROMPT_AFTER, recordSilentStop, secondsSince } from './stopTaps';

describe('recordSilentStop', () => {
  it('prompts on the third declined tap of one contraction', () => {
    let tally = NO_TAPS;
    const prompts = [];
    for (let i = 0; i < 4; i += 1) {
      const next = recordSilentStop(tally, 'c1');
      tally = next.tally;
      prompts.push(next.prompt);
    }
    expect(prompts).toEqual([false, false, true, true]);
    expect(PROMPT_AFTER).toBe(3);
  });

  it('a new contraction starts the count over', () => {
    let { tally } = recordSilentStop(NO_TAPS, 'c1');
    ({ tally } = recordSilentStop(tally, 'c1'));
    const next = recordSilentStop(tally, 'c2');
    expect(next.prompt).toBe(false);
    expect(next.tally).toEqual({ contractionId: 'c2', count: 1 });
  });
});

describe('secondsSince', () => {
  it('rounds to whole seconds and never goes negative', () => {
    const now = Date.parse('2026-09-03T20:00:10Z');
    expect(secondsSince('2026-09-03T20:00:02.400Z', now)).toBe(8);
    expect(secondsSince('2026-09-03T20:00:12Z', now)).toBe(0);
    expect(secondsSince('not a date', now)).toBe(0);
  });
});
