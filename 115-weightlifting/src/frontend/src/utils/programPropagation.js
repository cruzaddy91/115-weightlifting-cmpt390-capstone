const weekNum = (exercise) => {
  const raw = String(exercise?.week ?? '').trim()
  if (!raw) return 1
  const n = Number.parseInt(raw, 10)
  return Number.isFinite(n) && n > 0 ? n : 1
}

const emptyPrescriptionFields = {
  sets: '',
  reps: '',
  percent_1rm: '',
  rpe: '',
  weight: '',
  tempo: '',
  rest: '',
  notes: '',
  intensity: '',
}

export const propagateExerciseNamesAcrossWeeks = (programData, {
  sourceWeek = 1,
  maxWeeks = 1,
  overwriteNames = true,
} = {}) => {
  const sourceWeekNum = Math.max(1, Number.parseInt(String(sourceWeek), 10) || 1)
  const weekCap = Math.max(1, Number.parseInt(String(maxWeeks), 10) || 1)
  const days = Array.isArray(programData?.days) ? programData.days : []

  return {
    ...programData,
    days: days.map((day) => {
      const existing = Array.isArray(day?.exercises) ? day.exercises : []
      const source = existing
        .filter((exercise) => weekNum(exercise) === sourceWeekNum && String(exercise?.name || '').trim())
        .map((exercise) => String(exercise.name).trim())
      if (source.length === 0) return { ...day, exercises: existing }

      const byWeek = new Map()
      for (const exercise of existing) {
        const wk = weekNum(exercise)
        if (!byWeek.has(wk)) byWeek.set(wk, [])
        byWeek.get(wk).push({ ...exercise, week: String(wk) })
      }

      for (let wk = 1; wk <= weekCap; wk += 1) {
        if (wk === sourceWeekNum) continue
        const bucket = byWeek.get(wk) || []
        for (let i = 0; i < source.length; i += 1) {
          if (bucket[i]) {
            if (overwriteNames || !String(bucket[i].name || '').trim()) bucket[i].name = source[i]
          } else {
            bucket.push({
              week: String(wk),
              name: source[i],
              ...emptyPrescriptionFields,
            })
          }
        }
        byWeek.set(wk, bucket)
      }

      const merged = []
      for (let wk = 1; wk <= weekCap; wk += 1) {
        if (byWeek.has(wk)) merged.push(...byWeek.get(wk))
      }
      for (const [wk, bucket] of byWeek.entries()) {
        if (wk > weekCap) merged.push(...bucket)
      }

      return { ...day, exercises: merged }
    }),
  }
}

