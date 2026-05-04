// Color-scheme preference: persisted per-browser so the same athlete sees
// the theme they chose last time. On first visit we respect the OS-level
// prefers-color-scheme, falling back to 'dark' (our brand default).
//
// Applied via data-theme="light" on <html>; index.css has the token overrides
// gated on that attribute. `dark` is the absence of the attribute so the
// default :root tokens win -- no extra rule needed for dark.

const STORAGE_KEY = 'wl_color_scheme'
const VALID = new Set(['light', 'dark'])

export const getStoredTheme = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return VALID.has(raw) ? raw : null
  } catch {
    return null
  }
}

export const getSystemTheme = () => {
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
  }
  return 'dark'
}

export const resolveInitialTheme = () => getStoredTheme() || getSystemTheme()

export const applyTheme = (theme) => {
  if (typeof document === 'undefined') return
  if (theme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light')
  } else {
    document.documentElement.removeAttribute('data-theme')
  }
}

export const setTheme = (theme) => {
  if (!VALID.has(theme)) return
  try { localStorage.setItem(STORAGE_KEY, theme) } catch { /* quota, ignore */ }
  applyTheme(theme)
}

export const toggleTheme = (current) => {
  const next = current === 'light' ? 'dark' : 'light'
  setTheme(next)
  return next
}
