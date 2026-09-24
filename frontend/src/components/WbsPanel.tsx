import { useState } from 'react'
import { useAddWbsElement, useDeleteWbsElement, usePromoteWbs, useRenameWbsElement, useWbs } from '../api/hooks'
import type { Plan, Wbs, WbsElement } from '../api/types'
import { money, num } from '../lib/format'
import './WbsPanel.css'

/** The plan's budget by WBS element: every labor line, material and ODC sits on a work package
 * (a leaf), and each grouping element rolls up the packages under it. Scope Manager owns the WBS
 * once a project has one there; until then (a pursuit) the plan keeps its own draft, edited here. */

interface Roll {
  hours: number
  labor: number
  material: number
  odc: number
  lines: number
}

const zero = (): Roll => ({ hours: 0, labor: 0, material: 0, odc: 0, lines: 0 })
const total = (r: Roll) => r.labor + r.material + r.odc

function rollup(plan: Plan, wbs: Wbs) {
  const leaves = new Set(wbs.elements.filter((e) => e.leaf).map((e) => e.code))
  const byCode = new Map<string, Roll>(wbs.elements.map((e) => [e.code, zero()]))
  const parentOf = new Map(wbs.elements.map((e) => [e.code, e.parent_code]))
  const off = zero()
  const offLines: { label: string; code: string | null; amount: number }[] = []

  const add = (code: string | null, part: Partial<Roll>, label: string) => {
    const onLeaf = code != null && leaves.has(code)
    if (!onLeaf) {
      off.hours += part.hours ?? 0
      off.labor += part.labor ?? 0
      off.material += part.material ?? 0
      off.odc += part.odc ?? 0
      off.lines += 1
      offLines.push({ label, code, amount: (part.labor ?? 0) + (part.material ?? 0) + (part.odc ?? 0) })
      return
    }
    // The package itself, then every element above it.
    for (let c: string | null | undefined = code; c; c = parentOf.get(c)) {
      const r = byCode.get(c)
      if (!r) break
      r.hours += part.hours ?? 0
      r.labor += part.labor ?? 0
      r.material += part.material ?? 0
      r.odc += part.odc ?? 0
      r.lines += 1
    }
  }

  const seen = new Map<string, number>()
  for (const l of plan.lines) {
    seen.set(l.category, (seen.get(l.category) ?? 0) + 1)
    add(l.wbs, { hours: l.total_hours, labor: l.total_cost ?? 0 }, `${l.category} #${seen.get(l.category)}`)
  }
  for (const c of plan.costs) {
    const part = c.kind === 'material' ? { material: c.loaded_total } : { odc: c.loaded_total }
    add(c.wbs, part, c.description || c.kind)
  }
  return { byCode, off, offLines }
}

export default function WbsPanel({ plan }: { plan: Plan }) {
  const { data: wbs, isLoading, error } = useWbs(plan.id)
  if (isLoading) return <section className="plan-card wbs-panel">Loading the WBS…</section>
  if (error || !wbs) return <section className="plan-card wbs-panel">The WBS couldn't be loaded.</section>
  return <Panel plan={plan} wbs={wbs} />
}

