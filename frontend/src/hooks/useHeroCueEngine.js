import { useCallback, useEffect, useRef, useState } from 'react';
import {
  HERO_CUES,
  HERO_DURATION,
  initialHeroState,
  makeCueContext,
} from '../components/landing/heroCues';

/**
 * Drives the hero phone UI from the video playhead (Lily-Hero-Video-Plan.md
 * §1 "the sync engine"). A requestAnimationFrame loop reads
 * `video.currentTime` every frame and fires any cue the playhead has crossed
 * — never setTimeout: buffering, backgrounded tabs, and delayed autoplay all
 * drift wall-clock timers, while currentTime cannot drift.
 *
 * - Loop wrap (currentTime jumps backward): state resets, cues re-arm, and
 *   any cues before the new position replay instantly — which also makes
 *   scrubbing/seeking free during development.
 * - `clockMode` (mobile, no video visible): an internal accumulator stands in
 *   for currentTime so the choreography still performs, wrapping at
 *   HERO_DURATION.
 * - `running` gates the loop (IntersectionObserver visibility).
 */
export default function useHeroCueEngine({ videoRef, clockMode = false, running = true }) {
  const baseRef = useRef(null);
  const ctxRef = useRef(null);
  if (baseRef.current === null) {
    baseRef.current = Date.now();
    ctxRef.current = makeCueContext(baseRef.current);
  }
  const [state, setState] = useState(() => initialHeroState(baseRef.current));
  const nextCueRef = useRef(0);
  const lastTRef = useRef(0);
  const clockRef = useRef({ t: 0, stamp: null });

  const reset = useCallback(() => {
    nextCueRef.current = 0;
    lastTRef.current = 0;
    clockRef.current = { t: 0, stamp: null };
    baseRef.current = Date.now();
    ctxRef.current = makeCueContext(baseRef.current);
    setState(initialHeroState(baseRef.current));
  }, []);

  useEffect(() => {
    if (!running) {
      clockRef.current.stamp = null;
      return undefined;
    }

    let raf;

    const tick = (now) => {
      raf = requestAnimationFrame(tick);

      let t;
      if (clockMode) {
        const clock = clockRef.current;
        if (clock.stamp != null) clock.t += (now - clock.stamp) / 1000;
        clock.stamp = now;
        if (clock.t >= HERO_DURATION) clock.t %= HERO_DURATION;
        t = clock.t;
      } else {
        const video = videoRef.current;
        if (!video || video.readyState < 2) return;
        t = video.currentTime;
      }

      // Wrap or backward seek: re-arm everything and replay up to t.
      if (t < lastTRef.current - 0.5) {
        nextCueRef.current = 0;
        baseRef.current = Date.now();
        ctxRef.current = makeCueContext(baseRef.current);
        setState(initialHeroState(baseRef.current));
      }
      lastTRef.current = t;

      // Advance the cue pointer OUTSIDE the state updater: React StrictMode
      // double-invokes updaters, so an updater that mutates refs silently
      // swallows cues in development.
      const start = nextCueRef.current;
      let end = start;
      while (end < HERO_CUES.length && HERO_CUES[end].t <= t) end += 1;
      if (end === start) return;
      nextCueRef.current = end;

      const ctx = ctxRef.current;
      const toApply = HERO_CUES.slice(start, end);
      setState((prev) => toApply.reduce((acc, cue) => cue.apply(acc, ctx), prev));
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [videoRef, clockMode, running]);

  return { state, reset };
}
