// Athlete-side encouragement math. Two numbers drive the hero encouragement
// pill and the humor-toast trigger:
//
//   - streak (consecutive calendar days ending today or yesterday that have
//     at least one workout log). Uses workoutLogs because those records carry
//     an explicit date; per-exercise completion entries do not.
//   - lifetimeCompletions (count of every completed: true flag across every
//     program's completion_data). This is the number we watch for milestone
//     crossings so we can pop a one-time toast with weightlifting-jargon
//     humor the first time the athlete hits 1 / 10 / 25 / 50 / 100 / ...
//
// Humor is intentionally heavy on jargon (CNS, hookgrip, third pull, block
// periodization) per the advisor's "make it fun for lifters, not generic
// fitness" note. Text-only per the no-emoji rule for this app.

// Format a Date as YYYY-MM-DD using its LOCAL fields. Using local time
// throughout (both here and in the dashboard hero that reads new Date().getDay())
// keeps the streak aligned with what day the athlete thinks they're on. A UTC
// pivot at midnight UTC would flip the streak day a few hours before / after
// the athlete's local midnight, silently awarding or dropping a day depending
// on timezone.
const toLocalDateKey = (d) => {
  if (!d || Number.isNaN(d.getTime())) return null
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const localMidnight = (now = new Date()) =>
  new Date(now.getFullYear(), now.getMonth(), now.getDate())

// Build a set of YYYY-MM-DD strings representing days on which the athlete
// logged at least one workout. Log dates stored by the backend are plain
// date strings (no timezone), so we read them verbatim.
const uniqueLogDates = (workoutLogs) => {
  const set = new Set()
  for (const log of workoutLogs || []) {
    if (log?.date) set.add(String(log.date).slice(0, 10))
  }
  return set
}

// Streak = run of consecutive days ending on today (or yesterday, if the
// athlete hasn't logged yet today). Zero if no log in the last 48h.
// All day arithmetic happens in the athlete's LOCAL timezone -- "today" in
// the hero and "today" in the streak agree even at the edges of the day.
export const computeStreak = (workoutLogs, now = new Date()) => {
  const logSet = uniqueLogDates(workoutLogs)
  if (logSet.size === 0) return 0

  const today = localMidnight(now)
  const todayKey = toLocalDateKey(today)
  const yesterday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1)
  const yesterdayKey = toLocalDateKey(yesterday)

  let cursor
  if (logSet.has(todayKey)) cursor = today
  else if (logSet.has(yesterdayKey)) cursor = yesterday
  else return 0

  let count = 0
  // Walk backwards one calendar day at a time. Using setDate-arithmetic keeps
  // DST transitions honest (adding/subtracting 24*60*60*1000ms would drift by
  // an hour twice a year on the fall-back / spring-forward day).
  while (logSet.has(toLocalDateKey(cursor))) {
    count += 1
    cursor = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() - 1)
  }
  return count
}

// Sum of every `completed: true` flag across every program's completion_data.
// `completions` shape: { [programId]: { entries: { [dayKey]: { [exIdx]: { completed, ... } } } } }.
export const computeLifetimeCompletions = (completions) => {
  let total = 0
  for (const programId in completions || {}) {
    const entries = completions[programId]?.entries || {}
    for (const dayKey in entries) {
      const dayBag = entries[dayKey] || {}
      for (const exIdx in dayBag) {
        if (dayBag[exIdx]?.completed) total += 1
      }
    }
  }
  return total
}

// Ordered ascending so we can find the highest threshold *just crossed*.
// Humor leans on weightlifting jargon by design -- advisor wanted it lifter-
// flavored, not a generic fitness app tone.
export const COMPLETION_MILESTONES = [
  { count: 1,    message: 'First lift logged. The barbell remembers.' },
  { count: 10,   message: '10 completions. Your CNS is taking notes.' },
  { count: 25,   message: '25 down. Chalk it up -- the third pull is starting to feel like yours.' },
  { count: 50,   message: '50 lifts in. Hookgrip is earning its name.' },
  { count: 100,  message: 'Triple digits. Welcome to the rarefied air of lifters who actually track.' },
  { count: 250,  message: '250 logged. Somewhere a monolift just sighed your name.' },
  { count: 500,  message: '500 reps of work. Bulgarian territory -- hope you are sleeping.' },
  { count: 1000, message: 'Four figures of bar work. You *are* the block periodization.' },
]

export const STREAK_MILESTONES = [
  { count: 3,  message: 'Three-day streak. Habit is forming. So are forearms.' },
  { count: 7,  message: 'Seven days -- a full micro-cycle of consistency.' },
  { count: 14, message: 'Two weeks locked in. Welcome to active recovery\u2019s least-favored child.' },
  { count: 21, message: 'Three weeks. The taper nerds are getting jealous.' },
  { count: 30, message: '30 without missing. Your CNS has sent a strongly-worded letter.' },
  { count: 60, message: '60-day streak. This is no longer training. This is identity.' },
  { count: 90, message: 'Ninety. Deload at your own risk -- momentum has a mind of its own.' },
]

// Given a previous count and a new count, return the milestone JUST crossed
// (the highest threshold strictly greater than `prev` and less-or-equal to
// `next`). Returns null if no threshold was crossed in this step. Callers use
// this to show a one-time toast without any backend state.
const findCrossedMilestone = (prev, next, table) => {
  if (next <= prev) return null
  let crossed = null
  for (const stop of table) {
    if (stop.count > prev && stop.count <= next) crossed = stop
  }
  return crossed
}

export const crossedCompletionMilestone = (prev, next) =>
  findCrossedMilestone(prev, next, COMPLETION_MILESTONES)

export const crossedStreakMilestone = (prev, next) =>
  findCrossedMilestone(prev, next, STREAK_MILESTONES)

// Persisted "already fired" set, keyed per-user so one athlete's celebrations
// don't suppress another's on the same browser. We refuse to re-fire a
// milestone the athlete has already seen, which matters when they unmark and
// remark an exercise (lifetime 1 -> 0 -> 1 would otherwise trigger the
// 'First lift logged' humor twice).
const storageKey = (userId) => `wl_milestones_fired:${userId || 'anon'}`

export const loadFiredMilestones = (userId, storage = globalThis.localStorage) => {
  try {
    const raw = storage?.getItem(storageKey(userId))
    if (!raw) return new Set()
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? new Set(parsed) : new Set()
  } catch {
    return new Set()
  }
}

export const markMilestoneFired = (userId, kind, count, storage = globalThis.localStorage) => {
  const set = loadFiredMilestones(userId, storage)
  set.add(`${kind}:${count}`)
  try { storage?.setItem(storageKey(userId), JSON.stringify([...set])) } catch { /* quota, ignore */ }
  return set
}

export const hasMilestoneFired = (userId, kind, count, storage = globalThis.localStorage) =>
  loadFiredMilestones(userId, storage).has(`${kind}:${count}`)

// Public local-date helpers so other modules (e.g. AthleteDashboard's
// auto-log) compute today using the same rules as the streak.
export const todayLocalDateKey = (now = new Date()) => toLocalDateKey(localMidnight(now))
export const __test = { toLocalDateKey, localMidnight, uniqueLogDates }
