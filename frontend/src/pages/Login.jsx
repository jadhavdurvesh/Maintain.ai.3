import { useEffect, useState } from 'react'
import { useAuth } from '../AuthContext.jsx'
import { supabaseAuth } from '../supabaseAuth.js'

const initial = { organization_name: '', username: '', full_name: '', email: '', password: '' }

export default function Login() {
  const { login, register, needsOnboarding, oauthProfile, completeOnboarding } = useAuth()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState(initial)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [oauthBusy, setOauthBusy] = useState(null)
  const [onboarding, setOnboarding] = useState({ organization_name: '', username: '', full_name: '' })

  useEffect(() => {
    if (needsOnboarding && oauthProfile) {
      setOnboarding(current => ({
        organization_name: current.organization_name,
        username: current.username || oauthProfile.username || '',
        full_name: current.full_name || oauthProfile.full_name || '',
      }))
    }
  }, [needsOnboarding, oauthProfile])

  const update = (key, value) => setForm(current => ({ ...current, [key]: value }))

  const finishOnboarding = async (e) => {
    e.preventDefault(); setError(null); setBusy(true)
    try {
      await completeOnboarding(
        onboarding.organization_name.trim(),
        onboarding.username.trim(),
        onboarding.full_name.trim() || oauthProfile?.full_name || '',
      )
    } catch (err) { setError(err.message || 'Could not finish organization setup.') }
    finally { setBusy(false) }
  }

  const submit = async (e) => {
    e.preventDefault(); setError(null); setBusy(true)
    try {
      if (mode === 'login') await login(form.email.trim(), form.password)
      else await register(form.organization_name.trim(), form.username.trim(), form.email.trim(), form.password, form.full_name.trim())
    } catch (err) { setError(err.message || 'Authentication failed. Please try again.') }
    finally { setBusy(false) }
  }

  const signInProvider = async (provider) => {
    setError(null); setOauthBusy(provider)
    try { await supabaseAuth.signInWithProvider(provider) }
    catch (err) { setOauthBusy(null); setError(err.message || 'Could not start provider authentication.') }
  }

  const switchMode = (nextMode) => {
    setError(null)
    setOauthBusy(null)
    setMode(nextMode)
  }

  if (needsOnboarding) {
    return (
      <main className="auth-screen">
        <div className="auth-background"><div className="auth-grid" /><div className="auth-glow auth-glow-one" /><div className="auth-glow auth-glow-two" /></div>
        <section className="auth-layout auth-onboarding-layout">
          <div className="auth-brand-column">
            <div className="auth-brand"><span className="auth-brand-mark">M</span><div><div className="auth-brand-name">MAINTAIN AI</div><div className="auth-brand-caption">ENGINEERING INTELLIGENCE PLATFORM</div></div></div>
            <div className="auth-copy"><div className="auth-eyebrow">ACCOUNT CONNECTED</div><h1>One last step before your engineering workspace is ready.</h1><p>Your {oauthProfile?.email || 'social'} account is authenticated. Tell us which company this Maintain.ai identity belongs to and the username you want to use inside the engineering platform.</p></div>
          </div>
          <div className="auth-card">
            <div className="auth-card-kicker">ORGANIZATION SETUP</div><h2>Complete your profile</h2><p className="auth-onboarding-sub">Organization name and username are required for every new Google or Apple registration.</p>
            <form onSubmit={finishOnboarding} className="auth-form">
              <div className="auth-field"><label>Company / organization name</label><input required value={onboarding.organization_name} onChange={e=>setOnboarding({...onboarding,organization_name:e.target.value})} placeholder="DMJ Group" autoComplete="organization" /></div>
              <div className="auth-field"><label>Username</label><input required value={onboarding.username} onChange={e=>setOnboarding({...onboarding,username:e.target.value})} placeholder="durvesh" autoComplete="username" /></div>
              <div className="auth-field"><label>Your name</label><input value={onboarding.full_name} onChange={e=>setOnboarding({...onboarding,full_name:e.target.value})} placeholder="Durvesh Jadhav" autoComplete="name" /></div>
              {error && <div className="auth-error"><span>!</span><div><strong>Setup issue</strong><p>{error}</p></div></div>}
              <button className="auth-submit" type="submit" disabled={busy}><span>{busy?'Creating workspace…':'Create Engineering Workspace'}</span><span className="auth-arrow">→</span></button>
            </form>
            <div className="auth-security"><span>●</span><span>Your Google/Apple identity is linked to this organization through the Maintain.ai API.</span></div>
          </div>
        </section>
      </main>
    )
  }

  return (
    <main className="auth-screen">
      <div className="auth-background"><div className="auth-grid" /><div className="auth-glow auth-glow-one" /><div className="auth-glow auth-glow-two" /></div>
      <section className="auth-layout">
        <div className="auth-brand-column">
          <div className="auth-brand"><span className="auth-brand-mark">M</span><div><div className="auth-brand-name">MAINTAIN AI</div><div className="auth-brand-caption">ENGINEERING INTELLIGENCE PLATFORM</div></div></div>
          <div className="auth-copy">
            <div className="auth-eyebrow">PREDICTIVE MAINTENANCE · CONTROL CENTER</div>
            <h1>{mode === 'login' ? 'See the condition of your fleet before it becomes a failure.' : 'Build your company’s maintenance intelligence workspace.'}</h1>
            <p>{mode === 'login' ? 'Monitor machines, degradation signals, maintenance activity and future-risk readiness from one engineering control center.' : 'Create the engineering workspace first. Then invite operations and workforce users into the same organization with controlled application access.'}</p>
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
            <button type="button" className={mode === 'login' ? 'active' : ''} onClick={() => switchMode('login')}>Sign in</button>
            <button type="button" className={mode === 'register' ? 'active' : ''} onClick={() => switchMode('register')}>New organization</button>
          </div>

          <div className="auth-social">
            <button type="button" disabled={oauthBusy !== null} onClick={() => signInProvider('google')}>
              <span className="provider-google" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="17" height="17"><path fill="#4285F4" d="M21.35 12.27c0-.79-.07-1.55-.22-2.27H12v4.3h5.23a4.48 4.48 0 0 1-1.94 2.94v2.45h3.14c1.84-1.69 2.92-4.18 2.92-7.42z"/><path fill="#34A853" d="M12 21.92c2.63 0 4.84-.87 6.45-2.23l-3.14-2.45c-.87.58-1.98.93-3.31.93-2.54 0-4.69-1.72-5.46-4.03H3.3v2.53A9.74 9.74 0 0 0 12 21.92z"/><path fill="#FBBC05" d="M6.54 14.14A5.86 5.86 0 0 1 6.23 12c0-.74.13-1.46.31-2.14V7.33H3.3A9.74 9.74 0 0 0 2.26 12c0 1.57.38 3.05 1.04 4.67l3.24-2.53z"/><path fill="#EA4335" d="M12 5.83c1.43 0 2.71.49 3.72 1.45l2.78-2.78C16.84 2.87 14.63 2 12 2a9.74 9.74 0 0 0-8.7 5.33l3.24 2.53C7.31 7.55 9.46 5.83 12 5.83z"/></svg>
              </span>
              {oauthBusy === 'google' ? 'Connecting…' : mode === 'register' ? 'Register with Google' : 'Continue with Google'}
            </button>
            <button type="button" disabled={oauthBusy !== null} onClick={() => signInProvider('apple')}>
              <span className="provider-apple" aria-hidden="true"></span>
              {oauthBusy === 'apple' ? 'Connecting…' : mode === 'register' ? 'Register with Apple' : 'Continue with Apple'}
            </button>
          </div>
          <div className="auth-divider"><span>{mode === 'register' ? 'or register with email' : 'or continue with email'}</span></div>

          <form onSubmit={submit} className="auth-form">
            {mode === 'register' && (
              <div className="auth-section">
                <div className="auth-section-title">Organization</div>
                <div className="auth-field"><label>Company / organization name</label><input required value={form.organization_name} onChange={e=>update('organization_name',e.target.value)} placeholder="Acme Manufacturing" autoComplete="organization" /></div>
                <div className="auth-two">
                  <div className="auth-field"><label>Your name</label><input required value={form.full_name} onChange={e=>update('full_name',e.target.value)} placeholder="Durvesh Jadhav" autoComplete="name" /></div>
                  <div className="auth-field"><label>Username</label><input required value={form.username} onChange={e=>update('username',e.target.value)} placeholder="durvesh" autoComplete="username" /></div>
                </div>
              </div>
            )}

            <div className="auth-section">
              {mode === 'register' && <div className="auth-section-title">Administrator account</div>}
              <div className="auth-field"><label>Work email</label><input type="email" required value={form.email} onChange={e=>update('email',e.target.value)} placeholder="you@company.com" autoComplete="email" /></div>
              <div className="auth-field">
                <div className="auth-label-row"><label>Password</label>{mode === 'login' && <span>Protected by Supabase Auth</span>}</div>
                <input type="password" required minLength="8" value={form.password} onChange={e=>update('password',e.target.value)} placeholder="Enter your password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
              </div>
            </div>

            {error && <div className="auth-error"><span>!</span><div><strong>Authentication issue</strong><p>{error}</p></div></div>}
            <button className="auth-submit" type="submit" disabled={busy}><span>{busy ? 'Authenticating…' : mode === 'login' ? 'Enter Control Center' : 'Create Organization'}</span><span className="auth-arrow">→</span></button>
          </form>

          <div className="auth-footer"><span>{mode === 'login' ? 'New company?' : 'Already have an account?'}</span><button type="button" onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}>{mode === 'login' ? 'Create an organization' : 'Sign in instead'}</button></div>
          <div className="auth-security"><span>●</span><span>Your company data stays behind the Maintain.ai API security boundary.</span></div>
        </div>
      </section>
    </main>
  )
}
