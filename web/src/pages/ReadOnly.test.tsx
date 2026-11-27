import { screen } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import projects from '../../../shared/fixtures/projects.json'
import { renderAt } from '../test/render'
import { API, server } from '../test/server'

const sample = { ...projects[0], name: 'Sample ERP (read-only)', read_only: true }

describe('the shared sample project', () => {
  it('is offered from the home page and marked read-only', async () => {
    server.use(http.get(`${API}/projects`, () => HttpResponse.json([sample])))
    renderAt('/')
    const open = await screen.findByRole('link', { name: 'Open the sample project' })
    expect(open).toHaveAttribute('href', `/projects/${sample.id}?tab=Dashboard`)
    expect(screen.getByText('sample · read-only')).toBeInTheDocument()
  })

  it('hides uploads and new runs', async () => {
    server.use(http.get(`${API}/projects`, () => HttpResponse.json([sample])))
    renderAt(`/projects/${sample.id}?tab=Runs`)
    expect(await screen.findByText(/A shared sample, built when the demo started/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /load erp sample/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /start run/i })).not.toBeInTheDocument()
  })

  it('shows no upload buttons while the project list is still loading', async () => {
    let release = () => {}
    const pending = new Promise<void>((resolve) => (release = resolve))
    server.use(
      http.get(`${API}/projects`, async () => {
        await pending
        return HttpResponse.json([sample])
      }),
    )
    renderAt(`/projects/${sample.id}`)
    expect(await screen.findByText('Loading project…')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /load erp sample/i })).not.toBeInTheDocument()
    release()
    expect(await screen.findByText(/A shared sample/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /load erp sample/i })).not.toBeInTheDocument()
  })

  it('explains a project this browser cannot see', async () => {
    server.use(http.get(`${API}/projects`, () => HttpResponse.json([])))
    renderAt(`/projects/${sample.id}`)
    expect(await screen.findByText(/This project was not found/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /load erp sample/i })).not.toBeInTheDocument()
  })
})
