// In-memory only. Never localStorage, never the URL, never logged.
// Holds the Bearer session token for lecturer / authority sessions (spec: session_token).
let token = null;
export const setSessionToken = (t) => { token = t; };
export const getSessionToken = () => token;
export const clearSessionToken = () => { token = null; };
