import { createBrowserRouter } from 'react-router'
import { Layout } from './components/Layout'
import { ProjectPage } from './pages/ProjectPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { RunPage } from './pages/RunPage'

export const routes = [
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <ProjectsPage /> },
      { path: 'projects/:projectId', element: <ProjectPage /> },
      { path: 'runs/:runId', element: <RunPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
