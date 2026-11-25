import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, displayError } from '../shared/api/index.js';
import { categoryLabel } from '../shared/api/dashboardContract.js';

function StatusPill({ status }) {
  const cls = `status-pill status-${status || 'collecting'}`;
  return <span className={cls}>{status || 'collecting'}</span>;
}

export function StudentHomePage() {
  const navigate = useNavigate();
  const [reports, setReports] = useState([]);
  const [sessionInfo, setSessionInfo] = useState(null);
  const [trackInput, setTrackInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      try {
        const [sess, reps] = await Promise.all([api.getSession(), api.listReports()]);
        if (!active) return;
        setSessionInfo(sess);
        setReports(Array.isArray(reps) ? reps : []);
      } catch (err) {
        if (!active) return;
        if (err?.status === 401) {
          navigate('/sign-in');
          return;
        }
        setError(displayError(err));
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [navigate]);

  const handleTrackJump = (e) => {
    e.preventDefault();
    const cleaned = trackInput.trim().toUpperCase();
    if (cleaned) navigate(`/student/reports/${encodeURIComponent(cleaned)}`);
  };

  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Student workspace</span>
        <h1 className="h2">My reports & <span className="accent">corroborations.</span></h1>
        <div className="actions">
          <Link className="btn btn-primary btn-sm" to="/student/reports/new">File a report</Link>
          <Link className="btn btn-outline btn-sm" to="/student/findings">Confirm open findings</Link>
          <Link className="btn btn-outline btn-sm" to="/setup">Department & courses</Link>
        </div>
      </header>

      {sessionInfo && sessionInfo.setup_state !== 'ready' && (
        <div className="alert alert-warn" style={{ marginBottom: 18 }}>
          Setup incomplete ({sessionInfo.setup_state.replace(/_/g, ' ')}).{' '}
          <Link to="/setup" style={{ textDecoration: 'underline', fontWeight: 700 }}>Complete setup first</Link>.
        </div>
      )}

      {error && <div className="alert alert-err" role="alert" style={{ marginBottom: 18 }}>{error}</div>}

      <form className="card" onSubmit={handleTrackJump} style={{ marginBottom: 22 }}>
        <div className="form-row form-row-2" style={{ alignItems: 'end' }}>
          <div className="field">
            <label htmlFor="quick-track">Look up tracking code</label>
            <input
              id="quick-track"
              type="text"
              placeholder="VIO-XXXXXXXX"
              value={trackInput}
              onChange={(e) => setTrackInput(e.target.value)}
            />
          </div>
          <div className="actions">
            <button className="btn btn-outline btn-sm" type="submit">Track report</button>
          </div>
        </div>
      </form>

      {loading ? (
        <div className="card"><p>Loading your submitted reports...</p></div>
      ) : reports.length === 0 ? (
        <div className="card">
          <h3>No reports submitted yet</h3>
          <p>File a report for a registered course or confirm an existing incident reported by classmates.</p>
        </div>
      ) : (
        <ul className="item-list">
          {reports.map((r) => (
            <li className="item-card" key={r.tracking_code}>
              <div className="item-top">
                <strong className="mono">{r.tracking_code}</strong>
                <StatusPill status={r.finding_status} />
              </div>
              <div className="item-meta">
                <span><strong>{r.course_code}</strong> · {r.course_title}</span>
                <span>{categoryLabel(r.category)}</span>
                <span>Date: {r.incident_date}</span>
              </div>
              <p>{r.description}</p>
              <div className="actions">
                <Link className="btn btn-outline btn-sm" to={`/student/reports/${encodeURIComponent(r.tracking_code)}`}>
                  View timeline
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function NewReportPage() {
  const navigate = useNavigate();
  const [options, setOptions] = useState(null);
  const [courseId, setCourseId] = useState('');
  const [category, setCategory] = useState('class_not_held');
  const [incidentDate, setIncidentDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [noticeGiven, setNoticeGiven] = useState(false);
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [created, setCreated] = useState(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      try {
        const opts = await api.getReportOptions();
        if (!active) return;
        setOptions(opts);
        if (opts?.courses?.length) setCourseId(opts.courses[0].course_id);
        if (opts?.categories?.length) setCategory(opts.categories[0].value);
      } catch (err) {
        if (!active) return;
        if (err?.status === 401) {
          navigate('/sign-in');
          return;
        }
        setError(displayError(err));
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const res = await api.createReport({
        course_id: courseId,
        category,
        incident_date: incidentDate,
        description: description.trim(),
        notice_given: noticeGiven,
      });
      setCreated(res);
    } catch (err) {
      setError(displayError(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="page wrap page-narrow">
        <div className="card"><p>Loading registered courses and reporting window...</p></div>
      </div>
    );
  }

  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">File a report</span>
        <h1 className="h2">Submit a factual <span className="accent">incident.</span></h1>
        <p className="lead">
          Your report goes through automated safety and consistency checks before joining or starting a finding.
        </p>
      </header>

      {error && (
        <div className="alert alert-err" role="alert" style={{ marginBottom: 18 }}>
          {error}{' '}
          {error.toLowerCase().includes('profile') || error.toLowerCase().includes('session') ? (
            <Link to="/setup" style={{ textDecoration: 'underline', fontWeight: 700 }}>Go to setup</Link>
          ) : null}
        </div>
      )}

      {created ? (
        <div className="card">
          <span className="status-pill status-collecting">{created.status || 'collecting'}</span>
          <h3>Report received</h3>
          <p>{created.message}</p>
          <p>
            Tracking code: <strong className="mono">{created.tracking_code}</strong>
          </p>
          <div className="actions">
            <Link className="btn btn-primary btn-sm" to={`/student/reports/${encodeURIComponent(created.tracking_code)}`}>
              View status timeline
            </Link>
            <button className="btn btn-outline btn-sm" type="button" onClick={() => { setCreated(null); setDescription(''); }}>
              File another report
            </button>
          </div>
        </div>
      ) : options && options.courses?.length === 0 ? (
        <div className="card">
          <h3>No courses registered yet</h3>
          <p>Register at least one course in your department before submitting a report.</p>
          <div className="actions">
            <Link className="btn btn-primary btn-sm" to="/setup/courses">Register courses</Link>
          </div>
        </div>
      ) : (
        <form className="card form-grid" onSubmit={handleSubmit}>
          <div className="form-row form-row-2">
            <div className="field">
              <label htmlFor="rep-course">Registered course</label>
              <select id="rep-course" value={courseId} onChange={(e) => setCourseId(e.target.value)} required>
                {(options?.courses || []).map((c) => (
                  <option key={c.course_id} value={c.course_id}>{c.course_code} — {c.course_title}</option>
                ))}
              </select>
            </div>

            <div className="field">
              <label htmlFor="rep-cat">Category</label>
              <select id="rep-cat" value={category} onChange={(e) => setCategory(e.target.value)} required>
                {(options?.categories || []).map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-row form-row-2">
            <div className="field">
              <label htmlFor="rep-date">Incident date</label>
              <input
                id="rep-date"
                type="date"
                required
                min={options?.incident_date?.earliest || undefined}
                max={options?.incident_date?.latest || undefined}
                value={incidentDate}
                onChange={(e) => setIncidentDate(e.target.value)}
              />
              {options?.incident_date?.earliest && (
                <span className="field-hint">
                  Session window: {options.incident_date.earliest} to {options.incident_date.latest}
                </span>
              )}
            </div>

            <div className="field" style={{ alignContent: 'center' }}>
              <label className="check-item" style={{ background: '#fff' }}>
                <input
                  type="checkbox"
                  checked={noticeGiven}
                  onChange={(e) => setNoticeGiven(e.target.checked)}
                />
                <span>Advance notice was given before class</span>
              </label>
            </div>
          </div>

          <div className="field">
            <label htmlFor="rep-desc">What happened (factual details, no names)</label>
            <textarea
              id="rep-desc"
              required
              minLength={options?.description?.min_length || 20}
              maxLength={options?.description?.max_length || 2000}
              placeholder="Example: The scheduled CSC 201 lecture did not hold at the assigned lecture theatre and no reschedule notice was given."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <span className="field-hint">
              Minimum {options?.description?.min_length || 20} characters. Describe what happened and match your chosen category.
            </span>
          </div>

          <div className="actions">
            <button className="btn btn-primary" type="submit" disabled={submitting || !courseId}>
              {submitting ? 'Running safety & intake checks...' : 'Submit report'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export function TrackReportPage() {
  const { trackingCode } = useParams();
  const navigate = useNavigate();
  const [queryCode, setQueryCode] = useState(trackingCode || '');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(Boolean(trackingCode));
  const [error, setError] = useState('');

  useEffect(() => {
    if (!trackingCode) {
      setLoading(false);
      setReport(null);
      return;
    }
    let active = true;
    async function load() {
      setLoading(true);
      setError('');
      try {
        let data;
        try {
          data = await api.getStudentReport(trackingCode);
        } catch (err) {
          if (err?.status === 401 || err?.status === 404) {
            data = await api.trackReport(trackingCode);
          } else {
            throw err;
          }
        }
        if (active) setReport(data);
      } catch (err) {
        if (active) setError(displayError(err));
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [trackingCode]);

  const handleLookup = (e) => {
    e.preventDefault();
    const cleaned = queryCode.trim().toUpperCase();
    if (cleaned) navigate(`/track/${encodeURIComponent(cleaned)}`);
  };

  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Report status</span>
        <h1 className="h2">Track an <span className="accent">incident.</span></h1>
      </header>

      {!trackingCode && (
        <form className="card" onSubmit={handleLookup} style={{ marginBottom: 20 }}>
          <div className="field">
            <label htmlFor="track-code-input">Tracking code</label>
            <input
              id="track-code-input"
              type="text"
              required
              placeholder="VIO-XXXXXXXX"
              value={queryCode}
              onChange={(e) => setQueryCode(e.target.value)}
            />
          </div>
          <div className="actions">
            <button className="btn btn-primary btn-sm" type="submit">Check status</button>
          </div>
        </form>
      )}

      {loading && <div className="card"><p>Loading report timeline...</p></div>}
      {error && <div className="alert alert-err" role="alert">{error}</div>}

      {report && (
        <div className="card">
          <div className="item-top">
            <strong className="mono">{report.tracking_code}</strong>
            <StatusPill status={report.finding_status || report.status} />
          </div>
          <div className="item-meta">
            <span><strong>{report.course_code}</strong> · {report.course_title}</span>
            <span>{categoryLabel(report.category)}</span>
            {report.incident_date && <span>Date: {report.incident_date}</span>}
          </div>
          {report.public_summary && (
            <div className="alert">
              <strong>Verified summary:</strong> {report.public_summary}
            </div>
          )}
          {Array.isArray(report.timeline) && report.timeline.length > 0 && (
            <ul className="timeline">
              {report.timeline.map((t, i) => (
                <li key={`${t.event}-${i}`}>
                  <strong>{t.label}</strong>
                  {t.occurred_at && <div className="field-hint">{new Date(t.occurred_at).toLocaleString()}</div>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export function FindingsListPage() {
  const navigate = useNavigate();
  const [findings, setFindings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      try {
        const rows = await api.listFindings();
        if (active) setFindings(Array.isArray(rows) ? rows : []);
      } catch (err) {
        if (!active) return;
        if (err?.status === 401) {
          navigate('/sign-in');
          return;
        }
        setError(displayError(err));
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [navigate]);

  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Corroboration</span>
        <h1 className="h2">Open findings in your <span className="accent">courses.</span></h1>
        <p className="lead">
          Confirm incidents you witnessed personally. You cannot confirm an incident you originally reported.
        </p>
      </header>

      {error && <div className="alert alert-err" role="alert" style={{ marginBottom: 18 }}>{error}</div>}

      {loading ? (
        <div className="card"><p>Loading confirmable findings...</p></div>
      ) : findings.length === 0 ? (
        <div className="card">
          <h3>No open findings to confirm right now</h3>
          <p>Either none of your registered courses have open findings, or you already reported/confirmed them.</p>
          <div className="actions">
            <Link className="btn btn-primary btn-sm" to="/student/reports/new">File a report</Link>
          </div>
        </div>
      ) : (
        <ul className="item-list">
          {findings.map((f) => (
            <li className="item-card" key={f.finding_id}>
              <div className="item-top">
                <strong>{f.course_code} — {f.course_title}</strong>
                <StatusPill status={f.status} />
              </div>
              <div className="item-meta">
                <span>{f.category_label || categoryLabel(f.category)}</span>
                <span>Date: {f.incident_date}</span>
                <span>{f.department}</span>
              </div>
              <div className="actions">
                <Link className="btn btn-primary btn-sm" to={`/student/findings/${f.finding_id}`}>
                  Review & confirm
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function FindingDetailPage() {
  const { findingId } = useParams();
  const navigate = useNavigate();
  const [finding, setFinding] = useState(null);
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [confirmed, setConfirmed] = useState(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      try {
        const data = await api.getFinding(findingId);
        if (active) setFinding(data);
      } catch (err) {
        if (!active) return;
        if (err?.status === 401) {
          navigate('/sign-in');
          return;
        }
        setError(displayError(err));
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [findingId, navigate]);

  const handleConfirm = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const res = await api.confirmFinding(findingId, comment.trim());
      setConfirmed(res);
      setFinding((prev) => prev ? { ...prev, can_confirm: false, is_confirmer: true, status: res.finding_status || prev.status } : prev);
    } catch (err) {
      setError(displayError(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="page wrap page-narrow"><div className="card"><p>Loading finding...</p></div></div>;

  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Finding corroboration</span>
        <h1 className="h2">{finding ? `${finding.course_code} incident` : 'Finding'}</h1>
      </header>

      {error && <div className="alert alert-err" role="alert" style={{ marginBottom: 18 }}>{error}</div>}
      {confirmed && (
        <div className="alert alert-ok" role="status" style={{ marginBottom: 18 }}>
          {confirmed.message} Total supporters: <strong>{confirmed.total_supporters}</strong> (status: <strong>{confirmed.finding_status}</strong>).
        </div>
      )}

      {finding && (
        <div className="card">
          <div className="item-top">
            <strong>{finding.course_code} — {finding.course_title}</strong>
            <StatusPill status={finding.status} />
          </div>
          <div className="item-meta">
            <span>{finding.category_label || categoryLabel(finding.category)}</span>
            <span>Incident date: {finding.incident_date}</span>
            <span>{finding.department}</span>
          </div>
          {finding.public_summary && (
            <div className="alert"><strong>Summary:</strong> {finding.public_summary}</div>
          )}

          {finding.can_confirm ? (
            <form className="form-grid" onSubmit={handleConfirm}>
              <div className="field">
                <label htmlFor="conf-comment">Optional factual confirmation note</label>
                <textarea
                  id="conf-comment"
                  maxLength={500}
                  placeholder="Example: I was present at the venue and this lecture did not hold."
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                />
              </div>
              <div className="actions">
                <button className="btn btn-primary" type="submit" disabled={submitting}>
                  {submitting ? 'Confirming...' : 'Confirm this finding'}
                </button>
              </div>
            </form>
          ) : (
            <p className="field-hint">
              {finding.is_reporter
                ? 'You originally reported this incident, so you cannot also confirm it.'
                : finding.is_confirmer
                ? 'You have already confirmed this finding.'
                : 'This finding is no longer open for confirmation.'}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
