import { useEffect, useState } from 'react'
import api from '../api/client.js'
import { Loading, ErrorState } from './Dashboard.jsx'
import { usePageHeader } from '../PageHeaderContext.jsx'
import SparePartsIntelligence from '../components/SparePartsIntelligence.jsx'

export default function SpareParts() {
  const [parts, setParts] = useState(null)
  const [machines, setMachines] = useState([])
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', part_number: '', quantity: 0, minimum_stock: 1, compatible_machine_categories: '' })

  usePageHeader('Spare Parts', <button className="btn" onClick={() => setShowForm((s) => !s)}>{showForm ? 'Cancel' : '+ Add Part'}</button>)
  const load = () => api.get('/api/spare-parts').then(setParts).catch((e) => setError(e.message))
  useEffect(() => {
    load()
    api.get('/api/machines').then(setMachines).catch(() => setMachines([]))
  }, [])

  const create = async (e) => {
    e.preventDefault()
    await api.post('/api/spare-parts', { ...form, quantity: Number(form.quantity), minimum_stock: Number(form.minimum_stock) })
    setForm({ name: '', part_number: '', quantity: 0, minimum_stock: 1, compatible_machine_categories: '' })
    setShowForm(false)
    load()
  }

  const setQty = async (id, quantity) => { await api.patch(`/api/spare-parts/${id}?quantity=${quantity}`); load() }
  const addMachineCompatibility = (machineId) => {
    const machine = machines.find((m) => String(m.id) === String(machineId))
    if (!machine) return
    const current = String(form.compatible_machine_categories || '').split(',').map((v) => v.trim()).filter(Boolean)
    const values = [machine.name, machine.machine_code, machine.category].filter(Boolean)
    const next = [...current]
    for (const value of values) if (!next.some((item) => item.toLowerCase() === String(value).toLowerCase())) next.push(value)
    setForm({ ...form, compatible_machine_categories: next.join(', ') })
  }

  if (error) return <ErrorState message={error} />
  if (!parts) return <Loading />
  return <>
    {showForm && <div className="panel section-gap"><form className="panel-body grid-3" onSubmit={create}>
      <div className="field"><label>Name</label><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
      <div className="field"><label>Part number</label><input required value={form.part_number} onChange={(e) => setForm({ ...form, part_number: e.target.value })} /></div>
      <div className="field"><label>Compatibility</label><input value={form.compatible_machine_categories} onChange={(e) => setForm({ ...form, compatible_machine_categories: e.target.value })} placeholder="Select a machine or enter a category" /><div style={{ marginTop: 6, color: 'var(--text-faint)', fontSize: 10 }}>You can select an existing machine below; its name, code and category are stored in the existing compatibility field.</div></div>
      <div className="field"><label>Compatible machine</label><select defaultValue="" onChange={(e) => { addMachineCompatibility(e.target.value); e.target.value = '' }}><option value="">Select existing machine…</option>{machines.map((m) => <option key={m.id} value={m.id}>{m.name}{m.machine_code ? ` · ${m.machine_code}` : ''}{m.category ? ` · ${m.category}` : ''}</option>)}</select></div>
      <div className="field"><label>Quantity</label><input type="number" min="0" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></div>
      <div className="field"><label>Minimum stock</label><input type="number" min="0" value={form.minimum_stock} onChange={(e) => setForm({ ...form, minimum_stock: e.target.value })} /></div>
      <button className="btn" type="submit" style={{ alignSelf: 'end' }}>Save</button>
    </form></div>}
    <div className="panel"><table><thead><tr><th>Part</th><th>Part #</th><th>Qty</th><th>Min</th><th>Status</th></tr></thead><tbody>
      {parts.map((p) => { const low = p.quantity <= p.minimum_stock; return <tr key={p.id}><td>{p.name}</td><td className="mono">{p.part_number}</td><td className="mono"><input type="number" min="0" style={{ width: 70 }} defaultValue={p.quantity} onBlur={(e) => Number(e.target.value) !== p.quantity && setQty(p.id, e.target.value)} /></td><td className="mono">{p.minimum_stock}</td><td>{low ? <span className="badge critical">Low stock</span> : <span className="badge healthy">OK</span>}</td></tr> })}
      {parts.length === 0 && <tr><td colSpan={5} className="empty-state">No spare parts tracked yet.</td></tr>}
    </tbody></table></div>
    <SparePartsIntelligence parts={parts} machines={machines} />
  </>
}
