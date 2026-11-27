import { describe, expect, it } from 'vitest'
import { ApiRequestError } from './client'
import { nextPoll, shouldRetry } from './hooks'

function apiError(status: number, details: Record<string, unknown> = {}) {
  return new ApiRequestError(status, { error: { code: 'X', message: 'x', details } })
}

describe('polling after errors', () => {
  it('keeps its schedule while refreshes work', () => {
    expect(nextPoll(null, 1000)).toBe(1000)
  })

  it('stops on answers that waiting will not change', () => {
    for (const status of [404, 409, 422]) expect(nextPoll(apiError(status), 1000)).toBe(false)
  })

  it('waits as long as the server asks after 429', () => {
    expect(nextPoll(apiError(429, { retry_after_seconds: 42 }), 1000)).toBe(42_000)
    expect(nextPoll(apiError(429), 1000)).toBe(30_000)
  })

  it('backs off while the API is down or waking up', () => {
    expect(nextPoll(new TypeError('Failed to fetch'), 1000)).toBe(10_000)
    expect(nextPoll(apiError(502), 1000)).toBe(10_000)
  })

  it('retries once, but never a client error', () => {
    expect(shouldRetry(0, new TypeError('Failed to fetch'))).toBe(true)
    expect(shouldRetry(1, apiError(503))).toBe(false)
    expect(shouldRetry(0, apiError(404))).toBe(false)
    expect(shouldRetry(0, apiError(429))).toBe(false)
  })
})
