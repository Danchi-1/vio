import { Link } from "react-router-dom";

export default function LecturerNoticesPage() {
  return (
    <section className="secure-page secure-page--notices">
      <div className="wrap secure-page__wrap">
        <div className="secure-eyebrow"><span className="secure-eyebrow__line" />Lecturer workspace</div>
        <div className="secure-page__heading">
          <div>
            <p className="secure-label">Advance class notices</p>
            <h1 className="secure-title">Keep students informed about class changes.</h1>
          </div>
          <p className="secure-copy">
            This space is intended for lecturer notices related to scheduled classes and academic
            updates. Notices will appear here when the VIO notice service is available.
          </p>
        </div>
        <div className="secure-empty">
          <div className="secure-empty__graphic" aria-hidden="true">
            <span className="secure-empty__paper"><i /><i /><i /></span>
            <span className="secure-empty__plus">+</span>
          </div>
          <p className="secure-label">Notice service unavailable</p>
          <h2>No notices to show yet.</h2>
          <p>
            The notice backend is not connected in this build. This screen will display notices
            returned by VIO; it does not create sample or placeholder notices.
          </p>
          <Link className="btn btn-outline" to="/lecturer/access">Lecturer access information</Link>
        </div>
      </div>
    </section>
  );
}
