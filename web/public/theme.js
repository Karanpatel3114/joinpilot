// Apply a saved night-mode choice before the first paint, so the page never flashes light.
// Day mode is the default; the theme toggle stores the choice under this key.
try {
  if (localStorage.getItem('joinpilot-theme') === 'dark') document.documentElement.classList.add('dark')
} catch {
  // storage can be unavailable (private mode): stay in day mode
}
