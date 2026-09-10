import { usePageHeader } from '../PageHeaderContext.jsx'
import { Database, Code2, Monitor, Bot, BrainCircuit, Users } from 'lucide-react'

const CREATORS = ['Durvesh M. Jadhav', 'Shrikant K. Katkar', 'Viraj V. Patil']

const STACK = [
  { label: 'Backend', value: 'FastAPI · SQLAlchemy · SQLite', icon: Database },
  { label: 'Frontend', value: 'React · Vite · Recharts', icon: Code2 },
  { label: 'Desktop', value: 'Electron · PyInstaller', icon: Monitor },
  { label: 'AI Assistant', value: 'Offline knowledge-base + optional Gemini API', icon: Bot },
  { label: 'Predictive Model', value: 'scikit-learn RandomForest', icon: BrainCircuit },
]

export default function About() {
  usePageHeader('About')
  return (
    <div style={{ maxWidth: 980, margin: '0 auto', padding: '22px 18px 42px' }}>
      <section className="panel" style={{ textAlign: 'center', padding: '54px 34px 48px', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', width: 180, height: 180, borderRadius: '50%', background: 'var(--accent-glow)', filter: 'blur(12px)', left: '50%', top: -90, transform: 'translateX(-50%)', pointerEvents: 'none' }} />
        <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', gap: 8, marginBottom: 16, padding: '7px 12px', borderRadius: 999, border: '1px solid var(--border)', background: 'var(--panel-raised)', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--healthy)', boxShadow: '0 0 10px var(--healthy-glow)' }} />
          MAINTENANCE INTELLIGENCE PLATFORM
        </div>
        <h1 style={{ position: 'relative', margin: 0, fontSize: 'clamp(34px, 6vw, 60px)', lineHeight: 1, letterSpacing: '-0.04em', fontWeight: 700 }}>MAINTAIN <span style={{ color: 'var(--accent)' }}>AI</span></h1>
        <p style={{ maxWidth: 680, margin: '20px auto 0', color: 'var(--text-dim)', fontSize: 16, lineHeight: 1.7 }}>Predictive maintenance and intelligent maintenance management for modern industrial operations.</p>
        <div style={{ width: 72, height: 3, margin: '26px auto 0', borderRadius: 999, background: 'var(--accent)', boxShadow: '0 0 18px var(--accent-glow)' }} />
      </section>

      <section className="panel section-gap" style={{ textAlign: 'center' }}>
        <div className="panel-header" style={{ justifyContent: 'center' }}><span className="panel-title">Built by</span></div>
        <div className="panel-body" style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 12 }}>
          {CREATORS.map((name) => (
            <div key={name} style={{ display: 'inline-flex', alignItems: 'center', gap: 9, padding: '10px 14px', borderRadius: 12, border: '1px solid var(--border)', background: 'var(--panel-raised)', color: 'var(--text)', fontWeight: 600 }}>
              <Users size={16} style={{ color: 'var(--accent)' }} />{name}
            </div>
          ))}
        </div>
      </section>

      <section className="panel section-gap">
        <div className="panel-header" style={{ justifyContent: 'center' }}><span className="panel-title">Technology stack</span></div>
        <div className="panel-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
          {STACK.map((item) => {
            const Icon = item.icon
            return (
              <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: 16, borderRadius: 14, border: '1px solid var(--border)', background: 'var(--panel-raised)' }}>
                <div style={{ width: 38, height: 38, display: 'grid', placeItems: 'center', borderRadius: 11, background: 'var(--accent-dim)', color: 'var(--accent)', flexShrink: 0 }}><Icon size={19} /></div>
                <div style={{ minWidth: 0, textAlign: 'left' }}>
                  <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '.08em', color: 'var(--text-faint)', marginBottom: 3 }}>{item.label}</div>
                  <div style={{ color: 'var(--text)', lineHeight: 1.45 }}>{item.value}</div>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <footer style={{ textAlign: 'center', color: 'var(--text-faint)', fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '.08em', paddingTop: 8 }}>
        PREDICT · PREVENT · MAINTAIN
      </footer>
    </div>
  )
}
