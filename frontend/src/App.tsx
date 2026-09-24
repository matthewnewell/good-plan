import { DrawerLayout } from '@conways/drawer'
import { Route, Routes, useMatch } from 'react-router-dom'
import { useHealth, usePlan, useProjects } from './api/hooks'
import Nav from './components/Nav'
import PlanSettings from './components/PlanSettings'
import { readPersonId } from './lib/person'
import SplashPage from './pages/SplashPage'
import PlansPage from './pages/PlansPage'
import PlanPage from './pages/PlanPage'
import './App.css'

const DEPOT_URL = 'http://localhost:8090'

/** Shared chrome for every operational page, inside the ecosystem's shared Agent | Journal drawer
 * (@conways/drawer). On a plan the drawer is scoped to that plan's project: the Agent is Good
 * Plan's own (it reads the plan's lines, pricing and contract terms) and the Journal is the
 * project's. On the plan list it's person-scoped: the Agent is the Depot's portfolio assistant
 * and the Journal opens on the person's own notes, with a picker for any project. */
function Layout({ children }: { children: React.ReactNode }) {
  const planId = useMatch('/plans/:planId')?.params.planId
  const { data: plan } = usePlan(planId)
  const { data: health } = useHealth()
  const { data: projects } = useProjects()
  const personId = readPersonId()

  return (
    <div className="app-layout">
      <Nav />
      <DrawerLayout
        storageKey="good-plan:drawer"
        scrollMain={false}
        // On a plan, the contract & pricing terms live in an ℹ️ tab at the top of the drawer rail.
        tabs={plan ? [{ id: 'plan-info', icon: 'ℹ️', label: 'Contract & pricing', content: <PlanSettings key={plan.id} plan={plan} /> }] : []}
        agent={
          planId
            ? {
                chatUrl: `/api/plans/${planId}/chat`,
                aiConfigured: health?.ai_configured ?? false,
                resetKey: planId,
                intro: "Ask about this plan — where the hours go, what it costs, how much budget is still undistributed.",
                starters: ['Where is most of the cost?', 'Is the plan over budget?', 'What would happen if we added an engineer?'],
              }
            : {
                chatUrl: `${DEPOT_URL}/api/chat`,
                chatExtra: { person_id: personId },
                aiConfigured: true,
                resetKey: 'plans',
                intro: 'Ask about your projects and where they stand — or open a plan to ask about its numbers.',
              }
        }
        journal={{
          depotUrl: DEPOT_URL,
          projectId: plan?.depot_project_id,
          personId,
          projects: (projects?.projects ?? []).map((p) => ({ id: p.depot_project_id, name: p.name })),
        }}
      >
        <div className="app-layout__body">{children}</div>
      </DrawerLayout>
    </div>
  )
}

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/about" element={<SplashPage />} />
        <Route path="/" element={<Layout><PlansPage /></Layout>} />
        <Route path="/plans/:planId" element={<Layout><PlanPage /></Layout>} />
      </Routes>
    </>
  )
}
