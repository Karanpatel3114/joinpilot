import { createBrowserRouter } from 'react-router'
import { Layout } from './components/Layout'
import { ProjectPage } from './pages/ProjectPage'
import { ProjectsPage } from './pages/ProjectsPage'

export const routes = [
  {
    path: '/',
    element: <Layout />,
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
