import { useState } from 'react'
import { useAuth } from '../AuthContext.jsx'

export default function Login() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [form, setForm] = useState({ organization_name: '', username: '', full_name: '', email: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'login') {
        await login(form.email, form.password)
      } else {
        await register(form.organization_name, form.username, form.email, form.password, form.full_name)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-gradient), var(--bg)',
    }}>
      <div className="panel" style={{ width: 380, padding: 32 }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div className="brand-mark" style={{ fontSize: 20 }}>MAINTAIN AI</div>
          <div className="brand-sub">{mode === 'login' ? 'Sign in to your organization' : 'Register a new organization'}</div>
        </div>

        <form onSubmit={submit}>
          {mode === 'register' && (
            <>
              <div className="field">
                <label>Company / organization name</label>
                <input required value={form.organization_name} onChange={(e) => setForm({ ...form, organization_name: e.target.value })} placeholder="Acme Manufacturing" />
              </div>
              <div className="field">
                <label>Your username</label>
                <input required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="jdoe" />
              </div>
              <div className="field">
                <label>Full name (optional)</label>
                <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
              </div>
            </>
          )}
          <div className="field">
            <label>Email</label>
            <input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@company.com" />
          </div>
          <div className="field">
            <label>Password</label>
            <input type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </div>

          {error && <p style={{ color: 'var(--critical)', fontSize: 13, marginBottom: 12 }}>{error}</p>}

          <button className="btn" type="submit" disabled={busy} style={{ width: '100%' }}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Organization'}
          </button>
        </form>

        <p style={{ textAlign: 'center', fontSize: 13, color: 'var(--text-faint)', marginTop: 16 }}>
          {mode === 'login' ? (
            <>New company? <a href="#" style={{ color: 'var(--accent)' }} onClick={(e) => { e.preventDefault(); setMode('register') }}>Register one</a></>
          ) : (
            <>Already registered? <a href="#" style={{ color: 'var(--accent)' }} onClick={(e) => { e.preventDefault(); setMode('login') }}>Sign in</a></>
          )}
        </p>
      </div>
    </div>
  )
}
