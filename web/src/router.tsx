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
    ],
  },
]

export const router = createBrowserRouter(routes)
