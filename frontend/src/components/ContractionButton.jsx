import { useEffect, useState } from 'react';

// `pending` covers the moment between the tap and the server's answer. It is
// the only button in the app that lacked one, and it is the one that matters
// most: two parents watch this page and neither knows who will press it.
export default function ContractionButton({ onStart, onStop, startTime, pending = false }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startTime) {
      setElapsed(0);
      return undefined;
    }
    const startedAt = new Date(startTime);
    const tick = () => setElapsed(Math.floor((new Date() - startedAt) / 1000));
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  if (startTime) {
    return (
      <div className="flex flex-col items-center gap-4">
        {/* the clock ticks every second — a screen reader must not read it
            every second, so it is a timer that announces nothing on its own;
            the status line below says the state changed, once */}
        <div
          role="timer"
          aria-live="off"
          aria-label="Contraction elapsed time"
          className="text-6xl font-mono font-bold text-red-500 dark:text-red-400"
        >
          {formatTime(elapsed)}
        </div>
        <p className="sr-only" role="status">Contraction in progress</p>
        <button
          onClick={onStop}
          disabled={pending}
          aria-busy={pending}
          className="w-48 h-48 rounded-full bg-red-500 hover:bg-red-600 text-white text-2xl font-bold
                     shadow-2xl hover:shadow-red-500/50 transition-all duration-200 active:scale-95
                     motion-safe:animate-pulse-slow flex items-center justify-center
                     disabled:opacity-60 disabled:active:scale-100"
        >
          STOP
        </button>
        <p className="t-muted text-sm">
          Tap when contraction ends
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="text-6xl font-mono font-bold t-faint" aria-hidden="true">
        00:00
      </div>
      <p className="sr-only" role="status">No contraction running</p>
      <button
        onClick={onStart}
        disabled={pending}
        aria-busy={pending}
        className="w-48 h-48 rounded-full t-btn-accent t-glow text-xl font-bold
                   shadow-2xl transition-all duration-200 active:scale-95
                   flex items-center justify-center
                   disabled:opacity-60 disabled:active:scale-100"
      >
        START<br/>CONTRACTION
      </button>
      <p className="t-muted text-sm">
        Tap when contraction begins
      </p>
    </div>
  );
}
