import { HttpResponse, http } from 'msw'
import { setupServer } from 'msw/node'
import projects from '../../../shared/fixtures/projects.json'
import glossary from '../../../shared/fixtures/glossary.json'
import profile from '../../../shared/fixtures/profile.json'
import proposals from '../../../shared/fixtures/proposals.json'
import run from '../../../shared/fixtures/run.json'
import runs from '../../../shared/fixtures/runs.json'
import checks from '../../../shared/fixtures/checks.json'
import views from '../../../shared/fixtures/views.json'
import tables from '../../../shared/fixtures/tables.json'
import dashboard from '../../../shared/fixtures/dashboard.json'
import answer from '../../../shared/fixtures/answer.json'

const API = 'http://localhost:8000'

/** A mock API built from the shared contract fixtures. */
export const handlers = [
  http.get(`${API}/projects`, () => HttpResponse.json(projects)),
  http.post(`${API}/projects`, async ({ request }) => {
    const body = (await request.json()) as { name: string }
    return HttpResponse.json({ ...projects[0], name: body.name, table_count: 0 }, { status: 201 })
  }),
  http.post(`${API}/projects/:id/tables`, () => HttpResponse.json(tables, { status: 201 })),
  http.get(`${API}/projects/:id/profile`, () => HttpResponse.json(profile)),
  http.get(`${API}/projects/:id/glossary`, () => HttpResponse.json(glossary)),
  http.get(`${API}/projects/:id/runs`, () => HttpResponse.json(runs)),
  http.get(`${API}/runs/:id`, () => HttpResponse.json(run)),
  http.get(`${API}/runs/:id/proposals`, () => HttpResponse.json(proposals)),
  http.get(`${API}/runs/:id/views`, ({ request }) => {
    const dialect = new URL(request.url).searchParams.get('dialect') ?? 'duckdb'
    return HttpResponse.json(views.map((v) => ({ ...v, dialect })))
  }),
  http.get(`${API}/runs/:id/checks`, () => HttpResponse.json(checks)),
  http.get(`${API}/projects/:id/dashboard`, () => HttpResponse.json(dashboard)),
  http.post(`${API}/projects/:id/ask`, () => HttpResponse.json(answer)),
]

export const server = setupServer(...handlers)
export { API }
