import { Link } from 'react-router-dom';
import { safeMessage } from '../../shared/api/index.js';

// Skeleton matches the real structure (heading, text, five bars) so nothing jumps when data arrives.
export function Skeleton() {
  return (
    <div aria-hidden="true">
      {[1, 2, 3].map((n) => (
        <section className="dash-sec" key={n}>
          <div className="dash-sec__head"><i className="sk sk--label" /><i className="sk sk--title" /><i className="sk sk--text" /></div>
          <div className="dbars">{[88, 64, 52, 40, 28].map((w, i) => <div className="bar bar--sk" key={i}><i className="sk sk--row" /><i className="sk sk--track" style={{ width: `${w}%` }} /></div>)}</div>
        </section>
      ))}
    </div>
  );
}

export function EmptyPanel({ filtered, onClear }) {
  return (
    <div className="dash-panel" role="status">
      <h2 className="dash-h3">{filtered ? 'Nothing to show for this selection' : 'No published findings to show yet'}</h2>
      <p>{filtered
        ? 'No published group matches these filters. Groups with too few students are hidden to protect privacy.'
        : 'Findings appear here only after they are published, and only in groups large enough to show. Nothing is estimated or filled in.'}</p>
      {filtered
        ? <button type="button" className="btn btn-primary" onClick={onClear}>Clear filters</button>
        : <Link className="btn btn-outline" to="/guidelines">How reporting works</Link>}
    </div>
  );
}

export function ErrorPanel({ error, filtered, onRetry, onClear }) {
  const retryable = ['network', 'unavailable', 'rate_limited', 'unknown'].includes(error.kind);
  return (
    <div className="dash-panel" role="alert">
      <h2 className="dash-h3">{filtered && error.kind === 'validation' ? 'Those filters could not be applied' : 'The dashboard is unavailable'}</h2>
      <p>{safeMessage(error)}</p>
      <div className="dash-panel__actions">
        {retryable && <button type="button" className="btn btn-primary" onClick={onRetry}>Retry</button>}
        {filtered && <button type="button" className="btn btn-outline" onClick={onClear}>Clear filters</button>}
      </div>
    </div>
  );
}
