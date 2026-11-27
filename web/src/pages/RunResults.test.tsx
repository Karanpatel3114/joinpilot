import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import proposals from '../../../shared/fixtures/proposals.json'
import run from '../../../shared/fixtures/run.json'
import { renderAt } from '../test/render'
import { API, server } from '../test/server'

const { downloadFile } = vi.hoisted(() => ({ downloadFile: vi.fn(() => Promise.resolve()) }))
vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  downloadFile,
}))

function completedRun() {
  server.use(
    http.get(`${API}/runs/:id`, () => HttpResponse.json({ ...run, status: 'completed' })),
    http.get(`${API}/runs/:id/proposals`, () =>
      HttpResponse.json(proposals.map((p) => ({ ...p, status: p.recommended ? 'approved' : 'rejected' }))),
    ),
  )
}

describe('Run results: SQL and checks', () => {
  it('shows each generated view with its SQL and status', async () => {
    completedRun()
    renderAt('/runs/7c9e6679-7425-40de-944b-e07fc1f90ae7')
    const sql = await screen.findByRole('region', { name: 'Generated SQL' })
    expect(await within(sql).findByText('v_bsid')).toBeInTheDocument()
    expect(within(sql).getAllByText(/CREATE OR REPLACE VIEW/).length).toBe(2)
    await userEvent.click(within(sql).getByRole('button', { name: /download sql/i }))
    expect(downloadFile).toHaveBeenLastCalledWith(
      '/runs/7c9e6679-7425-40de-944b-e07fc1f90ae7/export?dialect=duckdb',
      'joinpilot-7c9e6679-duckdb.sql',
    )
  })

  it('switches the SQL dialect', async () => {
    completedRun()
    renderAt('/runs/7c9e6679-7425-40de-944b-e07fc1f90ae7')
    await userEvent.selectOptions(await screen.findByLabelText('Dialect'), 'snowflake')
    await userEvent.click(screen.getByRole('button', { name: /download sql/i }))
    expect(downloadFile).toHaveBeenLastCalledWith(
      expect.stringContaining('dialect=snowflake'),
      expect.stringContaining('-snowflake.sql'),
    )
  })

  it('summarizes the checks with what each result means', async () => {
    completedRun()
    renderAt('/runs/7c9e6679-7425-40de-944b-e07fc1f90ae7')
    const checks = await screen.findByRole('region', { name: 'Check results' })
    expect(await within(checks).findByText('15 of 15 passed')).toBeInTheDocument()
    expect(within(checks).getAllByText('Reconciliation').length).toBeGreaterThan(0)
  })
})
