import { ApiError } from './errors.js';

// ASSUMED RESPONSE SHAPE (UNRESOLVED). VIO_HACKATHON_SPECIFICATION.md gives GET /dashboard/overview
// with ?department_id=&month= but no response body. Its public_dashboard view groups published findings
// by department, month and category, so this adapter expects:
//   { rows: [ { department_id, department_name, month: "YYYY-MM", category, count } ] }
// Groups the backend suppresses are simply absent. The frontend never infers or estimates them.
// When the backend confirms the real shape, change ONLY this file.

const CATEGORY_LABELS = {
  class_not_held: 'Class not held',
  practical_not_held: 'Practical not held',
  outline_incomplete: 'Course outline incomplete',
  poor_delivery: 'Teaching delivery',
  unfair_assessment: 'Assessment concern',
  unresolved_complaint: 'Unresolved complaint',
  other_academic: 'Other academic',
  institutional: 'Institutional',
};
const humanise = (s) => String(s).replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
export const categoryLabel = (c) => CATEGORY_LABELS[c] ?? humanise(c);

export function monthLabel(m) {
  const match = /^(\d{4})-(\d{2})$/.exec(String(m));
  if (!match) return String(m);
  const d = new Date(Date.UTC(+match[1], +match[2] - 1, 1));
  return new Intl.DateTimeFormat('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(d);
}

export function normalizeDashboard(raw) {
  if (!raw || !Array.isArray(raw.rows)) throw new ApiError('unknown'); // shape mismatch: honest unavailable state
  const rows = raw.rows
    .filter((r) => r && Number.isFinite(r.count) && r.count >= 0)
    .map((r) => ({
      departmentId: r.department_id ?? null,
      departmentName: r.department_name ?? null,
      month: r.month ?? null,
      category: r.category ?? null,
      count: r.count,
    }));
  return { rows };
}

export function optionsFrom(rows) {
  const departments = new Map();
  const months = new Set();
  for (const r of rows) {
    if (r.departmentId != null && r.departmentName) departments.set(r.departmentId, r.departmentName);
    if (r.month) months.add(r.month);
  }
  return { departments, months };
}

const DEFS = [
  { id: 'time', kicker: 'Over time', title: 'Published findings by month',
    explain: 'Each bar adds up the published findings that fall in that month, across the groups shown.',
    key: (r) => r.month, label: monthLabel, byKey: true },
  { id: 'category', kicker: 'By category', title: 'Published findings by category',
    explain: 'Each bar adds up the published findings of one category, across the groups shown.',
    key: (r) => r.category, label: categoryLabel },
  { id: 'department', kicker: 'By department', title: 'Published findings by department',
    explain: 'Each bar adds up the published findings for one department, across the groups shown.',
    key: (r) => r.departmentName, label: (x) => x },
];

// Only dimensions the returned rows actually carry become charts. No grand total is ever computed.
export function buildCharts(rows) {
  return DEFS.map((d) => {
    const m = new Map();
    for (const r of rows) {
      const k = d.key(r);
      if (k == null || k === '') continue;
      m.set(k, (m.get(k) ?? 0) + r.count);
    }
    const items = [...m].map(([key, count]) => ({ key, label: d.label(key), count }));
    items.sort(d.byKey ? (a, b) => String(a.key).localeCompare(String(b.key)) : (a, b) => b.count - a.count || a.label.localeCompare(b.label));
    return { id: d.id, kicker: d.kicker, title: d.title, explain: d.explain, items };
  }).filter((c) => c.items.length);
}

export function periodText(rows, selectedMonth) {
  const ms = [...new Set(rows.map((r) => r.month).filter(Boolean))].sort();
  if (selectedMonth) return monthLabel(selectedMonth);
  if (!ms.length) return 'Period not stated by the data';
  return ms.length === 1 ? monthLabel(ms[0]) : `${monthLabel(ms[0])} to ${monthLabel(ms[ms.length - 1])}`;
}
