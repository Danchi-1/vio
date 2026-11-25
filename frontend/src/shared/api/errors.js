// Central, safe error handling. Only generic text is shown by default.
// Backend { error: { code, message } } is kept on the object but never logged.
export class ApiError extends Error {
  constructor(kind, { status = 0, code = null, backendMessage = null } = {}) {
    super(kind);
    this.kind = kind; // network | rate_limited | unavailable | unauthorized | forbidden | not_found | validation | unsupported | unknown
    this.status = status;
    this.code = code;
    this.backendMessage = backendMessage;
  }
}

export function kindFromStatus(status) {
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not_found';
  if (status === 400 || status === 422) return 'validation';
  if (status === 429) return 'rate_limited';
  if (status === 502 || status === 503 || status === 504) return 'unavailable';
  return 'unknown';
}

const SAFE_TEXT = {
  network: 'You appear to be offline. Check your connection and try again.',
  rate_limited: 'Too many attempts. Please wait a moment and try again.',
  unavailable: 'VIO is temporarily unavailable. Please try again shortly.',
  unauthorized: 'Your session has ended. Please sign in again.',
  forbidden: 'That action is not available.',
  not_found: 'We could not find that.',
  validation: 'Please check what you entered and try again.',
  unsupported: 'This feature is not connected yet.',
  unknown: 'Something went wrong. Please try again.',
};

export const safeMessage = (err) => SAFE_TEXT[err?.kind] ?? SAFE_TEXT.unknown;
