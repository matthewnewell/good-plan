import { useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  useAddLine,
  useDeleteLine,
  useFunctions,
  usePlan,
  useRates,
  useSetWeeks,
  useSpread,
  useUpdateLine,
  useUpdatePlan,
} from '../api/hooks'
import type { Plan, PlanLine } from '../api/types'
import CostSection from '../components/CostSection'
import PlanChart, { type ChartSeries } from '../components/PlanChart'
import { FEE_LABEL } from '../components/PlanSettings'
import { money, moneyShort, num, shortDate } from '../lib/format'
import './PlanPage.css'

type Metric = 'hours' | 'fte' | 'cost'
type Mode = 'weekly' | 'cumulative'
type Unit = 'hours' | 'fte'

function mondayIso(d: Date): string {
  const m = new Date(d)
  m.setDate(m.getDate() - ((m.getDay() + 6) % 7))
  return `${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, '0')}-${String(m.getDate()).padStart(2, '0')}`
}

const round2 = (n: number) => Math.round(n * 100) / 100

export default function PlanPage() {
  const { planId } = useParams<{ planId: string }>()
  const { data: plan, isLoading, error } = usePlan(planId)

  if (isLoading) return <div className="plan-page__loading">Loading plan…</div>
  if (error || !plan) return <div className="plan-page__loading">That plan couldn't be loaded. <Link to="/">Back to plans</Link></div>
  return <PlanView plan={plan} />
}

type TabId = 'labor' | 'materials' | 'odc'
const TABS: { id: TabId; label: string; amount: (t: Plan['totals']) => number }[] = [
  { id: 'labor', label: 'Labor', amount: (t) => t.labor_cost },
  { id: 'materials', label: 'Materials', amount: (t) => t.material_cost },
  { id: 'odc', label: 'Other direct costs', amount: (t) => t.odc_cost },
]

