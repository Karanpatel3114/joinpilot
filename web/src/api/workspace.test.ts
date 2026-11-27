import { afterEach, describe, expect, it, vi } from 'vitest'
import { downloadFile } from './client'
import { workspaceId } from './workspace'

describe('workspace id', () => {
  it('is made once per browser and kept', () => {
    const id = workspaceId()
    expect(id).toMatch(/^[A-Za-z0-9_-]{16,64}$/)
    expect(workspaceId()).toBe(id)
    expect(localStorage.getItem('joinpilot-workspace')).toBe(id)
  })

  afterEach(() => vi.restoreAllMocks())

  it('is sent as a header on downloads, never in the URL', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('SELECT 1;'))
    URL.createObjectURL = vi.fn(() => 'blob:sql')
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await downloadFile('/runs/r1/export?dialect=duckdb', 'model.sql')
    const [url, init] = fetch.mock.calls[0]
    expect(String(url)).toMatch(/\/runs\/r1\/export\?dialect=duckdb$/)
    expect(init?.headers).toEqual({ 'X-Workspace': workspaceId() })
    expect(click).toHaveBeenCalledOnce()
  })
})
