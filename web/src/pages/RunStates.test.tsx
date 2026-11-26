import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import run from '../../../shared/fixtures/run.json'
import { renderAt } from '../test/render'
import { API, server } from '../test/server'

const RUN = '/runs/7c9e6679-7425-40de-944b-e07fc1f90ae7'
const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

describe('Run page states', () => {
  it('marks the step that failed and shows the reason', async () => {
    server.use(
      http.get(`${API}/runs/:id`, () =>
        HttpResponse.json({
          ...run,
          status: 'failed',
          error: 'Ranking failed: the table list was empty.',
          timings_ms: { profile: 12, parse_requirement: 1 },
        }),
      ),
    )
    renderAt(RUN)
    const steps = await screen.findByRole('list', { name: 'Run steps' })
    expect(within(steps).getByLabelText('Profile tables: done')).toBeInTheDocument()
    expect(within(steps).getByLabelText('Rank and explain joins: failed')).toBeInTheDocument()
    expect(within(steps).getByLabelText('Your approval: not started')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Ranking failed')
  })

  it('says so when profiling found no join candidates', async () => {
    server.use(
      http.get(`${API}/runs/:id`, () => HttpResponse.json({ ...run, status: 'completed' })),
      http.get(`${API}/runs/:id/proposals`, () => HttpResponse.json([])),
    )
    renderAt(RUN)
    expect(await screen.findByText(/no join candidates were found/i)).toBeInTheDocument()
    expect(screen.queryByLabelText('Join graph')).not.toBeInTheDocument()
  })

  it('polls a working run until it settles, then stops', async () => {
    let calls = 0
    server.use(
      http.get(`${API}/runs/:id`, () => {
        calls += 1
        return HttpResponse.json({ ...run, status: calls < 2 ? 'generating' : 'completed' })
      }),
    )
    renderAt(RUN)
    expect(await screen.findByText('completed', {}, { timeout: 3000 })).toBeInTheDocument()
    const settled = calls
    await pause(1300)
    expect(calls).toBe(settled)
  })

  it('stops polling a run that cannot be loaded', async () => {
    let calls = 0
    server.use(
      http.get(`${API}/runs/:id`, () => {
        calls += 1
        return HttpResponse.json(
          { error: { code: 'NOT_FOUND', message: 'Run not found.', details: {} } },
          { status: 404 },
        )
      }),
    )
    renderAt(RUN)
    expect(await screen.findByRole('alert')).toHaveTextContent('Run not found.')
    await pause(1300)
    expect(calls).toBe(1)
  })

  it('hides the approve button once the approval is accepted', async () => {
    server.use(
      http.post(`${API}/runs/:id/approvals`, () =>
        HttpResponse.json({ ...run, status: 'generating' }, { status: 202 }),
      ),
    )
    renderAt(RUN)
    await userEvent.click(await screen.findByRole('button', { name: /approve 5 joins/i }))
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /approve \d+ joins/i })).not.toBeInTheDocument(),
    )
  })

  it('shows why an approval was refused', async () => {
    server.use(
      http.post(`${API}/runs/:id/approvals`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'CONFLICT',
              message: 'This run is not waiting for approval.',
              details: {},
            },
          },
          { status: 409 },
        ),
      ),
    )
    renderAt(RUN)
    await userEvent.click(await screen.findByRole('button', { name: /approve 5 joins/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('not waiting for approval')
  })
})
