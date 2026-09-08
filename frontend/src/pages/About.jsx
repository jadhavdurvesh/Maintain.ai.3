import { usePageHeader } from '../PageHeaderContext.jsx'

const CREATORS = [
  'Durvesh M. Jadhav',
  'Shrikant K. Katkar',
  'Viraj V. Patil',
]

const STACK = [
  { label: 'Backend', value: 'FastAPI · SQLAlchemy · SQLite' },
  { label: 'Frontend', value: 'React · Vite · Recharts' },
  { label: 'Desktop', value: 'Electron · PyInstaller' },
  { label: 'AI Assistant', value: 'Offline knowledge-base engine + optional Gemini API' },
  { label: 'Predictive Model', value: 'scikit-learn RandomForest, trained locally on-device' },
]

export default function About() {
  usePageHeader('About')

  return (
    <div style={{ maxWidth: 640 }}>
      <div className="panel section-gap">
        <div className="panel-body" style={{ textAlign: 'center', padding: '40px 24px' }}>
          <div className="brand-mark" style={{ fontSize: 22, marginBottom: 6 }}>MAINTAIN AI</div>
          <div style={{ color: 'var(--text-faint)', fontSize: 13, marginBottom: 28 }}>
            AI-powered predictive maintenance &amp; intelligent maintenance management system
          </div>

          <div style={{ color: 'var(--text-faint)', fontSize: 11, letterSpacing: '0.04em', marginBottom: 10 }}>
            CREATED BY
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {CREATORS.map((name) => (
              <div key={name} style={{ fontSize: 16, fontWeight: 600 }}>{name}</div>
            ))}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header"><span className="panel-title">Built With</span></div>
        <div className="panel-body">
          {STACK.map((s) => (
            <div key={s.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ color: 'var(--text-faint)' }}>{s.label}</span>
              <span style={{ textAlign: 'right' }}>{s.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