function Panel({ plan, wbs }: { plan: Plan; wbs: Wbs }) {
  const { byCode, off, offLines } = rollup(plan, wbs)
  const add = useAddWbsElement(plan.id)
  const rename = useRenameWbsElement(plan.id)
  const remove = useDeleteWbsElement(plan.id)
  const promote = usePromoteWbs(plan.id)
  const err = [add, rename, remove, promote].map((m) => m.error).find(Boolean)
  const fromScope = wbs.source === 'scope_manager'
  const planTotal = plan.totals.cost
  const depth = (code: string) => code.split('.').length - 1

  const send = () => {
    if (
      window.confirm(
        'Send this draft WBS to Scope Manager? Scope Manager owns it from then on (codes, titles, progress), and it is no longer edited here. Every line keeps its work package.',
      )
    )
      promote.mutate(undefined)
  }

  return (
    <section className="plan-card wbs-panel">
      <div className="plan-card__head">
        <h2>
          Budget by WBS{' '}
          <span className={`wbs-panel__source wbs-panel__source--${wbs.source}`}>
            {fromScope ? 'from Scope Manager' : wbs.source === 'draft' ? 'draft' : 'not set up'}
          </span>
        </h2>
        {fromScope && (
          <a className="gp-btn gp-btn--ghost" href={wbs.scope_manager_url} target="_blank" rel="noreferrer">
            Edit the WBS in Scope Manager ↗
          </a>
        )}
        {wbs.can_promote && (
          <button className="gp-btn gp-btn--primary" onClick={send} disabled={promote.isPending}>
            {promote.isPending ? 'Sending…' : 'Send the WBS to Scope Manager'}
          </button>
        )}
      </div>

      <div className="wbs-panel__intro">
        {fromScope && (
          <p>
            Scope Manager owns this project's WBS: its scope, charge numbers and progress. Every labor line,
            material and ODC here sits on one of its work packages, which is how Reckon lines budget, progress
            and S4 actuals up per element.
          </p>
        )}
        {wbs.source !== 'scope_manager' && wbs.phase === 'pursuit' && (
          <p>
            <strong>A pursuit has no WBS in Scope Manager yet, so this plan keeps a draft.</strong> The estimate
            and Labor Supply &amp; Demand's forward-looking staffing are built on it. Capture and proposal effort
            itself charges to{' '}
            {wbs.bp_charge_number ? (
              <>
                the pursuit&rsquo;s B&amp;P (bid and proposal) charge number <code>{wbs.bp_charge_number}</code> from S4
              </>
            ) : (
              'the pursuit\u2019s B&P (bid and proposal) charge number from S4'
            )}
            , not to this WBS. Once the work is awarded, the draft goes to Scope Manager.
          </p>
        )}
        {wbs.source !== 'scope_manager' && wbs.phase !== 'pursuit' && (
          <p>
            This project has no WBS in Scope Manager.{' '}
            {wbs.source === 'draft'
              ? 'The draft below is what the plan budgets against. Send it over so Scope Manager owns it.'
              : 'Set it up in Scope Manager, or build a draft here and send it over.'}{' '}
            <a href={wbs.scope_manager_url} target="_blank" rel="noreferrer">
              Open Scope Manager ↗
            </a>
          </p>
        )}
        {!wbs.reachable && <p className="wbs-panel__warn">Scope Manager isn't reachable right now, so a project WBS there can't be shown.</p>}
      </div>

      {err && <div className="plan-page__banner">{err.message}</div>}

      <table className="wbs-table">
        <thead>
          <tr>
            <th className="wbs-table__code">WBS</th>
            <th>Element</th>
            <th className="num">Labor hours</th>
            <th className="num">Labor</th>
            <th className="num">Materials</th>
            <th className="num">ODCs</th>
            <th className="num">Total</th>
            <th className="num">Share</th>
            {fromScope ? <th>Charge no. · progress</th> : <th />}
          </tr>
        </thead>
        <tbody>
          {wbs.elements.map((e) => {
            const r = byCode.get(e.code) ?? zero()
            return (
              <Row
                key={e.code}
                el={e}
                r={r}
                depth={depth(e.code)}
                share={planTotal ? total(r) / planTotal : 0}
                fromScope={fromScope}
                editable={wbs.editable}
                onAddChild={() => {
                  const title = window.prompt(`New element under ${e.code} ${e.title}:`)
                  if (title?.trim()) add.mutate({ title: title.trim(), parent_code: e.code })
                }}
                onRename={(title) => rename.mutate({ id: e.id, title })}
                onDelete={() => remove.mutate(e.id)}
              />
            )
          })}
          {wbs.elements.length === 0 && (
            <tr>
              <td colSpan={9} className="wbs-table__empty">
                No WBS yet. {wbs.editable ? 'Add its top-level elements below, then the work packages under them.' : ''}
              </td>
            </tr>
          )}
          {off.lines > 0 && (
            <tr className="wbs-table__off">
              <td className="wbs-table__code">—</td>
              <td>
                <strong>Not on a work package</strong>
                <div className="wbs-table__offlist">
                  {offLines.slice(0, 6).map((l, i) => (
                    <span key={i}>
                      {l.label}
                      {l.code ? ` (${l.code})` : ''}
                    </span>
                  ))}
                  {offLines.length > 6 && <span>+{offLines.length - 6} more</span>}
                </div>
              </td>
              <td className="num">{num(off.hours)}</td>
              <td className="num">{money(off.labor)}</td>
              <td className="num">{money(off.material)}</td>
              <td className="num">{money(off.odc)}</td>
              <td className="num">{money(total(off))}</td>
              <td className="num">{planTotal ? `${Math.round((total(off) / planTotal) * 100)}%` : ''}</td>
              <td className="wbs-table__hint">Pick a work package on each line</td>
            </tr>
          )}
        </tbody>
      </table>

      {wbs.editable && <AddTop onAdd={(title) => add.mutate({ title })} pending={add.isPending} />}
    </section>
  )
}

