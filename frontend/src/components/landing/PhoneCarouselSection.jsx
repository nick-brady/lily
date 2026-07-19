import { useEffect, useRef, useState } from 'react';
import OnePlaceSlide from './OnePlaceSlide';
import TimerSlide from './TimerSlide';
import KeepsakeSlide from './KeepsakeSlide';

// The phone-demo carousel under the hero (Lily-Landing-Sections.md §1–3).
// One section, one story told in slides that share the phone motif:
//   1. "One place to update" — chaos → one calm update (OnePlaceSlide)
//   2. "It's a contraction timer" — the parent presses the real button (TimerSlide)
//   3. "A keepsake, forever" — scrolling back through the finished story
// Slide 1 starts when the section scrolls into view; a few seconds after each
// slide finishes its sequence, the carousel auto-advances to the next —
// unless the visitor has navigated manually, which hands them the wheel for
// good. Fully leaving the viewport resets everything (slides remount via
// key), matching the play-once/replay-on-reenter convention of the band.

const SLIDE_COUNT = 3;
const AUTO_ADVANCE_DELAY_MS = 3200;
const SWIPE_THRESHOLD_PX = 48;

export default function PhoneCarouselSection() {
  const rootRef = useRef(null);
  const advanceTimerRef = useRef(null);
  const userNavigatedRef = useRef(false);
  const visibleRef = useRef(false);
  const touchXRef = useRef(null);

  const [active, setActive] = useState(0);
  const activeRef = useRef(0);
  activeRef.current = active;
  // Turns true at the 0.35 visibility threshold and starts slide 1.
  const [armed, setArmed] = useState(false);
  // Bumped on full exit to remount (= reset) both slides.
  const [runId, setRunId] = useState(0);

  const [reducedMotion] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );

  useEffect(() => {
    if (reducedMotion) return undefined;

    const observer = new IntersectionObserver(
      ([entry]) => {
        visibleRef.current = entry.isIntersecting;
        if (entry.intersectionRatio >= 0.35) {
          setArmed(true);
        } else if (!entry.isIntersecting) {
          clearTimeout(advanceTimerRef.current);
          userNavigatedRef.current = false;
          setArmed(false);
          setActive(0);
          setRunId((n) => n + 1);
        }
      },
      { threshold: [0, 0.35] },
    );
    observer.observe(rootRef.current);

    return () => {
      observer.disconnect();
      clearTimeout(advanceTimerRef.current);
    };
  }, [reducedMotion]);

  const goTo = (index) => {
    if (index < 0 || index >= SLIDE_COUNT) return;
    userNavigatedRef.current = true;
    clearTimeout(advanceTimerRef.current);
    setActive(index);
  };

  // A slide finished its sequence — advance past it after a hold, provided
  // the visitor hasn't taken the wheel and we're still on that slide.
  const handleSlideComplete = (index) => {
    if (index >= SLIDE_COUNT - 1) return;
    advanceTimerRef.current = setTimeout(() => {
      if (!userNavigatedRef.current && visibleRef.current && activeRef.current === index) {
        setActive(index + 1);
      }
    }, AUTO_ADVANCE_DELAY_MS);
  };

  const onTouchStart = (e) => {
    touchXRef.current = e.touches[0].clientX;
  };
  const onTouchEnd = (e) => {
    if (touchXRef.current === null) return;
    const dx = e.changedTouches[0].clientX - touchXRef.current;
    touchXRef.current = null;
    if (Math.abs(dx) >= SWIPE_THRESHOLD_PX) goTo(active + (dx < 0 ? 1 : -1));
  };

  return (
    <section
      ref={rootRef}
      aria-roledescription="carousel"
      aria-label="Why families love Arrival Story"
      className="overflow-hidden bg-gradient-to-b from-white via-primary-50/70 to-white px-6 py-20 dark:from-gray-950 dark:via-gray-900 dark:to-gray-950"
    >
      <div className="mx-auto max-w-4xl">
        <div className="overflow-hidden" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
          <div
            className="flex transition-transform duration-700 ease-out"
            style={{ transform: `translateX(-${active * 100}%)` }}
          >
            <div
              className="w-full flex-shrink-0"
              role="group"
              aria-roledescription="slide"
              aria-label="1 of 3"
              aria-hidden={active !== 0}
            >
              <OnePlaceSlide
                key={`one-${runId}`}
                playing={armed}
                reducedMotion={reducedMotion}
                onComplete={() => handleSlideComplete(0)}
              />
            </div>
            <div
              className="w-full flex-shrink-0"
              role="group"
              aria-roledescription="slide"
              aria-label="2 of 3"
              aria-hidden={active !== 1}
            >
              <TimerSlide
                key={`timer-${runId}`}
                active={active === 1}
                reducedMotion={reducedMotion}
                onComplete={() => handleSlideComplete(1)}
              />
            </div>
            <div
              className="w-full flex-shrink-0"
              role="group"
              aria-roledescription="slide"
              aria-label="3 of 3"
              aria-hidden={active !== 2}
            >
              <KeepsakeSlide
                key={`keep-${runId}`}
                active={active === 2}
                reducedMotion={reducedMotion}
              />
            </div>
          </div>
        </div>

        <div className="mt-10 flex items-center justify-center gap-5">
          <button
            type="button"
            aria-label="Previous slide"
            disabled={active === 0}
            onClick={() => goTo(active - 1)}
            className="p-1 text-gray-400 transition-colors hover:text-primary-500 disabled:opacity-30 disabled:hover:text-gray-400 dark:text-gray-500"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          {Array.from({ length: SLIDE_COUNT }, (_, i) => (
            <button
              key={i}
              type="button"
              aria-label={`Go to slide ${i + 1}`}
              aria-current={active === i}
              onClick={() => goTo(i)}
              className={`h-2.5 rounded-full transition-all duration-300 ${
                active === i
                  ? 'w-6 bg-primary-500'
                  : 'w-2.5 bg-gray-300 hover:bg-gray-400 dark:bg-gray-600 dark:hover:bg-gray-500'
              }`}
            />
          ))}
          <button
            type="button"
            aria-label="Next slide"
            disabled={active === SLIDE_COUNT - 1}
            onClick={() => goTo(active + 1)}
            className="p-1 text-gray-400 transition-colors hover:text-primary-500 disabled:opacity-30 disabled:hover:text-gray-400 dark:text-gray-500"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </section>
  );
}
