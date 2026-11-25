import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API_MODE } from '../shared/api/index.js';
import { buildCharts, periodText } from '../shared/api/dashboardContract.js';
import { useDashboard } from './dashboard/useDashboard.js';
import Filters from './dashboard/Filters.jsx';
import BarChart from './dashboard/BarChart.jsx';
import { Skeleton, EmptyPanel, ErrorPanel } from './dashboard/Panels.jsx';

export default function DashboardPage() {
  const [params, setParams] = useSearchParams();
  const filters = { department: params.get('department') ?? '', month: params.get('month') ?? '' };
  const { status, rows, error, options, retry } = useDashboard(filters);

  const setFilters = (f) => {
    const next = new URLSearchParams(params); // keeps other params such as mockState
    f.department ? next.set('department', f.department) : next.delete('department');
    f.month ? next.set('month', f.month) : next.delete('month');
    setParams(next, { replace: true });
  };
  const clear = () => setFilters({ department: '', month: '' });
  const filtered = Boolean(filters.department || filters.month);
  const charts = useMemo(() => buildCharts(rows), [rows]);
  const period = periodText(rows, filters.month);
  const busy = status === 'loading' || status === 'refreshing';

  return (
    <div className="dash wrap" aria-busy={busy}>
      <header className="dash-hero">
        <span className="eyebrow">Public dashboard</span>
        <h1 className="h2">Published patterns, <span className="accent">never names.</span></h1>
        <p className="lead">This page shows published findings in groups large enough to show. It never shows report text, tracking codes or anyone&rsquo;s identity.</p>
        <span className="pill" style={{ '--c': 'var(--st-published)' }}>Published findings only</span>
        {API_MODE === 'mock' && <p className="placeholder-note">Sample data, not real findings. Groups were left out on purpose to mimic privacy suppression.</p>}
      </header>

      <Filters options={options} value={filters} onChange={setFilters} disabled={status === 'loading'} />

      <p className="sr-only" role="status" aria-live="polite">
        {status === 'ready' ? `Dashboard updated. ${charts.length} chart${charts.length === 1 ? '' : 's'} shown.` : status === 'empty' ? 'No published findings to show.' : status === 'error' ? 'The dashboard could not be loaded.' : 'Loading dashboard.'}
      </p>

      {status === 'loading' && <Skeleton />}
      {status === 'error' && <ErrorPanel error={error} filtered={filtered} onRetry={retry} onClear={clear} />}
      {status === 'empty' && <EmptyPanel filtered={filtered} onClear={clear} />}
      {(status === 'ready' || status === 'refreshing') && (
        <div className={status === 'refreshing' ? 'is-refreshing' : undefined}>
          {charts.map((c, i) => <BarChart key={c.id} index={i + 1} period={period} {...c} />)}
          <p className="small dash-foot">Small groups are hidden by VIO and are never estimated, so the bars may not add up to everything that was reported. A published finding is a separate thing from a single report.</p>
        </div>
      )}
    </div>
  );
}
