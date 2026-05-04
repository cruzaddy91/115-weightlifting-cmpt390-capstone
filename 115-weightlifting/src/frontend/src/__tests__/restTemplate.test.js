import { describe, expect, it } from 'vitest'
import { buildRestDayExercises, createRestExercise } from '../utils/restTemplate'

describe('restTemplate', () => {
  it('creates a canonical rest exercise row', () => {
    const row = createRestExercise(3)
    expect(row.week).toBe('3')
    expect(row.name).toBe('Rest')
    expect(row.sets).toBe('')
    expect(row.reps).toBe('')
    expect(row.rest).toBe('')
  })

  it('builds one rest row per week', () => {
    const rows = buildRestDayExercises(4)
    expect(rows).toHaveLength(4)
    expect(rows.map((r) => r.week)).toEqual(['1', '2', '3', '4'])
    expect(rows.every((r) => r.name === 'Rest')).toBe(true)
  })
})