function PlanView({ plan }: { plan: Plan }) {
  const [params, setParams] = useSearchParams()
  const tabParam = params.get('tab')
  const tab: TabId = tabParam === 'materials' || tabParam === 'odc' ? tabParam : 'labor'
  const setTab = (id: TabId) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (id === 'labor') next.delete('tab')
        else next.set('tab', id)
        return next
      },
      { replace: true },
    )
  const [chartOpen, setChartOpen] = useState(() => {
    try {
      return window.localStorage.getItem('good-plan:chart-open') !== '0'
    } catch {
      return true
    }
  })
  const toggleChart = () =>
    setChartOpen((open) => {
      try {
        window.localStorage.setItem('good-plan:chart-open', open ? '0' : '1')
      } catch {
        /* storage blocked — just won't be remembered */
      }
      return !open
    })
  const [metric, setMetric] = useState<Metric>('hours')
  const [mode, setMode] = useState<Mode>('weekly')
  const [showCats, setShowCats] = useState(false)
  const t = plan.totals
  const type = plan.contract_type
  const hasFee = type !== 'internal'

  // ── chart series ──────────────────────────────────────────────────────────────────────────
  const series = useMemo<ChartSeries[]>(() => {
    const cumulate = (vals: number[]) => vals.reduce<number[]>((acc, v) => [...acc, (acc[acc.length - 1] ?? 0) + v], [])
    // Cumulative FTE would be FTE-weeks, which nobody reads — FTE is always the weekly view.
    const shape = (vals: number[]) => (mode === 'cumulative' && metric !== 'fte' ? cumulate(vals) : vals)
    const perHour = metric === 'fte' ? 1 / plan.hours_per_fte_week : 1
    const total = plan.weeks.map((w) => (metric === 'cost' ? t.cost_by_week[w] : (t.hours_by_week[w] ?? 0) * perHour) ?? 0)
    const out: ChartSeries[] = [{ key: 'total', label: 'Total', values: shape(total), strong: true }]
    if (showCats && metric === 'cost') {
      const k = t.cost_by_week_kind
      const kinds: [string, Record<string, number>][] = [['Labor', k.labor], ['Materials', k.material], ['Other direct costs', k.odc]]
      for (const [label, byWeek] of kinds) out.push({ key: label, label, values: shape(plan.weeks.map((w) => byWeek[w] ?? 0)) })
    } else if (showCats) {
      const byCat = new Map<string, number[]>()
      for (const line of plan.lines) {
        const vals = plan.weeks.map((w) => {
          const h = line.hours[w] ?? 0
          return metric === 'cost' ? h * (line.effective_rate ?? 0) : h * perHour
        })
        const prev = byCat.get(line.category) ?? plan.weeks.map(() => 0)
        byCat.set(line.category, prev.map((v, i) => v + vals[i]))
      }
      for (const [cat, vals] of byCat) out.push({ key: cat, label: cat, values: shape(vals) })
    }
    return out
  }, [plan, metric, mode, showCats, t])

  // Cost can't exceed what the contract funds, so the line to watch is the budget base, not the
  // contract value (which includes fee).
  const refLine =
    metric === 'cost' && mode === 'cumulative' && t.contract_budget_base != null
      ? { value: t.contract_budget_base, label: `${hasFee ? 'Budget base' : 'Budget'} ${moneyShort(t.contract_budget_base)}` }
      : null

  const over = t.undistributed != null && t.undistributed < 0

  return (
    <div className="plan-page">
      <div className="plan-page__head">
        <div className="plan-page__title">
          <Link to="/" className="plan-page__back">← Plans</Link>
          <h1>{plan.project_name}</h1>
          {plan.portfolio_name && <span className="plan-page__portfolio">{plan.portfolio_name}</span>}
        </div>
        <nav className="plan-tabs" role="tablist" aria-label="Cost type">
          {TABS.map((tb) => (
            <button
              key={tb.id}
              role="tab"
              aria-selected={tab === tb.id}
              className={`plan-tabs__tab${tab === tb.id ? ' plan-tabs__tab--on' : ''}`}
              onClick={() => setTab(tb.id)}
            >
              {tb.label}
              <span className="plan-tabs__amt">{moneyShort(tb.amount(t))}</span>
            </button>
          ))}
        </nav>
      </div>

      {!plan.rates_reachable && (
        <div className="plan-page__banner">Reckon isn't reachable — pricing uses the last rates that loaded (if any).</div>
      )}
      {t.cost_outside_window > 0 && (
        <div className="plan-page__banner">
          {money(t.cost_outside_window)} of cost is dated beyond this plan's weeks — it counts in the totals but isn't on the chart. Extend the window (+ 4 weeks on the Labor tab).
        </div>
      )}
      {t.cost_unscheduled > 0 && (
        <div className="plan-page__banner">{money(t.cost_unscheduled)} of cost has no date, so it isn't on the chart yet. Give those lines a date.</div>
      )}
      {t.unpriced_hours > 0 && (
        <div className="plan-page__banner">
          {num(t.unpriced_hours)} labor hours have no rate. Pick a category from Reckon's table, or set a rate on the line.
        </div>
      )}

      {/* summary */}
      <section className="plan-tiles">
        <Tile
          label={hasFee ? 'Contract value' : 'Budget'}
          value={plan.contract_value != null ? money(plan.contract_value) : '—'}
          sub={
            t.contract_budget_base != null && hasFee
              ? `Budget base ${money(t.contract_budget_base)} (excludes fee)`
              : plan.contract_value == null
                ? 'Set it above'
                : undefined
          }
        />
        {hasFee && (
          <Tile
            label={`${FEE_LABEL[type]} (${plan.fee_percent}%)`}
            value={t.fee != null ? money(t.fee) : '—'}
            sub={
              type === 'cpaf' && t.award_fee != null
                ? `Award pool ${money(t.award_fee)} (${plan.award_fee_percent}%) — earned, not guaranteed`
                : type === 'cpff'
                  ? 'Fixed by the contract'
                  : type === 'ffp'
                    ? 'Planned profit on the price'
                    : undefined
            }
          />
        )}
        <Tile
          label={plan.include_burden ? 'Planned cost (burdened)' : 'Planned cost (direct)'}
          value={money(t.cost)}
          sub={`Labor ${moneyShort(t.labor_cost)} · Materials ${moneyShort(t.material_cost)} · Other ${moneyShort(t.odc_cost)}`}
        />
        <Tile
          label="Undistributed budget"
          value={t.undistributed != null ? money(t.undistributed) : '—'}
          sub={
            t.undistributed_pct != null
              ? over
                ? `${Math.abs(t.undistributed_pct).toFixed(0)}% OVER the budget base`
                : `${t.undistributed_pct.toFixed(0)}% of the budget base — shrinks as material, subcontract and travel are planned`
              : 'Needs a contract value'
          }
          tone={over ? 'critical' : undefined}
        />
        {type === 'ffp' && t.margin != null && (
          <Tile
            label="Margin vs price"
            value={money(t.margin)}
            sub={t.margin_pct != null ? `${t.margin_pct.toFixed(1)}% — labor only so far` : undefined}
            tone={t.margin < 0 ? 'critical' : undefined}
          />
        )}
        <Tile
          label="Labor hours"
          value={num(t.hours)}
          sub={`${num(t.hours / plan.hours_per_fte_week / Math.max(1, plan.weeks.length), 1)} avg FTE over ${plan.weeks.length} wks${t.hours > 0 ? ` · ${money(t.labor_cost / t.hours)}/h` : ''}`}
        />
      </section>


      {tab === 'labor' && (
        <>
        {/* chart */}
        <section className="plan-card">
          <div className="plan-card__head">
            <h2>
              {metric === 'cost' ? 'Planned cost over time' : 'Labor over time'}{' '}
              <button className="plan-card__collapse" onClick={toggleChart} aria-expanded={chartOpen}>
                {chartOpen ? 'Hide chart ▴' : 'Show chart ▾'}
              </button>
            </h2>
            {chartOpen && <div className="plan-toggles">
              <Segmented value={metric} onChange={setMetric} options={[['hours', 'Hours'], ['fte', 'FTE'], ['cost', 'Cost $']]} />
              {metric !== 'fte' && (
                <Segmented value={mode} onChange={setMode} options={[['weekly', 'Weekly'], ['cumulative', 'Cumulative']]} />
              )}
              <label className="plan-toggles__cats">
                <input type="checkbox" checked={showCats} onChange={(e) => setShowCats(e.target.checked)} /> {metric === 'cost' ? 'By cost type' : 'By category'}
              </label>
            </div>}
          </div>
          {chartOpen && (
            <PlanChart
              weeks={plan.weeks}
              series={series}
              format={metric === 'cost' ? moneyShort : metric === 'fte' ? (n) => num(n, 1) : (n) => num(n)}
              refLine={refLine}
            />
          )}
        </section>
          <Grid plan={plan} />
        </>
      )}
      {tab === 'materials' && (
        <CostSection
          plan={plan}
          kind="material"
          title="Materials"
          hint="Estimates, free-typed: what you'll buy, how many, at what price, and when you need it."
          addLabel="+ Add a material"
        />
      )}
      {tab === 'odc' && (
        <>
          <CostSection
            plan={plan}
            kind="subcontract"
            title="Subcontracts"
            hint="Work a vendor does for you. Pay it on milestones with Split."
            unitLabel="Amount"
            addLabel="+ Add a subcontract"
          />
          <CostSection
            plan={plan}
            kind="services"
            title="Services"
            hint="Consulting, test time, calibration — bought by the job or the month."
            unitLabel="Amount"
            addLabel="+ Add a service"
          />
          <CostSection
            plan={plan}
            kind="travel"
            title="Travel"
            hint="Use Calc to work a trip out from airfare, lodging, per diem and car."
            qtyLabel="Person-trips"
            unitLabel="Per person-trip"
            addLabel="+ Add travel"
          />
          <CostSection plan={plan} kind="other" title="Other" hint="Anything else you buy that isn't material." unitLabel="Amount" addLabel="+ Add other" />
        </>
      )}
    </div>
  )
}

