import { useEffect, useState } from 'react'
import api from '../api/client.js'

const fmt=(v,d=1)=>v==null?'—':Number(v).toFixed(d)
const pct=v=>v==null?'—':Number(v).toFixed(1)+'%'
export default function MachinePerformanceCard({machineId,canEdit=false}){
  const [month,setMonth]=useState(new Date().toISOString().slice(0,7))
  const [data,setData]=useState(null); const [busy,setBusy]=useState(false); const [error,setError]=useState('')
  const [profile,setProfile]=useState({started_on:'',rated_capacity:'',capacity_unit:'parts/hour',oee_target:'85'})
  const [monthly,setMonthly]=useState({month:'',planned_hours:'',manual_runtime_hours:'',total_units:'',good_units:'',rejected_units:'',ideal_cycle_seconds:''})
  const load=async()=>{try{const d=await api.get('/api/machines/'+machineId+'/performance?month='+month);setData(d);if(d.profile)setProfile({...profile,...d.profile,started_on:d.profile.started_on?.slice(0,10)||''});if(d.monthly)setMonthly({...monthly,...d.monthly})}catch(e){setError(e.message)}}
  useEffect(()=>{load()},[machineId,month])
  const saveProfile=async e=>{e.preventDefault();setBusy(true);try{await api.put('/api/machines/'+machineId+'/performance/profile',{started_on:profile.started_on||null,rated_capacity:profile.rated_capacity===''?null:Number(profile.rated_capacity),capacity_unit:profile.capacity_unit||null,oee_target:profile.oee_target===''?null:Number(profile.oee_target)});await load()}catch(e){setError(e.message)}finally{setBusy(false)}}
  const saveMonth=async e=>{e.preventDefault();setBusy(true);try{await api.put('/api/machines/'+machineId+'/performance/month',{month,planned_hours:monthly.planned_hours===''?null:Number(monthly.planned_hours),manual_runtime_hours:monthly.manual_runtime_hours===''?null:Number(monthly.manual_runtime_hours),total_units:monthly.total_units===''?null:Number(monthly.total_units),good_units:monthly.good_units===''?null:Number(monthly.good_units),rejected_units:monthly.rejected_units===''?null:Number(monthly.rejected_units),ideal_cycle_seconds:monthly.ideal_cycle_seconds===''?null:Number(monthly.ideal_cycle_seconds)});await load()}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <div className="panel section-gap"><div className="panel-header"><div><span className="panel-title">Machine Performance</span><div style={{fontSize:11,color:'var(--text-faint)',marginTop:4}}>Automatic KPIs from telemetry and maintenance history, with manual production inputs</div></div><input type="month" value={month} onChange={e=>setMonth(e.target.value)}/></div>
  <div className="panel-body">
    {error&&<div style={{color:'var(--critical)',fontSize:12,marginBottom:10}}>{error}</div>}
    <div className="stat-grid">
      <div className="stat-tile"><div className="stat-label">STARTED ON</div><div className="stat-value" style={{fontSize:16}}>{data?.started_on?new Date(data.started_on).toLocaleDateString():'—'}</div></div>
      <div className="stat-tile"><div className="stat-label">CURRENT WORKING HRS</div><div className="stat-value">{fmt(data?.current_working_hours,1)} h</div></div>
      <div className="stat-tile"><div className="stat-label">CAPACITY</div><div className="stat-value" style={{fontSize:16}}>{data?.capacity==null?'—':fmt(data.capacity,1)+' '+(data.capacity_unit||'')}</div></div>
      <div className="stat-tile"><div className="stat-label">MTBF</div><div className="stat-value">{data?.mtbf_hours==null?'—':fmt(data.mtbf_hours,1)+' h'}</div></div>
      <div className="stat-tile"><div className="stat-label">MTTR</div><div className="stat-value">{data?.mttr_minutes==null?'—':fmt(data.mttr_minutes,1)+' min'}</div></div>
      <div className="stat-tile"><div className="stat-label">AVAILABILITY</div><div className="stat-value">{pct(data?.availability_percent)}</div></div>
      <div className="stat-tile"><div className="stat-label">OEE</div><div className="stat-value">{pct(data?.oee_percent)}</div></div>
      <div className="stat-tile"><div className="stat-label">PERIOD RUNTIME</div><div className="stat-value">{fmt(data?.period_working_hours,1)} h</div><div style={{fontSize:10,color:'var(--text-faint)',marginTop:3}}>{data?.runtime_source||'No data'}</div></div>
    </div>
    <div style={{marginTop:14,padding:12,border:'1px solid var(--border)',borderRadius:10,fontSize:12,color:'var(--text-dim)'}}>
      OEE = Availability × Performance × Quality. Current OEE is shown only when the required production inputs are available; the system does not invent KPI values.
      {data?.oee_target!=null&&<span> Target: {fmt(data.oee_target,0)}%.</span>}
    </div>
    {canEdit&&<details style={{marginTop:14}}><summary style={{cursor:'pointer',fontWeight:700}}>Enter / update performance data</summary>
      <form onSubmit={saveProfile} style={{marginTop:12}}><div className="grid-3">
        <div className="field"><label>Started on</label><input type="date" value={profile.started_on||''} onChange={e=>setProfile({...profile,started_on:e.target.value})}/></div>
        <div className="field"><label>Rated capacity</label><input type="number" min="0" step="0.01" value={profile.rated_capacity??''} onChange={e=>setProfile({...profile,rated_capacity:e.target.value})}/></div>
        <div className="field"><label>Capacity unit</label><input value={profile.capacity_unit||''} onChange={e=>setProfile({...profile,capacity_unit:e.target.value})} placeholder="parts/hour"/></div>
        <div className="field"><label>OEE target %</label><input type="number" min="0" max="100" step="0.1" value={profile.oee_target??''} onChange={e=>setProfile({...profile,oee_target:e.target.value})}/></div>
      </div><button className="btn" disabled={busy}>Save machine data</button></form>
      <form onSubmit={saveMonth} style={{marginTop:16}}><div className="grid-3">
        <div className="field"><label>Planned production hours</label><input type="number" min="0" step="0.1" value={monthly.planned_hours??''} onChange={e=>setMonthly({...monthly,planned_hours:e.target.value})}/></div>
        <div className="field"><label>Manual runtime hours (fallback)</label><input type="number" min="0" step="0.1" value={monthly.manual_runtime_hours??''} onChange={e=>setMonthly({...monthly,manual_runtime_hours:e.target.value})}/></div>
        <div className="field"><label>Total units produced</label><input type="number" min="0" step="1" value={monthly.total_units??''} onChange={e=>setMonthly({...monthly,total_units:e.target.value})}/></div>
        <div className="field"><label>Good units</label><input type="number" min="0" step="1" value={monthly.good_units??''} onChange={e=>setMonthly({...monthly,good_units:e.target.value})}/></div>
        <div className="field"><label>Rejected units</label><input type="number" min="0" step="1" value={monthly.rejected_units??''} onChange={e=>setMonthly({...monthly,rejected_units:e.target.value})}/></div>
        <div className="field"><label>Ideal cycle time (seconds/unit)</label><input type="number" min="0" step="0.01" value={monthly.ideal_cycle_seconds??''} onChange={e=>setMonthly({...monthly,ideal_cycle_seconds:e.target.value})}/></div>
      </div><button className="btn" disabled={busy}>Save {month} production data</button></form>
    </details>}
  </div></div>
}
