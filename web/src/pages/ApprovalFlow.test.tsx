import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import run from '../../../shared/fixtures/run.json'
import { renderAt } from '../test/render'
import { API, server } from '../test/server'

const RUN = '/runs/7c9e6679-7425-40de-944b-e07fc1f90ae7'

describe('Approval workflow', () => {
  it('pre-approves recommended joins and sends every decision', async () => {
    let sent: unknown = null
    server.use(
      http.post(`${API}/runs/:id/approvals`, async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({ ...run, status: 'generating' }, { status: 202 })
      }),
    )
    renderAt(RUN)
    await userEvent.click(await screen.findByRole('button', { name: /show 3 other candidates/i }))
    const list = screen.getByRole('list', { name: 'Proposed joins' })
    const boxes = within(list).getAllByRole('checkbox')
    expect(boxes.filter((b) => (b as HTMLInputElement).checked)).toHaveLength(5)
    await userEvent.click(boxes[0])
    await userEvent.click(screen.getByRole('button', { name: /approve 4 joins/i }))
    await waitFor(() => expect(sent).not.toBeNull())
    const decisions = (sent as { decisions: { action: string }[] }).decisions
    expect(decisions).toHaveLength(8)
    expect(decisions.filter((d) => d.action === 'approve')).toHaveLength(4)
  })

  it('shows the run steps and its warnings', async () => {
    renderAt(RUN)
    const steps = await screen.findByRole('list', { name: 'Run steps' })
    expect(within(steps).getByText('Your approval')).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Warnings' })).toHaveTextContent('Keyword parsing used')
  })

  it('starts a run from the project page and opens it', async () => {
    server.use(
      http.post(`${API}/projects/:id/runs`, () => HttpResponse.json(run, { status: 202 })),
    )
    renderAt('/projects/3f0b7c1e-6a2d-4c8e-9b1a-2d5e8f7a9c10')
    await userEvent.click(await screen.findByRole('tab', { name: 'Runs' }))
    await userEvent.click(screen.getByRole('button', { name: /start run/i }))
    expect(await screen.findByRole('list', { name: 'Run steps' })).toBeInTheDocument()
  })
})
