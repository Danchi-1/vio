import { useEffect, useRef, useState } from 'react';

// Labelled preview of the dashboard's unavailable state. "Check again" only shows a short skeleton.
export default function StatePreview() {
  const [loading, setLoading] = useState(false);
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const check = () => { setLoading(true); clearTimeout(timer.current); timer.current = setTimeout(() => setLoading(false), 900); };
  return (
    <div className={`state${loading ? ' loading' : ''}`}>
      <span className="tag-light">Preview of the unavailable state</span>
      <h3>Dashboard data is not available</h3>
      <p className="msg" role="status">No published aggregates are available in this preview. When the live dashboard cannot load, this message appears with a way to try again.</p>
      <div className="skel" aria-hidden="true"><i /><i /><i /></div>
      <button className="btn btn-outline btn-sm" type="button" onClick={check}>Check again</button>
    </div>
  );
}
