import { useEffect, useRef, useState } from 'react';
import PhoneFrame from './PhoneFrame';
import AppScreen from './AppScreen';
import NotificationChaos, { CHAOS_TOTAL_MS } from './NotificationChaos';
import {
  DEMO_UPDATE_ID,
  REACTION_TICKS,
  makeBaseEvents,
  makeDemoComment,
  makeFinalEvents,
  makeUpdateEvent,
} from './demoBirth';

// Carousel slide 1 — "one place to update, not scattered threads" (see
// Lily-Landing-Sections.md §1). One phone whose contents transform: chaos
// (texts pile up) → settle (the payoff: everything goes quiet) → broadcast
// (one calm update, reactions, a comment). Starts when `playing` turns true;
// the carousel remounts the slide (key bump) to reset it, and hears about
// the sequence finishing via `onComplete` so it can auto-advance.

const SETTLE_MS = 1200;
const BROADCAST_AT = CHAOS_TOTAL_MS + SETTLE_MS;
const UPDATE_POSTS_AT = BROADCAST_AT + 600;

const BANNER = "Lily's family is timing contractions. Following along 🤍";

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

export default function OnePlaceSlide({ playing, reducedMotion, onComplete }) {
  const timersRef = useRef([]);
  const startedRef = useRef(false);
  // idle → chaos → settle → broadcast → done
  const [phase, setPhase] = useState('idle');
  const [events, setEvents] = useState(makeBaseEvents);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    if (reducedMotion || !playing || startedRef.current) return;
    startedRef.current = true;

    const patchUpdate = (patch) =>
      setEvents((prev) =>
        prev.map((ev) => (ev.id === DEMO_UPDATE_ID ? { ...ev, ...patch } : ev)),
      );

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
      [
        UPDATE_POSTS_AT + 4300,
        () => {
          setPhase('done');
          onCompleteRef.current?.();
        },
      ],
    ];
    timersRef.current = cues.map(([at, fn]) => setTimeout(fn, at));
  }, [playing, reducedMotion]);

  useEffect(
    () => () => {
      timersRef.current.forEach(clearTimeout);
    },
    [],
  );

  const showApp = phase === 'broadcast' || phase === 'done';

  if (reducedMotion) {
    return (
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
                <AppScreen events={makeFinalEvents()} banner={BANNER} />
              </div>
            </PhoneFrame>
            <figcaption className="text-xl font-light text-gray-800 dark:text-gray-100">
              Give updates in one place
            </figcaption>
          </figure>
        </div>
      </>
    );
  }

  return (
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
            <AppScreen events={events} banner={BANNER} />
          </div>
        </PhoneFrame>
      </div>
    </div>
  );
}
