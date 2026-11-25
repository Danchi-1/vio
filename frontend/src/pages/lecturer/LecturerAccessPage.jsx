import { Link } from "react-router-dom";

export default function LecturerAccessPage() {
  return (
    <section className="secure-page">
      <div className="wrap secure-page__wrap">
        <div className="secure-eyebrow"><span className="secure-eyebrow__line" />Private link access</div>
        <div className="secure-card">
          <div className="secure-card__top">
            <span className="secure-card__symbol" aria-hidden="true">↗</span>
            <span className="secure-label">For lecturers</span>
          </div>
          <h1 className="secure-title">You’ve been invited to review a VIO finding.</h1>
          <p className="secure-copy">
            Lecturer access is provided through a private, time-limited link. Open the original
            link you received to view the finding connected to your invitation.
          </p>
          <div className="secure-callout">
            <span className="secure-callout__mark" aria-hidden="true">i</span>
            <p>
              This page does not verify access by itself. The secure link and VIO session must be
              validated by the service before any finding details are shown.
            </p>
          </div>
          <div className="secure-card__actions">
            <Link className="btn btn-primary" to="/">Return to VIO home <span aria-hidden="true">↗</span></Link>
            <Link className="secure-text-link" to="/guidelines">Read reporting guidelines</Link>
          </div>
        </div>
        <p className="secure-footnote">
          If your link has expired or does not open, contact the person or office that issued it.
          Do not forward a private access link.
        </p>
      </div>
    </section>
  );
}
