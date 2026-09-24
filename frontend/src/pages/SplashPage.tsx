import { Link } from 'react-router-dom'
import Nav from '../components/Nav'
import './SplashPage.css'

// The figure: one project's budget by cost element, against what the contract funds. Illustrative
// numbers; the point is the shape (every element of cost in one plan, and the gap left to plan).
const CONTRACT = 1000
const ELEMENTS = [
  { label: 'Labor', amount: 520, detail: 'hours by labor category, week by week', cls: 'labor' },
  { label: 'Materials', amount: 190, detail: 'parts and raw stock, by need date', cls: 'material' },
  { label: 'Subcontracts', amount: 110, detail: 'outside work, by milestone', cls: 'subcontract' },
  { label: 'ODCs', amount: 60, detail: 'travel, services, other direct costs', cls: 'odc' },
]

const FEATURES = [
  {
    title: 'Every element of cost',
    body: 'Labor, materials, subcontracts, and other direct costs (travel, services and the rest) in one plan, each spread over time against the WBS element it belongs to. The same shape as the estimate you bid, not just the labor part of it.',
  },
  {
    title: 'Labor priced from real history',
    body: "Labor is hours per category per week, priced at Reckon's historical rates by labor category instead of one blended guess. Labor Supply & Demand reads the same plan to see what staffing it asks for; override any rate when you know better.",
  },
  {
    title: 'Budget against the contract',
    body: 'Pick the contract type (cost plus fixed fee, award fee, firm fixed price, or internal) and see the fee and the undistributed budget, meaning what the contract funds that is not yet planned into labor, materials, or ODCs, as you plan.',
  },
]

function BudgetFigure() {
  const x0 = 10
  const width = 340
  const scale = width / CONTRACT
  let x = x0
  const planned = ELEMENTS.reduce((sum, e) => sum + e.amount, 0)
  return (
    <svg viewBox="0 0 360 214" role="img" aria-labelledby="gp-figure-title">
      <title id="gp-figure-title">
        One project's budget broken into labor, materials, subcontracts, and other direct costs,
        stacked against the contract value, with the undistributed budget still left to plan.
      </title>
      <text x={x0} y={14} className="splash-figure__label">Contract value</text>
      <text x={x0 + width} y={14} textAnchor="end" className="splash-figure__amt">$1.0M</text>
      {ELEMENTS.map((e) => {
        const w = e.amount * scale
        const seg = <rect key={e.label} x={x} y={22} width={w - 2} height={22} rx={3} className={`splash-seg splash-seg--${e.cls}`} />
        x += w
        return seg
      })}
      <rect x={x} y={22} width={x0 + width - x} height={22} rx={3} className="splash-seg splash-seg--ub" />
      <text x={(x + x0 + width) / 2} y={37} textAnchor="middle" className="splash-figure__ub">UB</text>
      {ELEMENTS.map((e, i) => {
        const y = 70 + i * 30
        return (
          <g key={e.label}>
            <rect x={x0} y={y - 9} width={10} height={10} rx={2} className={`splash-seg splash-seg--${e.cls}`} />
            <text x={x0 + 16} y={y} className="splash-figure__label">{e.label}</text>
            <text x={x0 + 16} y={y + 12} className="splash-figure__detail">{e.detail}</text>
            <text x={x0 + width} y={y} textAnchor="end" className="splash-figure__amt">${e.amount}K</text>
          </g>
        )
      })}
      <line x1={x0} x2={x0 + width} y1={184} y2={184} className="splash-figure__rule" />
      <text x={x0} y={202} className="splash-figure__label">Undistributed budget</text>
      <text x={x0 + width} y={202} textAnchor="end" className="splash-figure__amt splash-figure__amt--ub">${CONTRACT - planned}K</text>
    </svg>
  )
}

export default function SplashPage() {
  return (
    <div className="splash-page">
      <Nav />
      <div className="splash-page__scroll">
        <div className="splash-page__content">
          <header className="splash-hero">
            <h1 className="splash-hero__title">Let's make a plan.</h1>
            <p className="splash-hero__sub">
              Good Plan is a project's budget, built bottom-up: labor, materials, and other direct
              costs, planned over time against what the contract funds.
            </p>
            <div className="splash-hero__actions">
              <Link className="gp-btn gp-btn--primary" to="/">View the plan</Link>
            </div>
          </header>

          <figure className="splash-figure">
            <BudgetFigure />
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
