import { describe, expect, it } from 'vitest'
import {
  createEmptyDay,
  createEmptyWeek,
  getDayCompletionKey,
  normalizeProgramData,
  readDayCompletion,
} from '../utils/dataStructure'

describe('dataStructure day ids', () => {
  it('createEmptyDay assigns a random id prefixed with d', () => {
    const a = createEmptyDay('Monday')
    const b = createEmptyDay('Monday')
    expect(a.id).toMatch(/^d[a-z0-9]+$/i)
    expect(b.id).toMatch(/^d[a-z0-9]+$/i)
    expect(a.id).not.toBe(b.id)
  })

  it('createEmptyWeek seeds each day with its own id', () => {
    const week = createEmptyWeek()
    const ids = week.days.map((d) => d.id)
    expect(new Set(ids).size).toBe(week.days.length)
    ids.forEach((id) => expect(id).toMatch(/^d/))
  })

  it('normalizeProgramData preserves existing day ids across reloads', () => {
    const input = {
      week_start_date: '2026-04-21',
      days: [
        { id: 'dmonday', day: 'Monday', exercises: [] },
        { id: 'dtuesday', day: 'Tuesday', exercises: [] },
      ],
    }
    const result = normalizeProgramData(input)
    expect(result.days.map((d) => d.id)).toEqual(['dmonday', 'dtuesday'])
  })

  it('normalizeProgramData backfills deterministic ids for legacy days without ids', () => {
    const input = {
      week_start_date: '2026-04-21',
      days: [
        { day: 'Monday', exercises: [] },
        { day: 'Tuesday', exercises: [] },
      ],
    }
    const result = normalizeProgramData(input)
    // Deterministic fallback -- same input yields same ids on reload.
    expect(result.days.map((d) => d.id)).toEqual(['d0', 'd1'])
    const secondPass = normalizeProgramData(input)
    expect(secondPass.days.map((d) => d.id)).toEqual(result.days.map((d) => d.id))
  })
})

describe('getDayCompletionKey / readDayCompletion', () => {
  it('prefers day.id when present', () => {
    expect(getDayCompletionKey({ id: 'dabc' }, 0)).toBe('dabc')
    expect(getDayCompletionKey({ id: 'dabc' }, 5)).toBe('dabc')
  })

  it('falls back to string(index) when no id', () => {
    expect(getDayCompletionKey({}, 2)).toBe('2')
    expect(getDayCompletionKey(null, 3)).toBe('3')
  })

  it('reads completion by id first, then by legacy index key', () => {
    const completion = {
      entries: {
        dabc: { 0: { completed: true } },
        1: { 0: { completed: false } }, // legacy index-keyed
      },
    }
    expect(readDayCompletion(completion, { id: 'dabc' }, 0)).toEqual({ 0: { completed: true } })
    expect(readDayCompletion(completion, { id: 'dnew' }, 1)).toEqual({ 0: { completed: false } })
    expect(readDayCompletion(completion, { id: 'dnothing' }, 99)).toEqual({})
  })
})
