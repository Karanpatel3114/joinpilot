import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import dashboard from '../../../../shared/fixtures/dashboard.json'
import { renderAt } from '../../test/render'
import { API, server } from '../../test/server'

const PROJECT = '/projects/3f0b7c1e-6a2d-4c8e-9b1a-2d5e8f7a9c10'

describe('KPI dashboard', () => {
  it('shows every metric, the asked-for ones first', async () => {
    renderAt(`${PROJECT}?tab=Dashboard`)
    const dashboard = await screen.findByRole('region', { name: 'Dashboard' })
    const cards = within(dashboard).getAllByRole('article')
    expect(cards).toHaveLength(5)
    expect(within(cards[0]).getByRole('heading')).toHaveTextContent('Open receivables by aging bucket')
    expect(within(cards[0]).getByText('asked for')).toBeInTheDocument()
  })

  it('shows the rows and the SQL behind a metric', async () => {
    renderAt(`${PROJECT}?tab=Dashboard`)
    const card = await screen.findByRole('article', { name: 'Open receivables by aging bucket' })
    await userEvent.click(within(card).getByRole('button', { name: 'Table' }))
    const table = within(card).getByRole('table', { name: /aging bucket data/ })
    expect(within(table).getByText('not_due')).toBeInTheDocument()
    expect(within(table).getByText('12,813,002.84')).toBeInTheDocument()
    await userEvent.click(within(card).getByRole('button', { name: 'SQL' }))
    expect(within(card).getByText(/ROUND\(SUM\("DMBTR"\), 2\)/)).toBeInTheDocument()
  })

  it('explains an empty dashboard', async () => {
    server.use(
      http.get(`${API}/projects/:id/dashboard`, () => HttpResponse.json({ run_id: null, metrics: [] })),
    )
    renderAt(PROJECT)
    await userEvent.click(await screen.findByRole('tab', { name: 'Dashboard' }))
    expect(await screen.findByText(/no dashboard yet/i)).toBeInTheDocument()
  })

  it('says why a metric could not be computed', async () => {
    const [first, ...rest] = dashboard.metrics
    const failed = { ...first, status: 'failed', data: [], message: 'The metric could not be computed (BinderException).' }
    server.use(
      http.get(`${API}/projects/:id/dashboard`, () =>
        HttpResponse.json({ ...dashboard, metrics: [failed, ...rest] }),
      ),
    )
    renderAt(`${PROJECT}?tab=Dashboard`)
    const card = await screen.findByRole('article', { name: first.title })
    expect(within(card).getByRole('alert')).toHaveTextContent('could not be computed')
    expect(within(card).queryByRole('button', { name: 'SQL' })).not.toBeInTheDocument()
  })
})
