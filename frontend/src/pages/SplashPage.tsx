import { Link } from 'react-router-dom'
import Nav from '../components/Nav'
import './SplashPage.css'

const ROWS = [
  { role: 'Program Manager', fte: 0.25, x: 10, w: 300 },
  { role: 'Systems Engineer', fte: 1.0, x: 10, w: 130 },
  { role: 'Mechanical Engineer', fte: 1.5, x: 60, w: 140 },
  { role: 'Machinist', fte: 2.0, x: 160, w: 140 },
  { role: 'Quality Inspector', fte: 0.5, x: 220, w: 90 },
]

const FEATURES = [
  {
    title: 'Demand, not commitment',
    body: 'A project says what it needs — a role, how much of it, and when. Deciding who actually fills that, from real availability, is a different job for a different persona: a complementary organizational app ("Big Plan") a functional manager uses, not built here.',
  },
  {
    title: 'One line per phase',
    body: "Demand for a role rarely holds flat for a whole program. Two lines — one lighter, one heavier — say more than a single number averaged across a project that doesn't move at one pace.",
  },
  {
    title: 'No fake precision',
    body: "Summing FTE across lines with different date ranges would imply a peak headcount this app doesn't actually know. So it doesn't — you see the real lines, not a computed total dressed up as one.",
  },
]

export default function SplashPage() {
  return (
    <div className="splash-page">
      <Nav />
      <div className="splash-page__scroll">
        <div className="splash-page__content">
          <header className="splash-hero">
            <h1 className="splash-hero__title">Good Plan</h1>
            <p className="splash-hero__sub">
              Define the labor a project needs, before anyone commits a person to it.
            </p>
            <div className="splash-hero__actions">
              <Link className="gp-btn gp-btn--primary" to="/">View the plan</Link>
            </div>
          </header>

          <figure className="splash-figure">
            <svg viewBox="0 0 360 200" role="img" aria-labelledby="gp-figure-title">
              <title id="gp-figure-title">
                Five roles, each demanding a different amount of FTE across a different slice of
                the program timeline — labor demand as it actually shapes up, not one flat number.
              </title>
              {ROWS.map((r, i) => {
                const y = 16 + i * 36
                return (
                  <g key={r.role}>
                    <text x={10} y={y - 6} className="splash-figure__label">{r.role}</text>
                    <rect x={r.x} y={y} width={r.w} height={18} rx={5} fill="var(--color-accent-soft)" stroke="var(--color-accent)" strokeWidth={1.5} />
                    <text x={r.x + r.w / 2} y={y + 13} textAnchor="middle" className="splash-figure__fte">{r.fte} FTE</text>
                  </g>
                )
              })}
            </svg>
          </figure>

          <div className="splash-grid">
            {FEATURES.map((f) => (
              <div key={f.title} className="splash-card">
                <div className="splash-card__heading">{f.title}</div>
                <p className="splash-card__body">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
