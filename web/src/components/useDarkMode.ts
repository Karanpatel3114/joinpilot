import { useSyncExternalStore } from 'react'

function subscribe(onChange: () => void): () => void {
  const observer = new MutationObserver(onChange)
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
  return () => observer.disconnect()
}

const isDark = () => document.documentElement.classList.contains('dark')

/** True while the app's own theme toggle (the `dark` class on <html>) is set to dark. */
export function useDarkMode(): boolean {
  return useSyncExternalStore(subscribe, isDark, () => false)
}
