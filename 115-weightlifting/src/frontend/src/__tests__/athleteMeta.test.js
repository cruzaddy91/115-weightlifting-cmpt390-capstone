import { describe, expect, it } from 'vitest'
import { athleteProfileSuffix } from '../utils/athleteMeta'

describe('athleteProfileSuffix', () => {
  it('builds suffix from program athlete_* fields', () => {
    const s = athleteProfileSuffix({
      athlete_competitive_weight_class: '89 kg',
      athlete_bodyweight_kg: '79.5',
    })
    expect(s).toContain('89 kg')
    expect(s).toContain('79.5 kg BW')
  })

  it('returns empty when no data', () => {
    expect(athleteProfileSuffix({})).toBe('')
    expect(athleteProfileSuffix(null)).toBe('')
  })
})
