import { ApiError } from './errors.js';
import { liveService } from './live.js';

// MOCK ADAPTER. Same interface as liveService. Only used when VITE_API_MODE=mock.
// Every page shows a banner while this is active. Values are labelled samples, not real data.
const wait = (ms = 400, signal) => new Promise((res, rej) => {
  const t = setTimeout(res, ms);
  signal?.addEventListener('abort', () => { clearTimeout(t); rej(new DOMException('Aborted', 'AbortError')); });
});
const unsupported = () => Promise.reject(new ApiError('unsupported'));

// SAMPLE dashboard rows. Some groups are left out on purpose to mimic backend suppression.
const SAMPLE_DEPTS = [['sample-csc', 'Computer Science'], ['sample-mts', 'Mathematics'], ['sample-chm', 'Chemistry'], ['sample-phs', 'Physics']];
const SAMPLE_CATS = ['class_not_held', 'outline_incomplete', 'unfair_assessment', 'poor_delivery'];
const SAMPLE_MONTHS = ['2026-08', '2026-09', '2026-10'];
const SAMPLE_ROWS = [];
SAMPLE_DEPTS.forEach(([id, name], di) => SAMPLE_MONTHS.forEach((month, mi) => SAMPLE_CATS.forEach((category, ci) => {
  const count = ((di * 7 + mi * 5 + ci * 3) % 13) + 1;
  if (count >= 4) SAMPLE_ROWS.push({ department_id: id, department_name: name, month, category, count });
})));

// Test states without a backend: add ?mockState=empty or ?mockState=down to the dashboard URL.
export const mockService = {
  ...Object.fromEntries(Object.keys(liveService).map((k) => [k, unsupported])), // anything not mocked stays unsupported
  requestOtp: async () => { await wait(); return { sent: true }; },
  verifyOtp: async (_email, code) => {
    await wait();
    if (code !== '000000') throw new ApiError('validation');
    return { verified: true };
  },
  createReport: async () => { await wait(); return { tracking_code: 'SAMPLE-0001' }; },
  getDashboard: async (q = {}, signal) => {
    await wait(700, signal);
    const state = new URLSearchParams(window.location.search).get('mockState');
    if (state === 'down') throw new ApiError('unavailable');
    if (state === 'empty') return { rows: [] };
    return { rows: SAMPLE_ROWS.filter((r) => (!q.department_id || r.department_id === q.department_id) && (!q.month || r.month === q.month)) };
  },
};
