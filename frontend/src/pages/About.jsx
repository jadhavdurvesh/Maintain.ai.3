import { usePageHeader } from '../PageHeaderContext.jsx'
import { Database, Code2, Monitor, Bot, BrainCircuit, Users, Radio, Cpu, ShieldCheck, Smartphone } from 'lucide-react'

const CREATORS = ['Durvesh M. Jadhav', 'Shrikant K. Katkar', 'Viraj V. Patil']

const STACK = [
  { label: 'Backend', value: 'FastAPI · SQLAlchemy · PostgreSQL / Neon', icon: Database },
  { label: 'Web control center', value: 'React · Vite · Recharts', icon: Code2 },
  { label: 'Mobile workforce', value: 'Android · Flutter Workforce Client', icon: Smartphone },
  { label: 'Realtime', value: 'Supabase Auth · Realtime with tenant + machine scope', icon: Radio },
  { label: 'IoT layer', value: 'Maintain.ai IoT Gateway · machine device-key telemetry', icon: Cpu },
  { label: 'AI & ML', value: 'Online behaviour · degradation · temporal evidence · advanced models', icon: BrainCircuit },
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
        <p style={{ maxWidth: 680, margin: '20px auto 0', color: 'var(--text-dim)', fontSize: 16, lineHeight: 1.7 }}>A multi-client predictive maintenance platform connecting engineering, workforce, mobile operations, and industrial telemetry in one organization-scoped system.</p>
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
        <div className="panel-header" style={{ justifyContent: 'center' }}><span className="panel-title">How Maintain.ai works</span></div>
        <div className="panel-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
          {[
            ['01', 'Connect', 'Machines send telemetry through machine-specific device identity.'],
            ['02', 'Understand', 'Telemetry becomes live health, behaviour, degradation, faults, alerts, and maintenance evidence.'],
            ['03', 'Coordinate', 'Engineering plans work while technicians operate only on machines and work orders they are authorized to access.'],
            ['04', 'Learn', 'Maintenance outcomes become ML evidence without presenting heuristics as unsupported failure probabilities.'],
          ].map(([n, title, text]) => (
            <div key={n} style={{ padding: 18, borderRadius: 14, border: '1px solid var(--border)', background: 'var(--panel-raised)' }}>
              <div style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontSize: 11, marginBottom: 8 }}>{n}</div>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>{title}</div>
              <div style={{ color: 'var(--text-dim)', lineHeight: 1.55, fontSize: 13 }}>{text}</div>
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

      <section className="panel section-gap">
        <div className="panel-header" style={{ justifyContent: 'center' }}><span className="panel-title">Built around isolation</span></div>
        <div className="panel-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 }}>
          {[
            ['Organization scope', 'Every tenant-owned resource resolves through the authenticated organization.'],
            ['Machine assignment', 'Technicians receive only assigned active machines and their operational resources.'],
            ['Application access', 'Engineering, Android, and Workforce access are explicit application permissions.'],
            ['Realtime authorization', 'Engineering uses organization scope; mobile workforce clients use authorized machine scope.'],
          ].map(([title, text]) => (
            <div key={title} style={{ display: 'flex', gap: 12, padding: 16, borderRadius: 14, border: '1px solid var(--border)', background: 'var(--panel-raised)' }}>
              <ShieldCheck size={19} style={{ color: 'var(--accent)', flexShrink: 0 }} />
              <div><div style={{ fontWeight: 650, marginBottom: 4 }}>{title}</div><div style={{ color: 'var(--text-dim)', fontSize: 13, lineHeight: 1.5 }}>{text}</div></div>
            </div>
          ))}
        </div>
      </section>

      <footer style={{ textAlign: 'center', color: 'var(--text-faint)', fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '.08em', paddingTop: 8 }}>
        PREDICT · PREVENT · MAINTAIN
      </footer>
    </div>
  )
}
