import { Link } from 'react-router-dom';

export default function GuidelinesPage() {
  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Reporting guidelines</span>
        <h1 className="h2">Factual reports, <span className="accent">zero names.</span></h1>
        <p className="lead">
          VIO routes corroborated academic issues without exposing student identities or publishing unverified accusations.
        </p>
      </header>

      <div className="card">
        <h3>What belongs in a report</h3>
        <ul style={{ margin: 0, paddingLeft: 20, display: 'grid', gap: 8 }}>
          <li>State the course, date, and what actually occurred (at least 20 characters).</li>
          <li>Choose the category that matches your description (class not held, practical not held, outline incomplete, poor delivery, unfair assessment, unresolved complaint, other academic, or institutional).</li>
          <li>Keep descriptions factual—avoid personal insults, student names, matric numbers, or lecturer names.</li>
          <li>Automated safety and consistency models review submissions; abusive or prompt-injection text is rejected.</li>
        </ul>

        <h3>How findings clear</h3>
        <p>
          A single report stays in <strong>collecting</strong> status until enough independent enrolled students corroborate the same incident. Once the score threshold and 3-model gate pass, aggregate stats appear on the public dashboard.
        </p>

        <div className="actions">
          <Link className="btn btn-primary" to="/sign-in">Student sign in</Link>
          <Link className="btn btn-outline" to="/track">Track a report</Link>
          <Link className="btn btn-outline" to="/dashboard">View dashboard</Link>
        </div>
      </div>
    </div>
  );
}
