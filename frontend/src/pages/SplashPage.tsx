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
    title: 'Priced from real history',
    body: "Labor rates come from Reckon's historical averages by labor category, not a single blended guess — so a shift from junior to senior hours moves the budget the way it really would. Override any line when you know better.",
  },
  {
    title: 'Weekly, like a schedule',
    body: 'Allocate hours per category per week, fill a range with a steady FTE, and watch labor over time — hours or dollars, weekly or cumulative, against the contract value.',
  },
  {
    title: 'Budget against the contract',
    body: 'Pick the contract type (cost plus fixed fee, award fee, firm fixed price, or internal) and see the fee and the undistributed budget — what the contract funds that is not yet planned into work — as you plan. Labor Supply & Demand reads the same plan to see what staffing it asks for.',
  },
]

export default function SplashPage() {
  return (
    <div className="splash-page">
      <Nav />
      <div className="splash-page__scroll">
        <div className="splash-page__content">
          <header className="splash-hero">
            <h1 className="splash-hero__title">Let's make a plan.</h1>
            <p className="splash-hero__sub">
              Good Plan helps you plan labor, materials, subcontracts, and travel against your
              project budget.
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
