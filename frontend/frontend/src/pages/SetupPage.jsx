import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, displayError } from '../shared/api/index.js';

const LEVELS = [100, 200, 300, 400, 500, 600];

export default function SetupPage({ section = 'profile' }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingCourses, setSavingCourses] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [academicSession, setAcademicSession] = useState('2026/2027');
  const [catalogue, setCatalogue] = useState([]);
  const [departmentId, setDepartmentId] = useState('');
  const [level, setLevel] = useState(200);
  const [selectedCourses, setSelectedCourses] = useState(() => new Set());
  const [courseFilter, setCourseFilter] = useState('');
  const [profileReady, setProfileReady] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const [sess, prof, cat] = await Promise.all([
          api.getSession(),
          api.getProfile(),
          api.getCatalogue('FUNAAB'),
        ]);
        if (!active) return;

        if (sess?.academic_session) setAcademicSession(sess.academic_session);
        setCatalogue(Array.isArray(cat) ? cat : []);

        if (prof?.department_id) {
          setDepartmentId(prof.department_id);
          setProfileReady(true);
        }
        if (prof?.level) setLevel(Number(prof.level));

        try {
          const enrolled = await api.getCourses();
          if (active && Array.isArray(enrolled)) {
            setSelectedCourses(new Set(enrolled.map((c) => String(c.course_id || c.id))));
          }
        } catch {
          // Courses may be unavailable until session/profile is confirmed.
        }
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

  const departments = useMemo(() => {
    const map = new Map();
    for (const row of catalogue) {
      if (row.department_id && !map.has(row.department_id)) {
        map.set(row.department_id, {
          id: row.department_id,
          name: row.department,
          faculty: row.faculty,
        });
      }
    }
    return [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [catalogue]);

  const departmentCourses = useMemo(() => {
    const seen = new Map();
    const q = courseFilter.trim().toLowerCase();
    for (const row of catalogue) {
      if (departmentId && row.department_id !== departmentId) continue;
      if (!row.course_id || seen.has(row.course_id)) continue;
      const label = `${row.course_code} ${row.course_title}`.toLowerCase();
      if (q && !label.includes(q)) continue;
      seen.set(row.course_id, {
        id: row.course_id,
        code: row.course_code,
        title: row.course_title,
        level: row.level,
      });
    }
    return [...seen.values()];
  }, [catalogue, departmentId, courseFilter]);

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    if (!departmentId) {
      setError('Select your department first.');
      return;
    }
    setError('');
    setNotice('');
    setSavingProfile(true);
    try {
      await api.updateProfile({ department_id: departmentId, level: Number(level) });
      if (academicSession) {
        await api.confirmSession(academicSession);
      }
      setProfileReady(true);
      setNotice(`Profile and ${academicSession} session saved. Now choose your courses below.`);
    } catch (err) {
      setError(displayError(err));
    } finally {
      setSavingProfile(false);
    }
  };

  const toggleCourse = (id) => {
    setSelectedCourses((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSaveCourses = async (e) => {
    e.preventDefault();
    setError('');
    setNotice('');
    setSavingCourses(true);
    try {
      await api.updateCourses([...selectedCourses], academicSession);
      setNotice('Registered courses saved! You can now file or confirm reports.');
    } catch (err) {
      setError(displayError(err));
    } finally {
      setSavingCourses(false);
    }
  };

  if (loading) {
    return (
      <div className="page wrap page-narrow">
        <div className="card"><p>Loading your student setup and course catalogue...</p></div>
      </div>
    );
  }

  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Student setup · {academicSession}</span>
        <h1 className="h2">Department, level, and <span className="accent">courses.</span></h1>
        <p className="lead">
          You can only file or confirm reports for courses registered under your department for the active session.
        </p>
      </header>

      {error && <div className="alert alert-err" role="alert" style={{ marginBottom: 18 }}>{error}</div>}
      {notice && <div className="alert alert-ok" role="status" style={{ marginBottom: 18 }}>{notice}</div>}

      <div className="form-grid">
        {section !== 'timetable' && (
          <form className="card" onSubmit={handleSaveProfile}>
            <h3>1. Profile & Academic Session</h3>
            <div className="form-row form-row-2">
              <div className="field">
                <label htmlFor="setup-dept">Department</label>
                <select
                  id="setup-dept"
                  value={departmentId}
                  onChange={(e) => { setDepartmentId(e.target.value); setSelectedCourses(new Set()); }}
                  required
                >
                  <option value="">Select department...</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label htmlFor="setup-level">Level</label>
                <select id="setup-level" value={level} onChange={(e) => setLevel(Number(e.target.value))}>
                  {LEVELS.map((lv) => (
                    <option key={lv} value={lv}>{lv} Level</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="actions">
              <button className="btn btn-primary btn-sm" type="submit" disabled={savingProfile}>
                {savingProfile ? 'Saving...' : 'Save profile & confirm session'}
              </button>
            </div>
          </form>
        )}

        <form className="card" onSubmit={handleSaveCourses}>
          <div className="item-top">
            <h3>2. Register Courses ({selectedCourses.size} selected)</h3>
            {section === 'timetable' && (
              <span className="status-pill">Catalogue mode</span>
            )}
          </div>
          {!profileReady && (
            <p className="field-hint">Save step 1 first so your department is locked in before saving courses.</p>
          )}
          <div className="field">
            <label htmlFor="course-filter">Filter courses</label>
            <input
              id="course-filter"
              type="search"
              placeholder="Search by code or title (e.g. CSC 201, MTS)"
              value={courseFilter}
              onChange={(e) => setCourseFilter(e.target.value)}
            />
          </div>

          {departmentCourses.length === 0 ? (
            <p className="field-hint">
              {departmentId ? 'No matching courses found for that filter.' : 'Select a department above to view its courses.'}
            </p>
          ) : (
            <ul className="check-list">
              {departmentCourses.map((c) => (
                <li key={c.id}>
                  <label className="check-item">
                    <input
                      type="checkbox"
                      checked={selectedCourses.has(c.id)}
                      onChange={() => toggleCourse(c.id)}
                    />
                    <span>
                      <strong>{c.code}</strong> — {c.title}
                      {c.level ? <span className="field-hint"> ({c.level}L)</span> : null}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}

          <div className="actions">
            <button className="btn btn-primary btn-sm" type="submit" disabled={savingCourses || !profileReady}>
              {savingCourses ? 'Saving courses...' : 'Save registered courses'}
            </button>
            <Link className="btn btn-outline btn-sm" to="/student/reports/new">Go to file a report →</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
