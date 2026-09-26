import { useEffect, useMemo, useState } from 'react'
import api from '../api/client.js'
import { useDemoMode } from './DemoMode.jsx'

const DEMO_PARTS = [
  { id: 'demo-1', name: 'Motor Bearing 6205', part_number: 'BRG-6205', quantity: 2, minimum_stock: 5, compatible_machine_categories: 'induction_motor' },
  { id: 'demo-2', name: 'Compressor Seal Kit', part_number: 'SEAL-CMP-01', quantity: 6, minimum_stock: 3, compatible_machine_categories: 'compressor' },
  { id: 'demo-3', name: 'V-Belt A42', part_number: 'BELT-A42', quantity: 1, minimum_stock: 4, compatible_machine_categories: 'compressor,pump' },
  { id: 'demo-4', name: 'Pump Mechanical Seal', part_number: 'SEAL-PMP-02', quantity: 8, minimum_stock: 3, compatible_machine_categories: 'pump' },
]

function categories(part) { return String(part.compatible_machine_categories || '').split(',').map((v) => v.trim().toLowerCase()).filter(Boolean) }

export default function SparePartsIntelligence() {
  const demoMode = useDemoMode()
  const [machines, setMachines] = useState([])
  const [parts, setParts] = useState([])
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedMachine, setSelectedMachine] = useState('all')
  const [error, setError] = useState(null)

  useEffect(() => {
    if (demoMode) { setMachines([{ id: 'demo-m1', name: 'Compressor Demo', category: 'compressor' }, { id: 'demo-m2', name: 'Pump Demo', category: 'pump' }]); setParts(DEMO_PARTS); return }
    Promise.all([api.get('/api/machines'), api.get('/api/spare-parts')]).then(([m, p]) => { setMachines(m || []); setParts(p || []) }).catch((e) => setError(e?.message || 'Could not load spare-parts intelligence.'))
  }, [demoMode])

  const categoriesList = useMemo(() => [...new Set(parts.flatMap(categories))].sort(), [parts])
  const machine = machines.find((m) => String(m.id) === String(selectedMachine))
  const machineCategory = machine?.category?.toLowerCase()
  const compatible = useMemo(() => parts.filter((part) => (selectedCategory === 'all' || categories(part).includes(selectedCategory)) && (!machineCategory || categories(part).some((cat) => cat === machineCategory))), [parts, selectedCategory, machineCategory])
  const lowStock = parts.filter((p) => Number(p.quantity) <= Number(p.minimum_stock))
  const criticalStock = parts.filter((p) => Number(p.quantity) === 0)
  const coverage = parts.length ? Math.round((parts.filter((p) => Number(p.quantity) > Number(p.minimum_stock)).length / parts.length) * 100) : 0

  if (error) return <div className="panel section-gap"><div className="panel-body" style={{ color: 'var(--danger)' }}>{error}</div></div>
  return <div className="panel section-gap">
    <div className="panel-header"><div><span className="panel-title">Spare-parts Intelligence</span><div style={{ marginTop: 4, color: 'var(--text-faint)', fontSize: 11 }}>Compatibility and stock risk use the existing inventory and machine categories. No backend model or schema changes.</div></div>{demoMode && <span className="badge healthy">Demo data</span>}</div>
    <div className="panel-body">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10 }}><MiniStat label="Tracked parts" value={parts.length} /><MiniStat label="Low stock" value={lowStock.length} /><MiniStat label="Out of stock" value={criticalStock.length} /><MiniStat label="Stock coverage" value={`${coverage}%`} /></div>
      <div style={{ marginTop: 14, display: 'flex', gap: 10, flexWrap: 'wrap' }}><select value={selectedMachine} onChange={(e) => setSelectedMachine(e.target.value)} style={{ minWidth: 220 }}><option value="all">All machines</option>{machines.map((m) => <option key={m.id} value={m.id}>{m.name}{m.category ? ` · ${m.category}` : ''}</option>)}</select><select value={selectedCategory} onChange={(e) => setSelectedCategory(e.target.value)} style={{ minWidth: 190 }}><option value="all">All part categories</option>{categoriesList.map((cat) => <option key={cat} value={cat}>{cat}</option>)}</select></div>
      {machine && <div style={{ marginTop: 12, padding: 12, borderRadius: 10, border: '1px solid var(--border)', background: 'var(--panel-2)' }}><div style={{ fontWeight: 700 }}>Recommended inventory for {machine.name}</div><div style={{ color: 'var(--text-dim)', fontSize: 11, marginTop: 4 }}>{compatible.length} compatible part{compatible.length === 1 ? '' : 's'} found for category <span className="mono">{machine.category || 'unknown'}</span>.</div></div>}
      <div style={{ marginTop: 12, overflowX: 'auto' }}><table><thead><tr><th>Part</th><th>Compatible with</th><th>Stock risk</th><th>Gap</th><th>Last used</th></tr></thead><tbody>{compatible.map((p) => { const qty = Number(p.quantity); const min = Number(p.minimum_stock); const gap = Math.max(0, min - qty); const status = qty === 0 ? 'Out of stock' : qty <= min ? 'Reorder' : 'Healthy'; return <tr key={p.id}><td><div style={{ fontWeight: 600 }}>{p.name}</div><div className="mono" style={{ color: 'var(--text-faint)', fontSize: 10 }}>{p.part_number}</div></td><td>{categories(p).join(', ') || 'Unspecified'}</td><td><span className={'badge ' + (status === 'Healthy' ? 'healthy' : status === 'Reorder' ? 'warning' : 'critical')}>{status}</span></td><td className="mono">{gap ? `+${gap}` : '—'}</td><td>{p.last_used_date ? new Date(p.last_used_date).toLocaleDateString() : 'Never recorded'}</td></tr> })}{!compatible.length && <tr><td colSpan={5} className="empty-state">No compatible parts match the selected filters.</td></tr>}</tbody></table></div>
    </div>
  </div>
}
function MiniStat({ label, value }) { return <div style={{ padding: 12, borderRadius: 10, background: 'var(--panel-2)', border: '1px solid var(--border)' }}><div style={{ color: 'var(--text-faint)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '.05em' }}>{label}</div><div className="mono" style={{ marginTop: 6, fontSize: 22, fontWeight: 700 }}>{value}</div></div> }
