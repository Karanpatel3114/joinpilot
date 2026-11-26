import type { ApiError } from '../types/api'

/** Base URL of the JoinPilot API (set VITE_API_URL for deployments). */
export const API_URL: string = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

/** An API error with the contract's code, message and details. */
export class ApiRequestError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, body: ApiError | null) {
    super(body?.error.message ?? `Request failed with status ${status}`)
    this.status = status
    this.code = body?.error.code ?? 'UNKNOWN'
    this.details = body?.error.details ?? {}
  }
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let body: ApiError | null = null
    try {
      body = (await response.json()) as ApiError
    } catch {
      body = null
    }
    throw new ApiRequestError(response.status, body)
  }
  return (await response.json()) as T
}

/** GET a JSON resource. */
export async function getJson<T>(path: string): Promise<T> {
  return parse<T>(await fetch(`${API_URL}${path}`))
}

/** POST JSON and read a JSON response. */
export async function postJson<T>(path: string, body: unknown): Promise<T> {
  return parse<T>(
    await fetch(`${API_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  )
}

/** POST files as multipart form data (field `files`). */
export async function postFiles<T>(path: string, files: File[]): Promise<T> {
  const form = new FormData()
  for (const file of files) form.append('files', file, file.name)
  return parse<T>(await fetch(`${API_URL}${path}`, { method: 'POST', body: form }))
}
