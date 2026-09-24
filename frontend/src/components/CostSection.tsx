import { useState } from 'react'
import { useAddCost, useDeleteCost, useSetPhases, useUpdateCost, useWbs } from '../api/hooks'
import WbsPicker from './WbsPicker'
import type { CostKind, CostLine, Plan } from '../api/types'
import { money } from '../lib/format'
import './CostSection.css'

interface Props {
  plan: Plan
  kind: CostKind
  title: string
  /** One line saying what goes here. */
  hint: string
  qtyLabel?: string
  unitLabel?: string
  addLabel: string
}

const commas = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 2 })
const parseNum = (text: string) => Number(text.replace(/[$,\s]/g, ''))

/** One kind of non-labor cost — materials, or one of the "other direct costs" (subcontracts,
 * services, travel, other). Free-typed lines: description, quantity × unit cost, and WHEN it lands
 * (a single need date, or milestones for a payment schedule). Each line shows what it costs burdened
 * too, since a kind carries its own multiplier from Reckon. Everything commits on blur. */
export default function CostSection({ plan, kind, title, hint, qtyLabel = 'Qty', unitLabel = 'Unit cost', addLabel }: Props) {
  const addCost = useAddCost(plan.id)
  const lines = plan.costs.filter((c) => c.kind === kind)
  const [open, setOpen] = useState<{ id: string; mode: 'milestones' | 'travel' } | null>(null)
  const subtotal = lines.reduce((sum, c) => sum + c.loaded_total, 0)

  return (
    <section className="plan-card cost-section">
      <div className="plan-card__head">
        <div>
          <h2>
            {title} <span className="cost-section__count">{lines.length}</span>
          </h2>
          <p className="cost-section__hint">{hint}</p>
        </div>
        <div className="cost-section__subtotal">
          <span>{plan.include_burden ? 'With burden' : 'Direct'}</span>
          <strong>{money(subtotal)}</strong>
        </div>
      </div>

      {lines.length > 0 && (
        <div className="cost-section__scroll">
          <table className="cost-table">
            <thead>
              <tr>
                <th className="cost-table__desc">Description</th>
                <th>Vendor</th>
                <th>WBS</th>
                <th className="num">{qtyLabel}</th>
                <th className="num">{unitLabel}</th>
                <th className="num">Total</th>
                <th className="num">{plan.include_burden ? 'With burden' : 'Direct'}</th>
                <th>When</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {lines.map((c) => (
                <CostRows
                  key={c.id}
                  plan={plan}
                  line={c}
                  open={open?.id === c.id ? open.mode : null}
                  setOpen={(mode) => setOpen(mode ? { id: c.id, mode } : null)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div>
        <button className="gp-btn gp-btn--ghost" disabled={addCost.isPending} onClick={() => addCost.mutate({ kind })}>
          {addLabel}
        </button>
        {addCost.error && <span className="cost-section__error">{addCost.error.message}</span>}
      </div>
    </section>
  )
}

function CostRows({
  plan,
  line,
  open,
  setOpen,
}: {
  plan: Plan
  line: CostLine
  open: 'milestones' | 'travel' | null
  setOpen: (mode: 'milestones' | 'travel' | null) => void
}) {
  const update = useUpdateCost(plan.id)
  const remove = useDeleteCost(plan.id)
  const { data: wbs } = useWbs(plan.id)
  const text = (field: 'description' | 'vendor') => (
    <input
      key={`${field}:${line[field] ?? ''}`}
      className={`cost-table__input cost-table__input--${field}`}
      defaultValue={line[field] ?? ''}
      placeholder={field === 'description' ? 'What is it?' : '—'}
      onBlur={(e) => e.target.value.trim() !== (line[field] ?? '') && update.mutate({ id: line.id, [field]: e.target.value })}
      onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
    />
  )
  const number = (field: 'qty' | 'unit_cost') => (
    <input
      key={`${field}:${line[field]}`}
      className="cost-table__input cost-table__input--num"
      defaultValue={commas(line[field])}
      inputMode="decimal"
      onBlur={(e) => {
        const v = parseNum(e.target.value)
        if (Number.isNaN(v) || v < 0) return void (e.target.value = commas(line[field]))
        if (v !== line[field]) update.mutate({ id: line.id, [field]: v })
      }}
      onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
    />
  )
  const hasMilestones = line.phases.length > 0

  return (
    <>
      <tr>
        <td className="cost-table__desc">{text('description')}</td>
        <td>{text('vendor')}</td>
        <td>
          <WbsPicker wbs={wbs} value={line.wbs} onChange={(code) => code !== line.wbs && update.mutate({ id: line.id, wbs: code ?? '' })} />
          {update.error && <div className="cost-section__error">{update.error.message}</div>}
        </td>
        <td className="num">{number('qty')}</td>
        <td className="num">{number('unit_cost')}</td>
        <td className="num">{money(line.total)}</td>
        <td className="num cost-table__loaded" title={line.factor !== 1 ? `× ${line.factor} burden` : undefined}>
          {money(line.loaded_total)}
        </td>
        <td className="cost-table__when">
          {hasMilestones ? (
            <button className="cost-table__link" onClick={() => setOpen(open === 'milestones' ? null : 'milestones')}>
              {line.phases.length} milestone{line.phases.length === 1 ? '' : 's'}
            </button>
          ) : (
            <input
              key={line.need_date ?? 'none'}
              className="cost-table__date"
              type="date"
              defaultValue={line.need_date ?? ''}
              onChange={(e) => update.mutate({ id: line.id, need_date: e.target.value || null })}
            />
          )}
          {!line.need_date && !hasMilestones && <span className="cost-table__nodate">no date</span>}
        </td>
        <td className="cost-table__actions">
          <button className="cost-table__link" onClick={() => setOpen(open === 'milestones' ? null : 'milestones')} title="Split this cost across dates">
            {hasMilestones ? 'Edit' : 'Split'}
          </button>
          {line.kind === 'travel' && (
            <button className="cost-table__link" onClick={() => setOpen(open === 'travel' ? null : 'travel')} title="Work out the cost of a trip">
              Calc
            </button>
          )}
          <button className="cost-table__link cost-table__link--danger" onClick={() => remove.mutate(line.id)} title="Remove this line" aria-label="Remove line">
            ×
          </button>
        </td>
      </tr>
      {open === 'milestones' && (
        <tr className="cost-table__panel">
          <td colSpan={9}>
            <MilestoneEditor plan={plan} line={line} onClose={() => setOpen(null)} />
          </td>
        </tr>
      )}
      {open === 'travel' && (
        <tr className="cost-table__panel">
          <td colSpan={9}>
            <TravelCalc plan={plan} line={line} onClose={() => setOpen(null)} />
          </td>
        </tr>
      )}
    </>
  )
}

/** Pay a cost on several dates — a subcontract 30/30/40, a service billed quarterly. The percents
 * must total 100; clearing them puts the line back on its single date. */
function MilestoneEditor({ plan, line, onClose }: { plan: Plan; line: CostLine; onClose: () => void }) {
  const setPhases = useSetPhases(plan.id)
  const [rows, setRows] = useState<{ date: string; percent: string }[]>(
    line.phases.length
      ? line.phases.map((p) => ({ date: p.date, percent: String(p.percent) }))
      : [{ date: line.need_date ?? plan.start_week, percent: '100' }],
  )
  const total = rows.reduce((s, r) => s + (Number(r.percent) || 0), 0)
  const ok = Math.abs(total - 100) < 0.01 && rows.every((r) => r.date)

  return (
    <div className="milestones">
      <div className="milestones__rows">
        {rows.map((r, i) => (
          <div key={i} className="milestones__row">
            <input type="date" value={r.date} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, date: e.target.value } : x)))} />
            <input
              className="milestones__pct"
              value={r.percent}
              inputMode="decimal"
              onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, percent: e.target.value } : x)))}
            />
            <span>%</span>
            <span className="milestones__amt">{money((line.total * (Number(r.percent) || 0)) / 100)}</span>
            <button className="cost-table__link cost-table__link--danger" onClick={() => setRows(rows.filter((_, j) => j !== i))} aria-label="Remove milestone">
              ×
            </button>
          </div>
        ))}
      </div>
      <div className="milestones__foot">
        <button className="cost-table__link" onClick={() => setRows([...rows, { date: rows[rows.length - 1]?.date ?? plan.start_week, percent: '0' }])}>
          + Add milestone
        </button>
        <span className={ok || rows.length === 0 ? 'milestones__sum' : 'milestones__sum milestones__sum--bad'}>
          {rows.length === 0 ? 'No milestones — uses the single date' : `${total}% of 100%`}
        </span>
        <button className="gp-btn gp-btn--primary" disabled={(!ok && rows.length > 0) || setPhases.isPending} onClick={() => setPhases.mutate({ costId: line.id, phases: rows.map((r) => ({ date: r.date, percent: Number(r.percent) })) }, { onSuccess: onClose })}>
          Save
        </button>
        <button className="gp-btn gp-btn--ghost" onClick={() => setPhases.mutate({ costId: line.id, phases: [] }, { onSuccess: onClose })}>
          Clear
        </button>
        <button className="gp-btn gp-btn--ghost" onClick={onClose}>
          Cancel
        </button>
        {setPhases.error && <span className="cost-section__error">{setPhases.error.message}</span>}
      </div>
    </div>
  )
}

