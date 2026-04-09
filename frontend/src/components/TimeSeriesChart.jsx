import { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { detectGaps } from '../utils/statistics';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export default function TimeSeriesChart({ contractions, type = 'duration' }) {
  const chartData = useMemo(() => {
    // Filter completed contractions and sort by time
    const completed = contractions
      .filter(c => c.end_time && c.duration_seconds)
      .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));

    if (completed.length === 0) return null;

    const gaps = detectGaps(completed);
    const gapIndices = new Set(gaps.map(g => g.afterIndex));

    const labels = [];
    const data = [];

    if (type === 'duration') {
      completed.forEach((c, i) => {
        labels.push(new Date(c.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        data.push(c.duration_seconds);
        // Add null after gap to break the line
        if (gapIndices.has(i)) {
          labels.push('');
          data.push(null);
        }
      });
    } else {
      // Interval chart
      for (let i = 1; i < completed.length; i++) {
        const prev = new Date(completed[i - 1].start_time);
        const curr = new Date(completed[i].start_time);
        const interval = (curr - prev) / 1000 / 60; // minutes

        labels.push(curr.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        data.push(interval);

        if (gapIndices.has(i)) {
          labels.push('');
          data.push(null);
        }
      }
    }

    return {
      labels,
      datasets: [{
        data,
        borderColor: type === 'duration' ? 'rgb(217, 70, 239)' : 'rgb(59, 130, 246)',
        backgroundColor: type === 'duration' ? 'rgba(217, 70, 239, 0.1)' : 'rgba(59, 130, 246, 0.1)',
        tension: 0.3,
        fill: true,
        spanGaps: false,
        pointRadius: 4,
        pointHoverRadius: 6,
      }],
    };
  }, [contractions, type]);

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (context) => {
            if (type === 'duration') {
              const secs = context.raw;
              const mins = Math.floor(secs / 60);
              const s = secs % 60;
              return mins > 0 ? `${mins}m ${s}s` : `${s}s`;
            }
            return `${context.raw.toFixed(1)} min`;
          }
        }
      }
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(156, 163, 175, 0.1)',
        },
        ticks: {
          color: 'rgb(156, 163, 175)',
          maxRotation: 45,
          minRotation: 45,
        }
      },
      y: {
        beginAtZero: true,
        grid: {
          color: 'rgba(156, 163, 175, 0.1)',
        },
        ticks: {
          color: 'rgb(156, 163, 175)',
          callback: (value) => {
            if (type === 'duration') {
              const mins = Math.floor(value / 60);
              const secs = value % 60;
              return mins > 0 ? `${mins}m` : `${secs}s`;
            }
            return `${value} min`;
          }
        },
        title: {
          display: true,
          text: type === 'duration' ? 'Duration' : 'Interval',
          color: 'rgb(156, 163, 175)',
        }
      }
    }
  };

  if (!chartData) {
    return (
      <div className="card h-64 flex items-center justify-center">
        <p className="text-gray-400">
          {type === 'duration' ? 'Duration chart' : 'Interval chart'} will appear after logging contractions
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">
        {type === 'duration' ? 'Contraction Duration' : 'Time Between Contractions'}
      </h3>
      <div className="h-64">
        <Line data={chartData} options={options} />
      </div>
    </div>
  );
}
