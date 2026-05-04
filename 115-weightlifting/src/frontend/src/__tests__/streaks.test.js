import { describe, expect, it } from 'vitest'
import {
  COMPLETION_MILESTONES,
  STREAK_MILESTONES,
  computeLifetimeCompletions,
  computeStreak,
  crossedCompletionMilestone,
  crossedStreakMilestone,
  hasMilestoneFired,
  loadFiredMilestones,
  markMilestoneFired,
  todayLocalDateKey,
} from '../utils/streaks'

// Minimal in-memory Storage stand-in so the persistence tests don't depend on
// jsdom's localStorage state leaking between tests.
const makeMemoryStorage = () => {
  const data = new Map()
  return {
    getItem: (k) => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => { data.set(k, String(v)) },
    removeItem: (k) => { data.delete(k) },
    clear: () => data.clear(),
  }
}

const atUTC = (iso) => new Date(`${iso}T12:00:00Z`)

describe('computeStreak', () => {
  it('returns 0 when the athlete has no logs at all', () => {
    expect(computeStreak([], atUTC('2026-04-22'))).toBe(0)
  })

  it('counts a single log today as a 1-day streak', () => {
    const logs = [{ date: '2026-04-22' }]
    expect(computeStreak(logs, atUTC('2026-04-22'))).toBe(1)
  })

  it('keeps counting if today is missing but yesterday is logged', () => {
    const logs = [{ date: '2026-04-21' }, { date: '2026-04-20' }]
    expect(computeStreak(logs, atUTC('2026-04-22'))).toBe(2)
  })

  it('resets to 0 after a 2-day gap', () => {
    const logs = [{ date: '2026-04-18' }, { date: '2026-04-17' }]
    expect(computeStreak(logs, atUTC('2026-04-22'))).toBe(0)
  })

  it('dedupes multiple logs on the same calendar day', () => {
    const logs = [
      { date: '2026-04-22' }, { date: '2026-04-22' }, { date: '2026-04-22' },
      { date: '2026-04-21' },
    ]
    expect(computeStreak(logs, atUTC('2026-04-22'))).toBe(2)
  })

  it('breaks the streak at the first gap, even if older days exist', () => {
    const logs = [
      { date: '2026-04-22' }, { date: '2026-04-21' }, { date: '2026-04-20' },
      // gap on 2026-04-19
      { date: '2026-04-18' }, { date: '2026-04-17' },
    ]
    expect(computeStreak(logs, atUTC('2026-04-22'))).toBe(3)
  })
})

describe('computeLifetimeCompletions', () => {
  it('returns 0 for empty completions map', () => {
    expect(computeLifetimeCompletions({})).toBe(0)
    expect(computeLifetimeCompletions(null)).toBe(0)
  })

  it('counts every completed: true flag across every program/day/exercise', () => {
    const completions = {
      12: { entries: {
        d0: { 0: { completed: true }, 1: { completed: false }, 2: { completed: true } },
        d1: { 0: { completed: true } },
      } },
      13: { entries: {
        d0: { 0: { completed: true }, 1: { completed: true } },
      } },
    }
    expect(computeLifetimeCompletions(completions)).toBe(5)
  })

  it('ignores entries that are missing the completed flag', () => {
    const completions = {
      1: { entries: { d0: { 0: {}, 1: { result: '105kg' } } } },
    }
    expect(computeLifetimeCompletions(completions)).toBe(0)
  })
})

