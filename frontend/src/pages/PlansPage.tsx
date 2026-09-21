import { useNavigate } from 'react-router-dom'
import { useCreatePlan, useProjects } from '../api/hooks'
import { money, num } from '../lib/format'
import './PlansPage.css'

const PHASE_LABEL: Record<string, string> = {
  pursuit: 'Pursuit',
  award: 'Award',
  execution: 'Execution',
  closeout: 'Closeout',
}

/** Every Conway's Depot project, with its plan if it has one. A project in ANY phase can have a
 * plan — in pursuit it is the bid estimate. Creating a plan just opens an empty one for that
 * project; the project itself (name, phase, portfolio) always comes from the Depot. */
export default function PlansPage() {
  const { data, isLoading } = useProjects()
  const createPlan = useCreatePlan()
  const navigate = useNavigate()

  const rows = [...(data?.projects ?? [])].sort(
    (a, b) => Number(!!b.plan_id) - Number(!!a.plan_id) || a.name.localeCompare(b.name),
  )

  return (
    <div className="plans-page">
      <div className="plans-page__head">
        <h1>Plans</h1>
        <p>Labor, priced from Reckon's historical rates and compared to the contract value — one plan per project, from pursuit on.</p>
      </div>

      {data && !data.depot_reachable && (
        <div className="plans-page__banner">Conway's Depot isn't reachable, so the project list can't load. Start the Depot and reload.</div>
      )}
      {data && data.depot_reachable && !data.rates_reachable && (
        <div className="plans-page__banner">Reckon isn't reachable, so labor can't be priced (the last known rates are used if any loaded).</div>
      )}
      {createPlan.error && <div className="plans-page__banner">{createPlan.error.message}</div>}

      {isLoading ? (
        <div className="plans-page__empty">Loading…</div>
      ) : (
        <table className="plans-table">
          <thead>
            <tr>
              <th>Project</th>
              <th>Phase</th>
              <th>Type</th>
              <th className="num">Labor hours</th>
              <th className="num">Planned cost</th>
              <th className="num">Contract value</th>
              <th className="num">Undistributed</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.depot_project_id} className={p.plan_id ? 'plans-table__row--plan' : ''}>
                <td>
                  <div className="plans-table__name">{p.name}</div>
                  {p.portfolio_name && <div className="plans-table__sub">{p.portfolio_name}</div>}
                </td>
                <td>{p.phase ? PHASE_LABEL[p.phase] ?? p.phase : '—'}</td>
                <td className="plans-table__type">{p.plan_id && p.contract_type ? p.contract_type.toUpperCase() : ''}</td>
                {p.plan_id ? (
                  <>
                    <td className="num">{num(p.hours ?? 0)}</td>
                    <td className="num">{money(p.cost)}</td>
                    <td className="num">{money(p.contract_value)}</td>
                    <td className={`num ${p.undistributed != null && p.undistributed < 0 ? 'plans-table__margin--low' : ''}`}>
                      {p.undistributed != null ? `${money(p.undistributed)} (${p.undistributed_pct?.toFixed(0)}%)` : '—'}
                    </td>
                    <td className="plans-table__action">
                      <button className="gp-btn gp-btn--primary" onClick={() => navigate(`/plans/${p.plan_id}`)}>
                        Open plan
                      </button>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="num plans-table__none" colSpan={4}>
                      No plan yet
                    </td>
                    <td className="plans-table__action">
                      <button
                        className="gp-btn gp-btn--ghost"
                        disabled={createPlan.isPending}
                        onClick={() => createPlan.mutate(p.depot_project_id, { onSuccess: (plan) => navigate(`/plans/${plan.id}`) })}
                      >
                        Create plan
                      </button>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
