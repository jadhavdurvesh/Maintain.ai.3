import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../api/client.js'
import { Loading, ErrorState } from '../pages/Dashboard.jsx'
import MachineDetail from '../pages/MachineDetail.jsx'
import SpecializedMachineDetail from './SpecializedMachineDetail.jsx'

const SPECIALIZED = new Set(['cnc','robot','lathe','milling_machine','drill_press','grinding_machine','hydraulic_press','injection_molding','packaging_machine','generator','transformer','boiler','furnace','hvac','fan_blower','gearbox','turbine','crane_hoist','specialized_other'])
const isSpecialized = category => SPECIALIZED.has(String(category || '')) || String(category || '').startsWith('robot_')

export default function MachineDetailRouter() {
  const { id } = useParams(); const [machine,setMachine]=useState(null); const [error,setError]=useState(null)
  useEffect(()=>{let cancelled=false;setMachine(null);setError(null);api.get(`/api/machines/${id}`).then(m=>{if(!cancelled)setMachine(m)}).catch(e=>{if(!cancelled)setError(e.message||'Unable to load machine')});return()=>{cancelled=true}},[id])
  if(error)return <ErrorState message={error}/>
  if(!machine)return <Loading/>
  return isSpecialized(machine.category) ? <SpecializedMachineDetail/> : <MachineDetail/>
}
