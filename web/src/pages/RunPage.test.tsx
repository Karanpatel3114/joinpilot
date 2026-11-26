import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../test/render'

const RUN = '/runs/7c9e6679-7425-40de-944b-e07fc1f90ae7'

describe('Run page: join graph and evidence', () => {
  it('draws the join graph and lists every proposal', async () => {
    renderAt(RUN)
    expect(await screen.findByLabelText('Join graph')).toBeInTheDocument()
    const list = screen.getByRole('list', { name: 'Proposed joins' })
    expect(within(list).getAllByRole('checkbox')).toHaveLength(8)
  })

  it('explains a selected join with the numbers behind its evidence ids', async () => {
    renderAt(RUN)
    const list = await screen.findByRole('list', { name: 'Proposed joins' })
    await userEvent.click(within(list).getByRole('button', { name: /BSID\.KUNNR → KNA1\.KUNNR/ }))
    const panel = screen.getByRole('complementary', { name: 'Evidence' })
    expect(within(panel).getByText('lpad_zeros:10')).toBeInTheDocument()
    expect(await within(panel).findByText(/of BSID\.KUNNR values found in KNA1\.KUNNR after lpad_zeros:10/)).toBeInTheDocument()
    expect(within(panel).getByText(/KNA1\.\(KUNNR\) is 100\.0% unique/)).toBeInTheDocument()
  })
})
