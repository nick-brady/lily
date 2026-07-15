import { colorForSource } from '../palette';

// One row per acquisition source: visits + signups side by side. This table
// is also the accessible fallback for the chart colors — every series value
// is readable here as plain text.
export default function SourcesTable({ visitSources, signupSources }) {
  const signupsBySource = Object.fromEntries(
    signupSources.map((s) => [s.source, s.count]),
  );
  const sources = [...visitSources];
  for (const s of signupSources) {
    if (!sources.some((v) => v.source === s.source)) {
      sources.push({ source: s.source, count: 0 });
    }
  }

  return (
    <div className="card">
      <h3 className="text-base font-semibold text-gray-800 mb-3">Sources</h3>
      {sources.length === 0 ? (
        <p className="text-gray-400 text-sm">No visits recorded in this range yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-100">
              <th className="py-2 font-medium">Source</th>
              <th className="py-2 font-medium text-right">Visits</th>
              <th className="py-2 font-medium text-right">Signups</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((row) => (
              <tr key={row.source} className="border-b border-gray-50 last:border-0">
                <td className="py-2 text-gray-800">
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-full mr-2 align-middle"
                    style={{ backgroundColor: colorForSource(row.source) }}
                  />
                  {row.source}
                </td>
                <td className="py-2 text-right tabular text-gray-800">{row.count}</td>
                <td className="py-2 text-right tabular text-gray-800">
                  {signupsBySource[row.source] ?? 0}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
