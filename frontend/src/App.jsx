import { Routes, Route, NavLink } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useTelemetryStream } from './realtime.js'
import api from './api/client.js'
import {
  LayoutDashboard, Factory, Wrench, ClipboardList, Bot,
  AlertTriangle, Package, BarChart3, Settings as SettingsIcon, History as HistoryIcon, Info, Bug, BrainCircuit,
} from 'lucide-react'

import { PageHeaderProvider, useCurrentHeader } from './PageHeaderContext.jsx'
import ThemeToggle, { useTheme, useReducedEffects } from './ThemeToggle.jsx'
import { useAuth } from './AuthContext.jsx'

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
    window.maintainAI.getConnectionStatus().then(setDesktopStatus)
    return window.maintainAI.onConnectionStatus(setDesktopStatus)
  }, [])
  return <div className="sidebar-glass"><div className="sidebar-inner"><div className="brand"><span className={`brand-status-dot${streamStatus === "offline" || streamStatus === "reconnecting" ? " offline" : ""}`} title={`Live telemetry: ${streamStatus}`} /><div><div className="brand-mark">MAINTAIN AI</div><div className="brand-sub">predictive maintenance</div></div></div><nav className="nav-group">{NAV.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}><Icon size={16} strokeWidth={1.75} />{label}</NavLink>)}</nav></div></div>
}

function TelemetryFallback() {
  useEffect(() => {
    let stopped = false
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
          window.dispatchEvent(new CustomEvent('maintain-ai-telemetry', {
            detail: {
              type: 'telemetry',
              machine_id: row.machine_id,
              reading_id: row.reading_id,
              reading_type: row.reading_type,
              value: row.value,
              unit: row.unit,
              recorded_at: row.recorded_at,
            },
          }))
        }
        if (fresh) {
          window.dispatchEvent(new CustomEvent('maintain-ai-realtime-status', { detail: 'connected' }))
        }
      } catch {
        // Supabase Realtime remains the primary path; this fallback is best effort.
      }
    }
    poll()
    const timer = window.setInterval(poll, 2500)
    return () => { stopped = true; window.clearInterval(timer) }
  }, [])
  return null
}

export default function App() {
  const [theme, setTheme] = useTheme()
  useReducedEffects()
  const { checking, needsLogin } = useAuth()
  useEffect(() => {
    // Keep the backend-fed telemetry stream alive even if the browser or
    // deployment cannot maintain the Supabase Realtime socket.
  }, [])
  if (checking) return null
  if (needsLogin) return <Login />
  return <PageHeaderProvider><TelemetryFallback /><div className="app-shell"><Sidebar /><div className="main"><Topbar theme={theme} setTheme={setTheme} /><div className="content"><Routes>
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
  </Routes></div></div></div></PageHeaderProvider>
}
