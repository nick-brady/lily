import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../auth';
import Header from '../components/Header';
import { levelColor } from '../palette';

// Shaped after Datadog's log explorer: facets down the left side with
// counts, a search box and a time range across the top, one line per record
// with a colour stripe for its level, and the whole record on click.

const RANGES = [
  { key: '1h', label: '1h', ms: 60 * 60 * 1000 },
  { key: '24h', label: '24h', ms: 24 * 60 * 60 * 1000 },
  { key: '7d', label: '7d', ms: 7 * 24 * 60 * 60 * 1000 },
  { key: '30d', label: '30d', ms: 30 * 24 * 60 * 60 * 1000 },
];
const LEVELS = ['INFO', 'WARNING', 'ERROR', 'CRITICAL'];
const SERVICES = ['web', 'worker'];
const PAGE = 200;
const LIVE_EVERY_MS = 60 * 1000;

function relative(iso, now = Date.now()) {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

function exact(iso) {
  return new Date(iso).toLocaleString();
}

function csv(value) {
  return value ? value.split(',').filter(Boolean) : [];
}

export default function LogsPage() {
  const { logout } = useAuth();
  const [params, setParams] = useSearchParams();

  // Filters live in the URL so the dashboard's numbers can link straight
  // to "errors, last 24 hours", and a reload keeps what you were looking at.
  const levels = csv(params.get('levels'));
  const services = csv(params.get('services'));
  const rangeKey = RANGES.some((r) => r.key === params.get('range')) ? params.get('range') : '24h';
  const q = params.get('q') || '';

  const setFilter = useCallback(
    (patch) => {
      const next = new URLSearchParams(params);
      for (const [key, value] of Object.entries(patch)) {
        if (value == null || value === '' || (Array.isArray(value) && value.length === 0)) {
          next.delete(key);
        } else {
          next.set(key, Array.isArray(value) ? value.join(',') : value);
        }
      }
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  const toggle = (key, list, value) =>
    setFilter({ [key]: list.includes(value) ? list.filter((v) => v !== value) : [...list, value] });

  const [draftQ, setDraftQ] = useState(q);
  useEffect(() => {
    const t = setTimeout(() => {
      if (draftQ !== q) setFilter({ q: draftQ });
    }, 300);
    return () => clearTimeout(t);
  }, [draftQ, q, setFilter]);

  const [data, setData] = useState(null);
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [olderExhausted, setOlderExhausted] = useState(false);
  const [openId, setOpenId] = useState(null);
  const [live, setLive] = useState(true);
  const [now, setNow] = useState(Date.now());

  // computed per load so "last hour" keeps sliding while Live is on
  const sinceNow = () => new Date(Date.now() - RANGES.find((r) => r.key === rangeKey).ms).toISOString();

  const load = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getLogs({ levels, services, since: sinceNow(), q, limit: PAGE })
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setItems(res.items);
        setOlderExhausted(res.items.length < PAGE);
        setNow(Date.now());
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [levels.join(','), services.join(','), rangeKey, q]);

  useEffect(() => load(), [load]);

  // Live: refresh every minute while the tab is visible.
  const loadRef = useRef(load);
  loadRef.current = load;
  useEffect(() => {
    if (!live) return undefined;
    const tick = () => {
      if (document.visibilityState === 'visible') loadRef.current();
    };
    const id = setInterval(tick, LIVE_EVERY_MS);
    return () => clearInterval(id);
  }, [live]);

  const loadOlder = () => {
    const oldest = items[items.length - 1];
    if (!oldest) return;
    setLoading(true);
    api
      .getLogs({ levels, services, since: sinceNow(), q, before: oldest.logged_at, limit: PAGE })
      .then((res) => {
        setItems((prev) => [...prev, ...res.items]);
        setOlderExhausted(res.items.length < PAGE);
      })
      .catch(setError)
      .finally(() => setLoading(false));
  };

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

  const levelCounts = data?.level_counts ?? {};
  const serviceCounts = data?.service_counts ?? {};
  const shownLevels = LEVELS.filter((l) => l !== 'CRITICAL' || (levelCounts.CRITICAL ?? 0) > 0);

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-4">
      <Header />

      <div className="flex items-center gap-3 flex-wrap">
        <input
          type="search"
          value={draftQ}
          onChange={(e) => setDraftQ(e.target.value)}
          placeholder="Search messages"
          className="flex-1 min-w-[12rem] rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
        <div className="flex rounded-lg overflow-hidden border border-gray-200 bg-white">
          {RANGES.map((r) => (
            <button
              key={r.key}
              onClick={() => setFilter({ range: r.key })}
              className={`px-3 py-1.5 text-sm font-medium ${
                rangeKey === r.key ? 'bg-primary-600 text-white' : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1.5 text-sm text-gray-600 select-none">
          <input
            type="checkbox"
            checked={live}
            onChange={(e) => setLive(e.target.checked)}
            className="accent-primary-600"
          />
          Live
        </label>
        <button
          onClick={() => load()}
          className="px-3 py-1.5 text-sm font-medium rounded-lg border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
        >
          Refresh
        </button>
      </div>

      {error && <div className="card text-red-600 text-sm">{error.message}</div>}

      <div className="grid grid-cols-1 md:grid-cols-[13rem_1fr] gap-4 items-start">
        <aside className="space-y-4">
          <Facet
            title="Status"
            options={shownLevels.map((l) => ({
              value: l,
              label: l.toLowerCase(),
              count: levelCounts[l] ?? 0,
              color: levelColor(l),
            }))}
            selected={levels}
            onToggle={(v) => toggle('levels', levels, v)}
          />
          <Facet
            title="Service"
            options={SERVICES.map((s) => ({ value: s, label: s, count: serviceCounts[s] ?? 0 }))}
            selected={services}
            onToggle={(v) => toggle('services', services, v)}
          />
          {data?.worker && (
            <div className="card p-4 text-sm">
              <div className="text-gray-500 mb-1">Worker</div>
              <div className={data.worker.ok ? 'text-gray-800' : 'text-red-600 font-medium'}>
                {data.worker.seen_at
                  ? `${data.worker.ok ? 'alive' : 'stale'} · seen ${relative(data.worker.seen_at, now)}`
                  : 'never heard from'}
              </div>
            </div>
          )}
        </aside>

        <div className={`card p-0 overflow-hidden ${loading && items.length ? 'opacity-60' : ''}`}>
          {loading && items.length === 0 ? (
            <p className="p-6 text-gray-400 text-sm">Loading…</p>
          ) : items.length === 0 ? (
            <p className="p-6 text-gray-400 text-sm">
              Nothing logged {q ? `matching “${q}” ` : ''}in this range.
            </p>
          ) : (
            <table className="w-full text-sm table-fixed">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-100 text-xs uppercase tracking-wide">
                  <th className="py-2 pl-4 pr-2 font-medium w-24">When</th>
                  <th className="py-2 px-2 font-medium w-20">Status</th>
                  <th className="py-2 px-2 font-medium w-16">Service</th>
                  <th className="py-2 px-2 font-medium w-40 hidden lg:table-cell">Logger</th>
                  <th className="py-2 px-2 font-medium">Message</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <LogRow
                    key={row.id}
                    row={row}
                    now={now}
                    open={openId === row.id}
                    onToggle={() => setOpenId(openId === row.id ? null : row.id)}
                  />
                ))}
              </tbody>
            </table>
          )}
          {items.length > 0 && !olderExhausted && (
            <div className="border-t border-gray-100 p-3 text-center">
              <button
                onClick={loadOlder}
                disabled={loading}
                className="text-sm font-medium text-gray-600 hover:text-gray-900 disabled:opacity-50"
              >
                Older
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Facet({ title, options, selected, onToggle }) {
  return (
    <div className="card p-4">
      <div className="text-xs uppercase tracking-wide text-gray-500 mb-2">{title}</div>
      <ul className="space-y-1">
        {options.map((opt) => {
          const on = selected.includes(opt.value);
          return (
            <li key={opt.value}>
              <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={on}
                  onChange={() => onToggle(opt.value)}
                  className="accent-primary-600"
                />
                {opt.color && (
                  <span
                    className="inline-block w-2 h-2 rounded-full"
                    style={{ backgroundColor: opt.color }}
                  />
                )}
                <span className={`flex-1 ${on ? 'text-gray-900 font-medium' : 'text-gray-700'}`}>
                  {opt.label}
                </span>
                <span className="tabular text-gray-400 text-xs">{opt.count}</span>
              </label>
            </li>
          );
        })}
      </ul>
      {selected.length > 0 && (
        <button
          onClick={() => selected.forEach(onToggle)}
          className="mt-2 text-xs text-gray-400 hover:text-gray-600"
        >
          Clear
        </button>
      )}
    </div>
  );
}

function LogRow({ row, now, open, onToggle }) {
  const color = levelColor(row.level);
  return (
    <>
      <tr
        onClick={onToggle}
        className={`border-b border-gray-50 cursor-pointer hover:bg-gray-50 ${open ? 'bg-gray-50' : ''}`}
        style={{ boxShadow: `inset 3px 0 0 ${color}` }}
      >
        <td className="py-1.5 pl-4 pr-2 text-gray-500 tabular whitespace-nowrap" title={exact(row.logged_at)}>
          {relative(row.logged_at, now)}
        </td>
        <td className="py-1.5 px-2">
          <span
            className="inline-block rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-white"
            style={{ backgroundColor: color }}
          >
            {row.level === 'WARNING' ? 'warn' : row.level.toLowerCase()}
          </span>
        </td>
        <td className="py-1.5 px-2 text-gray-600">{row.service}</td>
        <td className="py-1.5 px-2 text-gray-500 truncate hidden lg:table-cell" title={row.logger}>
          {row.logger}
        </td>
        <td className="py-1.5 px-2 text-gray-800 truncate font-mono text-[13px]" title={row.message}>
          {row.message}
        </td>
      </tr>
      {open && (
        <tr className="border-b border-gray-100 bg-gray-50">
          <td colSpan={5} className="px-4 py-3">
            <Detail row={row} />
          </td>
        </tr>
      )}
    </>
  );
}

function Detail({ row }) {
  const meta = [
    ['time', exact(row.logged_at)],
    ['logger', row.logger],
    ['request id', row.request_id],
    ['user id', row.user_id],
    ['fingerprint', row.fingerprint],
    ...Object.entries(row.extra ?? {}).map(([k, v]) => [k, typeof v === 'string' ? v : JSON.stringify(v)]),
  ].filter(([, v]) => v != null && v !== '');
  return (
    <div className="space-y-3 text-sm">
      <p className="font-mono text-[13px] text-gray-900 whitespace-pre-wrap break-words">{row.message}</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
        {meta.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-gray-500">{k}</dt>
            <dd className="text-gray-800 font-mono break-all">{v}</dd>
          </div>
        ))}
      </dl>
      {row.exception && (
        <pre className="overflow-x-auto rounded-lg bg-gray-900 text-gray-100 text-xs p-3 leading-relaxed">
          {row.exception}
        </pre>
      )}
    </div>
  );
}
