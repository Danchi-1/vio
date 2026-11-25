import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import Logo from './Logo.jsx';

// Nav from the onboarding page: logo left, small links, pill buttons right, hairline under, circular burger on mobile.
export default function SiteNav({ links = [], actions = null, logoTo = '/', label = 'Main' }) {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname, loc.hash]);
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);
  return (
    <header className="nav-wrap">
      <div className="wrap">
        <nav className={`nav${open ? ' open' : ''}`} aria-label={label}>
          <Logo to={logoTo} />
          {links.length > 0 && <ul className="nav__links">{links.map((l) => <li key={l.label}><Link to={l.to}>{l.label}</Link></li>)}</ul>}
          <div className="nav__actions">
            {actions}
            {links.length > 0 && (
              <button className="burger" type="button" aria-expanded={open} aria-controls="mobile-menu" aria-label={open ? 'Close menu' : 'Open menu'} onClick={() => setOpen((o) => !o)}><span /></button>
            )}
          </div>
          {links.length > 0 && <div className="nav__menu" id="mobile-menu"><ul>{links.map((l) => <li key={l.label}><Link to={l.to}>{l.label}</Link></li>)}</ul></div>}
        </nav>
      </div>
    </header>
  );
}
