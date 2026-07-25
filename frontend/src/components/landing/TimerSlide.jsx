import { useEffect, useRef, useState } from 'react';
import PhoneFrame from './PhoneFrame';
import ContractionButton from '../ContractionButton';
import Timeline from '../Timeline';
import { makeTimerBaseEvents, makeLoggedContraction } from './demoBirth';

// Carousel slide 2 — "it's a contraction timer" (see Lily-Landing-Sections.md
// §2). The parent's side of the phone for the first time: the real
// ContractionButton gets "pressed", times a contraction, and the logged row
// drops into the real Timeline. Starts once when the slide first becomes
// active; the carousel remounts it (key bump) to reset.

// The press backdates startTime ~48s so the timer reads mid-contraction and
// the logged duration is realistic — an honest 7s demo contraction would log
// a nonsense "7s" row. One frame of cheat, hidden under the press ripple.
const PRESS_AT_MS = 2200;
const BACKDATE_MS = 48000;
const STOP_AT_MS = PRESS_AT_MS + 7000;
const COMPLETE_AT_MS = STOP_AT_MS + 1800;

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
        And yes — it's a contraction timer.
      </h2>
      <p className="max-w-md text-base text-gray-500 dark:text-gray-400">
        One tap when a contraction starts, one when it ends. Timing, spacing, and
        telling everyone — handled.
      </p>
      <p className="sr-only">
        The parent's view of the page is a contraction timer: a large start button,
        a running count while the contraction lasts, and a stop tap that logs it to
        the timeline everyone follows — durations and spacing tracked automatically.
      </p>
    </>
  );
}

// The parent's screen: same page chrome, but the manage view — the real
// ContractionButton in its card above the real Timeline of logged
// contractions, mirroring the birth page's parent layout in miniature.
function ParentScreen({ startTime, events, pressed }) {
  return (
    <div
      className="demo-phone flex h-full flex-col overflow-hidden"
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
      <div className="flex-1 overflow-hidden px-3 py-3">
        <div className="card relative mb-3 flex justify-center py-5">
          <div className="scale-[0.82] origin-top">
            <ContractionButton onStart={() => {}} onStop={() => {}} startTime={startTime} />
          </div>
          {pressed && (
            <span
              className="pointer-events-none absolute left-1/2 top-1/2 h-24 w-24 -translate-x-1/2 -translate-y-1/4 animate-ping rounded-full bg-white/60"
              style={{ animationIterationCount: 3 }}
            />
          )}
        </div>
        <Timeline events={events} slug="lily-demo" />
      </div>
    </div>
  );
}

export default function TimerSlide({ active, reducedMotion, onComplete }) {
  const timersRef = useRef([]);
  const startedRef = useRef(false);
  const [startTime, setStartTime] = useState(null);
  const [pressed, setPressed] = useState(false);
  // idle → running → logged
  const [phase, setPhase] = useState('idle');
  const [events, setEvents] = useState(makeTimerBaseEvents);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    if (!active || reducedMotion || startedRef.current) return;
    startedRef.current = true;

    const cues = [
      [
        PRESS_AT_MS,
        () => {
          setPressed(true);
          setStartTime(new Date(Date.now() - BACKDATE_MS).toISOString());
          setPhase('running');
        },
      ],
      [PRESS_AT_MS + 1400, () => setPressed(false)],
      [
        STOP_AT_MS,
        () => {
          const startedAt = Date.now() - BACKDATE_MS - (STOP_AT_MS - PRESS_AT_MS);
          const duration = Math.round((BACKDATE_MS + STOP_AT_MS - PRESS_AT_MS) / 1000);
          setStartTime(null);
          setEvents((prev) => [...prev, makeLoggedContraction(startedAt, duration)]);
          setPhase('logged');
        },
      ],
      [COMPLETE_AT_MS, () => onCompleteRef.current?.()],
    ];
    timersRef.current = cues.map(([at, fn]) => setTimeout(fn, at));
  }, [active, reducedMotion]);

  useEffect(
    () => () => {
      timersRef.current.forEach(clearTimeout);
    },
    [],
  );

  // Reduced motion: the idle timer above the already-logged contractions —
  // both halves of the story, statically.
  const staticEvents = useState(() => [
    ...makeTimerBaseEvents(),
    makeLoggedContraction(Date.now() - 60 * 1000, 55),
  ])[0];

  return (
    <div className="flex flex-col gap-10 md:flex-row md:items-start md:gap-12">
      <div className="text-left md:flex-1 md:pt-6">
        <Headline />
        <div className="relative mt-10 h-16 md:mt-32">
          {reducedMotion ? (
            <Caption visible>Tap once when it starts, again when it ends</Caption>
          ) : (
            <>
              <Caption visible={phase === 'idle'}>A contraction starts — tap</Caption>
              <Caption visible={phase === 'running'}>Tap again when it ends</Caption>
              <Caption visible={phase === 'logged'}>Timed, logged, shared — automatically</Caption>
            </>
          )}
        </div>
      </div>

      <div className="flex justify-center md:flex-1 md:justify-start md:pl-6">
        <PhoneFrame>
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 select-none">
            <ParentScreen
              startTime={reducedMotion ? null : startTime}
              events={reducedMotion ? staticEvents : events}
              pressed={pressed}
            />
          </div>
        </PhoneFrame>
      </div>
    </div>
  );
}
