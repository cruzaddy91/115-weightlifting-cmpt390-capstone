import { beforeEach, describe, expect, it } from 'vitest'
import { applyUxMode, resolveInitialUxMode, setUxMode, toggleUxMode } from '../utils/uxMode'

describe('uxMode', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-ux-mode')
  })

  it('defaults to complex mode', () => {
    expect(resolveInitialUxMode()).toBe('complex')
  })

  it('persists simple mode and applies the document flag', () => {
    setUxMode('simple')
    expect(resolveInitialUxMode()).toBe('simple')
    expect(document.documentElement.getAttribute('data-ux-mode')).toBe('simple')
  })

  it('toggles back to complex mode', () => {
    setUxMode('simple')
    expect(toggleUxMode('simple')).toBe('complex')
    expect(document.documentElement.hasAttribute('data-ux-mode')).toBe(false)
  })

  it('can apply complex mode without storage', () => {
    applyUxMode('simple')
    applyUxMode('complex')
    expect(document.documentElement.hasAttribute('data-ux-mode')).toBe(false)
  })
})