function Tile({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: 'ok' | 'warn' | 'critical' }) {
  return (
    <div className={`plan-tile${tone ? ` plan-tile--${tone}` : ''}`}>
      <div className="plan-tile__label">{label}</div>
      <div className="plan-tile__value">{value}</div>
      {sub && <div className="plan-tile__sub">{sub}</div>}
    </div>
  )
}

function Segmented<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T
  onChange: (v: T) => void
  options: [T, string][]
}) {
  return (
    <span className="plan-seg">
      {options.map(([v, label]) => (
        <button key={v} className={value === v ? 'plan-seg__btn plan-seg__btn--on' : 'plan-seg__btn'} onClick={() => onChange(v)}>
          {label}
        </button>
      ))}
    </span>
  )
}

// ── the weekly grid ───────────────────────────────────────────────────────────────────────────
function Grid({ plan }: { plan: Plan }) {
  const { data: ratesData } = useRates()
  const { data: functionsData } = useFunctions()
  const addLine = useAddLine(plan.id)
  const updateLine = useUpdateLine(plan.id)
  const deleteLine = useDeleteLine(plan.id)
  const setWeeks = useSetWeeks(plan.id)
  const spread = useSpread(plan.id)
  const updatePlan = useUpdatePlan(plan.id)
  const [unit, setUnit] = useState<Unit>('hours')
  // A role is a Function, then a category inside it — a non-choice for most functions (they
  // hold exactly one category), a real pick only for Manufacturing. Falls back to Reckon's flat
  // rate list if Org Charts isn't reachable, so adding a line never dead-ends.
  const functions = functionsData?.functions ?? []
  const [newFunction, setNewFunction] = useState('')
  const categoriesFor = (fn: string) => functions.find((f) => f.name === fn)?.categories ?? []
  const [newCategory, setNewCategory] = useState('')
  const [fillFor, setFillFor] = useState<string | null>(null)
  const thisMonday = mondayIso(new Date())
  const hpw = plan.hours_per_fte_week
  const t = plan.totals

  const display = (h: number) => (h > 0 ? String(round2(unit === 'hours' ? h : h / hpw)) : '')
  // A line is ONE PERSON. Above a full week (1.0 FTE) they're over-allocated; well above it (1.25)
  // is unsustainable overtime. Team totals are allowed to exceed this — only person-lines are checked.
  const overClass = (h: number) => (h > hpw * 1.25 + 1e-6 ? ' plan-grid__cell--over-hard' : h > hpw + 1e-6 ? ' plan-grid__cell--over' : '')
  // "Machinist #2" — number people within a run of the same category.
  const ordinals = new Map<string, string>()
  {
    let prev = ''
    let n = 0
    const counts = new Map<string, number>()
    plan.lines.forEach((l) => counts.set(l.category, (counts.get(l.category) ?? 0) + 1))
    for (const l of plan.lines) {
      n = l.category === prev ? n + 1 : 1
      prev = l.category
      ordinals.set(l.id, (counts.get(l.category) ?? 0) > 1 ? ` #${n}` : '')
    }
  }

  function commitCell(line: PlanLine, week: string, text: string) {
    const trimmed = text.trim()
    const v = trimmed === '' ? 0 : Number(trimmed)
    if (Number.isNaN(v) || v < 0) return
    const hours = unit === 'hours' ? v : v * hpw
    if (round2(hours) === round2(line.hours[week] ?? 0)) return
    setWeeks.mutate({ lineId: line.id, weeks: { [week]: hours } })
  }

  const mutationError = [addLine, updateLine, deleteLine, setWeeks, spread, updatePlan].map((m) => m.error).find(Boolean)

  return (
    <section className="plan-card">
      <div className="plan-card__head">
        <h2>
          Labor plan <span className="plan-card__hint">one line per person · yellow above 1.0 FTE, red above 1.25</span>
        </h2>
        <div className="plan-toggles">
          <span className="plan-toggles__label">Cells show</span>
          <Segmented value={unit} onChange={setUnit} options={[['hours', 'Hours'], ['fte', 'FTE']]} />
          <button className="gp-btn gp-btn--ghost" onClick={() => updatePlan.mutate({ week_count: plan.week_count + 4 })}>
            + 4 weeks
          </button>
        </div>
      </div>
      {mutationError && <div className="plan-page__banner">{mutationError.message}</div>}

      <div className="plan-grid__scroll">
        <table className="plan-grid">
          <thead>
            <tr>
              <th className="plan-grid__cat">Labor category</th>
              <th>WBS</th>
              <th>Direct $/h</th>
              <th className="num">Hours</th>
              <th className="num">Cost</th>
              {plan.weeks.map((w) => (
                <th key={w} className={`plan-grid__wk${w === thisMonday ? ' plan-grid__wk--now' : w < thisMonday ? ' plan-grid__wk--past' : ''}`}>
                  {shortDate(w)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {plan.lines.map((line) => (
              <LineRows
                key={line.id}
                line={line}
                plan={plan}
                thisMonday={thisMonday}
                display={display}
                overClass={overClass}
                ordinal={ordinals.get(line.id) ?? ''}
                hpw={hpw}
                onCell={commitCell}
                onUpdate={(data) => updateLine.mutate({ id: line.id, ...data })}
                onDelete={() => deleteLine.mutate(line.id)}
                filling={fillFor === line.id}
                onToggleFill={() => setFillFor(fillFor === line.id ? null : line.id)}
                onFill={(fte, start, end) => {
                  spread.mutate({ lineId: line.id, fte, start, end }, { onSuccess: () => setFillFor(null) })
                }}
              />
            ))}
          </tbody>
          <tfoot>
            <tr className="plan-grid__total">
              <td className="plan-grid__cat">Total</td>
              <td />
              <td />
              <td className="num">{num(t.hours)}</td>
              <td className="num">{money(t.labor_cost)}</td>
              {plan.weeks.map((w) => (
                <td key={w} className="plan-grid__wk num">
                  {display(t.hours_by_week[w] ?? 0)}
                </td>
              ))}
            </tr>
            <tr className="plan-grid__total plan-grid__total--cost">
              <td className="plan-grid__cat">Cost</td>
              <td />
              <td />
              <td />
              <td />
              {plan.weeks.map((w) => (
                <td key={w} className="plan-grid__wk num">
                  {(t.cost_by_week_kind.labor[w] ?? 0) > 0 ? moneyShort(t.cost_by_week_kind.labor[w]) : ''}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>

      <form
        className="plan-add"
        onSubmit={(e) => {
          e.preventDefault()
          const c = newCategory.trim()
          if (!c) return
          addLine.mutate({ category: c }, { onSuccess: () => { setNewFunction(''); setNewCategory('') } })
        }}
      >
        <span className="plan-add__label">Add a person from</span>
        <select
          value={newFunction}
          onChange={(e) => {
            const fn = e.target.value
            setNewFunction(fn)
            const cats = categoriesFor(fn)
            setNewCategory(cats.length === 1 ? cats[0] : '')
          }}
        >
          <option value="" disabled>
            Function…
          </option>
          {functions.map((f) => (
            <option key={f.name} value={f.name}>
              {f.name}
              {f.manager_name ? ` — ${f.manager_name}` : ''}
            </option>
          ))}
        </select>
        {categoriesFor(newFunction).length > 1 && (
          <select value={newCategory} onChange={(e) => setNewCategory(e.target.value)}>
            <option value="" disabled>
              Category…
            </option>
            {categoriesFor(newFunction).map((cat) => {
              const rate = ratesData?.rates.find((r) => r.name === cat)
              return (
                <option key={cat} value={cat}>
                  {cat}
                  {rate ? ` — $${rate.avg_rate}/h direct · $${rate.loaded_rate}/h loaded` : ''}
                </option>
              )
            })}
          </select>
        )}
        <button className="gp-btn gp-btn--primary" type="submit" disabled={!newCategory.trim() || addLine.isPending}>
          + Add a person
        </button>
      </form>
    </section>
  )
}

function LineRows({
  line,
  plan,
  thisMonday,
  display,
  overClass,
  ordinal,
  hpw,
  onCell,
  onUpdate,
  onDelete,
  filling,
  onToggleFill,
  onFill,
}: {
  line: PlanLine
  plan: Plan
  thisMonday: string
  display: (h: number) => string
  overClass: (h: number) => string
  ordinal: string
  hpw: number
  onCell: (line: PlanLine, week: string, text: string) => void
  onUpdate: (data: { wbs?: string | null; rate_override?: number | null }) => void
  onDelete: () => void
  filling: boolean
  onToggleFill: () => void
  onFill: (fte: number, start: string, end: string) => void
}) {
  const overWeeks = plan.weeks.filter((w) => (line.hours[w] ?? 0) > hpw + 1e-6).length
  const [fte, setFte] = useState('1')
  const [from, setFrom] = useState(plan.weeks[0])
  const [to, setTo] = useState(plan.weeks[Math.min(plan.weeks.length - 1, 11)])

  return (
    <>
      <tr>
        <td className="plan-grid__cat">
          <div className="plan-grid__catrow">
            <span className="plan-grid__catname" title={line.note ?? undefined}>
              {line.category}
              {ordinal}
            </span>
            {overWeeks > 0 && (
              <span className="plan-grid__over-badge" title={`Planned above 1.0 FTE in ${overWeeks} week${overWeeks === 1 ? '' : 's'}`}>
                over {overWeeks} wk{overWeeks === 1 ? '' : 's'}
              </span>
            )}
            <span className="plan-grid__catactions">
              <button className="plan-grid__link" onClick={onToggleFill} title="Fill a range of weeks with a steady FTE">
                Fill
              </button>
              <button className="plan-grid__link plan-grid__link--danger" onClick={onDelete} title="Remove this line" aria-label="Remove line">
                ×
              </button>
            </span>
          </div>
        </td>
        <td>
          <input
            key={line.wbs ?? ''}
            className="plan-grid__wbs"
            defaultValue={line.wbs ?? ''}
            placeholder="—"
            onBlur={(e) => e.target.value.trim() !== (line.wbs ?? '') && onUpdate({ wbs: e.target.value.trim() || null })}
          />
        </td>
        <td>
          <div className="plan-grid__rate" title={line.effective_rate != null ? `Direct $${line.direct_rate}/h × ${line.burden_factor} burden = $${line.effective_rate}/h` : 'No rate for this category'}>
            <input
              key={String(line.rate_override)}
              defaultValue={line.rate_override ?? ''}
              placeholder={line.direct_rate != null ? String(line.direct_rate) : 'none'}
              inputMode="decimal"
              onBlur={(e) => {
                const raw = e.target.value.trim()
                const next = raw === '' ? null : Number(raw)
                if (next !== null && (Number.isNaN(next) || next <= 0)) return
                if (next !== line.rate_override) onUpdate({ rate_override: next })
              }}
            />
            <small>{line.effective_rate != null ? `= $${line.effective_rate.toFixed(0)}/h` : 'unpriced'}</small>
          </div>
        </td>
        <td className="num">{num(line.total_hours)}</td>
        <td className="num">{line.total_cost != null ? money(line.total_cost) : '—'}</td>
        {plan.weeks.map((w) => (
          <td key={w} className={`plan-grid__wk${w === thisMonday ? ' plan-grid__wk--now' : w < thisMonday ? ' plan-grid__wk--past' : ''}`}>
            <input
              key={`${w}:${line.hours[w] ?? 0}:${display(line.hours[w] ?? 0)}`}
              className={`plan-grid__cell${overClass(line.hours[w] ?? 0)}`}
              defaultValue={display(line.hours[w] ?? 0)}
              inputMode="decimal"
              onBlur={(e) => onCell(line, w, e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
            />
          </td>
        ))}
      </tr>
      {filling && (
        <tr className="plan-grid__fill">
          <td colSpan={5 + plan.weeks.length}>
            <div className="plan-fill">
              <span>Fill</span>
              <input value={fte} onChange={(e) => setFte(e.target.value)} inputMode="decimal" className="plan-fill__fte" />
              <span>FTE from</span>
              <select value={from} onChange={(e) => setFrom(e.target.value)}>
                {plan.weeks.map((w) => (
                  <option key={w} value={w}>
                    {shortDate(w)}
                  </option>
                ))}
              </select>
              <span>through</span>
              <select value={to} onChange={(e) => setTo(e.target.value)}>
                {plan.weeks.map((w) => (
                  <option key={w} value={w}>
                    {shortDate(w)}
                  </option>
                ))}
              </select>
              <button
                className="gp-btn gp-btn--primary"
                disabled={Number.isNaN(Number(fte)) || Number(fte) < 0 || to < from}
                onClick={() => onFill(Number(fte), from, to)}
              >
                Apply
              </button>
              <button className="gp-btn gp-btn--ghost" onClick={onToggleFill}>
                Cancel
              </button>
              <small>0 clears the range. It overwrites those weeks.</small>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
