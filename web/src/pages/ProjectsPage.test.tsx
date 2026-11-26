import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
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
    renderAt('/projects/3f0b7c1e-6a2d-4c8e-9b1a-2d5e8f7a9c10')
    await userEvent.click(await screen.findByRole('button', { name: /load erp sample/i }))
    await waitFor(() => expect(screen.queryByText('Loading tables…')).not.toBeInTheDocument())
  })
})
