// The only place the API base URL and mode are read.
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
export const API_MODE = import.meta.env.VITE_API_MODE === 'live' ? 'live' : 'mock';
// Spec: student_session cookie. Turn on only once cookie auth works across the two domains.
export const USE_CREDENTIALS = import.meta.env.VITE_API_CREDENTIALS === 'true';
