/** The header and query name the API reads the workspace from (docs/contract.md, "Workspaces"). */
export const WORKSPACE_HEADER = 'X-Workspace'
const KEY = 'joinpilot-workspace'

let memory: string | null = null

function newId(): string {
  return crypto.randomUUID().replaceAll('-', '')
}

/**
 * This browser's private workspace id: made once, then kept in local storage.
 * Without storage (private windows) it lasts for the page's lifetime.
 */
export function workspaceId(): string {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved && /^[A-Za-z0-9_-]{16,64}$/.test(saved)) return saved
    const id = newId()
    localStorage.setItem(KEY, id)
    return id
  } catch {
    memory ??= newId()
    return memory
  }
}
