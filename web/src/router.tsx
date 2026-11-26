import { createBrowserRouter } from 'react-router'
import { Layout } from './components/Layout'
import { ProjectPage } from './pages/ProjectPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { RouteError } from './pages/RouteError'

export const routes = [
  {
    path: '/',
    element: <Layout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <ProjectsPage /> },
      { path: 'projects/:projectId', element: <ProjectPage /> },
      // The run page carries React Flow, so it loads on first visit.
      {
        path: 'runs/:runId',
        lazy: async () => ({ Component: (await import('./pages/RunPage')).RunPage }),
      },
    ],
  },
]

export const router = createBrowserRouter(routes)
