import { describe, expect, it } from 'vitest'
import { downloadUrl } from './client'
import { workspaceId } from './workspace'

describe('workspace id', () => {
  it('is made once per browser and kept', () => {
    const id = workspaceId()
    expect(id).toMatch(/^[A-Za-z0-9_-]{16,64}$/)
    expect(workspaceId()).toBe(id)
    expect(localStorage.getItem('joinpilot-workspace')).toBe(id)
  })

  it('rides along on download links', () => {
    expect(downloadUrl('/runs/r1/export?dialect=duckdb')).toMatch(
      new RegExp(`/runs/r1/export\\?dialect=duckdb&workspace=${workspaceId()}$`),
    )
  })
})
