import { Outlet } from 'react-router-dom';
import Logo from '../shared/components/Logo.jsx';
import ModeBanner from '../shared/components/ModeBanner.jsx';
import ScrollManager from '../shared/components/ScrollManager.jsx';

// Shared by the lecturer and authority private-link pages.
// Logo, a "Private link" note, no public navigation, no links into student pages.
// The logo is deliberately NOT a link here.
export default function SecureShell() {
  return (
    <div className="secure-shell">
      <ScrollManager />
      <a className="skip" href="#main">Skip to content</a>
      <ModeBanner />
      <header className="secure-topbar">
        <div className="wrap secure-topbar__inner">
          <Logo to={null} />
          <div className="secure-topbar__meta">
            <span className="secure-topbar__lock" aria-hidden="true">●</span>
            <span>Private link</span>
          </div>
        </div>
      </header>
      <main id="main" className="secure-main"><Outlet /></main>
      <footer className="secure-footer">
        <div className="wrap">
          <span>VIO · Voice It Out</span>
          <span>Private academic response space</span>
        </div>
      </footer>
    </div>
  );
}
