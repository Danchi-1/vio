import { Link, Outlet } from 'react-router-dom';
import ModeBanner from '../shared/components/ModeBanner.jsx';
import ScrollManager from '../shared/components/ScrollManager.jsx';
import SiteNav from '../shared/components/SiteNav.jsx';

const LINKS = [
  { to: '/#how-it-works', label: 'How it works' }, { to: '/#privacy', label: 'Privacy' }, { to: '/#statuses', label: 'Statuses' },
  { to: '/dashboard', label: 'Dashboard' }, { to: '/guidelines', label: 'Guidelines' },
];

export default function PublicShell() {
  return (
    <>
      <ScrollManager />
      <a className="skip" href="#main">Skip to content</a>
      <ModeBanner />
      <SiteNav links={LINKS} actions={<>
        <Link className="btn btn-outline btn-sm hide-sm" to="/dashboard">View dashboard</Link>
        <Link className="btn btn-primary btn-sm" to="/sign-in">Student sign in</Link>
      </>} />
      <main id="main"><Outlet /></main>
      <footer className="site-footer dark">
        <div className="wrap">
          <div className="foot">
            <div>
              <p><strong>VIO, Voice It Out</strong></p>
              <p className="muted">Academic accountability for university students.</p>
              <p className="muted" style={{ marginTop: 8 }}>Privacy policy and terms: approved text to be supplied by the team.</p>
            </div>
            <ul>
              <li><Link to="/#how-it-works">How it works</Link></li>
              <li><Link to="/dashboard">Dashboard</Link></li>
              <li><Link to="/guidelines">Guidelines</Link></li>
            </ul>
          </div>
        </div>
      </footer>
    </>
  );
}
