import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, displayError } from '../shared/api/index.js';
import { categoryLabel } from '../shared/api/dashboardContract.js';
import { setSessionToken } from '../shared/api/sessionStore.js';

export function AccessExpiredPage() {
  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Access unavailable</span>
        <h1 className="h2">This link cannot be <span className="accent">used.</span></h1>
        <p className="lead">
          Authority capability links are single-use and expire after their response deadline.
        </p>
      </header>
      <div className="card">
        <p>If this incident has escalated, check your latest institutional notification email or return to the public dashboard.</p>
        <div className="actions">
          <Link className="btn btn-outline btn-sm" to="/dashboard">View public dashboard</Link>
        </div>
      </div>
    </div>
  );
}

export function AuthorityAccessPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [token, setToken] = useState(params.get('token') || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const t = params.get('token');
    if (!t) return;
    let active = true;
    async function redeem() {
      setBusy(true);
      try {
        const res = await api.redeemAuthorityLink(t);
        if (!active) return;
        if (res?.session_token) setSessionToken(res.session_token);
        navigate(`/authority/deliveries/${res.delivery_id}`, { state: { delivery: res }, replace: true });
      } catch (err) {
        if (!active) return;
        if (err?.status === 409 || err?.status === 410) {
          navigate('/access-expired', { replace: true });
          return;
        }
        setError(displayError(err));
      } finally {
        if (active) setBusy(false);
      }
    }
    redeem();
    return () => { active = false; };
  }, [params, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const res = await api.redeemAuthorityLink(token.trim());
      if (res?.session_token) setSessionToken(res.session_token);
      navigate(`/authority/deliveries/${res.delivery_id}`, { state: { delivery: res } });
    } catch (err) {
      if (err?.status === 409 || err?.status === 410) {
        navigate('/access-expired');
        return;
      }
      setError(displayError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Authority access</span>
        <h1 className="h2">Redeem delivery <span className="accent">link.</span></h1>
      </header>
      <div className="card">
        {error && <div className="alert alert-err" role="alert">{error}</div>}
        <form className="form-grid" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="auth-token">One-time access token</label>
            <input
              id="auth-token"
              type="text"
              required
              minLength={16}
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Paste the token from your notification link"
            />
          </div>
          <div className="actions">
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? 'Opening delivery...' : 'Open delivery'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function AuthorityDeliveryPage() {
  const { deliveryId } = useParams();
  const location = useLocation();
  const [delivery, setDelivery] = useState(location.state?.delivery || null);
  const [outcome, setOutcome] = useState('action_taken');
  const [respBody, setRespBody] = useState('');
  const [appealBody, setAppealBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const res = await api.getDelivery(deliveryId);
        if (active) setDelivery(res);
      } catch (err) {
        if (active && !delivery) setError(displayError(err));
      }
    }
    load();
    return () => { active = false; };
  }, [deliveryId]);

  const handleAck = async () => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api.acknowledgeDelivery(deliveryId);
      setDelivery((d) => d ? { ...d, status: 'acknowledged' } : d);
      setNotice('Delivery acknowledged.');
    } catch (err) {
      setError(displayError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleRespond = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api.respondToDelivery(deliveryId, { outcome, body: respBody.trim() });
      setDelivery((d) => d ? { ...d, status: 'responded' } : d);
      setNotice('Official response recorded.');
      setRespBody('');
    } catch (err) {
      setError(displayError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleAppeal = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api.appealDelivery(deliveryId, appealBody.trim());
      setNotice('Appeal filed.');
      setAppealBody('');
    } catch (err) {
      setError(displayError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Authority delivery</span>
        <h1 className="h2">Institutional <span className="accent">review.</span></h1>
      </header>

      {error && <div className="alert alert-err" role="alert" style={{ marginBottom: 16 }}>{error}</div>}
      {notice && <div className="alert alert-ok" role="status" style={{ marginBottom: 16 }}>{notice}</div>}

      {delivery && (
        <div className="form-grid">
          <div className="card">
            <div className="item-top">
              <strong>{delivery.authority_name} ({delivery.authority_role?.toUpperCase()})</strong>
              <span className="status-pill">{delivery.status}</span>
            </div>
            {delivery.incident && (
              <>
                <div className="item-meta">
                  <span><strong>{delivery.incident.course_code}</strong> · {delivery.incident.course_title}</span>
                  <span>{categoryLabel(delivery.incident.category)}</span>
                  <span>Date: {delivery.incident.incident_date}</span>
                  <span>Tier {delivery.incident.clearance_tier}</span>
                </div>
                {delivery.incident.public_summary && (
                  <div className="alert">{delivery.incident.public_summary}</div>
                )}
              </>
            )}
            <div className="actions">
              <button className="btn btn-primary btn-sm" type="button" onClick={handleAck} disabled={busy || delivery.status === 'acknowledged' || delivery.status === 'responded'}>
                Acknowledge receipt
              </button>
            </div>
          </div>

          <form className="card" onSubmit={handleRespond}>
            <h3>Record official response</h3>
            <div className="field">
              <label htmlFor="resp-outcome">Outcome</label>
              <select id="resp-outcome" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
                <option value="action_taken">Action taken</option>
                <option value="explanation_accepted">Explanation accepted</option>
                <option value="disputed">Disputed</option>
                <option value="no_action">No action</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="resp-body">Official notes</label>
              <textarea id="resp-body" required value={respBody} onChange={(e) => setRespBody(e.target.value)} />
            </div>
            <div className="actions">
              <button className="btn btn-primary btn-sm" type="submit" disabled={busy}>Submit response</button>
            </div>
          </form>

          <form className="card" onSubmit={handleAppeal}>
            <h3>File an appeal</h3>
            <div className="field">
              <label htmlFor="appeal-body">Appeal statement</label>
              <textarea id="appeal-body" required value={appealBody} onChange={(e) => setAppealBody(e.target.value)} />
            </div>
            <div className="actions">
              <button className="btn btn-outline btn-sm" type="submit" disabled={busy}>Submit appeal</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

export function LecturerAccessPage() {
  const navigate = useNavigate();
  const [lecturerId, setLecturerId] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [findingId, setFindingId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const handleStart = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await api.obtainLecturerSession({
        lecturer_id: lecturerId.trim(),
        department_id: departmentId.trim(),
        finding_id: findingId.trim() || null,
      });
      if (res?.session_token) setSessionToken(res.session_token);
      if (findingId.trim()) {
        navigate(`/lecturer/findings/${encodeURIComponent(findingId.trim())}`);
      } else {
        navigate('/lecturer/notices');
      }
    } catch (err) {
      setError(displayError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Lecturer access</span>
        <h1 className="h2">Open lecturer <span className="accent">session.</span></h1>
      </header>
      <div className="card">
        {error && <div className="alert alert-err" role="alert">{error}</div>}
        <form className="form-grid" onSubmit={handleStart}>
          <div className="field">
            <label htmlFor="lec-id">Lecturer UUID</label>
            <input id="lec-id" type="text" required value={lecturerId} onChange={(e) => setLecturerId(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="lec-dept">Department UUID</label>
            <input id="lec-dept" type="text" required value={departmentId} onChange={(e) => setDepartmentId(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="lec-finding">Finding UUID (optional)</label>
            <input id="lec-finding" type="text" value={findingId} onChange={(e) => setFindingId(e.target.value)} />
          </div>
          <div className="actions">
            <button className="btn btn-primary" type="submit" disabled={busy}>Continue</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function LecturerNoticesPage() {
  const [courseId, setCourseId] = useState('');
  const [kind, setKind] = useState('cancelled');
  const [forDate, setForDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await api.postClassNotice({
        course_id: courseId.trim(),
        kind,
        for_date: forDate,
        note: note.trim() || null,
      });
      setNotice(`Class notice posted (${res?.notice_id || 'ok'}).`);
    } catch (err) {
      setError(displayError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Lecturer</span>
        <h1 className="h2">Post advance <span className="accent">class notice.</span></h1>
      </header>
      <div className="card">
        {error && <div className="alert alert-err" role="alert">{error}</div>}
        {notice && <div className="alert alert-ok" role="status">{notice}</div>}
        <form className="form-grid" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="notice-course">Course UUID</label>
            <input id="notice-course" type="text" required value={courseId} onChange={(e) => setCourseId(e.target.value)} />
          </div>
          <div className="form-row form-row-2">
            <div className="field">
              <label htmlFor="notice-kind">Notice type</label>
              <select id="notice-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="cancelled">Cancelled</option>
                <option value="rescheduled">Rescheduled</option>
                <option value="extra_class">Extra class</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="notice-date">For date</label>
              <input id="notice-date" type="date" required value={forDate} onChange={(e) => setForDate(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="notice-note">Note (optional)</label>
            <textarea id="notice-note" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          <div className="actions">
            <button className="btn btn-primary" type="submit" disabled={busy}>Post class notice</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function LecturerFindingPage() {
  const { findingId } = useParams();
  const [reason, setReason] = useState('rescheduled');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const handleReply = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await api.postLecturerReply({
        finding_id: findingId,
        reason,
        body: body.trim(),
      });
      setNotice(`Reply recorded (assessment: ${res?.assessment_action || 'recorded'}).`);
      setBody('');
    } catch (err) {
      setError(displayError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Lecturer reply</span>
        <h1 className="h2">Respond to <span className="accent">finding.</span></h1>
      </header>
      <div className="card">
        {error && <div className="alert alert-err" role="alert">{error}</div>}
        {notice && <div className="alert alert-ok" role="status">{notice}</div>}
        <form className="form-grid" onSubmit={handleReply}>
          <div className="field">
            <label htmlFor="reply-reason">Reason</label>
            <select id="reply-reason" value={reason} onChange={(e) => setReason(e.target.value)}>
              <option value="rescheduled">Rescheduled</option>
              <option value="official_duty">Official duty</option>
              <option value="illness">Illness</option>
              <option value="venue_issue">Venue issue</option>
              <option value="disputed">Disputed (starts appeal)</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="reply-body">Explanation</label>
            <textarea id="reply-body" required value={body} onChange={(e) => setBody(e.target.value)} />
          </div>
          <div className="actions">
            <button className="btn btn-primary" type="submit" disabled={busy}>Submit reply</button>
          </div>
        </form>
      </div>
    </div>
  );
}
