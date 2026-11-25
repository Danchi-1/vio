import { Outlet } from 'react-router-dom';
import ModeBanner from '../shared/components/ModeBanner.jsx';
import ScrollManager from '../shared/components/ScrollManager.jsx';
import SiteNav from '../shared/components/SiteNav.jsx';

const LINKS = [
  { to: '/student', label: 'My reports' }, { to: '/student/reports/new', label: 'File a report' }, { to: '/student/findings', label: 'Findings' },
];

export default function StudentShell() {
  return (
    <>
      <ScrollManager />
      <a className="skip" href="#main">Skip to content</a>
      <ModeBanner />
      {/* The spec defines no sign-out endpoint, so Sign out stays disabled until one exists. */}
      <SiteNav label="Student" logoTo="/student" links={LINKS} actions={
        <button type="button" className="btn btn-outline btn-sm" aria-disabled="true" title="Sign-out is not connected yet">Sign out</button>
      } />
      <main id="main"><Outlet /></main>
    </>
  );
}
