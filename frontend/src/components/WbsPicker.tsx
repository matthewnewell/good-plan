import type { Wbs } from '../api/types'
import './WbsPicker.css'

/** Which work package a line sits on: only the WBS's leaves are offered. A code already on the
 * line that isn't a work package any more (the WBS changed under it) stays visible, flagged, so
 * it can be moved rather than silently dropped. */
export default function WbsPicker({
  wbs,
  value,
  onChange,
}: {
  wbs: Wbs | undefined
  value: string | null
  onChange: (code: string | null) => void
}) {
  const leaves = wbs?.elements.filter((e) => e.leaf) ?? []
  const current = wbs?.elements.find((e) => e.code === value)
  const stray = !!value && !!wbs && (!current || !current.leaf)
  const none = !!wbs && wbs.source === 'none'

  return (
    <select
      className={`wbs-picker${stray ? ' wbs-picker--stray' : ''}${!value ? ' wbs-picker--empty' : ''}`}
      value={value ?? ''}
      disabled={!wbs || none}
      title={
        none
          ? 'This project has no WBS yet: set one up on the WBS tab'
          : stray
            ? `WBS ${value} isn't a work package in this project's WBS. Pick one.`
            : current
              ? `${current.code} ${current.title}`
              : 'Pick the work package this sits on'
      }
      onChange={(e) => onChange(e.target.value || null)}
    >
      <option value="">—</option>
      {stray && <option value={value!}>{value} (not a work package)</option>}
      {leaves.map((e) => (
        <option key={e.code} value={e.code}>
          {e.code} · {e.title}
        </option>
      ))}
    </select>
  )
}
