import { describe, expect, it } from 'vitest'
import { programTitleForDisplay } from '../utils/safeDisplay'

describe('programTitleForDisplay', () => {
  it('returns empty for nullish or whitespace-only', () => {
    expect(programTitleForDisplay(null)).toBe('')
    expect(programTitleForDisplay(undefined)).toBe('')
    expect(programTitleForDisplay('   ')).toBe('')
  })

  it('passes through normal titles', () => {
    expect(programTitleForDisplay('Current Block — jon_snow')).toBe('Current Block — jon_snow')
    expect(programTitleForDisplay('Accumulation Block 3')).toBe('Accumulation Block 3')
  })

  it('removes angle brackets so titles never read as markup', () => {
    expect(programTitleForDisplay("<script>alert('xss')</script> Sneaky")).toBe(
      "scriptalert('xss')/script Sneaky",
    )
    expect(programTitleForDisplay('<<foo>>')).toBe('foo')
  })
})
