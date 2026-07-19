import { useEffect, useRef, useState } from 'react';
import PhoneFrame from './PhoneFrame';
import AppScreen from './AppScreen';
import { makeKeepsakeEvents } from './demoBirth';

// Carousel slide 3 — "a keepsake, forever" (see Lily-Landing-Sections.md §3).
// The same Lily Wren page, after the big day: the phone slowly scrolls back
// through the completed story — name announcement, first photo, the born
// milestone, Dad's voice memo, the contractions, all the way to the 40-week
// bump photo. Starts once when the slide first becomes active; the carousel
// remounts it (key bump) to reset.

const SCROLL_DELAY_MS = 1100;
const SCROLL_DURATION_MS = 18000;

const BANNER = 'Lily is here 🤍 The whole story, saved.';

function easeInOut(t) {
  return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
}

function Headline() {
  return (
    <>
      <h2 className="mb-3 text-3xl font-light text-gray-800 dark:text-gray-100">
        A keepsake, forever.
      </h2>
      <p className="max-w-md text-base text-gray-500 dark:text-gray-400">
        After the big day, the page becomes the story — every voice memo, photo, and
        contraction, kept exactly as it happened.
      </p>
      <p className="sr-only">
        The finished Arrival Story page reads like a memory book: the name
        announcement, the first photo, the moment she was born, a voice memo from
        Dad, and every contraction of the long night — scrolled back through like
        you're reliving it.
      </p>
    </>
  );
}

export default function KeepsakeSlide({ active, reducedMotion }) {
  const scrollRef = useRef(null);
  const startedRef = useRef(false);
  const [events] = useState(makeKeepsakeEvents);

  useEffect(() => {
    if (!active || reducedMotion || startedRef.current) return undefined;
    startedRef.current = true;

    const el = scrollRef.current;
    let raf;
    let startTs;
    const step = (ts) => {
      if (startTs === undefined) startTs = ts;
      const progress = Math.min(1, (ts - startTs) / SCROLL_DURATION_MS);
      el.scrollTop = (el.scrollHeight - el.clientHeight) * easeInOut(progress);
      if (progress < 1) raf = requestAnimationFrame(step);
    };
    const timer = setTimeout(() => {
      raf = requestAnimationFrame(step);
    }, SCROLL_DELAY_MS);

    return () => {
      clearTimeout(timer);
      cancelAnimationFrame(raf);
    };
  }, [active, reducedMotion]);

  return (
    <div className="flex flex-col gap-10 md:flex-row md:items-start md:gap-12">
      <div className="text-left md:flex-1 md:pt-6">
        <Headline />
        <div className="relative mt-10 h-16 md:mt-32">
          <p className="absolute inset-0 flex items-center justify-center text-center text-2xl font-light leading-snug text-gray-800 dark:text-gray-100 md:justify-start md:text-left">
            Look back anytime
          </p>
        </div>
      </div>

      <div className="flex justify-center md:flex-1 md:justify-start md:pl-6">
        <PhoneFrame>
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 select-none">
            <AppScreen
              events={events}
              banner={BANNER}
              bannerPulse={false}
              scrollRef={scrollRef}
            />
          </div>
        </PhoneFrame>
      </div>
    </div>
  );
}
