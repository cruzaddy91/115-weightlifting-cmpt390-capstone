import { describe, expect, it } from 'vitest'
import { _pickDefaultDayId, _isDayComplete } from '../pages/AthleteDashboard'

const makeDay = (id, name, exerciseCount) => ({
  id,
  day: name,
  exercises: Array.from({ length: exerciseCount }, () => ({})),
})

describe('pickDefaultDayId', () => {
  it('returns today when today has work left', () => {
    const days = [
      makeDay('d0', 'Monday', 3),
      makeDay('d1', 'Wednesday', 2),
      makeDay('d2', 'Friday', 3),
    ]
    const entries = { d1: { 0: { completed: true } } } // Wed: 1 of 2 done
    expect(_pickDefaultDayId(days, entries, 'Wednesday')).toBe('d1')
  })

  it('advances to the next day with work left when today is fully done', () => {
    const days = [
      makeDay('d0', 'Monday', 3),
      makeDay('d1', 'Wednesday', 2),
      makeDay('d2', 'Friday', 3),
    ]
    // Wed is complete; Fri still has work.
    const entries = { d1: { 0: { completed: true }, 1: { completed: true } } }
    expect(_pickDefaultDayId(days, entries, 'Wednesday')).toBe('d2')
  })

  it('wraps around when today is Friday and only Monday has work left', () => {
    const days = [
      makeDay('d0', 'Monday', 3),
      makeDay('d1', 'Wednesday', 2),
      makeDay('d2', 'Friday', 3),
    ]
    const entries = {
      d2: { 0: { completed: true }, 1: { completed: true }, 2: { completed: true } }, // Fri done
      d1: { 0: { completed: true }, 1: { completed: true } }, // Wed done
    }
    expect(_pickDefaultDayId(days, entries, 'Friday')).toBe('d0')
  })

  it('returns today even when every day is complete (the congratulations view)', () => {
    const days = [
      makeDay('d0', 'Monday', 2),
      makeDay('d1', 'Wednesday', 2),
    ]
    const entries = {
      d0: { 0: { completed: true }, 1: { completed: true } },
      d1: { 0: { completed: true }, 1: { completed: true } },
    }
    expect(_pickDefaultDayId(days, entries, 'Wednesday')).toBe('d1')
  })

  it('falls back to the first incomplete day when today is not in the program', () => {
    const days = [
      makeDay('d0', 'Monday', 3),
      makeDay('d1', 'Wednesday', 2),
    ]
    const entries = {}
    // Today is Sunday; no match -> first incomplete is Monday.
    expect(_pickDefaultDayId(days, entries, 'Sunday')).toBe('d0')
  })

  it('returns null when the program has no days', () => {
    expect(_pickDefaultDayId([], {}, 'Wednesday')).toBeNull()
    expect(_pickDefaultDayId(null, {}, 'Wednesday')).toBeNull()
  })
})

describe('_isDayComplete', () => {
  it('treats a 0-exercise day as complete (rest day)', () => {
    expect(_isDayComplete({ id: 'r', day: 'Sunday', exercises: [] }, {})).toBe(true)
  })

  it('returns false when fewer exercises are completed than total', () => {
    const day = { id: 'd', day: 'Wed', exercises: [{}, {}] }
    const entries = { d: { 0: { completed: true } } }
    expect(_isDayComplete(day, entries)).toBe(false)
  })

  it('returns true when every exercise for the day has completed: true', () => {
    const day = { id: 'd', day: 'Wed', exercises: [{}, {}] }
    const entries = { d: { 0: { completed: true }, 1: { completed: true } } }
    expect(_isDayComplete(day, entries)).toBe(true)
  })
})
