import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../test/render'

const PROJECT = '/projects/3f0b7c1e-6a2d-4c8e-9b1a-2d5e8f7a9c10'

describe('Profile explorer', () => {
  it('shows a table with its keys, column statistics and evidence ids', async () => {
    renderAt(PROJECT)
    const tables = await screen.findByRole('navigation', { name: 'Tables' })
    await userEvent.click(within(tables).getByRole('button', { name: /KNA1/ }))
    expect(screen.getByText('Keys: (KUNNR)')).toBeInTheDocument()
    const columns = screen.getByRole('table', { name: 'Columns of KNA1' })
    expect(within(columns).getByText('NAME1')).toBeInTheDocument()
    expect(within(columns).getAllByText(/^uk_\d+$/).length).toBeGreaterThan(0)
  })

  it('shows normalized overlaps with their raw ratio', async () => {
    renderAt(PROJECT)
    const tables = await screen.findByRole('navigation', { name: 'Tables' })
    await userEvent.click(within(tables).getByRole('button', { name: /BSID/ }))
    expect(screen.getByText('BSID.KUNNR → KNA1.KUNNR')).toBeInTheDocument()
    expect(screen.getAllByText(/lpad_zeros:10 \(raw 0\.0%\)/).length).toBeGreaterThan(0)
  })

  it('finds columns by business words', async () => {
    renderAt(PROJECT)
    await userEvent.type(await screen.findByLabelText('Find columns by business words'), 'customer name')
    await userEvent.click(screen.getByRole('button', { name: /search/i }))
    expect(await screen.findByText('KNA1.NAME1')).toBeInTheDocument()
  })
})
