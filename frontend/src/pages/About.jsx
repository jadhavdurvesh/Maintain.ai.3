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
  { label: 'Predictive Model', value: 'scikit-learn RandomForest' },
]

export default function About() {
  usePageHeader('About')

  return (
    <div className="about-page">
      <div className="about-container">
        <div className="panel about-hero">
          <div className="about-logo-dot" />
          <h1 className="about-title">MAINTAIN AI</h1>
          <p className="about-tagline">
            Predictive maintenance and intelligent maintenance management for modern industrial operations.
          </p>
          <div className="about-divider" />
          <div className="about-section-title">CREATED BY</div>
          <div className="about-creators">
            {CREATORS.map((name) => <div className="about-creator" key={name}>{name}</div>)}
          </div>
        </div>

        <div className="panel section-gap">
          <div className="panel-header"><span className="panel-title">Platform</span></div>
          <div className="panel-body">
            <div className="about-stack">
              {STACK.map((item) => (
                <div className="about-stack-card" key={item.label}>
                  <div className="about-stack-label">{item.label}</div>
                  <div className="about-stack-value">{item.value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="about-footer">
          MAINTAIN AI · Predict · Prevent · Maintain
        </div>
      </div>
    </div>
  )
}
