import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { levelColor } from '../palette';

// The last day in one line: how many errors and warnings, whether the
// worker is alive, whether the database answers. The numbers link to the
// Logs page with that filter already on.
export default function HealthCard() {
  const [logs, setLogs] = useState(null);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    api.getLogs({ since, limit: 1 }).then((d) => !cancelled && setLogs(d)).catch(() => {});
    api.getHealth().then((d) => !cancelled && setHealth(d)).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!logs && !health) return null;
  const errors = (logs?.level_counts?.ERROR ?? 0) + (logs?.level_counts?.CRITICAL ?? 0);
  const warnings = logs?.level_counts?.WARNING ?? 0;
  const worker = health?.worker ?? logs?.worker;

  return (
    <div className="card py-3 px-5 flex items-center gap-x-5 gap-y-1 flex-wrap text-sm">
      <span className="text-gray-500">Last 24 hours</span>
      <Count n={errors} noun="error" level="ERROR" />
      <Count n={warnings} noun="warning" level="WARNING" />
      <span className="text-gray-300">·</span>
      <Status ok={worker?.ok} label="worker" detail={worker?.seen_at ? `seen ${ago(worker.seen_at)}` : 'never heard from'} />
      {health && (
        <Status ok={health.db === 'ok'} label="database" detail={health.revision ? `schema ${health.revision}` : 'unreachable'} />
      )}
      <Link to="/logs" className="ml-auto text-gray-500 hover:text-gray-900 font-medium">
        All logs →
      </Link>
    </div>
  );
}

function Count({ n, noun, level }) {
  const color = n > 0 ? levelColor(level) : undefined;
  return (
    <Link
      to={`/logs?levels=${level}${level === 'ERROR' ? ',CRITICAL' : ''}&range=24h`}
      className="hover:underline"
      style={{ color: color ?? '#52514e', fontWeight: n > 0 ? 600 : 400 }}
    >
      <span className="tabular">{n}</span> {noun}
      {n === 1 ? '' : 's'}
    </Link>
  );
}

function Status({ ok, label, detail }) {
  return (
    <span className={ok ? 'text-gray-700' : 'text-red-600 font-medium'}>
      <span
        className="inline-block w-2 h-2 rounded-full mr-1.5 align-middle"
        style={{ backgroundColor: ok ? '#008300' : '#e34948' }}
      />
      {label} {ok ? 'ok' : 'down'}
      <span className="text-gray-400 font-normal"> · {detail}</span>
    </span>
  );
}

function ago(iso) {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}
