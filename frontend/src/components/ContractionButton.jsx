import { useEffect, useState } from 'react';

export default function ContractionButton({ onStart, onStop, startTime }) {
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
        <div className="text-6xl font-mono font-bold text-red-500 dark:text-red-400">
          {formatTime(elapsed)}
        </div>
        <button
          onClick={onStop}
          className="w-48 h-48 rounded-full bg-red-500 hover:bg-red-600 text-white text-2xl font-bold
                     shadow-2xl hover:shadow-red-500/50 transition-all duration-200 active:scale-95
                     animate-pulse-slow flex items-center justify-center"
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
      <div className="text-6xl font-mono font-bold t-faint">
        00:00
      </div>
      <button
        onClick={onStart}
        className="w-48 h-48 rounded-full t-btn-accent t-glow text-xl font-bold
                   shadow-2xl transition-all duration-200 active:scale-95
                   flex items-center justify-center"
      >
        START<br/>CONTRACTION
      </button>
      <p className="t-muted text-sm">
        Tap when contraction begins
      </p>
    </div>
  );
}
