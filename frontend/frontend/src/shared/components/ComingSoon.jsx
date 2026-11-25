import { Link } from 'react-router-dom';

export default function ComingSoon({ title, note }) {
  return (
    <section className="ph-page">
      <div className="wrap">
        <p className="label">Not built yet</p>
        <h1 className="h2">{title}</h1>
        <p className="lead">{note ?? 'This page is on the build list and has not been built yet.'}</p>
        <div className="ph-actions"><Link className="btn btn-primary" to="/">Back to home</Link></div>
      </div>
    </section>
  );
}
