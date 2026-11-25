import { Outlet } from 'react-router-dom';
import ModeBanner from '../shared/components/ModeBanner.jsx';
import ScrollManager from '../shared/components/ScrollManager.jsx';
import SiteNav from '../shared/components/SiteNav.jsx';

// Logo, a "Private link" note, no public navigation, no links into student pages.
export default function SecureShell() {
  return (
    <>
      <ScrollManager />
      <ModeBanner />
      <SiteNav label="Private link" logoTo={null} actions={<span className="pill" style={{ '--c': 'var(--st-collecting)' }}>Private link</span>} />
      <main id="main"><Outlet /></main>
    </>
  );
}
