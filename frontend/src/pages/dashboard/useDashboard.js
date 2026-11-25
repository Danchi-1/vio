import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../../shared/api/index.js';
import { normalizeDashboard, optionsFrom } from '../../shared/api/dashboardContract.js';

// status: loading (first load) | refreshing (filter change) | ready | empty | error
export function useDashboard(filters) {
  const [state, setState] = useState({ status: 'loading', rows: [], error: null });
  const [options, setOptions] = useState({ departments: new Map(), months: new Set() });
  const [tick, setTick] = useState(0);
  const loadedOnce = useRef(false);

  useEffect(() => {
    const ac = new AbortController();
    setState((s) => ({ ...s, status: loadedOnce.current ? 'refreshing' : 'loading', error: null }));
    api.getDashboard({ department_id: filters.department || undefined, month: filters.month || undefined }, ac.signal)
      .then((raw) => {
        const { rows } = normalizeDashboard(raw);
        loadedOnce.current = true;
        const seen = optionsFrom(rows);
        // Keep every option seen so far, so choosing one filter does not erase the others.
        setOptions((o) => ({
          departments: new Map([...o.departments, ...seen.departments]),
          months: new Set([...o.months, ...seen.months]),
        }));
        setState({ status: rows.length ? 'ready' : 'empty', rows, error: null });
      })
      .catch((e) => {
        if (e?.name === 'AbortError') return;
        setState({ status: 'error', rows: [], error: e instanceof ApiError ? e : new ApiError('unknown') });
      });
    return () => ac.abort();
  }, [filters.department, filters.month, tick]);

  const retry = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, options, retry };
}
