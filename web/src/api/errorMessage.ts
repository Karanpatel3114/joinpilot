import { ApiRequestError } from './client'

const UNREACHABLE =
  'The JoinPilot API could not be reached. The free demo server sleeps when idle and takes about a minute to wake up; this page keeps trying, or reload in a moment.'

/** What to tell people: the API's own message, or a cold-start note when it could not answer. */
export function errorMessage(error: unknown): string {
  // fetch rejects with a TypeError when the server cannot be reached at all
  if (error instanceof TypeError) return UNREACHABLE
  // the hosting proxy answers 502-504 without our error body while the server starts
  if (error instanceof ApiRequestError && error.code === 'UNKNOWN' && error.status >= 502) return UNREACHABLE
  return error instanceof Error ? error.message : 'Something went wrong.'
}
