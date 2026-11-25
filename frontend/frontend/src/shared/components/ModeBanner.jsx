import { API_MODE } from '../api/index.js';

export default function ModeBanner() {
  if (API_MODE !== 'mock') return null;
  return <div className="mode-banner" role="status">MOCK MODE: sample data only. Nothing here is real or saved.</div>;
}
