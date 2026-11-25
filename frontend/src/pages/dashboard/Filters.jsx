import { monthLabel } from '../../shared/api/dashboardContract.js';

// Only filters the backend supports (department_id, month), and only when it supplied options for them.
export default function Filters({ options, value, onChange, disabled }) {
  const hasDept = options.departments.size > 0;
  const hasMonth = options.months.size > 0;
  if (!hasDept && !hasMonth) return null;
  const months = [...options.months].sort();
  const active = value.department || value.month;
  return (
    <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Dashboard filters">
      {hasDept && (
        <div className="field">
          <label htmlFor="f-dept">Department</label>
          <select id="f-dept" value={value.department} disabled={disabled} onChange={(e) => onChange({ ...value, department: e.target.value })}>
            <option value="">All departments</option>
            {[...options.departments].sort((a, b) => a[1].localeCompare(b[1])).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
        </div>
      )}
      {hasMonth && (
        <div className="field">
          <label htmlFor="f-month">Month</label>
          <select id="f-month" value={value.month} disabled={disabled} onChange={(e) => onChange({ ...value, month: e.target.value })}>
            <option value="">All months</option>
            {months.map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
          </select>
        </div>
      )}
      {active && <button type="button" className="btn btn-outline btn-sm" onClick={() => onChange({ department: '', month: '' })}>Clear filters</button>}
    </form>
  );
}
