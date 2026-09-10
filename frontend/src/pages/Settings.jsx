import { useEffect, useState } from 'react'
import api from '../api/client.js'
import { Loading, ErrorState } from './Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'
import { useReducedEffects } from '../ThemeToggle.jsx'
import { useAuth } from '../AuthContext.jsx'
import '../user-management.css'

const emptyForm = { username: '', full_name: '', email: '', role: 'technician' }

export default function SettingsPage() {
  usePageHeader('Settings')
  const { authRequired, user, logout } = useAuth()
  const [reducedEffects, setReducedEffects] = useReducedEffects()
  const [users, setUsers] = useState(null)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [editing, setEditing] = useState(null)
  const [savingUser, setSavingUser] = useState(false)
  const [keyStatus, setKeyStatus] = useState(null)
  const [keyDraft, setKeyDraft] = useState('')
  const [keySaving, setKeySaving] = useState(false)

  const load = () => api.get('/api/users').then(setUsers).catch((e) => setError(e.message))
  const loadKeyStatus = () => api.get('/api/settings/gemini-key').then(setKeyStatus).catch(() => {})

  useEffect(() => { load(); loadKeyStatus() }, [])
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(null), 2800); return () => clearTimeout(timer) }, [toast])

  const create = async (e) => {
    e.preventDefault(); setSavingUser(true)
    try { await api.post('/api/users', form); setForm(emptyForm); await load(); setToast({ type: 'success', message: 'User added successfully.' }) }
    catch (e) { setToast({ type: 'error', message: `Could not add user: ${e.message}` }) }
    finally { setSavingUser(false) }
  }

  const startEdit = (u) => { setEditing(u.id); setForm({ username: u.username, full_name: u.full_name || '', email: u.email || '', role: u.role }) }

  const saveEdit = async (e) => {
    e.preventDefault(); setSavingUser(true)
    try { await api.patch(`/api/users/${editing}`, { full_name: form.full_name, email: form.email || null, role: form.role }); setEditing(null); setForm(emptyForm); await load(); setToast({ type: 'success', message: 'User updated successfully.' }) }
    catch (e) { setToast({ type: 'error', message: `Could not update user: ${e.message}` }) }
    finally { setSavingUser(false) }
  }

  const toggleActive = async (u) => {
    try { await api.patch(`/api/users/${u.id}`, { active: !u.active }); await load(); setToast({ type: 'success', message: u.active ? 'User deactivated.' : 'User reactivated.' }) }
    catch (e) { setToast({ type: 'error', message: `Could not update user: ${e.message}` }) }
  }

  const saveKey = async (e) => {
    e.preventDefault(); if (!keyDraft.trim()) return; setKeySaving(true)
    try { await api.post('/api/settings/gemini-key', { api_key: keyDraft.trim() }); setKeyDraft(''); await loadKeyStatus() }
    finally { setKeySaving(false) }
  }
  const clearKey = async () => { await api.del('/api/settings/gemini-key'); await loadKeyStatus() }

  if (error) return <ErrorState message={error} />
  if (!users) return <Loading />

  return <>
    {toast && <div className="ui-toast-stack" aria-live="polite"><div className={`ui-toast ${toast.type}`}>{toast.message}</div></div>}
    {authRequired && user && <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Account</span></div><div className="panel-body"><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><div><div style={{ fontWeight: 600 }}>{user.username}</div><div style={{ color: 'var(--text-faint)', fontSize: 12.5 }}>{user.organization_name} · {user.role}</div></div><button className="btn secondary" onClick={logout}>Sign Out</button></div></div></div>}
    <div className="panel section-gap"><div className="panel-header"><span className="panel-title">Display &amp; Performance</span></div><div className="panel-body"><p style={{ color: 'var(--text-dim)', fontSize: 13, marginBottom: 12 }}>The frosted-glass look uses a background blur effect. If the app feels sluggish on older hardware or remote desktop sessions, reduce it here.</p><label style={{ display: 'flex', alignItems: 'center', gap: 10 }}><input type="checkbox" style={{ width: 'auto' }} checked={reducedEffects} onChange={(e) => setReducedEffects(e.target.checked)} />Reduce visual effects (disables background blur)</label></div></div>
    <div className="panel section-gap"><div className="panel-header"><span className="panel-title">AI Assistant — Gemini API Key</span></div><div className="panel-body"><p style={{ color: 'var(--text-dim)', fontSize: 13, marginBottom: 12 }}>Stored in the application's database and never shipped in source code.</p>{keyStatus?.configured ? <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><span className="badge healthy">Configured · •••• {keyStatus.last4}</span><button className="btn secondary" onClick={clearKey}>Remove Key</button></div> : <form onSubmit={saveKey} style={{ display: 'flex', gap: 8 }}><input type="password" value={keyDraft} onChange={(e) => setKeyDraft(e.target.value)} placeholder="Paste your Gemini API key" /><button className="btn" type="submit" disabled={keySaving}>{keySaving ? 'Saving…' : 'Save Key'}</button></form>}</div></div>
    <div className="panel section-gap">
      <div className="panel-header"><span className="panel-title">User Management</span><span className="badge neutral">{users.filter((u) => u.active !== false).length} active · {users.length} total</span></div>
      <div className="panel-body">
        <div style={{ color: 'var(--text-dim)', fontSize: 13, marginBottom: 14 }}>Add the people who can receive maintenance work orders. Viewers stay visible in the team but cannot be assigned work.</div>
        <form className="user-form-grid" onSubmit={editing ? saveEdit : create}>
          <div className="field"><label>Username</label><input required disabled={!!editing} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="ravi.k" /></div>
          <div className="field"><label>Full name</label><input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="Ravi Kulkarni" /></div>
          <div className="field"><label>Email</label><input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="ravi@example.com" /></div>
          <div className="field"><label>Role</label><select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}><option value="admin">Administrator</option><option value="technician">Technician</option><option value="viewer">Viewer</option></select></div>
          <div className="user-form-actions"><button className="btn" type="submit" disabled={savingUser}>{savingUser ? 'Saving…' : editing ? 'Save Changes' : 'Add User'}</button>{editing && <button className="btn secondary" type="button" onClick={() => { setEditing(null); setForm(emptyForm) }}>Cancel</button>}</div>
        </form>
      </div>
      <div style={{ overflowX: 'auto' }}><table><thead><tr><th>User</th><th>Email</th><th>Role</th><th>Status</th><th></th></tr></thead><tbody>
        {users.map((u) => <tr key={u.id}><td><div style={{ fontWeight: 600 }}>{u.full_name || u.username}</div><div className="mono" style={{ fontSize: 11, color: 'var(--text-faint)' }}>@{u.username}</div></td><td>{u.email || '—'}</td><td><span className={`badge ${u.role === 'admin' ? 'healthy' : u.role === 'technician' ? 'neutral' : 'warning'}`}>{u.role}</span></td><td><span className={`badge ${u.active !== false ? 'healthy' : 'critical'}`}>{u.active !== false ? 'Active' : 'Inactive'}</span></td><td><div className="chip-row"><button className="btn secondary" onClick={() => startEdit(u)}>Edit</button><button className="btn secondary" disabled={user?.id === u.id && u.active !== false} onClick={() => toggleActive(u)}>{u.active !== false ? 'Deactivate' : 'Activate'}</button></div></td></tr>)}
        {users.length === 0 && <tr><td colSpan={5} className="empty-state">No users yet.</td></tr>}
      </tbody></table></div>
    </div>
    <p style={{ color: 'var(--text-faint)', fontSize: 12, marginTop: 16 }}>{authRequired ? 'User roles are now enforced for user administration and work-order assignment.' : 'Local mode is active — the local session has administrator privileges.'}</p>
  </>
}
