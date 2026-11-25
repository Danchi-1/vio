import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <section className="ph-page">
      <div className="wrap">
        <p className="label">404</p>
        <h1 className="h2">We could not find that page</h1>
        <p className="lead">The address may be wrong, or the page may have moved.</p>
        <div className="ph-actions">
          <Link className="btn btn-primary" to="/">Go to home</Link>
          <Link className="btn btn-outline" to="/dashboard">View dashboard</Link>
        </div>
      </div>
    </section>
  );
}
