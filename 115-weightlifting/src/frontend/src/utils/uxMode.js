const STORAGE_KEY = 'wl_ux_mode'
const VALID = new Set(['simple', 'complex'])

export const getStoredUxMode = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return VALID.has(raw) ? raw : null
  } catch {
    return null
  }
}

export const resolveInitialUxMode = () => getStoredUxMode() || 'complex'

export const applyUxMode = (mode) => {
  if (typeof document === 'undefined') return
  if (mode === 'simple') {
    document.documentElement.setAttribute('data-ux-mode', 'simple')
  } else {
    document.documentElement.removeAttribute('data-ux-mode')
  }
}

export const setUxMode = (mode) => {
  if (!VALID.has(mode)) return
  try { localStorage.setItem(STORAGE_KEY, mode) } catch { /* quota, ignore */ }
  applyUxMode(mode)
}

export const toggleUxMode = (current) => {
  const next = current === 'simple' ? 'complex' : 'simple'
  setUxMode(next)
  return next
}
