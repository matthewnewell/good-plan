import { NavLink } from 'react-router-dom'
import './Nav.css'

/** Persistent top navbar — same pattern as the sibling apps: brand links to the splash page,
 * one top-level link for the rest (the list of plans; a plan opens from there). */
export default function Nav() {
  return (
    <nav className="gp-nav">
      <NavLink to="/about" className="gp-nav__brand">
        Good Plan
      </NavLink>
      <div className="gp-nav__links">
        <NavLink
          to="/"
          end
          className={({ isActive }) => `gp-nav__link ${isActive ? 'gp-nav__link--active' : ''}`}
        >
          Plans
        </NavLink>
      </div>
    </nav>
  )
}
