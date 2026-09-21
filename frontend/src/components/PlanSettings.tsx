import { useState } from 'react'
import { useUpdatePlan } from '../api/hooks'
import type { ContractType, Plan } from '../api/types'
import './PlanSettings.css'

export const TYPE_OPTIONS: [ContractType, string][] = [
  ['cpff', 'Cost plus fixed fee (CPFF)'],
  ['cpaf', 'Cost plus award fee (CPAF)'],
  ['ffp', 'Firm fixed price (FFP)'],
  ['internal', 'Internal / IRAD (no fee)'],
]

export const FEE_LABEL: Record<ContractType, string> = { cpff: 'Fixed fee', cpaf: 'Base fee', ffp: 'Target profit', internal: '' }

const TYPE_HELP: Record<ContractType, string> = {
  cpff: 'Contract value = estimated cost + a fixed fee. The fee is set by the contract and does not move when the plan\'s cost does.',
  cpaf: 'Contract value = estimated cost + a fixed base fee + an award-fee pool. The pool is earned, not guaranteed.',
  ffp: 'The contract value is the price. "Target profit" is what you plan to keep, so the budget base is the price less that profit.',
  internal: 'No fee. The budget is simply what you are funded to spend.',
}

const withCommas = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 2 })

/** The plan's contract and pricing terms — lives in the drawer's ℹ️ tab so the page itself can be
 * the plan: tiles, chart and grid. The contract value shows with commas at rest and as plain digits
 * while you type (formatting a number as it's typed fights the caret). */
export default function PlanSettings({ plan }: { plan: Plan }) {
  const updatePlan = useUpdatePlan(plan.id)
  const type = plan.contract_type
  const hasFee = type !== 'internal'
  const [cv, setCv] = useState(plan.contract_value != null ? withCommas(plan.contract_value) : '')

  function commitContractValue(text: string) {
    const cleaned = text.replace(/[$,\s]/g, '')
    const next = cleaned === '' ? null : Number(cleaned)
    if (next !== null && (Number.isNaN(next) || next < 0)) {
      setCv(plan.contract_value != null ? withCommas(plan.contract_value) : '')
      return
    }
    setCv(next != null ? withCommas(next) : '')
    if (next !== plan.contract_value) updatePlan.mutate({ contract_value: next })
  }

  const pctInput = (label: string, value: number, key: 'fee_percent' | 'award_fee_percent', title: string) => (
    <label className="plan-field" title={title}>
      <span>{label}</span>
      <div className="plan-field__pct">
        <input
          key={value}
          defaultValue={value}
          inputMode="decimal"
          onBlur={(e) => {
            const v = Number(e.target.value)
            if (!Number.isNaN(v) && v >= 0 && v !== value) updatePlan.mutate({ [key]: v })
          }}
          onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
        />
        <em>%</em>
      </div>
    </label>
  )

  return (
    <div className="plan-settings plan-settings--drawer">
      <h3 className="plan-settings__title">Contract &amp; pricing</h3>

      <label className="plan-field">
        <span>Contract type</span>
        <select
          className="plan-field__select"
          value={type}
          onChange={(e) => updatePlan.mutate({ contract_type: e.target.value as ContractType })}
        >
          {TYPE_OPTIONS.map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <p className="plan-settings__help">{TYPE_HELP[type]}</p>

      <label className="plan-field">
        <span>{hasFee ? 'Contract value' : 'Budget'}</span>
        <div className="plan-field__money">
          <em>$</em>
          <input
            value={cv}
            inputMode="decimal"
            placeholder="e.g. 2,900,000"
            onFocus={() => setCv((c) => c.replace(/,/g, ''))}
            onChange={(e) => setCv(e.target.value)}
            onBlur={(e) => commitContractValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
          />
        </div>
      </label>

      {hasFee &&
        pctInput(
          `${FEE_LABEL[type]} %`,
          plan.fee_percent,
          'fee_percent',
          'A percentage of the estimated cost. The fee is fixed by the contract — it does not move when the plan\'s cost does.',
        )}
      {type === 'cpaf' &&
        pctInput(
          'Award fee pool %',
          plan.award_fee_percent,
          'award_fee_percent',
          'The award-fee pool, as a percentage of estimated cost. It is earned, not guaranteed.',
        )}

      <label className="plan-check" title="Fringe, overhead and G&A spread on top of direct labor. Reckon holds each category's multiplier.">
        <input
          type="checkbox"
          checked={plan.include_burden}
          onChange={(e) => updatePlan.mutate({ include_burden: e.target.checked })}
        />
        <span>
          Include burden
          <small>fringe, overhead, G&amp;A on top of direct labor</small>
        </span>
      </label>

      {updatePlan.error && <span className="plan-settings__error">{updatePlan.error.message}</span>}
    </div>
  )
}
