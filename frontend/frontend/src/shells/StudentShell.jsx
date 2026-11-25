import { Outlet, useNavigate } from 'react-router-dom';
import { api } from '../shared/api/index.js';
import ModeBanner from '../shared/components/ModeBanner.jsx';
import ScrollManager from '../shared/components/ScrollManager.jsx';
import SiteNav from '../shared/components/SiteNav.jsx';

const LINKS = [
  { to: '/student', label: 'My reports' },
  { to: '/student/reports/new', label: 'File a report' },
  { to: '/student/findings', label: 'Confirm findings' },
  { to: '/setup', label: 'Setup' },
];

export default function StudentShell() {
  const navigate = useNavigate();

  const handleSignOut = async () => {
    try {
      await api.signOut();
    } catch {
      // Ignore network/mock errors on sign-out and return home.
    }
    navigate('/');
  };

  return (
    <>
      <ScrollManager />
      <a className="skip" href="#main">Skip to content</a>
      <ModeBanner />
      <SiteNav
        label="Student"
        logoTo="/student"
        links={LINKS}
        actions={
          <button type="button" className="btn btn-outline btn-sm" onClick={handleSignOut}>
            Sign out
          </button>
        }
      />
      <main id="main"><Outlet /></main>
    </>
  );
}