interface TravelDetail {
  trips: number
  travelers: number
  airfare: number
  lodging: number
  nights: number
  per_diem: number
  car: number
}

/** A trip, worked out: person-trips × (airfare + lodging × nights + per diem × days + car). Sets the
 * line's quantity (person-trips) and unit cost (per person-trip) and remembers the inputs. */
function TravelCalc({ plan, line, onClose }: { plan: Plan; line: CostLine; onClose: () => void }) {
  const update = useUpdateCost(plan.id)
  const saved: Partial<TravelDetail> = (() => {
    try {
      return line.detail ? JSON.parse(line.detail) : {}
    } catch {
      return {}
    }
  })()
  const [v, setV] = useState({
    trips: String(saved.trips ?? 1),
    travelers: String(saved.travelers ?? 1),
    airfare: String(saved.airfare ?? 650),
    lodging: String(saved.lodging ?? 175),
    nights: String(saved.nights ?? 3),
    per_diem: String(saved.per_diem ?? 74),
    car: String(saved.car ?? 180),
  })
  const n = (k: keyof typeof v) => Number(v[k]) || 0
  const perPersonTrip = n('airfare') + n('lodging') * n('nights') + n('per_diem') * (n('nights') + 1) + n('car')
  const personTrips = n('trips') * n('travelers')
  const field = (k: keyof typeof v, label: string) => (
    <label className="travel-calc__field">
      <span>{label}</span>
      <input value={v[k]} inputMode="decimal" onChange={(e) => setV({ ...v, [k]: e.target.value })} />
    </label>
  )

  return (
    <div className="travel-calc">
      <div className="travel-calc__fields">
        {field('trips', 'Trips')}
        {field('travelers', 'Travelers')}
        {field('airfare', 'Airfare / person')}
        {field('lodging', 'Lodging / night')}
        {field('nights', 'Nights')}
        {field('per_diem', 'Per diem / day')}
        {field('car', 'Car / trip')}
      </div>
      <div className="travel-calc__foot">
        <span>
          {personTrips} person-trip{personTrips === 1 ? '' : 's'} × {money(perPersonTrip)} = <strong>{money(personTrips * perPersonTrip)}</strong>
          <em> (per diem counts {n('nights') + 1} days)</em>
        </span>
        <button
          className="gp-btn gp-btn--primary"
          disabled={update.isPending || personTrips <= 0}
          onClick={() =>
            update.mutate(
              { id: line.id, qty: personTrips, unit_cost: perPersonTrip, detail: JSON.stringify({ ...Object.fromEntries(Object.entries(v).map(([k, x]) => [k, Number(x) || 0])) }) },
              { onSuccess: onClose },
            )
          }
        >
          Apply to line
        </button>
        <button className="gp-btn gp-btn--ghost" onClick={onClose}>
          Cancel
        </button>
      </div>
    </div>
  )
}

