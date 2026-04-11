import { useState } from 'react';

const PREDICTIONS = [
  { name: 'Alexis (Momma)', weight: 7.75, length: 20.5 },  // 7 lbs 12 oz
  { name: 'Nick (Daddy)', weight: 7.5, length: 20 },       // 7 lbs 8 oz
  { name: 'Nathan', weight: 7.25, length: 19.5 },          // 7 lbs 4 oz
  { name: 'Jena', weight: 8.4375, length: null },          // 8 lbs 7 oz
  { name: 'Krista', weight: 7.375, length: 20 },           // 7 lbs 6 oz
  { name: 'Kim (Nina)', weight: 8.125, length: 21 },       // 8 lbs 2 oz
  { name: 'Joan (Nonna)', weight: 7.3125, length: 20.5 },  // 7 lbs 5 oz
  { name: 'Leslie (Lala)', weight: 7.375, length: null },  // 7 lbs 6 oz
  { name: 'Steven (Papa)', weight: 9.6, length: 21.3 },    // 9 lbs 10 oz
  { name: 'Cynthia', weight: 8, length: 20 },              // 8 lbs
];

function formatWeight(lbs) {
  if (!lbs) return '-';
  const pounds = Math.floor(lbs);
  const oz = Math.round((lbs - pounds) * 16);
  return oz > 0 ? `${pounds} lbs ${oz} oz` : `${pounds} lbs`;
}

function formatLength(inches) {
  return inches ? `${inches}"` : '-';
}

function calculateScore(prediction, actual) {
  if (!actual.weight || !actual.length) return null;

  let score = 0;
  if (prediction.weight) {
    score += Math.abs(prediction.weight - actual.weight);
  }
  if (prediction.length) {
    // Weight oz difference roughly equals length in importance
    score += Math.abs(prediction.length - actual.length) * 0.5;
  }
  return score;
}

export default function Predictions() {
  // Set actual measurements once baby is born!
  const [actual, setActual] = useState({ weight: null, length: null });

  const predictions = PREDICTIONS.map(p => ({
    ...p,
    score: calculateScore(p, actual)
  })).sort((a, b) => {
    if (a.score === null && b.score === null) return 0;
    if (a.score === null) return 1;
    if (b.score === null) return -1;
    return a.score - b.score;
  });

  const hasWinner = actual.weight && actual.length;

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">
        Family Predictions
      </h3>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <th className="text-left py-2 px-2 font-medium text-gray-500 dark:text-gray-400">
                {hasWinner && '#'}
              </th>
              <th className="text-left py-2 px-2 font-medium text-gray-500 dark:text-gray-400">Name</th>
              <th className="text-right py-2 px-2 font-medium text-gray-500 dark:text-gray-400">Weight</th>
              <th className="text-right py-2 px-2 font-medium text-gray-500 dark:text-gray-400">Length</th>
            </tr>
          </thead>
          <tbody>
            {predictions.map((p, i) => (
              <tr
                key={p.name}
                className={`border-b border-gray-100 dark:border-gray-700/50 ${
                  hasWinner && i === 0 ? 'bg-amber-50 dark:bg-amber-900/20' : ''
                }`}
              >
                <td className="py-2 px-2">
                  {hasWinner && i === 0 && <span className="text-xl">🏆</span>}
                  {hasWinner && i === 1 && <span className="text-lg">🥈</span>}
                  {hasWinner && i === 2 && <span className="text-lg">🥉</span>}
                </td>
                <td className="py-2 px-2 font-medium text-gray-800 dark:text-gray-200">
                  {p.name}
                </td>
                <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-400">
                  {formatWeight(p.weight)}
                </td>
                <td className="py-2 px-2 text-right text-gray-600 dark:text-gray-400">
                  {formatLength(p.length)}
                </td>
              </tr>
            ))}
          </tbody>
          {hasWinner && (
            <tfoot>
              <tr className="bg-primary-50 dark:bg-primary-900/20 font-semibold">
                <td className="py-2 px-2">
                  <span className="text-xl">👶</span>
                </td>
                <td className="py-2 px-2 text-primary-700 dark:text-primary-300">Lily</td>
                <td className="py-2 px-2 text-right text-primary-700 dark:text-primary-300">
                  {formatWeight(actual.weight)}
                </td>
                <td className="py-2 px-2 text-right text-primary-700 dark:text-primary-300">
                  {formatLength(actual.length)}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {!hasWinner && (
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-3 text-center">
          Winner revealed once Lily arrives!
        </p>
      )}
    </div>
  );
}
