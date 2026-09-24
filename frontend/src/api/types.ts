/** One row of the Plans list: a Conway's Depot project (any phase) and, if it has one, its plan. */
export interface ProjectRow {
  depot_project_id: string
  name: string
  phase: string | null
  portfolio_name: string | null
  plan_id: string | null
  hours?: number
  cost?: number
  contract_value?: number | null
  contract_type?: ContractType
  /** Budget base minus planned cost — null until a contract value is set. */
  undistributed?: number | null
  undistributed_pct?: number | null
}

export type ContractType = 'cpff' | 'cpaf' | 'ffp' | 'internal'

export interface ProjectsResponse {
  projects: ProjectRow[]
  depot_reachable: boolean
  rates_reachable: boolean
}

export interface Rate {
  name: string
  avg_rate: number
  burden_factor: number
  loaded_rate: number
  basis_hours: number
}

export interface RatesResponse {
  rates: Rate[]
  reachable: boolean
}

export interface FunctionRow {
  name: string
  categories: string[]
  manager_name: string | null
}

export interface FunctionsResponse {
  functions: FunctionRow[]
  reachable: boolean
}

export interface PlanLine {
  id: string
  category: string
  wbs: string | null
  rate_override: number | null
  note: string | null
  /** Direct $/h (override, else Reckon's average) — null if neither exists. */
  direct_rate: number | null
  burden_factor: number
  /** What a labor hour is priced at: direct x burden when burden is on. Null = unpriced. */
  effective_rate: number | null
  /** ISO Monday -> hours */
  hours: Record<string, number>
  total_hours: number
  total_cost: number | null
}

export type CostKind = 'material' | 'subcontract' | 'services' | 'travel' | 'other'

export interface CostPhase {
  id: string
  date: string
  percent: number
}

/** A non-labor cost: materials, or an "other direct cost" (subcontract, services, travel, other). */
export interface CostLine {
  id: string
  kind: CostKind
  description: string
  vendor: string | null
  wbs: string | null
  qty: number
  unit_cost: number
  total: number
  /** This kind's burden multiplier (1.0 when burden is off). */
  factor: number
  loaded_total: number
  need_date: string | null
  /** Milestones override the single need date. */
  phases: CostPhase[]
  /** Travel calculator inputs, as JSON. */
  detail: string | null
  note: string | null
}

export interface PlanTotals {
  hours: number
  /** ALL planned cost — labor + materials + other direct costs (burdened when burden is on). */
  cost: number
  labor_cost: number
  material_cost: number
  subcontract_cost: number
  services_cost: number
  travel_cost: number
  other_cost: number
  /** Subcontracts + services + travel + other. */
  odc_cost: number
  /** Cost dated beyond the plan's window (in the totals, not on the chart). */
  cost_outside_window: number
  /** Cost with no date at all. */
  cost_unscheduled: number
  cost_by_week_kind: { labor: Record<string, number>; material: Record<string, number>; odc: Record<string, number> }
  /** What the contract funds in cost — the contract value with fee taken out. */
  contract_budget_base: number | null
  /** Fixed fee (CPFF), base fee (CPAF) or target profit (FFP). */
  fee: number | null
  award_fee: number | null
  /** Budget base minus the cost planned so far: authorized but not yet planned into work. */
  undistributed: number | null
  undistributed_pct: number | null
  /** Contract value minus planned cost (the plain profit view; most useful on an FFP). */
  margin: number | null
  margin_pct: number | null
  unpriced_hours: number
  hours_by_week: Record<string, number>
  cost_by_week: Record<string, number>
}

export interface Plan {
  id: string
  depot_project_id: string
  project_name: string
  portfolio_name: string | null
  contract_value: number | null
  contract_type: ContractType
  include_burden: boolean
  fee_percent: number
  award_fee_percent: number
  hours_per_fte_week: number
  start_week: string
  week_count: number
  weeks: string[]
  lines: PlanLine[]
  costs: CostLine[]
  totals: PlanTotals
  rates_reachable: boolean
}

// ── WBS: the one a plan budgets against (routes/wbs.py) ───────────────────────────────────────
export interface WbsElement {
  id: string
  code: string
  title: string
  parent_code: string | null
  /** A work package: the only kind of element a line may sit on. */
  leaf: boolean
  charge_number: string | null
  percent_complete: number | null
  status: string | null
}

export interface Wbs {
  /** scope_manager = the project's WBS; draft = this plan's own (a pursuit's); none = not set up. */
  source: 'scope_manager' | 'draft' | 'none'
  elements: WbsElement[]
  reachable: boolean
  phase: string | null
  editable: boolean
  can_promote: boolean
  /** A pursuit's Bid & Proposal charge number from S4 (via the Depot), for capture and proposal effort. */
  bp_charge_number: string | null
  scope_manager_url: string
}
