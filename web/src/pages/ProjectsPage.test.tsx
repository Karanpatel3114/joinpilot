import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import tables from '../../../shared/fixtures/tables.json'
import { renderAt } from '../test/render'
import { API, server } from '../test/server'

describe('Projects page', () => {
  it('lists projects from the API', async () => {
    renderAt('/')
    expect(await screen.findByText('Demo ERP')).toBeInTheDocument()
    expect(screen.getByText(/6 tables/)).toBeInTheDocument()
  })

  it('creates a project and opens it', async () => {
    renderAt('/')
    await userEvent.type(screen.getByLabelText('New project name'), 'Receivables')
    await userEvent.click(screen.getByRole('button', { name: /create project/i }))
    expect(await screen.findByRole('button', { name: /load erp sample/i })).toBeInTheDocument()
  })

  it('shows the API error message in plain language', async () => {
    server.use(
      http.get(`${API}/projects`, () =>
        HttpResponse.json(
          { error: { code: 'INTERNAL_ERROR', message: 'Something went wrong on the server.', details: {} } },
          { status: 500 },
        ),
      ),
    )
    renderAt('/')
    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong on the server.')
  })

  it('loads the ERP sample into a project', async () => {
    let sent: unknown = null
    server.use(
      http.post(`${API}/projects/:id/tables`, async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json(tables, { status: 201 })
      }),
    )
    renderAt('/projects/3f0b7c1e-6a2d-4c8e-9b1a-2d5e8f7a9c10')
    await userEvent.click(await screen.findByRole('button', { name: /load erp sample/i }))
    await waitFor(() => expect(sent).toEqual({ sample: 'erp_s1_sap' }))
    await waitFor(() => expect(screen.queryByText('Loading tables…')).not.toBeInTheDocument())
  })

  it('uploads files as multipart form data', async () => {
    // jsdom's File loses its name on the way through Node's fetch, so check the parts' contents.
    let parts: string[] = []
    server.use(
      http.post(`${API}/projects/:id/tables`, async ({ request }) => {
        const form = await request.formData()
        parts = await Promise.all(form.getAll('files').map((f) => (f as Blob).text()))
        return HttpResponse.json(tables, { status: 201 })
      }),
    )
    renderAt('/projects/3f0b7c1e-6a2d-4c8e-9b1a-2d5e8f7a9c10')
    const input = await screen.findByLabelText('Upload CSV or Parquet files')
    await userEvent.upload(input, [
      new File(['a,b\n1,2\n'], 'orders.csv', { type: 'text/csv' }),
      new File(['x\n1\n'], 'items.csv', { type: 'text/csv' }),
    ])
    await waitFor(() => expect(parts).toEqual(['a,b\n1,2\n', 'x\n1\n']))
  })
})
