import { Routes, Route, NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Factory, Wrench, ClipboardList, Bot,
  AlertTriangle, Package, BarChart3, Settings as SettingsIcon, History as HistoryIcon, Info,
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
import AIAssistant from './pages/AIAssistant.jsx'
import Alerts from './pages/Alerts.jsx'
import SpareParts from './pages/SpareParts.jsx'
import Reports from './pages/Reports.jsx'
import SettingsPage from './pages/Settings.jsx'
import History from './pages/History.jsx'
import About from './pages/About.jsx'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/machines', label: 'Machines', icon: Factory },
  { to: '/maintenance', label: 'Maintenance', icon: Wrench },
  { to: '/work-orders', label: 'Work Orders', icon: ClipboardList },
  { to: '/ai-assistant', label: 'AI Assistant', icon: Bot },
  { to: '/alerts', label: 'Alerts', icon: AlertTriangle },
  { to: '/spare-parts', label: 'Spare Parts', icon: Package },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/history', label: 'History', icon: HistoryIcon },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
  { to: '/about', label: 'About', icon: Info },
]

function Topbar({ theme, setTheme }) {
  const { title, actions } = useCurrentHeader()
  return (
    <div className="topbar-glass">
      <div className="topbar-inner">
        <div className="topbar-title">{title}</div>
        <div className="topbar-actions">
          {actions}
          <ThemeToggle theme={theme} setTheme={setTheme} />
        </div>
      </div>
    </div>
  )
}

function Sidebar() {
  return (
    <div className="sidebar-glass">
      <div className="sidebar-inner">
        <div className="brand">
          <span className="brand-status-dot" />
          <div>
            <div className="brand-mark">MAINTAIN AI</div>
            <div className="brand-sub">predictive maintenance</div>
          </div>
        </div>
        <nav className="nav-group">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              <Icon size={16} strokeWidth={1.75} />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}

export default function App() {
  const [theme, setTheme] = useTheme()
  useReducedEffects()
  const { checking, needsLogin } = useAuth()

  if (checking) return null
  if (needsLogin) return <Login />

  return (
    <PageHeaderProvider>
      <div className="app-shell">
        <Sidebar />
        <div className="main">
          <Topbar theme={theme} setTheme={setTheme} />
          <div className="content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/machines" element={<Machines />} />
              <Route path="/machines/:id" element={<MachineDetail />} />
              <Route path="/maintenance" element={<Maintenance />} />
              <Route path="/work-orders" element={<WorkOrders />} />
              <Route path="/ai-assistant" element={<AIAssistant />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/spare-parts" element={<SpareParts />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/history" element={<History />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/about" element={<About />} />
            </Routes>
          </div>
        </div>
      </div>
    </PageHeaderProvider>
  )
}
