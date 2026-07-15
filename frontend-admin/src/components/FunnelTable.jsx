// The share funnel, stage by stage. Labels are deliberately precise:
// "redemptions" are authenticated link redemptions (repeat visits by the
// same person included), NOT raw clicks — raw clicks are the /invite/ page
// visits. "Became owners" is all-time (conversion lags the date range).
export default function FunnelTable({ invites, conversion }) {
  const rows = [
    ['Invite links created', invites.created, 'in range'],
    ['Invite link visits', invites.link_visits, 'incl. anonymous clicks'],
    ['Redemptions', invites.redemptions, 'authenticated, incl. repeats'],
    ['Distinct people redeemed', invites.distinct_redeemers, 'in range'],
    ['Redeemers who became owners', conversion.became_owners, 'all-time'],
  ];

  return (
    <div className="card">
      <h3 className="text-base font-semibold text-gray-800 mb-3">Share funnel</h3>
      <table className="w-full text-sm">
        <tbody>
          {rows.map(([label, value, note]) => (
            <tr key={label} className="border-b border-gray-50 last:border-0">
              <td className="py-2 text-gray-800">{label}</td>
              <td className="py-2 text-right tabular font-semibold text-gray-900">{value}</td>
              <td className="py-2 pl-3 text-right text-xs text-gray-400 w-40">{note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-gray-400 mt-3">
        Viral conversion:{' '}
        <span className="font-medium text-gray-600">
          {conversion.rate == null
            ? 'n/a'
            : `${(conversion.rate * 100).toFixed(1)}% of ${conversion.all_redeemers} all-time redeemers`}
        </span>{' '}
        later started their own story.
      </p>
    </div>
  );
}
