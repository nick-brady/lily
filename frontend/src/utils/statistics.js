/**
 * Calculate mean of an array of numbers
 */
export function mean(values) {
  if (!values || values.length === 0) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

/**
 * Calculate standard deviation
 */
export function standardDeviation(values) {
  if (!values || values.length < 2) return 0;
  const avg = mean(values);
  const squareDiffs = values.map(value => Math.pow(value - avg, 2));
  return Math.sqrt(mean(squareDiffs));
}

/**
 * Generate points for a normal distribution curve
 */
export function normalDistributionCurve(values, numPoints = 50) {
  if (!values || values.length < 2) return { x: [], y: [] };

  const avg = mean(values);
  const std = standardDeviation(values);

  if (std === 0) return { x: [avg], y: [1] };

  const min = Math.max(0, avg - 3 * std);
  const max = avg + 3 * std;
  const step = (max - min) / numPoints;

  const x = [];
  const y = [];

  for (let i = 0; i <= numPoints; i++) {
    const xVal = min + i * step;
    const yVal = (1 / (std * Math.sqrt(2 * Math.PI))) *
                 Math.exp(-0.5 * Math.pow((xVal - avg) / std, 2));
    x.push(xVal);
    y.push(yVal);
  }

  return { x, y };
}

/**
 * Check if contractions meet the 5-1-1 rule
 * 5 minutes apart, lasting 1 minute, for 1 hour
 */
export function check511Rule(contractions) {
  // Need at least a few contractions
  if (!contractions || contractions.length < 4) {
    return { meets: false, message: "Need more data" };
  }

  // Filter completed contractions and sort by time
  const completed = contractions
    .filter(c => c.end_time && c.duration_seconds)
    .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));

  if (completed.length < 4) {
    return { meets: false, message: "Need more completed contractions" };
  }

  // Get last hour of contractions
  const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
  const lastHour = completed.filter(c => new Date(c.start_time) >= oneHourAgo);

  if (lastHour.length < 4) {
    return { meets: false, message: "Need more contractions in last hour" };
  }

  // Check if contractions are ~1 minute (45-90 seconds)
  const durations = lastHour.map(c => c.duration_seconds);
  const avgDuration = mean(durations);
  const durationOK = avgDuration >= 45 && avgDuration <= 90;

  // Calculate intervals between contractions
  const intervals = [];
  for (let i = 1; i < lastHour.length; i++) {
    // Skip if this contraction has ignore_interval_before set
    if (lastHour[i].ignore_interval_before) {
      continue;
    }
    const prev = new Date(lastHour[i - 1].start_time);
    const curr = new Date(lastHour[i].start_time);
    intervals.push((curr - prev) / 1000 / 60); // minutes
  }

  const avgInterval = mean(intervals);
  const intervalOK = avgInterval <= 5;

  // Check consistency
  const std = standardDeviation(intervals);
  const consistent = std < 2; // Less than 2 minutes variation

  if (durationOK && intervalOK && consistent) {
    return {
      meets: true,
      message: `5-1-1 pattern detected! Avg: ${avgInterval.toFixed(1)} min apart, ${avgDuration.toFixed(0)}s long`
    };
  }

  const issues = [];
  if (!durationOK) issues.push(`Duration avg ${avgDuration.toFixed(0)}s (need ~60s)`);
  if (!intervalOK) issues.push(`Interval avg ${avgInterval.toFixed(1)} min (need ≤5 min)`);
  if (!consistent) issues.push("Pattern inconsistent");

  return { meets: false, message: issues.join(", ") || "Pattern not met" };
}

/**
 * Format duration in seconds to human readable
 */
export function formatDuration(seconds) {
  if (!seconds) return "-";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins > 0) {
    return `${mins}m ${secs}s`;
  }
  return `${secs}s`;
}

/**
 * Format time since a given date
 */
export function formatTimeSince(dateString) {
  if (!dateString) return "-";
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 1000 / 60);
  const diffHours = Math.floor(diffMins / 60);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours}h ${diffMins % 60}m ago`;
  return date.toLocaleDateString();
}

/**
 * Detect gaps in data (periods >30 min with no activity)
 */
export function detectGaps(contractions, gapThresholdMinutes = 30) {
  if (!contractions || contractions.length < 2) return [];

  const sorted = [...contractions]
    .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));

  const gaps = [];
  for (let i = 1; i < sorted.length; i++) {
    const prevEnd = sorted[i - 1].end_time || sorted[i - 1].start_time;
    const currStart = sorted[i].start_time;
    const gapMinutes = (new Date(currStart) - new Date(prevEnd)) / 1000 / 60;

    if (gapMinutes >= gapThresholdMinutes) {
      gaps.push({
        afterIndex: i - 1,
        startTime: prevEnd,
        endTime: currStart,
        durationMinutes: gapMinutes
      });
    }
  }

  return gaps;
}
