import { useMemo, useRef, useState } from 'react'
import { shortDate } from '../lib/format'
import './PlanChart.css'

export interface ChartSeries {
  key: string
  label: string
  values: number[]
  /** The headline line (drawn heavier, with a soft area under it). */
  strong?: boolean
}

interface Props {
  weeks: string[]
  series: ChartSeries[]
  format: (n: number) => string
  /** A horizontal reference line, e.g. the contract value on the cumulative-cost chart. */
  refLine?: { value: number; label: string } | null
}

const W = 900
const H = 210
const PAD = { l: 64, r: 16, t: 14, b: 30 }
const PALETTE = ['#0ea5e9', '#f59e0b', '#10b981', '#a855f7', '#ef4444', '#14b8a6', '#eab308', '#6366f1', '#ec4899', '#84cc16']

function niceMax(max: number): number {
  if (max <= 0) return 1
  const rough = max / 4
  const pow = Math.pow(10, Math.floor(Math.log10(rough)))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * pow).find((s) => s >= rough) ?? pow * 10
  return step * 4
}

function mondayIso(d: Date): string {
  const m = new Date(d)
  m.setDate(m.getDate() - ((m.getDay() + 6) % 7))
  return `${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, '0')}-${String(m.getDate()).padStart(2, '0')}`
}

/** A dependency-free SVG line chart over the plan's weeks: one heavy line (the total) plus any
 * number of thin ones (labor categories), a dashed "this week" marker, an optional reference line,
 * and a hover readout of the exact weekly values. */
export default function PlanChart({ weeks, series, format, refLine }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [hover, setHover] = useState<number | null>(null)

  const { yMax, x, y } = useMemo(() => {
    const all = series.flatMap((s) => s.values).concat(refLine ? [refLine.value] : [])
    const yMax = niceMax(Math.max(0, ...all))
    const n = weeks.length
    return {
      yMax,
      x: (i: number) => PAD.l + ((W - PAD.l - PAD.r) * (n > 1 ? i / (n - 1) : 0.5)),
      y: (v: number) => PAD.t + (H - PAD.t - PAD.b) * (1 - v / yMax),
    }
  }, [series, weeks.length, refLine])

  const todayIdx = weeks.indexOf(mondayIso(new Date()))
  const labelEvery = Math.max(1, Math.ceil(weeks.length / 9))
  const path = (values: number[]) => values.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const strong = series.find((s) => s.strong)

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect || weeks.length === 0) return
    const px = ((e.clientX - rect.left) / rect.width) * W
    const idx = Math.round(((px - PAD.l) / (W - PAD.l - PAD.r)) * (weeks.length - 1))
    setHover(Math.max(0, Math.min(weeks.length - 1, idx)))
  }

  return (
    <div className="pc">
      <div className="pc__readout">
        {hover == null ? (
          <span className="pc__hint">Hover the chart for weekly values</span>
        ) : (
          <>
            <strong>Week of {shortDate(weeks[hover])}</strong>
            {series.map((s, i) => (
              <span key={s.key} className="pc__readout-item">
                <span className="pc__swatch" style={{ background: s.strong ? 'var(--color-accent)' : PALETTE[i % PALETTE.length] }} />
                {s.label}: {format(s.values[hover] ?? 0)}
              </span>
            ))}
          </>
        )}
      </div>

      <svg
        ref={svgRef}
        className="pc__svg"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Plan over time"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        {[0, 1, 2, 3, 4].map((t) => {
          const v = (yMax / 4) * t
          return (
            <g key={t}>
              <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} className="pc__grid" />
              <text x={PAD.l - 8} y={y(v) + 4} textAnchor="end" className="pc__tick">
                {format(v)}
              </text>
            </g>
          )
        })}

        {weeks.map((w, i) =>
          i % labelEvery === 0 ? (
            <text key={w} x={x(i)} y={H - 8} textAnchor="middle" className="pc__tick">
              {shortDate(w)}
            </text>
          ) : null,
        )}

        {todayIdx >= 0 && (
          <g>
            <line x1={x(todayIdx)} x2={x(todayIdx)} y1={PAD.t} y2={H - PAD.b} className="pc__today" />
            <text x={x(todayIdx) + 4} y={PAD.t + 10} className="pc__today-label">
              this week
            </text>
          </g>
        )}

        {refLine && (
          <g>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(refLine.value)} y2={y(refLine.value)} className="pc__ref" />
            <text x={W - PAD.r - 4} y={y(refLine.value) - 6} textAnchor="end" className="pc__ref-label">
              {refLine.label}
            </text>
          </g>
        )}

        {strong && weeks.length > 1 && (
          <path d={`${path(strong.values)} L${x(weeks.length - 1)},${y(0)} L${x(0)},${y(0)} Z`} className="pc__area" />
        )}
        {series.map((s, i) => (
          <path
            key={s.key}
            d={path(s.values)}
            fill="none"
            stroke={s.strong ? 'var(--color-accent)' : PALETTE[i % PALETTE.length]}
            strokeWidth={s.strong ? 2.6 : 1.4}
            strokeLinejoin="round"
            opacity={s.strong ? 1 : 0.85}
          />
        ))}

        {hover != null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={PAD.t} y2={H - PAD.b} className="pc__cursor" />
            {series.map((s, i) => (
              <circle
                key={s.key}
                cx={x(hover)}
                cy={y(s.values[hover] ?? 0)}
                r={s.strong ? 4 : 3}
                fill={s.strong ? 'var(--color-accent)' : PALETTE[i % PALETTE.length]}
              />
            ))}
          </g>
        )}
      </svg>
    </div>
  )
}
