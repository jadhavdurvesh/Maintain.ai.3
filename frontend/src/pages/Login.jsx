import { useState } from 'react'
import { useAuth } from '../AuthContext.jsx'

const initial = { organization_name: '', username: '', full_name: '', email: '', password: '' }

export default function Login() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState(initial)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }))

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'login') {
        await login(form.email.trim(), form.password)
      } else {
        await register(form.organization_name.trim(), form.username.trim(), form.email.trim(), form.password, form.full_name.trim())
      }
    } catch (err) {
      setError(err.message || 'Authentication failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const switchMode = () => {
    setError(null)
    setMode((current) => current === 'login' ? 'register' : 'login')
  }

  return (
    <main className="auth-screen">
      <div className="auth-background">
        <div className="auth-grid" />
        <div className="auth-glow auth-glow-one" />
        <div className="auth-glow auth-glow-two" />
      </div>

      <section className="auth-layout">
        <div className="auth-brand-column">
          <div className="auth-brand">
            <span className="auth-brand-mark">M</span>
            <div>
              <div className="auth-brand-name">MAINTAIN AI</div>
              <div className="auth-brand-caption">ENGINEERING INTELLIGENCE PLATFORM</div>
            </div>
          </div>

          <div className="auth-copy">
            <div className="auth-eyebrow">PREDICTIVE MAINTENANCE · CONTROL CENTER</div>
            <h1>{mode === 'login' ? 'See the condition of your fleet before it becomes a failure.' : 'Build your company’s maintenance intelligence workspace.'}</h1>
            <p>{mode === 'login'
              ? 'Monitor machines, degradation signals, maintenance activity and future-risk readiness from one engineering control center.'
              : 'Create the engineering workspace first. Then invite operations and workforce users into the same organization with controlled application access.'}</p>
          </div>

          <div className="auth-points">
            <div><span>01</span><div><strong>Temporal machine intelligence</strong><small>Live telemetry, degradation evidence and predictive signals.</small></div></div>
            <div><span>02</span><div><strong>One company identity</strong><small>Engineering, Android operations and Workforce share the same organization.</small></div></div>
            <div><span>03</span><div><strong>Technician feedback loop</strong><small>Maintenance outcomes become evidence for future model development.</small></div></div>
          </div>
        </div>

        <div className="auth-card">
          <div className="auth-card-top">
            <div>
              <div className="auth-card-kicker">{mode === 'login' ? 'WELCOME BACK' : 'GET STARTED'}</div>
              <h2>{mode === 'login' ? 'Sign in' : 'Create your organization'}</h2>
              <p>{mode === 'login' ? 'Continue to your engineering control center.' : 'The person creating the organization becomes its administrator.'}</p>
            </div>
            <div className="auth-status"><span /> SECURE SESSION</div>
          </div>

          <div className="auth-mode">
            <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => { setMode('login'); setError(null) }}>Sign in</button>
            <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => { setMode('register'); setError(null) }}>New organization</button>
          </div>

          <form onSubmit={submit} className="auth-form">
            {mode === 'register' && (
              <div className="auth-section">
                <div className="auth-section-title">Organization</div>
                <div className="auth-field">
                  <label>Company / organization name</label>
                  <input required value={form.organization_name} onChange={(e) => update('organization_name', e.target.value)} placeholder="Acme Manufacturing" autoComplete="organization" />
                </div>
                <div className="auth-two">
                  <div className="auth-field">
                    <label>Your name</label>
                    <input required value={form.full_name} onChange={(e) => update('full_name', e.target.value)} placeholder="Durvesh Jadhav" autoComplete="name" />
                  </div>
                  <div className="auth-field">
                    <label>Username</label>
                    <input required value={form.username} onChange={(e) => update('username', e.target.value)} placeholder="durvesh" autoComplete="username" />
                  </div>
                </div>
              </div>
            )}

            <div className="auth-section">
              {mode === 'register' && <div className="auth-section-title">Administrator account</div>}
              <div className="auth-field">
                <label>Work email</label>
                <input type="email" required value={form.email} onChange={(e) => update('email', e.target.value)} placeholder="you@company.com" autoComplete="email" />
              </div>
              <div className="auth-field">
                <div className="auth-label-row"><label>Password</label>{mode === 'login' && <span>Protected by Supabase Auth</span>}</div>
                <input type="password" required minLength="8" value={form.password} onChange={(e) => update('password', e.target.value)} placeholder="Enter your password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
              </div>
            </div>

            {error && <div className="auth-error"><span>!</span><div><strong>Authentication issue</strong><p>{error}</p></div></div>}

            <button className="auth-submit" type="submit" disabled={busy}>
              <span>{busy ? 'Authenticating…' : mode === 'login' ? 'Enter Control Center' : 'Create Organization'}</span>
              <span className="auth-arrow">→</span>
            </button>
          </form>

          <div className="auth-footer">
            <span>{mode === 'login' ? 'New company?' : 'Already have an account?'}</span>
            <button type="button" onClick={switchMode}>{mode === 'login' ? 'Create an organization' : 'Sign in instead'}</button>
          </div>

          <div className="auth-security">
            <span>●</span>
            <span>Your company data stays behind the Maintain.ai API security boundary.</span>
          </div>
        </div>
      </section>
    </main>
  )
}
