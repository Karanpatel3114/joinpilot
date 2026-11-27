import type { ApiError } from '../types/api'
import { WORKSPACE_HEADER, workspaceId } from './workspace'

/** Base URL of the JoinPilot API (set VITE_API_URL for deployments). */
export const API_URL: string = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

/** An API error with the contract's code, message and details. */
export class ApiRequestError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, body: ApiError | null) {
    // Bodies without the contract's envelope (a proxy page, FastAPI's own `detail`) fall back.
    super(body?.error?.message ?? `Request failed with status ${status}`)
    this.status = status
    this.code = body?.error?.code ?? 'UNKNOWN'
    this.details = body?.error?.details ?? {}
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

/** Headers every request carries: the browser's private workspace. */
function baseHeaders(): Record<string, string> {
  return { [WORKSPACE_HEADER]: workspaceId() }
}

/**
 * Fetch an API file with the workspace header and save it in the browser.
 * A plain link cannot send headers, and putting the workspace id in a URL would leak
 * it into logs, history and shared links.
 */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const response = await fetch(`${API_URL}${path}`, { headers: baseHeaders() })
  if (!response.ok) await parse<never>(response)
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  // Revoking right away can cancel the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** GET a JSON resource. */
export async function getJson<T>(path: string): Promise<T> {
  return parse<T>(await fetch(`${API_URL}${path}`, { headers: baseHeaders() }))
}

/** POST JSON and read a JSON response. */
export async function postJson<T>(path: string, body: unknown): Promise<T> {
  return parse<T>(
    await fetch(`${API_URL}${path}`, {
      method: 'POST',
      headers: { ...baseHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  )
}

/** POST files as multipart form data (field `files`). */
export async function postFiles<T>(path: string, files: File[]): Promise<T> {
  const form = new FormData()
  for (const file of files) form.append('files', file, file.name)
  return parse<T>(await fetch(`${API_URL}${path}`, { method: 'POST', headers: baseHeaders(), body: form }))
}
