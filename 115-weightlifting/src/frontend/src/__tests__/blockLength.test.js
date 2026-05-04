import { describe, expect, it } from 'vitest'
import { BLOCK_PRESETS, endDateForBlock, inferBlockKey } from '../utils/blockLength'

describe('blockLength', () => {
  it('exposes presets aligned with Excel template tabs (4 / 8 / 16 Week)', () => {
    expect(BLOCK_PRESETS.map((p) => p.weeks)).toEqual([4, 8, 16])
  })

  it('computes correct end date for a 4-week block starting on a Monday', () => {
    // 2026-04-20 is a Monday
    expect(endDateForBlock('2026-04-20', 4)).toBe('2026-05-17') // 4*7 - 1 = 27 days later
  })

  it('computes correct end date for an 8-week block', () => {
    expect(endDateForBlock('2026-01-05', 8)).toBe('2026-03-01') // 55 days later
  })

  it('computes correct end date for a 16-week block', () => {
    expect(endDateForBlock('2026-04-20', 16)).toBe('2026-08-09')
  })

  it('returns empty string for invalid inputs', () => {
    expect(endDateForBlock('', 4)).toBe('')
    expect(endDateForBlock('2026-04-20', 0)).toBe('')
    expect(endDateForBlock('2026-04-20', -1)).toBe('')
    expect(endDateForBlock('not-a-date', 4)).toBe('')
  })

  it("infers block key from start/end date pair", () => {
    expect(inferBlockKey('2026-04-20', '2026-05-17')).toBe('4wk')
    expect(inferBlockKey('2026-04-20', '2026-06-14')).toBe('8wk')
    expect(inferBlockKey('2026-04-20', '2026-08-09')).toBe('16wk')
    expect(inferBlockKey('2026-01-05', '2026-04-26')).toBe('16wk')
    expect(inferBlockKey('2026-04-20', '2026-05-03')).toBe('custom') // 2-week span not a preset
    expect(inferBlockKey('2026-04-20', '2026-07-12')).toBe('custom') // 12-week span not a preset
  })

  it("falls back to 'custom' for non-matching lengths", () => {
    expect(inferBlockKey('2026-04-20', '2026-04-30')).toBe('custom') // 11 days
    expect(inferBlockKey('', '2026-04-30')).toBe('custom')
    expect(inferBlockKey('2026-04-20', '')).toBe('custom')
  })
})
