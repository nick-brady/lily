import { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { mean, standardDeviation, normalDistributionCurve } from '../utils/statistics';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

export default function DistributionChart({ contractions }) {
  const chartData = useMemo(() => {
    const durations = contractions
      .filter(c => c.duration_seconds)
      .map(c => c.duration_seconds);

    if (durations.length < 3) return null;

    // Create histogram bins
    const min = Math.min(...durations);
    const max = Math.max(...durations);
    const range = max - min;
    const binCount = Math.min(10, Math.ceil(Math.sqrt(durations.length)));
    const binSize = Math.max(10, Math.ceil(range / binCount));

    const bins = {};
    const binLabels = [];

    for (let i = 0; i <= binCount; i++) {
      const binStart = min + i * binSize;
      bins[binStart] = 0;
      const mins = Math.floor(binStart / 60);
      const secs = binStart % 60;
      binLabels.push(mins > 0 ? `${mins}m${secs > 0 ? secs : ''}` : `${secs}s`);
    }

    durations.forEach(d => {
      const binIndex = Math.floor((d - min) / binSize);
      const binKey = min + binIndex * binSize;
      if (bins[binKey] !== undefined) {
        bins[binKey]++;
      }
    });

    const histogramData = Object.values(bins);

    // Calculate normal curve overlay
    const avg = mean(durations);
    const std = standardDeviation(durations);
    const normalCurve = binLabels.map((_, i) => {
      const x = min + i * binSize + binSize / 2;
      const y = (1 / (std * Math.sqrt(2 * Math.PI))) *
                Math.exp(-0.5 * Math.pow((x - avg) / std, 2)) *
                durations.length * binSize;
      return y;
    });

    return {
      labels: binLabels,
      datasets: [
        {
          type: 'bar',
          label: 'Frequency',
          data: histogramData,
          backgroundColor: 'rgba(217, 70, 239, 0.5)',
          borderColor: 'rgb(217, 70, 239)',
          borderWidth: 1,
        },
        {
          type: 'line',
          label: 'Normal Distribution',
          data: normalCurve,
          borderColor: 'rgb(239, 68, 68)',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
          fill: false,
        },
      ],
    };
  }, [contractions]);

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: {
          color: 'rgb(156, 163, 175)',
          usePointStyle: true,
        }
      },
      tooltip: {
        callbacks: {
          title: (context) => `Duration: ${context[0].label}`,
          label: (context) => {
            if (context.datasetIndex === 0) {
              return `Count: ${context.raw}`;
            }
            return '';
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
        },
        title: {
          display: true,
          text: 'Duration',
          color: 'rgb(156, 163, 175)',
        }
      },
      y: {
        beginAtZero: true,
        grid: {
          color: 'rgba(156, 163, 175, 0.1)',
        },
        ticks: {
          color: 'rgb(156, 163, 175)',
          stepSize: 1,
        },
        title: {
          display: true,
          text: 'Frequency',
          color: 'rgb(156, 163, 175)',
        }
      }
    }
  };

  if (!chartData) {
    return (
      <div className="card h-64 flex items-center justify-center">
        <p className="text-gray-400">
          Distribution chart will appear after 3+ contractions
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">
        Duration Distribution
      </h3>
      <div className="h-64">
        <Bar data={chartData} options={options} />
      </div>
    </div>
  );
}
