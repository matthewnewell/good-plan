/** One line of labor demand a project is asserting about its own plan — not a commitment, not
 * a real person assigned. See backend/models.py. */
export interface DemandLine {
  id: string
  project: string
  portfolio: string | null
  role: string
  fte: number
  start_date: string
  end_date: string
  note: string | null
  created_at: string
}
