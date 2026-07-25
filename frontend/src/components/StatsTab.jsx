import { useCallback, useMemo, useState } from 'react';
import { contractionsFromEvents } from '../utils/statistics';
import StatsPanel from './StatsPanel';
import TimeSeriesChart from './TimeSeriesChart';

/**
 * The parent-facing labor stats: range switcher, summary panel, and the
 * duration/interval charts. Self-contained — derives contractions from the
 * page's event list and owns its own range state (which therefore resets
 * when the parent switches tabs; deliberate, the ranges are ephemeral).
 */
export default function StatsTab({ events }) {
  const [timeRange, setTimeRange] = useState('all');
  const [customRange, setCustomRange] = useState({ start: 0, end: 100 });

  const contractions = useMemo(() => contractionsFromEvents(events), [events]);

  const timeBounds = useMemo(() => {
    const completed = contractions.filter((c) => c.end_time && c.duration_seconds);
    if (completed.length === 0) {
      const now = Date.now();
      return { min: now - 3600000, max: now };
    }
    const times = completed.map((c) => new Date(c.start_time).getTime());
    return { min: Math.min(...times), max: Math.max(...times, Date.now()) };
  }, [contractions]);

  const getCustomTimestamps = useCallback(() => {
    const range = timeBounds.max - timeBounds.min;
    return {
      start: new Date(timeBounds.min + (customRange.start / 100) * range),
      end: new Date(timeBounds.min + (customRange.end / 100) * range),
    };
  }, [timeBounds, customRange]);

  const timestamps = getCustomTimestamps();
  const formatTime = (date) =>
    date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <>
      <div className="card">
        <div className="flex justify-center mb-3">
          <div className="flex bg-gray-200 dark:bg-gray-700 rounded-lg p-1">
            {[
              { value: 'all', label: 'All Time' },
              { value: 'hour', label: 'Last Hour' },
              { value: 'custom', label: 'Custom' },
            ].map((option) => (
              <button
                key={option.value}
                onClick={() => setTimeRange(option.value)}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                  timeRange === option.value
                    ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {timeRange === 'custom' && (
          <div className="flex flex-col items-center gap-3 pt-2">
            <div className="w-full max-w-sm space-y-4">
              <RangeSlider
                label="Start"
                timeLabel={formatTime(timestamps.start)}
                value={customRange.start}
                onChange={(val) =>
                  setCustomRange((prev) => ({ ...prev, start: Math.min(val, prev.end - 1) }))
                }
              />
              <RangeSlider
                label="End"
                timeLabel={formatTime(timestamps.end)}
                value={customRange.end}
                onChange={(val) =>
                  setCustomRange((prev) => ({ ...prev, end: Math.max(val, prev.start + 1) }))
                }
              />
            </div>
          </div>
        )}
      </div>

      <StatsPanel
        contractions={contractions}
        timeRange={timeRange}
        customTimestamps={timestamps}
      />
      <div className="grid md:grid-cols-2 gap-6">
        <TimeSeriesChart
          contractions={contractions}
          type="duration"
          timeRange={timeRange}
          customTimestamps={timestamps}
        />
        <TimeSeriesChart
          contractions={contractions}
          type="interval"
          timeRange={timeRange}
          customTimestamps={timestamps}
        />
      </div>
    </>
  );
}

function RangeSlider({ label, timeLabel, value, onChange }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
        <span>{label}</span>
        <span className="font-medium text-gray-700 dark:text-gray-300">{timeLabel}</span>
      </div>
      <input
        type="range"
        min="0"
        max="100"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-primary-500"
      />
    </div>
  );
}
