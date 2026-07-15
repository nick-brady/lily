import { useEffect, useRef, useState } from 'react';
import Timeline from '../Timeline';
import PhoneFrame from './PhoneFrame';
import NotificationChaos, { CHAOS_TOTAL_MS } from './NotificationChaos';
import {
  DEMO_UPDATE_ID,
  REACTION_TICKS,
  makeBaseEvents,
  makeDemoComment,
  makeFinalEvents,
  makeUpdateEvent,
} from './demoBirth';

// The "one place to update, not scattered threads" section — see
// Lily-Landing-Sections.md §1. One phone whose contents transform:
// chaos (texts pile up) → settle (the payoff: everything goes quiet) →
// broadcast (one calm update, reactions, a comment). Plays once when
// scrolled into view; replays only after fully leaving the viewport.

const SETTLE_MS = 1200;
const BROADCAST_AT = CHAOS_TOTAL_MS + SETTLE_MS;
const UPDATE_POSTS_AT = BROADCAST_AT + 600;

function Caption({ visible, children }) {
  return (
    <p
      className={`absolute inset-0 flex items-center justify-center text-center text-2xl font-light leading-snug text-gray-800 dark:text-gray-100 transition-opacity duration-500 md:justify-start md:text-left ${
        visible ? 'opacity-100' : 'opacity-0'
      }`}
    >
      {children}
    </p>
  );
}

function Headline() {
  return (
    <>
      <h2 className="mb-3 text-3xl font-light text-gray-800 dark:text-gray-100">
        One place to update, not scattered threads.
      </h2>
      <p className="max-w-md text-base text-gray-500 dark:text-gray-400">
        Post once to your family's page — everyone follows along without blowing up
        your phone.
      </p>
      <p className="sr-only">
        Without Arrival Story, texts pile up from the whole family — "Any update??",
        "How's she doing?!" — all needing individual replies. With Arrival Story, one
        calm update posts to your family's page and everyone reacts there instead.
      </p>
    </>
  );
}

// The Arrival Story screen: real product components fed by the fixture,
// framed by a miniature of the public birth page chrome.
function AppScreen({ events }) {
  return (
    <div
      className="demo-phone h-full overflow-hidden"
      style={{ backgroundColor: 'var(--t-page-bg)' }}
    >
      <div
        className="px-4 pt-10 pb-3 text-center"
        style={{
          backgroundColor: 'var(--t-header-bg)',
          borderBottom: '1px solid var(--t-header-border)',
        }}
      >
        <div className="t-display text-[24px] leading-tight">Welcoming Lily Wren</div>
      </div>
      <div
        className="mx-3 mt-3 flex items-center gap-2 rounded-xl px-3 py-2"
        style={{ backgroundColor: 'var(--t-soft-bg)' }}
      >
        <span
          className="h-2 w-2 flex-shrink-0 rounded-full animate-pulse"
          style={{ backgroundColor: 'var(--t-dot)' }}
        />
        <p className="text-[11px]" style={{ color: 'var(--t-soft-text)' }}>
          Lily's family is timing contractions. Following along 🤍
        </p>
      </div>
      <div className="px-3 py-3">
        <Timeline events={events} slug="lily-demo" isUnlocked />
      </div>
    </div>
  );
}

