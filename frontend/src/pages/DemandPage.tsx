import { useMemo, useState } from 'react'
import { useCreateDemand, useDeleteDemand, useDemand, usePortfolios, useProjects, useRoles } from '../api/hooks'
import './DemandPage.css'

/** The whole app, for now: every demand line a project has asserted about its own labor plan —
 * a role, how much of it (FTE), and when. Not a commitment, not a real person — see
 * backend/models.py. No computed "total FTE" rollup: summing FTE across lines with different
 * date ranges would claim a peak-concurrent-headcount number this app doesn't actually know, so
 * the table just lists the raw lines, sorted, filterable — the honest thing. */
export default function DemandPage() {
  const [project, setProject] = useState('')
  const { data: projects } = useProjects()
  const { data: portfolios } = usePortfolios()
  const { data: roles } = useRoles()
  const { data: lines, isLoading } = useDemand({ project: project || undefined })
  const createDemand = useCreateDemand()
  const deleteDemand = useDeleteDemand()

  const [composing, setComposing] = useState(false)
  const [form, setForm] = useState({ project: '', portfolio: '', role: '', fte: '1', start_date: '', end_date: '', note: '' })

  const sorted = useMemo(() => {
    if (!lines) return []
    return [...lines].sort((a, b) => a.role.localeCompare(b.role) || a.start_date.localeCompare(b.start_date))
  }, [lines])

  function resetForm() {
    setForm({ project: project || '', portfolio: '', role: '', fte: '1', start_date: '', end_date: '', note: '' })
  }

  function submit() {
    const fte = parseFloat(form.fte)
    if (!form.project.trim() || !form.role.trim() || !form.start_date || !form.end_date || !(fte > 0)) return
    createDemand.mutate(
      {
        project: form.project.trim(),
        portfolio: form.portfolio.trim() || undefined,
        role: form.role.trim(),
        fte,
        start_date: form.start_date,
        end_date: form.end_date,
        note: form.note.trim() || undefined,
      },
      { onSuccess: () => { resetForm(); setComposing(false) } },
    )
  }

  return (
    <div className="demand-page">
      <div className="demand-page__inner">
        <header className="demand-page__header">
          <select value={project} onChange={(e) => setProject(e.target.value)}>
            <option value="">All projects</option>
            {(projects ?? []).map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          {!composing && (
            <button className="gp-btn gp-btn--primary" onClick={() => { resetForm(); setComposing(true) }}>
              + Add demand
            </button>
          )}
        </header>

        {composing && (
          <div className="demand-form">
            <div className="demand-form__row">
              <label>
                Project
                <input
                  list="gp-projects"
                  value={form.project}
                  onChange={(e) => setForm((f) => ({ ...f, project: e.target.value }))}
                  placeholder="Demo: Bracket Assembly Program"
                />
                <datalist id="gp-projects">
                  {(projects ?? []).map((p) => <option key={p} value={p} />)}
                </datalist>
              </label>
              <label>
                Portfolio <span className="demand-form__optional">(optional)</span>
                <input
                  list="gp-portfolios"
                  value={form.portfolio}
                  onChange={(e) => setForm((f) => ({ ...f, portfolio: e.target.value }))}
                  placeholder="Industrial Programs"
                />
                <datalist id="gp-portfolios">
                  {(portfolios ?? []).map((p) => <option key={p} value={p} />)}
                </datalist>
              </label>
            </div>
            <div className="demand-form__row">
              <label>
                Role
                <input
                  list="gp-roles"
                  value={form.role}
                  onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
                  placeholder="Mechanical Engineer"
                />
                <datalist id="gp-roles">
                  {(roles ?? []).map((r) => <option key={r} value={r} />)}
                </datalist>
              </label>
              <label>
                FTE
                <input
                  type="number" min="0.05" step="0.05"
                  value={form.fte}
                  onChange={(e) => setForm((f) => ({ ...f, fte: e.target.value }))}
                />
              </label>
            </div>
            <div className="demand-form__row">
              <label>
                Start
                <input type="date" value={form.start_date} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} />
              </label>
              <label>
                End
                <input type="date" value={form.end_date} onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))} />
              </label>
            </div>
            <label className="demand-form__note">
              Note <span className="demand-form__optional">(optional)</span>
              <input value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} placeholder="What phase, why this ratio…" />
            </label>
            <div className="demand-form__actions">
              <button className="gp-btn gp-btn--primary" onClick={submit} disabled={createDemand.isPending}>
                {createDemand.isPending ? 'Adding…' : 'Add'}
              </button>
              <button className="gp-btn gp-btn--ghost" onClick={() => setComposing(false)}>Cancel</button>
            </div>
            {createDemand.isError && (
              <p className="demand-form__error">{(createDemand.error as Error)?.message ?? 'Could not add that line.'}</p>
            )}
          </div>
        )}

        {isLoading && <p className="demand-page__empty">Loading…</p>}
        {!isLoading && sorted.length === 0 && (
          <p className="demand-page__empty">No labor demand recorded yet — add the first line above.</p>
        )}

        {sorted.length > 0 && (
          <table className="demand-table">
            <thead>
              <tr>
                <th>Role</th>
                <th>Project / Portfolio</th>
                <th className="demand-table__num">FTE</th>
                <th>Start</th>
                <th>End</th>
                <th>Note</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((d) => (
                <tr key={d.id}>
                  <td><span className="role-pill">{d.role}</span></td>
                  <td className="demand-table__meta">
                    {d.project}
                    {d.portfolio && <span className="demand-table__portfolio"> · {d.portfolio}</span>}
                  </td>
                  <td className="demand-table__num demand-table__strong">{d.fte}</td>
                  <td>{d.start_date}</td>
                  <td>{d.end_date}</td>
                  <td className="demand-table__notes">{d.note ?? ''}</td>
                  <td className="demand-table__actions">
                    <button
                      className="demand-table__delete"
                      title="Delete this line"
                      onClick={() => deleteDemand.mutate(d.id)}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
