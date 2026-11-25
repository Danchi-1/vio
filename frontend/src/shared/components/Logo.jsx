import { Link } from 'react-router-dom';

const Mark = () => (
  <svg viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="9" fill="#0B1F3A" />
    <path d="M8 9.5h16a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H15l-4.5 3.5V21.5H8a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2z" fill="#fff" />
    <path d="M11.5 15.5l3 3 6-6" fill="none" stroke="#26B7FF" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

// to={null} renders a plain, non-clickable logo (used on secure-link pages).
export default function Logo({ to = '/' }) {
  return to
    ? <Link className="logo" to={to} aria-label="VIO home"><Mark />VIO</Link>
    : <span className="logo"><Mark />VIO</span>;
}
