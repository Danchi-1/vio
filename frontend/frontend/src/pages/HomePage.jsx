import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { PHRASES, STATS, STEPS, FAIR, STATUSES, FAQ } from './home/content.js';
import Typewriter from './home/Typewriter.jsx';
import DeviceMock from './home/DeviceMock.jsx';
import StatePreview from './home/StatePreview.jsx';

const REVEAL = '.sec-head, .stat, .row, .pr li, .st li, .state, details, .closing .h2, .closing-actions';

export default function HomePage() {
  const root = useRef(null);

  // Scroll fade-in with a small stagger. Skipped entirely under reduced motion.
  useEffect(() => {
    const el = root.current;
    if (!el || window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;
    const items = Array.from(el.querySelectorAll(REVEAL));
    el.classList.add('js-reveal');
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { threshold: 0.12 });
    items.forEach((it) => {
      const i = Array.prototype.indexOf.call(it.parentNode.children, it);
      it.style.transitionDelay = `${Math.min(i, 4) * 60}ms`;
      it.classList.add('reveal');
      io.observe(it);
    });
    return () => {
      io.disconnect();
      el.classList.remove('js-reveal');
      items.forEach((it) => { it.classList.remove('reveal', 'in'); it.style.transitionDelay = ''; });
    };
  }, []);

  return (
    <div ref={root}>
      <section className="hero" id="top">
        <div className="wrap hero-grid">
          <div className="hero-copy">
            <h1 className="display">
              <span className="sr-only">Every student deserves to be heard.</span>
              <span aria-hidden="true" style={{ display: 'block' }}>Every student</span>
              <Typewriter phrases={PHRASES} />
            </h1>
            <p className="eyebrow">Academic accountability for students</p>
            <p className="lead">VIO gives students a structured, factual way to report academic problems such as cancelled lectures and unfair assessment. The public sees aggregate patterns, never names.</p>
            <div className="hero-actions">
              <Link className="btn btn-primary" to="/sign-in">Student sign in <span aria-hidden="true">→</span></Link>
              <Link className="btn btn-outline" to="/dashboard">View dashboard</Link>
            </div>
            <p className="hero-note small">Your school email verifies you and is not shown on reports.</p>
          </div>
          <DeviceMock />
        </div>
      </section>

      <div className="strip">
        <div className="wrap strip-grid">
          {STATS.map((s) => (
            <div className="stat" key={s.title}><b>{s.value}</b><span><strong>{s.title}</strong>{s.text}</span></div>
          ))}
        </div>
      </div>

      <section className="sec" id="how-it-works">
        <div className="wrap">
          <div className="sec-head">
            <div>
              <span className="label">01 · The process</span>
              <h2 className="h2">From a problem in class to a <span className="accent">pattern</span>.</h2>
            </div>
            <div>
              <p>Students verify with a school email, set up a profile, report the facts and follow what happens. Lecturers and school authorities reply through private links.</p>
              <p>The public sees only published aggregate results.</p>
            </div>
          </div>
          <ol className="rows">
            {STEPS.map((s) => (
              <li className="row" key={s.n}>
                <span className="n">{s.n}</span><h3>{s.title}</h3><p>{s.text}</p>
                <Link className="arrow" to={s.to} aria-label={s.label}>↗</Link>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="dark sec" id="privacy">
        <div className="wrap">
          <div className="sec-head">
            <div>
              <span className="label">02 · Fair to everyone</span>
              <h2 className="h2">Built to be fair to students and to <span className="accent">staff</span>.</h2>
            </div>
            <p className="muted">No system can guarantee absolute anonymity. Details in a description can point to a person, so write without names or identifying details.</p>
          </div>
          <ul className="pr">{FAIR.map((f) => <li key={f.title}><h3>{f.title}</h3><p>{f.text}</p></li>)}</ul>
        </div>
      </section>

      <section className="sec" id="statuses">
        <div className="wrap">
          <div className="sec-head">
            <div>
              <span className="label">03 · Statuses</span>
              <h2 className="h2">Always see where a finding <span className="accent">stands</span>.</h2>
            </div>
            <p>The system supplies each status and its explanation. VIO shows them as given and never guesses.</p>
          </div>
          <ul className="st">
            {STATUSES.map((s) => (
              <li key={s.key}><span className="pill" style={{ '--c': `var(--st-${s.key})` }}>{s.label}</span><span>{s.text}</span></li>
            ))}
          </ul>
        </div>
      </section>

      <section className="sec sec--tight-top" id="dashboard-preview">
        <div className="wrap">
          <div className="sec-head">
            <div>
              <span className="label">04 · Public dashboard</span>
              <h2 className="h2">Open to everyone, <span className="accent">about no one</span>.</h2>
            </div>
            <p>It will show published findings over time, by category and by department, using only figures the system returns. Small groups stay hidden and nothing links back to a student.</p>
          </div>
          <StatePreview />
        </div>
      </section>

      <section className="sec sec--tight-top" id="faq">
        <div className="wrap">
          <div className="sec-head sec-head--solo">
            <div>
              <span className="label">05 · Guidelines</span>
              <h2 className="h2">Questions students <span className="accent">ask</span>.</h2>
            </div>
          </div>
          <div className="faq">
            {FAQ.map((f) => (
              <details key={f.q}>
                <summary>{f.q}</summary>
                <div><p>{f.a}</p>{f.pending && <p className="pending">{f.pending}</p>}</div>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="dark closing">
        <div className="wrap">
          <h2 className="h2">Have something to <span className="accent">report</span>?</h2>
          <p className="muted" style={{ marginTop: 16, maxWidth: '46ch' }}>Sign in with your school email and a one-time code.</p>
          <div className="closing-actions">
            <Link className="btn btn-primary" to="/sign-in">Student sign in <span aria-hidden="true">→</span></Link>
            <Link className="btn btn-outline" to="/guidelines">Read the guidelines</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
