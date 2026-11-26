import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import answer from '../../../../shared/fixtures/answer.json'
import { renderAt } from '../../test/render'
import { API, server } from '../../test/server'

const PROJECT = '/projects/3f0b7c1e-6a2d-4c8e-9b1a-2d5e8f7a9c10?tab=Ask'

async function askQuestion(text: string) {
  await userEvent.type(await screen.findByLabelText('Your question'), text)
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
}

describe('Ask panel', () => {
  it('answers with rows, the guarded SQL and the evidence', async () => {
    let sent: unknown = null
    server.use(
      http.post(`${API}/projects/:id/ask`, async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json(answer)
      }),
    )
    renderAt(PROJECT)
    await askQuestion('Which 5 customers have the most overdue receivables?')
    const card = await screen.findByRole('article', { name: answer.question })
    expect(sent).toEqual({ question: 'Which 5 customers have the most overdue receivables?' })
    const rows = within(card).getByRole('table', { name: 'Answer rows' })
    expect(within(rows).getByText('South Torfield Logistics AG')).toBeInTheDocument()
    expect(within(rows).getByText('3,559,137.89')).toBeInTheDocument()
    expect(within(card).getByText(answer.evidence.explanation)).toBeInTheDocument()
    await userEvent.click(within(card).getByText('SQL and evidence'))
    expect(within(card).getByText(/FROM model\."v_bsid"/)).toBeInTheDocument()
    const evidence = within(card).getByLabelText('Evidence')
    expect(within(evidence).getByRole('link', { name: '7c9e6679' })).toBeInTheDocument()
    expect(within(evidence).getByText('v_bsid')).toBeInTheDocument()
  })

  it('explains a blocked question and how to fix a missing key', async () => {
    server.use(
      http.post(`${API}/projects/:id/ask`, () =>
        HttpResponse.json({
          ...answer,
          sql: null,
          columns: [],
          rows: [],
          evidence: null,
          blocked: true,
          reason_code: 'LLM_UNAVAILABLE',
          message: 'GEMINI_API_KEY is not set, so the language model is off.',
        }),
      ),
    )
    renderAt(PROJECT)
    await askQuestion('How many customers are in Germany?')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Add GEMINI_API_KEY to .env')
    expect(alert).toHaveTextContent('so the language model is off')
  })

  it('shows a single value as a number and runs an example question', async () => {
    server.use(
      http.post(`${API}/projects/:id/ask`, async ({ request }) => {
        const { question } = (await request.json()) as { question: string }
        return HttpResponse.json({
          ...answer,
          question,
          columns: ['open_amount'],
          rows: [{ open_amount: 32939507.11 }],
          chart: 'number',
        })
      }),
    )
    renderAt(PROJECT)
    await userEvent.click(
      await screen.findByRole('button', { name: 'What is the total amount of all open receivables?' }),
    )
    const card = await screen.findByRole('article', {
      name: 'What is the total amount of all open receivables?',
    })
    await waitFor(() => expect(within(card).getByText('32,939,507.11')).toBeInTheDocument())
    expect(within(card).queryByRole('table')).not.toBeInTheDocument()
  })
})
