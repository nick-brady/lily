import { useMemo } from 'react';
import { mean, standardDeviation, check511Rule, formatDuration } from '../utils/statistics';

export default function StatsPanel({ contractions, timeRange = 'all', customTimestamps = null }) {

  const stats = useMemo(() => {
    let completed = contractions.filter(c => c.end_time && c.duration_seconds);

    // Filter by time range
    if (timeRange === 'hour') {
      const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
      completed = completed.filter(c => new Date(c.start_time) >= oneHourAgo);
    } else if (timeRange === 'custom' && customTimestamps) {
      completed = completed.filter(c => {
        const time = new Date(c.start_time);
        return time >= customTimestamps.start && time <= customTimestamps.end;
      });
    }

    if (completed.length === 0) {
      return {
        count: 0,
        avgDuration: null,
        avgInterval: null,
        stdDuration: null,
        rule511: { meets: false, message: 'Need data' },
      };
    }

    // Duration stats
    const durations = completed.map(c => c.duration_seconds);
    const avgDuration = mean(durations);
    const stdDuration = standardDeviation(durations);

    // Interval stats
    const sorted = [...completed].sort((a, b) =>
      new Date(a.start_time) - new Date(b.start_time)
    );

    let avgInterval = null;
    if (sorted.length >= 2) {
      const intervals = [];
      for (let i = 1; i < sorted.length; i++) {
        // Skip if this contraction has ignore_interval_before set
        if (sorted[i].ignore_interval_before) {
          continue;
        }
        const prev = new Date(sorted[i - 1].start_time);
        const curr = new Date(sorted[i].start_time);
        const gapMinutes = (curr - prev) / 1000 / 60;
        // Exclude gaps > 30 minutes (break in labor)
        if (gapMinutes <= 30) {
          intervals.push(gapMinutes);
        }
      }
      if (intervals.length > 0) {
        avgInterval = mean(intervals);
      }
    }

    // 5-1-1 rule check (always uses full data)
    const rule511 = check511Rule(contractions);

    return {
      count: completed.length,
      avgDuration,
      avgInterval,
      stdDuration,
      rule511,
    };
  }, [contractions, timeRange, customTimestamps]);

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">
        Statistics
      </h3>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="text-center p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
          <div className="text-2xl font-bold text-primary-600 dark:text-primary-400">
            {stats.count}
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {timeRange === 'all' ? 'Total' : timeRange === 'hour' ? 'Last Hour' : 'Selected'} Contractions
          </div>
        </div>

        <div className="text-center p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
          <div className="text-2xl font-bold text-primary-600 dark:text-primary-400">
            {stats.avgDuration ? formatDuration(Math.round(stats.avgDuration)) : '-'}
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Avg Duration
          </div>
        </div>

        <div className="text-center p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
            {stats.avgInterval ? `${stats.avgInterval.toFixed(1)} min` : '-'}
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Avg Interval
          </div>
        </div>

        <div className="text-center p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
          <div className="text-2xl font-bold text-gray-600 dark:text-gray-400">
            {stats.stdDuration ? `±${formatDuration(Math.round(stats.stdDuration))}` : '-'}
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Std Deviation
          </div>
        </div>
      </div>

      {/* 5-1-1 Rule Indicator */}
      <div className={`p-4 rounded-lg border-2 ${
        stats.rule511.meets
          ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
          : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/30'
      }`}>
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${
            stats.rule511.meets
              ? 'bg-green-500 animate-pulse'
              : 'bg-gray-300 dark:bg-gray-600'
          }`} />
          <div>
            <div className={`font-semibold ${
              stats.rule511.meets
                ? 'text-green-700 dark:text-green-400'
                : 'text-gray-700 dark:text-gray-300'
            }`}>
              5-1-1 Rule
            </div>
            <div className={`text-sm ${
              stats.rule511.meets
                ? 'text-green-600 dark:text-green-500'
                : 'text-gray-500 dark:text-gray-400'
            }`}>
              {stats.rule511.message}
            </div>
          </div>
        </div>
        {stats.rule511.meets && (
          <div className="mt-3 text-sm text-green-700 dark:text-green-400 font-medium">
            Consider contacting your healthcare provider!
          </div>
        )}
      </div>

      <div className="mt-4 text-xs text-gray-400 dark:text-gray-500">
        5-1-1 Rule: Contractions 5 min apart, lasting 1 min, for 1 hour
      </div>
    </div>
  );
}
