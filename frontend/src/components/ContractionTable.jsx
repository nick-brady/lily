import { formatDuration } from '../utils/statistics';

export default function ContractionTable({ contractions, onDelete, isAdmin = false }) {
  const formatTime = (dateString) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatInterval = (index) => {
    if (index >= contractions.length - 1) return '-';
    const current = new Date(contractions[index].start_time);
    const next = new Date(contractions[index + 1].start_time);
    const diffMs = current - next;
    const diffMins = Math.floor(diffMs / 1000 / 60);

    if (diffMins < 60) return `${diffMins} min`;
    const hours = Math.floor(diffMins / 60);
    const mins = diffMins % 60;
    return `${hours}h ${mins}m`;
  };

  if (contractions.length === 0) {
    return (
      <div className="card text-center py-12">
        <p className="text-gray-500 dark:text-gray-400">
          No contractions logged yet.
        </p>
        <p className="text-gray-400 dark:text-gray-500 text-sm mt-2">
          Tap the button above to start tracking.
        </p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-700/50 text-left text-sm text-gray-600 dark:text-gray-300">
              <th className="px-4 py-3 font-medium">Time</th>
              <th className="px-4 py-3 font-medium">Duration</th>
              <th className="px-4 py-3 font-medium">Interval</th>
              {isAdmin && <th className="px-4 py-3 font-medium w-10"></th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {contractions.map((contraction, index) => (
              <tr
                key={contraction.id}
                className={`${
                  !contraction.end_time
                    ? 'bg-primary-50 dark:bg-primary-900/20'
                    : 'hover:bg-gray-50 dark:hover:bg-gray-700/30'
                } transition-colors`}
              >
                <td className="px-4 py-3">
                  <span className="font-medium text-gray-900 dark:text-gray-100">
                    {formatTime(contraction.start_time)}
                  </span>
                  {contraction.end_time && (
                    <span className="text-gray-400 dark:text-gray-500 text-sm">
                      {' → '}{formatTime(contraction.end_time)}
                    </span>
                  )}
                  {!contraction.end_time && (
                    <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary-100 text-primary-800 dark:bg-primary-900 dark:text-primary-200">
                      Active
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                  {contraction.duration_seconds ? (
                    <span className={
                      contraction.duration_seconds >= 45 && contraction.duration_seconds <= 90
                        ? 'text-green-600 dark:text-green-400 font-medium'
                        : ''
                    }>
                      {formatDuration(contraction.duration_seconds)}
                    </span>
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-700 dark:text-gray-300">
                  {formatInterval(index)}
                </td>
                {isAdmin && (
                  <td className="px-4 py-3">
                    <button
                      onClick={() => onDelete(contraction.id)}
                      className="text-gray-400 hover:text-red-500 transition-colors p-1"
                      title="Delete"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