export default function OnePlaceSection() {
  const rootRef = useRef(null);
  const timersRef = useRef([]);
  const phaseRef = useRef('idle');
  // idle → chaos → settle → broadcast → done
  const [phase, setPhase] = useState('idle');
  phaseRef.current = phase;
  const [events, setEvents] = useState(makeBaseEvents);

  const [reducedMotion] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );

  useEffect(() => {
    if (reducedMotion) return undefined;

    const patchUpdate = (patch) =>
      setEvents((prev) =>
        prev.map((ev) => (ev.id === DEMO_UPDATE_ID ? { ...ev, ...patch } : ev)),
      );

    const clearTimers = () => {
      timersRef.current.forEach(clearTimeout);
      timersRef.current = [];
    };

    const start = () => {
      setPhase('chaos');
      const cues = [
        [CHAOS_TOTAL_MS, () => setPhase('settle')],
        [BROADCAST_AT, () => setPhase('broadcast')],
        [UPDATE_POSTS_AT, () => setEvents((prev) => [...prev, makeUpdateEvent()])],
        ...REACTION_TICKS.map((tick) => [
          UPDATE_POSTS_AT + tick.at,
          () => patchUpdate({ reactions: tick.reactions }),
        ]),
        [
          UPDATE_POSTS_AT + 3300,
          () => patchUpdate({ comment_count: 1, demo_comments: [makeDemoComment()] }),
        ],
        [UPDATE_POSTS_AT + 4300, () => setPhase('done')],
      ];
      timersRef.current = cues.map(([at, fn]) => setTimeout(fn, at));
    };

    const reset = () => {
      clearTimers();
      setEvents(makeBaseEvents());
      setPhase('idle');
    };

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.intersectionRatio >= 0.35 && phaseRef.current === 'idle') {
          start();
        } else if (!entry.isIntersecting && phaseRef.current !== 'idle') {
          reset();
        }
      },
      { threshold: [0, 0.35] },
    );
    observer.observe(rootRef.current);

    return () => {
      observer.disconnect();
      clearTimers();
    };
  }, [reducedMotion]);

  const showApp = phase === 'broadcast' || phase === 'done';

  return (
    <section
      ref={rootRef}
      className="overflow-hidden bg-gradient-to-b from-white via-primary-50/70 to-white px-6 py-20 dark:from-gray-950 dark:via-gray-900 dark:to-gray-950"
    >
      <div className="mx-auto max-w-4xl">
        {reducedMotion ? (
          <>
            <div className="text-left">
              <Headline />
            </div>
            <div className="mt-12 flex flex-col items-center gap-12 md:flex-row md:items-start md:justify-center md:gap-14">
              <figure className="flex flex-col items-center gap-4">
                <PhoneFrame>
                  <div aria-hidden="true" className="pointer-events-none absolute inset-0 select-none">
                    <NotificationChaos staticAll />
                  </div>
                </PhoneFrame>
                <figcaption className="text-xl font-light text-gray-800 dark:text-gray-100">
                  Your family will want updates
                </figcaption>
              </figure>
              <figure className="flex flex-col items-center gap-4">
                <PhoneFrame>
                  <div aria-hidden="true" className="pointer-events-none absolute inset-0 select-none">
                    <AppScreen events={makeFinalEvents()} />
                  </div>
                </PhoneFrame>
                <figcaption className="text-xl font-light text-gray-800 dark:text-gray-100">
                  Give updates in one place
                </figcaption>
              </figure>
            </div>
          </>
        ) : (
          <div className="flex flex-col gap-10 md:flex-row md:items-start md:gap-12">
            {/* Left column: headline at the top, the swapping beat caption
                sitting mid-height beside the phone. */}
            <div className="text-left md:flex-1 md:pt-6">
              <Headline />
              <div className="relative mt-10 h-16 md:mt-32">
                <Caption visible={phase === 'chaos'}>Your family will want updates</Caption>
                <Caption visible={showApp}>Give updates in one place</Caption>
              </div>
            </div>

            <div className="flex justify-center md:flex-1 md:justify-start md:pl-6">
              <PhoneFrame>
                <div
                  aria-hidden="true"
                  className={`pointer-events-none absolute inset-0 select-none transition-opacity duration-700 ${
                    showApp ? 'opacity-0' : 'opacity-100'
                  }`}
                >
                  <NotificationChaos run={phase !== 'idle'} settled={phase !== 'idle' && phase !== 'chaos'} />
                </div>
                <div
                  aria-hidden="true"
                  className={`pointer-events-none absolute inset-0 select-none transition-opacity duration-700 ${
                    showApp ? 'opacity-100' : 'opacity-0'
                  }`}
                >
                  <AppScreen events={events} />
                </div>
              </PhoneFrame>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
