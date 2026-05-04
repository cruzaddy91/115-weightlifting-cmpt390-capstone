import { describe, expect, it } from 'vitest'
import { relativeTimeSince } from '../utils/relativeTime'

const NOW = new Date('2026-04-22T12:00:00Z').getTime()

describe('relativeTimeSince', () => {
  it('returns empty string for falsy/invalid input', () => {
    expect(relativeTimeSince('', NOW)).toBe('')
    expect(relativeTimeSince(null, NOW)).toBe('')
    expect(relativeTimeSince('not-a-date', NOW)).toBe('')
  })

  it("reports 'just now' for under ~45 seconds", () => {
    expect(relativeTimeSince('2026-04-22T11:59:30Z', NOW)).toBe('just now')
  })

  it('reports minutes granularity in the first hour', () => {
    expect(relativeTimeSince('2026-04-22T11:59:00Z', NOW)).toBe('1 min ago')
    expect(relativeTimeSince('2026-04-22T11:45:00Z', NOW)).toBe('15 min ago')
  })

  it('reports hours granularity within a day', () => {
    expect(relativeTimeSince('2026-04-22T10:00:00Z', NOW)).toBe('2 hr ago')
    expect(relativeTimeSince('2026-04-22T00:00:00Z', NOW)).toBe('12 hr ago')
  })

  it('reports yesterday / day granularity within a week', () => {
    expect(relativeTimeSince('2026-04-21T12:00:00Z', NOW)).toBe('yesterday')
    expect(relativeTimeSince('2026-04-18T12:00:00Z', NOW)).toBe('4 days ago')
  })

  it('reports week, month, and year buckets beyond that', () => {
    expect(relativeTimeSince('2026-04-14T12:00:00Z', NOW)).toBe('1 week ago')
    expect(relativeTimeSince('2026-03-10T12:00:00Z', NOW)).toBe('1 month ago')
    expect(relativeTimeSince('2025-01-10T12:00:00Z', NOW)).toMatch(/year/)
  })
})
