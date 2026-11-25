import { API_MODE } from './config.js';
import { liveService } from './live.js';
import { mockService } from './mock.js';

// Pages import { api } from here and never know which adapter is behind it.
export const api = API_MODE === 'mock' ? mockService : liveService;
export { API_MODE };
export { ApiError, safeMessage } from './errors.js';
