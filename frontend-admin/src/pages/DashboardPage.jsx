import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { useAuth } from '../auth';
import DailyLineChart from '../components/DailyLineChart';
import FunnelTable from '../components/FunnelTable';
import Header from '../components/Header';
import HealthCard from '../components/HealthCard';
import SourcesTable from '../components/SourcesTable';
import StatTile from '../components/StatTile';
import { colorForSource, SERIES_COLORS } from '../palette';

const RANGES = [
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
];

// Beyond 8 sources the palette is out of validated slots — fold the tail
// (by volume) into "Other" rather than inventing a 9th color.
const MAX_CHART_SOURCES = SERIES_COLORS.length;

function utcToday() {
  return new Date().toISOString().slice(0, 10);
}

function utcDaysAgo(days) {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

function formatUsd(cents) {
  return (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

function formatPercent(rate) {
  return rate == null ? '—' : `${(rate * 100).toFixed(0)}%`;
}

export default function DashboardPage() {
  const { logout } = useAuth();
  const [rangeDays, setRangeDays] = useState(30);
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getOverview({ startDate: utcDaysAgo(rangeDays - 1), endDate: utcToday() })
      .then((data) => {
        if (!cancelled) setOverview(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [rangeDays]);

  const visitSeries = useMemo(() => {
    if (!overview) return [];
    const totals = new Map(overview.visits.by_source.map((s) => [s.source, s.count]));
    const kept = [...totals.keys()].slice(0, MAX_CHART_SOURCES - 1);
    const keptSet = new Set(kept);
    const byDay = new Map(); // source -> {day: count}
    for (const row of overview.visits.by_day_by_source) {
      const source = keptSet.has(row.source) || totals.size <= MAX_CHART_SOURCES
        ? row.source
        : 'Other';
      if (!byDay.has(source)) byDay.set(source, {});
      const days = byDay.get(source);
      days[row.day] = (days[row.day] ?? 0) + row.count;
    }
    return [...byDay.entries()].map(([source, days]) => ({
      label: source,
      color: colorForSource(source),
      byDay: days,
    }));
  }, [overview]);

  const signupSeries = useMemo(() => {
    if (!overview) return [];
    return [
      {
        label: 'Signups',
        color: '#c026d3', // brand primary-600; single series, no legend
        byDay: Object.fromEntries(overview.signups.by_day.map((d) => [d.day, d.count])),
      },
    ];
  }, [overview]);

  if (error?.status === 403) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="card max-w-sm text-center">
          <p className="text-gray-800 font-medium">This account is not an administrator.</p>
          <button
            onClick={logout}
            className="mt-4 text-sm text-primary-700 hover:text-primary-800 font-semibold"
          >
            Sign out
          </button>
        </div>
      </div>
    );
  }
  if (error?.status === 401) {
    logout();
    return null;
  }

  return (
    <div className="max-w-6xl mx-auto p-4 sm:p-6 space-y-4">
      <Header>
        <div className="flex rounded-lg overflow-hidden border border-gray-200 bg-white">
          {RANGES.map((r) => (
            <button
              key={r.label}
              onClick={() => setRangeDays(r.days)}
              className={`px-3 py-1.5 text-sm font-medium ${
                rangeDays === r.days
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </Header>

      <HealthCard />

      {error && <div className="card text-red-600 text-sm">{error.message}</div>}
      {loading && !overview && <div className="card text-gray-400 text-sm">Loading…</div>}

      {overview && (
        <div className={loading ? 'opacity-60 space-y-4' : 'space-y-4'}>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatTile label="Visits" value={overview.visits.total} />
            <StatTile label="Signups" value={overview.signups.total} />
            <StatTile
              label="Activation"
              value={formatPercent(overview.activation.rate)}
              hint={`${overview.activation.activated} of ${overview.activation.signups} started a story`}
            />
            <StatTile
              label="Active (7d)"
              value={overview.active_users.wau}
              hint={`${overview.active_users.dau} today`}
            />
            <StatTile
              label="Viral loop"
              value={formatPercent(overview.conversion.rate)}
              hint="redeemers → owners, all-time"
            />
            <StatTile
              label="Revenue"
              value={formatUsd(overview.revenue.total_cents)}
              hint={`${overview.revenue.gift_count} gifts · ${formatUsd(overview.revenue.gift_cents)}`}
            />
          </div>

          <div className="grid lg:grid-cols-2 gap-4">
            <DailyLineChart
              title="Signups per day"
              startDate={overview.start_date}
              endDate={overview.end_date}
              series={signupSeries}
            />
            <DailyLineChart
              title="Visits per day by source"
              startDate={overview.start_date}
              endDate={overview.end_date}
              series={visitSeries}
            />
          </div>

          <div className="grid lg:grid-cols-2 gap-4">
            <SourcesTable
              visitSources={overview.visits.by_source}
              signupSources={overview.signups.by_source}
            />
            <FunnelTable invites={overview.invites} conversion={overview.conversion} />
          </div>
        </div>
      )}
    </div>
  );
}
