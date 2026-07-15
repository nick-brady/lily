import { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { AXIS_TICK_COLOR, GRID_COLOR, LEGEND_INK } from '../palette';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

// Every UTC day in [startDate, endDate], as 'YYYY-MM-DD'. Days with no data
// must render as explicit zeros — a gap would read as "no chart", not "0".
export function buildDayRange(startDate, endDate) {
  const days = [];
  const cursor = new Date(`${startDate}T00:00:00Z`);
  const end = new Date(`${endDate}T00:00:00Z`);
  while (cursor <= end) {
    days.push(cursor.toISOString().slice(0, 10));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return days;
}

/**
 * series: [{ label, color, byDay: {'YYYY-MM-DD': count} }]
 * A legend appears only for >= 2 series; a single series is named by the title.
 */
export default function DailyLineChart({ title, startDate, endDate, series }) {
  const days = useMemo(() => buildDayRange(startDate, endDate), [startDate, endDate]);

  const data = useMemo(
    () => ({
      labels: days.map((d) => d.slice(5)), // MM-DD; the card title carries the year/UTC note
      datasets: series.map((s) => ({
        label: s.label,
        data: days.map((d) => s.byDay[d] ?? 0),
        borderColor: s.color,
        backgroundColor: series.length === 1 ? `${s.color}1a` : s.color,
        fill: series.length === 1,
        borderWidth: 2,
        tension: 0.2,
        pointRadius: 2,
        pointHoverRadius: 6,
      })),
    }),
    [days, series],
  );

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        display: series.length > 1,
        labels: { color: LEGEND_INK, boxWidth: 12, boxHeight: 12 },
      },
      tooltip: { mode: 'index', intersect: false },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: AXIS_TICK_COLOR, maxTicksLimit: 12, maxRotation: 0 },
      },
      y: {
        beginAtZero: true,
        grid: { color: GRID_COLOR },
        ticks: { color: AXIS_TICK_COLOR, precision: 0 },
      },
    },
  };

  const isEmpty = series.every((s) => Object.keys(s.byDay).length === 0);

  return (
    <div className="card">
      <h3 className="text-base font-semibold text-gray-800 mb-3">
        {title} <span className="font-normal text-gray-400 text-sm">(UTC days)</span>
      </h3>
      <div className="h-64">
        {isEmpty ? (
          <div className="h-full flex items-center justify-center text-gray-400 text-sm">
            No data in this range yet
          </div>
        ) : (
          <Line data={data} options={options} />
        )}
      </div>
    </div>
  );
}
