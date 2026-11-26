import { HttpResponse, http } from 'msw'
import { setupServer } from 'msw/node'
import projects from '../../../shared/fixtures/projects.json'
import tables from '../../../shared/fixtures/tables.json'

const API = 'http://localhost:8000'

/** A mock API built from the shared contract fixtures. */
export const handlers = [
  http.get(`${API}/projects`, () => HttpResponse.json(projects)),
  http.post(`${API}/projects`, async ({ request }) => {
    const body = (await request.json()) as { name: string }
    return HttpResponse.json({ ...projects[0], name: body.name, table_count: 0 }, { status: 201 })
  }),
  http.post(`${API}/projects/:id/tables`, () => HttpResponse.json(tables, { status: 201 })),
]

export const server = setupServer(...handlers)
export { API }
