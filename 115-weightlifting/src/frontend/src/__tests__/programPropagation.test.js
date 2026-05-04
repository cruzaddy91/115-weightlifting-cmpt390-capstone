import { describe, expect, it } from 'vitest'
import { propagateExerciseNamesAcrossWeeks } from '../utils/programPropagation'

describe('programPropagation', () => {
  it('copies source-week exercise names to all target weeks', () => {
    const programData = {
      week_start_date: '2026-04-20',
      days: [
        {
          day: 'Monday',
          exercises: [
            { week: '1', name: 'Snatch', sets: '4', reps: '2' },
            { week: '1', name: 'Pulls', sets: '4', reps: '3' },
            { week: '2', name: '', sets: '5', reps: '2' },
          ],
        },
      ],
    }

    const next = propagateExerciseNamesAcrossWeeks(programData, { sourceWeek: 1, maxWeeks: 4 })
    const monday = next.days[0].exercises
    const week2 = monday.filter((row) => String(row.week) === '2')
    const week4 = monday.filter((row) => String(row.week) === '4')

    expect(week2[0].name).toBe('Snatch')
    expect(week2[0].sets).toBe('5')
    expect(week2[1].name).toBe('Pulls')
    expect(week2[1].sets).toBe('')
    expect(week4.map((row) => row.name)).toEqual(['Snatch', 'Pulls'])
  })

  it('does nothing when source week has no named exercises', () => {
    const programData = {
      days: [
        { day: 'Monday', exercises: [{ week: '1', name: '' }, { week: '2', name: 'Keep me' }] },
      ],
    }
    const next = propagateExerciseNamesAcrossWeeks(programData, { sourceWeek: 1, maxWeeks: 4 })
    expect(next).toEqual(programData)
  })
})

