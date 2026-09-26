import { Component, useEffect, useState } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import { useTelemetryStream } from './realtime.js'
import api from './api/client.js'
import { LayoutDashboard, Factory, Wrench, ClipboardList, Bot, AlertTriangle, Package, BarChart3, Settings as SettingsIcon, History as HistoryIcon, Info, Bug, BrainCircuit } from 'lucide-react'

import { PageHeaderProvider, useCurrentHeader } from './PageHeaderContext.jsx'
import ThemeToggle, { useTheme, useReducedEffects } from './ThemeToggle.jsx'
import { useAuth } from './AuthContext.jsx'
import MachineDetailEnhancementsRoute from './components/MachineDetailEnhancementsRoute.jsx'

import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Machines from './pages/Machines.jsx'
import MachineDetail from './pages/MachineDetail.jsx'
import Maintenance from './pages/Maintenance.jsx'
import WorkOrders from './pages/WorkOrders.jsx'
import Faults from './pages/Faults.jsx'
import AIAssistant from './pages/AIAssistant.jsx'
import Alerts from './pages/Alerts.jsx'
import SpareParts from './pages/SpareParts.jsx'
import Reports from './pages/Reports.jsx'
import SettingsPage from './pages/Settings.jsx'
import History from './pages/History.jsx'
import About from './pages/About.jsx'
import ModelLab from './pages/ModelLab.jsx'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/machines', label: 'Machines', icon: Factory },
  { to: '/maintenance', label: 'Maintenance', icon: Wrench },
  { to: '/work-orders', label: 'Work Orders', icon: ClipboardList },
  { to: '/faults', label: 'Fault Log', icon: Bug },
  { to: '/ai-assistant', label: 'AI Assistant', icon: Bot },
  { to: '/alerts', label: 'Alerts', icon: AlertTriangle },
  { to: '/spare-parts', label: 'Spare Parts', icon: Package },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/model-lab', label: 'AI Model Lab', icon: BrainCircuit },
  { to: '/history', label: 'History', icon: HistoryIcon },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
  { to: '/about', label: 'About', icon: Info },
]

function Topbar({ theme, setTheme }) {
  const { title, actions } = useCurrentHeader()
  return <div className="topbar-glass"><div className="topbar-inner"><div className="topbar-title">{title}</div><div className="topbar-actions">{actions}<ThemeToggle theme={theme} setTheme={setTheme} /></div></div></div>
}

function Sidebar() {
  const { status: streamStatus } = useTelemetryStream()
  const [desktopStatus, setDesktopStatus] = useState(null)
  useEffect(() => {
    if (!window.maintainAI) return
    window.maintainAI.getConnectionStatus().then(setDesktopStatus).catch(() => setDesktopStatus(null))
    return window.maintainAI.onConnectionStatus(setDesktopStatus)
  }, [])
  return <div className="sidebar-glass"><div className="sidebar-inner"><div className="brand"><span className={`brand-status-dot${streamStatus === "offline" || streamStatus === "reconnecting" ? " offline" : ""}`} title={`Live telemetry: ${streamStatus}`} /><div><div className="brand-mark">MAINTAIN AI</div><div className="brand-sub">predictive maintenance</div></div></div><nav className="nav-group">{NAV.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}><Icon size={16} strokeWidth={1.75} />{label}</NavLink>)}</nav></div></div>
}

