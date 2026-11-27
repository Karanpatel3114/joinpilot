import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError } from '../api/client'
import { errorMessage } from '../api/errorMessage'
import { LoadingNote, SLOW_MS } from './LoadingNote'

describe('cold starts', () => {
  afterEach(() => vi.useRealTimers())

  it('explain an unreachable or starting API in plain words', () => {
    expect(errorMessage(new TypeError('Failed to fetch'))).toMatch(/takes about a minute to wake up/)
    expect(errorMessage(new ApiRequestError(502, null))).toMatch(/wake up/)
    const own = new ApiRequestError(503, { error: { code: 'LLM_UNAVAILABLE', message: 'Model busy.', details: {} } })
    expect(errorMessage(own)).toBe('Model busy.')
  })

  it('add a wake-up note to slow loads', () => {
    vi.useFakeTimers()
    render(<LoadingNote label="Loading projects…" />)
    expect(screen.getByRole('status')).toHaveTextContent(/^Loading projects…$/)
    act(() => vi.advanceTimersByTime(SLOW_MS))
    expect(screen.getByRole('status')).toHaveTextContent(/about a minute to wake up/)
  })
})
