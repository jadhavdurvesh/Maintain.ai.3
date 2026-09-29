import { Component, useEffect, useState } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import { useTelemetryStream } from './realtime.js'
import api from './api/client.js'
import { LayoutDashboard, Factory, Wrench, ClipboardList, Bot, AlertTriangle, Package, BarChart3, Settings as SettingsIcon, History as HistoryIcon, Info, Bug, BrainCircuit, GitCompareArrows } from 'lucide-react'
import { PageHeaderProvider, useCurrentHeader } from './PageHeaderContext.jsx'
import ThemeToggle, { useTheme, useReducedEffects } from './ThemeToggle.jsx'
import { useAuth } from './AuthContext.jsx'
import MachineDetailRouter from './components/MachineDetailRouter.jsx'
import AlertToastLayer from './components/AlertToastLayer.jsx'
import './components/alert-toast.css'
import './layout-fix.css'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Machines from './pages/Machines.jsx'
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
import ModelLabConsole from './pages/ModelLabConsoleStable.jsx'
import ModelComparison from './pages/ModelComparison.jsx'

const NAV=[{to:'/',label:'Dashboard',icon:LayoutDashboard,end:true},{to:'/machines',label:'Machines',icon:Factory},{to:'/maintenance',label:'Maintenance',icon:Wrench},{to:'/work-orders',label:'Work Orders',icon:ClipboardList},{to:'/faults',label:'Fault Log',icon:Bug},{to:'/ai-assistant',label:'AI Assistant',icon:Bot},{to:'/alerts',label:'Alerts',icon:AlertTriangle},{to:'/spare-parts',label:'Spare Parts',icon:Package},{to:'/reports',label:'Reports',icon:BarChart3},{to:'/model-lab',label:'AI Model Lab',icon:BrainCircuit},{to:'/history',label:'History',icon:HistoryIcon},{to:'/settings',label:'Settings',icon:SettingsIcon},{to:'/about',label:'About',icon:Info}]
function Topbar({theme,setTheme}){const {title,actions}=useCurrentHeader();const onModelLab=window.location.hash==='#/model-lab';return <div className="topbar-glass"><div className="topbar-inner"><div className="topbar-title">{title}</div><div className="topbar-actions">{actions}{onModelLab&&<a className="btn secondary" href="#/model-lab/compare" title="Compare models"><GitCompareArrows size={14}/> Compare models</a>}<ThemeToggle theme={theme} setTheme={setTheme}/></div></div></div>}
function Sidebar(){const {status:streamStatus}=useTelemetryStream();const [desktopStatus,setDesktopStatus]=useState(null);useEffect(()=>{if(!window.maintainAI)return;window.maintainAI.getConnectionStatus().then(setDesktopStatus).catch(()=>setDesktopStatus(null));return window.maintainAI.onConnectionStatus(setDesktopStatus)},[]);return <div className="sidebar-glass"><div className="sidebar-inner"><div className="brand"><span className={`brand-status-dot${streamStatus==='offline'||streamStatus==='reconnecting'?' offline':''}`} title={`Live telemetry: ${streamStatus}`}/><div><div className="brand-mark">MAINTAIN AI</div><div className="brand-sub">predictive maintenance</div></div></div><nav className="nav-group">{NAV.map(({to,label,icon:Icon,end})=><NavLink key={to} to={to} end={end} className={({isActive})=>`nav-link${isActive?' active':''}`}><Icon size={16} strokeWidth={1.75}/>{label}</NavLink>)}</nav></div></div>}
function TelemetryFallback(){useEffect(()=>{let stopped=false;const seen=new Map();const poll=async()=>{if(stopped)return;try{const result=await api.get(`/api/devices/telemetry/latest?ts=${Date.now()}`);for(const row of (Array.isArray(result?.machines)?result.machines:[])){if(row?.machine_id==null||!row?.reading_type)continue;const key=`${row.machine_id}:${row.reading_type}`;if(seen.get(key)===row.reading_id)continue;seen.set(key,row.reading_id);window.dispatchEvent(new CustomEvent('maintain-ai-telemetry',{detail:{...row,type:'telemetry'}}))}}catch{}if(!stopped)window.setTimeout(poll,15000)};poll();return()=>{stopped=true}},[]);return null}
function App(){const {user,loading}=useAuth();const [theme,setTheme]=useTheme();useReducedEffects();if(loading)return <div className="app-loading">Loading…</div>;if(!user)return <Login/>;return <PageHeaderProvider><TelemetryFallback/><AlertToastLayer/><div className="app-shell"><Sidebar/><main className="main-content"><Topbar theme={theme} setTheme={setTheme}/><div className="page-content"><Routes><Route path="/" element={<Dashboard/>}/><Route path="/machines" element={<Machines/>}/><Route path="/machines/:id" element={<MachineDetailRouter/>}/><Route path="/maintenance" element={<Maintenance/>}/><Route path="/work-orders" element={<WorkOrders/>}/><Route path="/faults" element={<Faults/>}/><Route path="/ai-assistant" element={<AIAssistant/>}/><Route path="/alerts" element={<Alerts/>}/><Route path="/spare-parts" element={<SpareParts/>}/><Route path="/reports" element={<Reports/>}/><Route path="/model-lab" element={<ModelLabConsole/>}/><Route path="/model-lab/compare" element={<ModelComparison/>}/><Route path="/history" element={<History/>}/><Route path="/settings" element={<SettingsPage/>}/><Route path="/about" element={<About/>}/></Routes></div></main></div></PageHeaderProvider>}
export default App