function TelemetryFallback() {
  useEffect(() => {
    let stopped = false
    const seen = new Map()
    const poll = async () => {
      if (stopped) return
      try {
        const result = await api.get(`/api/devices/telemetry/latest?ts=${Date.now()}`)
        const rows = Array.isArray(result?.machines) ? result.machines : []
        let fresh = false
        const now = Date.now()
        for (const row of rows) {
          if (row?.machine_id == null || !row?.reading_type) continue
          const recorded = row.recorded_at ? Date.parse(row.recorded_at) : NaN
          if (Number.isFinite(recorded) && now - recorded < 45000) fresh = true
          const key = `${row.machine_id}:${row.reading_type}`
          if (seen.get(key) === row.reading_id) continue
          seen.set(key, row.reading_id)
          window.dispatchEvent(new CustomEvent('maintain-ai-telemetry', { detail: { type: 'telemetry', machine_id: row.machine_id, reading_id: row.reading_id, reading_type: row.reading_type, value: row.value, unit: row.unit, recorded_at: row.recorded_at } }))
        }
        if (fresh) window.dispatchEvent(new CustomEvent('maintain-ai-realtime-status', { detail: 'connected' }))
      } catch {}
    }
    poll()
    const timer = window.setInterval(poll, 2500)
    return () => { stopped = true; window.clearInterval(timer) }
  }, [])
  return null
}

class RouteErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(error) { return { error } }
  componentDidCatch(error, info) { console.error('Maintain AI route render failed:', error, info) }
  componentDidUpdate(prevProps) {
    if (prevProps.routeKey !== this.props.routeKey && this.state.error) this.setState({ error: null })
  }
  render() {
    if (!this.state.error) return this.props.children
    return <div className="panel section-gap">
      <div className="panel-header"><span className="panel-title">Machine page could not be rendered</span><span className="badge critical">Recovered</span></div>
      <div className="panel-body">
        <p style={{ color: 'var(--text-dim)', fontSize: 13, lineHeight: 1.6, margin: 0 }}>The application hit a frontend error while opening this page. Your data is not being deleted.</p>
        <div className="mono" style={{ marginTop: 10, padding: 10, borderRadius: 8, background: 'var(--panel-raised)', color: 'var(--text-faint)', fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{this.state.error?.message || String(this.state.error)}</div>
        <div className="chip-row" style={{ marginTop: 12 }}><button className="btn" onClick={() => this.setState({ error: null })}>Retry page</button><button className="btn secondary" onClick={() => { window.location.hash = '#/machines' }}>Back to machines</button></div>
      </div>
    </div>
  }
}

function AppLoading() {
  return <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'var(--bg, #0f1720)', color: 'var(--text, #e5edf5)', fontFamily: 'system-ui, sans-serif' }}><div style={{ textAlign: 'center' }}><div style={{ fontSize: 15, fontWeight: 700, letterSpacing: 1 }}>MAINTAIN AI</div><div style={{ marginTop: 8, fontSize: 12, opacity: 0.65 }}>Loading your workspace…</div></div></div>
}

export default function App() {
  const [theme, setTheme] = useTheme()
  useReducedEffects()
  const { checking, needsLogin } = useAuth()
  if (checking) return <AppLoading />
  if (needsLogin) return <Login />
  const routeKey = window.location.hash
  return <PageHeaderProvider><TelemetryFallback /><div className="app-shell"><Sidebar /><div className="main"><Topbar theme={theme} setTheme={setTheme} /><div className="content"><RouteErrorBoundary routeKey={routeKey}><Routes>
    <Route path="/" element={<Dashboard />} />
    <Route path="/machines" element={<Machines />} />
    <Route path="/machines/:id" element={<MachineDetail />} />
    <Route path="/maintenance" element={<Maintenance />} />
    <Route path="/work-orders" element={<WorkOrders />} />
    <Route path="/faults" element={<Faults />} />
    <Route path="/ai-assistant" element={<AIAssistant />} />
    <Route path="/alerts" element={<Alerts />} />
    <Route path="/spare-parts" element={<SpareParts />} />
    <Route path="/reports" element={<Reports />} />
    <Route path="/model-lab" element={<ModelLab />} />
    <Route path="/history" element={<History />} />
    <Route path="/settings" element={<SettingsPage />} />
    <Route path="/about" element={<About />} />
  </Routes></RouteErrorBoundary><MachineDetailEnhancementsRoute /></div></div></div></PageHeaderProvider>
}
