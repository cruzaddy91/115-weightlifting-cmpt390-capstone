const WEEKDAY_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

// Stable day ids let completion records survive day-reorder and day-rename.
// Prior to this, athlete completion was keyed by day position, so moving a day
// silently remapped all completion entries to the wrong day. Now each day
// carries its own identifier; completion is keyed by that id.
/** Stable per-day identity for React keys and completion lookup (export for duplicate-day flows). */
export const generateDayId = () => `d${Math.random().toString(36).slice(2, 10)}`

export const createEmptyExercise = () => ({
  name: '',
  sets: '',
  reps: '',
  intensity: '',
  notes: '',
})

export const createEmptyDay = (day = `Day ${Date.now()}`) => ({
  id: generateDayId(),
  day,
  exercises: [],
})

export const createEmptyWeek = (weekStartDate = new Date().toISOString().split('T')[0]) => ({
  week_start_date: weekStartDate,
  days: WEEKDAY_LABELS.map((day) => createEmptyDay(day)),
})

// Reader side: prefer day.id when looking up completion entries; fall back to
// the legacy position-index key so programs saved before day ids were a thing
// still find their completion records. First new write will upgrade the key.
export const getDayCompletionKey = (day, dayIndex) => day?.id || String(dayIndex)
export const readDayCompletion = (completionData, day, dayIndex) => {
  const entries = completionData?.entries || {}
  return entries[getDayCompletionKey(day, dayIndex)] || entries[String(dayIndex)] || {}
}

export const normalizeProgramData = (programData, fallbackWeekStartDate = new Date().toISOString().split('T')[0]) => {
  const base = createEmptyWeek(fallbackWeekStartDate)

  if (!programData || typeof programData !== 'object') {
    return base
  }

  const normalizeDay = (day, index) => {
    const existingId = day?.id && typeof day.id === 'string' ? day.id : null
    return {
      // Deterministic fallback so legacy data without ids is stable across
      // reloads; new empty days get a random id from createEmptyDay.
      id: existingId || `d${index}`,
      day: day?.day || `Day ${index + 1}`,
      exercises: Array.isArray(day?.exercises)
        ? day.exercises.map((exercise) => ({
            name: exercise?.name || '',
            sets: exercise?.sets || '',
            reps: exercise?.reps || '',
            intensity: exercise?.intensity || '',
            percent_1rm: exercise?.percent_1rm || '',
            rpe: exercise?.rpe || '',
            weight: exercise?.weight || '',
            tempo: exercise?.tempo || '',
            rest: exercise?.rest || '',
            notes: exercise?.notes || '',
            week: exercise?.week || '',
          }))
        : [],
    }
  }

  const normalized = {
    week_start_date: programData.week_start_date || fallbackWeekStartDate,
    days: Array.isArray(programData.days) && programData.days.length > 0
      ? programData.days.map((day, index) => normalizeDay(day, index))
      : base.days,
  }
  if (programData.intensity_mode === 'percent_1rm' || programData.intensity_mode === 'rpe' || programData.intensity_mode === 'weight') {
    normalized.intensity_mode = programData.intensity_mode
  }
  return normalized
}

export const countExercises = (programData) => {
  if (!programData?.days) return 0
  return programData.days.reduce((total, day) => total + (day.exercises?.length || 0), 0)
}