describe('milestone crossing', () => {
  it('fires the highest completion milestone strictly crossed in a single save', () => {
    expect(crossedCompletionMilestone(0, 1)?.count).toBe(1)
    expect(crossedCompletionMilestone(9, 10)?.count).toBe(10)
    expect(crossedCompletionMilestone(24, 26)?.count).toBe(25)
    // Jumping from 8 to 30 in one step lands on the *highest* in-range stop.
    expect(crossedCompletionMilestone(8, 30)?.count).toBe(25)
  })

  it('returns null when no milestone is crossed', () => {
    expect(crossedCompletionMilestone(10, 10)).toBeNull()
    expect(crossedCompletionMilestone(11, 20)).toBeNull()
    expect(crossedCompletionMilestone(5, 4)).toBeNull()
  })

  it('handles streak milestones on the same rules', () => {
    expect(crossedStreakMilestone(2, 3)?.count).toBe(3)
    expect(crossedStreakMilestone(6, 7)?.count).toBe(7)
    expect(crossedStreakMilestone(7, 7)).toBeNull()
  })

  it('exports monotonically-increasing milestone tables', () => {
    for (let i = 1; i < COMPLETION_MILESTONES.length; i += 1) {
      expect(COMPLETION_MILESTONES[i].count).toBeGreaterThan(COMPLETION_MILESTONES[i - 1].count)
    }
    for (let i = 1; i < STREAK_MILESTONES.length; i += 1) {
      expect(STREAK_MILESTONES[i].count).toBeGreaterThan(STREAK_MILESTONES[i - 1].count)
    }
  })

  it('every milestone has a non-empty humor message', () => {
    for (const stop of [...COMPLETION_MILESTONES, ...STREAK_MILESTONES]) {
      expect(stop.message.trim().length).toBeGreaterThan(0)
    }
  })
})

describe('fired-milestone persistence', () => {
  it('returns empty set when storage has nothing for this user', () => {
    const storage = makeMemoryStorage()
    expect(loadFiredMilestones(42, storage).size).toBe(0)
    expect(hasMilestoneFired(42, 'completion', 1, storage)).toBe(false)
  })

  it('marks and recalls a fired milestone', () => {
    const storage = makeMemoryStorage()
    markMilestoneFired(42, 'completion', 1, storage)
    expect(hasMilestoneFired(42, 'completion', 1, storage)).toBe(true)
    // Only the exact kind:count combo fires once
    expect(hasMilestoneFired(42, 'streak', 1, storage)).toBe(false)
    expect(hasMilestoneFired(42, 'completion', 10, storage)).toBe(false)
  })

  it('keys fired milestones per-user so athletes sharing a browser do not suppress each other', () => {
    const storage = makeMemoryStorage()
    markMilestoneFired(42, 'completion', 1, storage)
    expect(hasMilestoneFired(42, 'completion', 1, storage)).toBe(true)
    expect(hasMilestoneFired(99, 'completion', 1, storage)).toBe(false)
  })

  it('gracefully handles corrupted storage payloads (returns empty set, does not throw)', () => {
    const storage = makeMemoryStorage()
    storage.setItem('wl_milestones_fired:42', '{not valid json')
    expect(loadFiredMilestones(42, storage).size).toBe(0)
  })

  it('marking the same milestone twice is idempotent', () => {
    const storage = makeMemoryStorage()
    markMilestoneFired(42, 'completion', 1, storage)
    markMilestoneFired(42, 'completion', 1, storage)
    markMilestoneFired(42, 'completion', 1, storage)
    expect(loadFiredMilestones(42, storage).size).toBe(1)
  })
})

describe('todayLocalDateKey', () => {
  it('returns a YYYY-MM-DD key derived from the local date of the given instant', () => {
    // Pick a representative local noon to dodge timezone edges.
    const noonLocal = new Date(2026, 3, 22, 12, 0, 0) // April is month index 3
    expect(todayLocalDateKey(noonLocal)).toBe('2026-04-22')
  })

  it('pads single-digit months and days', () => {
    const d = new Date(2026, 0, 5, 10, 0, 0) // January 5
    expect(todayLocalDateKey(d)).toBe('2026-01-05')
  })

  it('matches the day the user actually sees even just after local midnight', () => {
    // One second after local midnight on a given date.
    const justAfterMidnight = new Date(2026, 3, 22, 0, 0, 1)
    expect(todayLocalDateKey(justAfterMidnight)).toBe('2026-04-22')
  })
})
