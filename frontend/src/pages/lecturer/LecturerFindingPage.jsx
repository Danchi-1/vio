import { Link, useParams } from "react-router-dom";

export default function LecturerFindingPage() {
  const { findingId } = useParams();

  return (
    <section className="secure-page secure-page--detail">
      <div className="wrap secure-page__wrap">
        <div className="secure-eyebrow"><span className="secure-eyebrow__line" />Lecturer response space</div>
        <div className="secure-card">
          <div className="secure-card__top">
            <span className="secure-label">Finding review</span>
            <span className="secure-status"><span />Access not verified</span>
          </div>
          <h1 className="secure-title">Finding details are not available here yet.</h1>
          <p className="secure-copy">
            This page is ready for the restricted finding view. VIO must validate the private
            session and return the finding details before this screen can display them.
          </p>
          <div className="secure-reference">
            <span>Link reference</span>
            <strong>{findingId || "Not provided"}</strong>
          </div>
          <div className="secure-callout">
            <span className="secure-callout__mark" aria-hidden="true">i</span>
            <p>
              No report text, student identity, finding status or response deadline is shown
              unless it is returned by the verified backend.
            </p>
          </div>
          <div className="secure-card__actions">
            <Link className="btn btn-primary" to="/lecturer/access">Access information</Link>
            <Link className="btn btn-outline" to="/">VIO home</Link>
          </div>
        </div>
        <p className="secure-footnote">Keep this private link confidential. Do not share it with others.</p>
      </div>
    </section>
  );
}
