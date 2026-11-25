import { API_BASE, USE_CREDENTIALS } from './config.js';
import { ApiError, kindFromStatus } from './errors.js';
import { getSessionToken } from './sessionStore.js';

// Spec envelope: { data } on success, { error: { code, message } } on failure.
// NOTE: there is deliberately NO retry here. Writes are never retried automatically.
export async function request(method, path, { body, query, bearer = false, signal } = {}) {
  const url = new URL(API_BASE + path, window.location.origin);
  if (query) for (const [k, v] of Object.entries(query)) if (v != null && v !== '') url.searchParams.set(k, v);

  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (bearer && getSessionToken()) headers.Authorization = `Bearer ${getSessionToken()}`;

  let res;
  try {
    res = await fetch(url, {
      method, headers, signal,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: USE_CREDENTIALS ? 'include' : 'same-origin',
      referrerPolicy: 'no-referrer',
    });
  } catch (e) {
    if (e?.name === 'AbortError') throw e;
    throw new ApiError('network');
  }

  let json = null;
  try { json = await res.json(); } catch { /* empty or non-JSON body */ }

  if (!res.ok) {
    throw new ApiError(kindFromStatus(res.status), {
      status: res.status, code: json?.error?.code ?? null, backendMessage: json?.error?.message ?? null,
    });
  }
  return json?.data ?? null;
}