function Row({
  el,
  r,
  depth,
  share,
  fromScope,
  editable,
  onAddChild,
  onRename,
  onDelete,
}: {
  el: WbsElement
  r: Roll
  depth: number
  share: number
  fromScope: boolean
  editable: boolean
  onAddChild: () => void
  onRename: (title: string) => void
  onDelete: () => void
}) {
  const [editing, setEditing] = useState(false)
  // A work package with budget can't be split: its lines would end up on a grouping element.
  const canSplit = !el.leaf || r.lines === 0
  return (
    <tr className={el.leaf ? 'wbs-table__leaf' : 'wbs-table__group'}>
      <td className="wbs-table__code">{el.code}</td>
      <td>
        <span className="wbs-table__title" style={{ paddingLeft: depth * 16 }}>
          {editing ? (
            <input
              autoFocus
              defaultValue={el.title}
              onBlur={(e) => {
                setEditing(false)
                if (e.target.value.trim() && e.target.value.trim() !== el.title) onRename(e.target.value.trim())
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
                if (e.key === 'Escape') setEditing(false)
              }}
            />
          ) : (
            el.title
          )}
          {el.leaf && <span className="wbs-table__wp" title="A work package: lines sit here">WP</span>}
        </span>
      </td>
      <td className="num">{r.hours ? num(r.hours) : ''}</td>
      <td className="num">{r.labor ? money(r.labor) : ''}</td>
      <td className="num">{r.material ? money(r.material) : ''}</td>
      <td className="num">{r.odc ? money(r.odc) : ''}</td>
      <td className="num wbs-table__total">{total(r) ? money(total(r)) : el.leaf ? <span className="wbs-table__nobudget">no budget</span> : ''}</td>
      <td className="num">
        {share > 0 && (
          <span className="wbs-table__share">
            <span style={{ width: `${Math.min(100, share * 100)}%` }} />
          </span>
        )}
      </td>
      {fromScope ? (
        <td className="wbs-table__meta">
          {el.charge_number && <code>{el.charge_number}</code>}
          {el.leaf && el.percent_complete != null && <span className="wbs-table__pct">{el.percent_complete}%</span>}
        </td>
      ) : (
        <td className="wbs-table__actions">
          {editable && (
            <>
              <button onClick={() => setEditing(true)} title="Rename">
                Rename
              </button>
              <button
                onClick={onAddChild}
                disabled={!canSplit}
                title={canSplit ? 'Add an element under this one' : `Move the ${r.lines} line(s) on ${el.code} first; budget can't sit on a grouping element`}
              >
                + Under
              </button>
              <button onClick={onDelete} className="wbs-table__del" title="Remove (only when it's empty)" aria-label={`Remove ${el.code}`}>
                ×
              </button>
            </>
          )}
        </td>
      )}
    </tr>
  )
}

function AddTop({ onAdd, pending }: { onAdd: (title: string) => void; pending: boolean }) {
  const [title, setTitle] = useState('')
  const submit = () => {
    if (!title.trim()) return
    onAdd(title.trim())
    setTitle('')
  }
  return (
    <div className="wbs-panel__add">
      <input
        value={title}
        placeholder="New top-level element, e.g. Program & Engineering"
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
      />
      <button className="gp-btn gp-btn--ghost" onClick={submit} disabled={!title.trim() || pending}>
        + Add top-level element
      </button>
    </div>
  )
}
