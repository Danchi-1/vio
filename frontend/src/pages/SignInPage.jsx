import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { api, displayError } from '../shared/api/index.js';

export default function SignInPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const initialVerify = location.pathname.endsWith('/verify');

  const [step, setStep] = useState(initialVerify ? 'verify' : 'email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [masked, setMasked] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  const handleRequestOtp = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');
    setBusy(true);
    try {
      const res = await api.requestOtp(email.trim());
      setMasked(res?.masked_destination || email.trim());
      setStep('verify');
      setInfo('Verification code requested. Enter the 6-digit code sent to your school email.');
    } catch (err) {
      setError(displayError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await api.verifyOtp(email.trim(), code.trim());
      try {
        const sess = await api.getSession();
        if (sess?.setup_state === 'ready') {
          navigate('/student');
          return;
        }
      } catch {
        // Fall through to setup if session summary fails or profile incomplete.
      }
      navigate('/setup');
    } catch (err) {
      setError(displayError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page wrap page-narrow">
      <header className="page-head">
        <span className="eyebrow">Student access</span>
        <h1 className="h2">Sign in with your <span className="accent">school email.</span></h1>
        <p className="lead">
          Only verified university student emails are accepted. Your email is hashed and never shown on any report or finding.
        </p>
      </header>

      <div className="card">
        {error && <div className="alert alert-err" role="alert">{error}</div>}
        {info && <div className="alert" role="status">{info}</div>}

        {step === 'email' ? (
          <form className="form-grid" onSubmit={handleRequestOtp}>
            <div className="field">
              <label htmlFor="student-email">Official student email</label>
              <input
                id="student-email"
                type="email"
                required
                placeholder="surnameab.26@student.funaab.edu.ng"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
              />
              <span className="field-hint">Must end with @student.funaab.edu.ng</span>
            </div>
            <div className="actions">
              <button className="btn btn-primary" type="submit" disabled={busy}>
                {busy ? 'Sending code...' : 'Send verification code'}
              </button>
              <Link className="btn btn-outline" to="/track">Track a report</Link>
            </div>
          </form>
        ) : (
          <form className="form-grid" onSubmit={handleVerifyOtp}>
            {initialVerify && (
              <div className="field">
                <label htmlFor="verify-email">Official student email</label>
                <input
                  id="verify-email"
                  type="email"
                  required
                  placeholder="surnameab.26@student.funaab.edu.ng"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            )}
            <div className="field">
              <label htmlFor="otp-code">6-digit verification code {masked ? `for ${masked}` : ''}</label>
              <input
                id="otp-code"
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                required
                placeholder="000000"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
              <span className="field-hint">Demo environment note: if dev bypass is active, use 000000.</span>
            </div>
            <div className="actions">
              <button className="btn btn-primary" type="submit" disabled={busy}>
                {busy ? 'Verifying...' : 'Verify & continue'}
              </button>
              <button
                className="btn btn-outline"
                type="button"
                disabled={busy}
                onClick={() => { setStep('email'); setError(''); setInfo(''); }}
              >
                Use different email
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
