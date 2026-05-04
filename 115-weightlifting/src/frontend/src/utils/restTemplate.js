const normalizeWeekCount = (value) => {
  const n = Number.parseInt(String(value ?? ''), 10)
  return Number.isFinite(n) && n > 0 ? n : 1
}

export const createRestExercise = (week) => ({
  week: String(normalizeWeekCount(week)),
  name: 'Rest',
  sets: '',
  reps: '',
  percent_1rm: '',
  rpe: '',
  weight: '',
  tempo: '',
  rest: '',
  intensity: '',
  notes: '',
})

export const buildRestDayExercises = (weekCount) => {
  const totalWeeks = normalizeWeekCount(weekCount)
  const rows = []
  for (let week = 1; week <= totalWeeks; week += 1) rows.push(createRestExercise(week))
  return rows
}

