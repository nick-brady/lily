import { useEffect, useState } from 'react';

// Beat 1 of the "one place to update" section: a dark lock screen filling
// with loving-but-relentless texts. Deliberately generic gray messaging-app
// styling — this is every other app, not ours. The family is never the
// villain; the fragmentation is.
//
// `at` is ms after the beat starts — the gaps shrink so the pile
// accelerates. Keep the pile's total height under the screen height.
const NOTIFICATIONS = [
  { at: 400, initial: 'M', sender: 'Mom', text: 'Any update?? 😊' },
  { at: 1500, initial: 'D', sender: 'Dad', text: "How's she doing?!" },
  { at: 2400, initial: 'E', sender: 'Em', text: 'Anything yet???' },
  { at: 3100, initial: 'M', sender: 'Mom', text: 'Is the baby here??' },
  { at: 3650, initial: 'L', sender: 'Aunt Linda', text: 'Call me when you can!' },
  {
    at: 4100,
    initial: 'J',
    sender: 'Grandma Janet',
    text: "Sorry, I know you're busy!! Just checking ❤️",
  },
  { at: 4450, kind: 'missed-call', sender: 'Mom', text: 'Missed Call' },
  { at: 4750, kind: 'typing', sender: 'Dad' },
];

export const CHAOS_TOTAL_MS = 5000;

function LockClock() {
  return (
    <div className="pt-12 pb-4 text-center select-none">
      <div className="text-5xl font-light text-white tracking-tight drop-shadow-sm">2:13</div>
      <div className="mt-1 text-[13px] text-white/70 drop-shadow-sm">Tuesday — she's in labor</div>
    </div>
  );
}

function NotificationCard({ item, animate }) {
  if (item.kind === 'typing') {
    return (
      <div
        className={`${animate ? 'notif-in' : ''} mx-auto flex w-fit items-center gap-2 rounded-full bg-white/85 px-4 py-2 shadow-md`}
      >
        <span className="text-[12px] text-gray-500">{item.sender} is typing</span>
        <span className="flex gap-0.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-1.5 w-1.5 rounded-full bg-gray-400 animate-pulse"
              style={{ animationDelay: `${i * 200}ms` }}
            />
          ))}
        </span>
      </div>
    );
  }

  const isMissedCall = item.kind === 'missed-call';
  return (
    <div
      className={`${animate ? 'notif-in' : ''} flex items-start gap-2.5 rounded-2xl bg-white/95 px-3 py-2.5 shadow-md`}
    >
      <div
        className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
          isMissedCall ? 'bg-red-100 text-red-500' : 'bg-gray-300 text-gray-600'
        }`}
      >
        {isMissedCall ? (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
            />
          </svg>
        ) : (
          item.initial
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate text-[12px] font-semibold text-gray-800">{item.sender}</span>
          <span className="flex-shrink-0 text-[10px] text-gray-400">now</span>
        </div>
        <p className={`text-[12px] leading-snug ${isMissedCall ? 'text-red-500' : 'text-gray-600'}`}>
          {item.text}
        </p>
      </div>
    </div>
  );
}

/**
 * `run` starts the arrival schedule (and resets the pile when it flips
 * back off); `settled` desaturates and quiets everything — the payoff
 * beat. `staticAll` renders the full pile immediately with no animation
 * (reduced-motion fallback).
 */
export default function NotificationChaos({ run = false, settled = false, staticAll = false }) {
  const [visible, setVisible] = useState(staticAll ? NOTIFICATIONS.length : 0);

  useEffect(() => {
    if (staticAll) return undefined;
    if (!run) {
      setVisible(0);
      return undefined;
    }
    const timers = NOTIFICATIONS.map((n, i) =>
      setTimeout(() => setVisible(i + 1), n.at),
    );
    return () => timers.forEach(clearTimeout);
  }, [run, staticAll]);

  const badge = staticAll ? NOTIFICATIONS.length : visible;

  return (
    <div className="h-full bg-gradient-to-b from-indigo-300 via-purple-300 to-purple-400">
      {badge > 0 && !settled && (
        <div className="absolute right-3 top-3 z-10 flex h-6 min-w-6 items-center justify-center rounded-full bg-red-500 px-1.5 text-[11px] font-bold text-white shadow">
          {badge}
        </div>
      )}
      <LockClock />
      <div
        className={`px-3 transition-all duration-1000 ${
          settled ? 'opacity-30 grayscale translate-y-1' : ''
        }`}
      >
        {NOTIFICATIONS.slice(0, staticAll ? undefined : visible).map((item, i) => (
          <div key={i} style={{ marginTop: i === 0 ? 0 : i > 3 ? -4 : 8 }}>
            <NotificationCard item={item} animate={!staticAll} />
          </div>
        ))}
      </div>
    </div>
  );
}
