import { useEffect, useMemo, useRef, useState } from 'react'
import AthleteExerciseCard from '../components/AthleteExerciseCard'
import AthleteTrainingTrendCharts from '../components/AthleteTrainingTrendCharts'
import WeekStrip from '../components/WeekStrip'
import {
  calculateRobi,
  calculateSinclair,
  createPersonalRecord,
  createWorkoutLog,
  getPersonalRecords,
  getProgramsFromBackend,
  getWorkoutLogs,
  patchCurrentUserProfile,
  updateProgramCompletion,
} from '../services/api'
import { getCurrentUser } from '../utils/auth'
import { getDayCompletionKey, normalizeProgramData } from '../utils/dataStructure'
import { formatApiError } from '../utils/errors'
import { athleteProfileSuffix } from '../utils/athleteMeta'
import { programTitleForDisplay } from '../utils/safeDisplay'
import {
  computeLifetimeCompletions,
  computeStreak,
  crossedCompletionMilestone,
  crossedStreakMilestone,
  hasMilestoneFired,
  markMilestoneFired,
  todayLocalDateKey,
} from '../utils/streaks'
import { relativeTimeSince } from '../utils/relativeTime'

const WEEKDAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

const liftLabels = { snatch: 'Snatch', clean_jerk: 'Clean & Jerk', total: 'Total' }

// Default-day selection for 'what's next today': match today's weekday name,
// BUT if today is already fully done, advance to the next day with work left
// so the athlete doesn't open the app and stare at an all-done page. Falls
// back to the first incomplete day, then to the first day in the program.
// Exported for unit-testing; import todayName to freeze 'now' in tests.
export const _isDayComplete = (day, entriesByDayId) => {
  const total = day.exercises?.length || 0
  if (total === 0) return true
  const entries = entriesByDayId[day.id] || {}
  const completed = Object.values(entries).filter((e) => e?.completed).length
  return completed >= total
}

export const _pickDefaultDayId = (days, entriesByDayId, todayName) => {
  if (!days || days.length === 0) return null
  const todayIndex = days.findIndex((d) => (d.day || '').trim().toLowerCase() === todayName.toLowerCase())

  if (todayIndex >= 0) {
    const todayDay = days[todayIndex]
    if (!_isDayComplete(todayDay, entriesByDayId)) return todayDay.id
    // Today is done. Walk forward through the week for the next day with
    // real work left so the athlete sees tomorrow's plan.
    for (let i = 1; i < days.length; i += 1) {
      const candidate = days[(todayIndex + i) % days.length]
      if (!_isDayComplete(candidate, entriesByDayId)) return candidate.id
    }
    // Whole week done -- fall through to today as a 'look what you did' view.
    return todayDay.id
  }

  // Today isn't in the program (e.g., rest-day not named): find first day
  // with work left, or just the first day as last resort.
  const firstIncomplete = days.find((d) => !_isDayComplete(d, entriesByDayId))
  return (firstIncomplete || days[0]).id
}

const pickDefaultDayId = (days, entriesByDayId) =>
  _pickDefaultDayId(days, entriesByDayId, WEEKDAY_NAMES[new Date().getDay()])

const AthleteDashboard = () => {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')
  const [programs, setPrograms] = useState([])
  const [completions, setCompletions] = useState({})
  const [workoutLogs, setWorkoutLogs] = useState([])
  const [personalRecords, setPersonalRecords] = useState([])
  const [activeProgramId, setActiveProgramId] = useState(null)
  const [selectedDayId, setSelectedDayId] = useState(null)
  const [drawerSection, setDrawerSection] = useState(null) // 'workout' | 'pr' | 'stats' | null
  // Encouragement toast is separate from saveMessage so the technical 'Logged'
  // status and the emotional milestone humor don't overwrite each other when
  // both fire in the same save cycle.
  const [encouragement, setEncouragement] = useState('')

  // completionsRef holds the latest completions synchronously so rapid-tap
  // handleSaveResult calls don't each read a stale closure-captured copy.
  // saveChainRef serializes PATCHes per program: each save awaits the
  // previous one, so server-side state stays consistent even if responses
  // would otherwise arrive out of order.
  const completionsRef = useRef(completions)
  const saveChainRef = useRef(Promise.resolve())
  useEffect(() => { completionsRef.current = completions }, [completions])

  const [logForm, setLogForm] = useState({
    date: new Date().toISOString().split('T')[0],
    notes: '',
  })
  const [prForm, setPrForm] = useState({
    lift_type: 'snatch',
    weight: '',
    date: new Date().toISOString().split('T')[0],
  })
  const [sinclairForm, setSinclairForm] = useState({ bodyweight_kg: '', total_kg: '', gender: 'M' })
  const [sinclairResult, setSinclairResult] = useState(null)
  const [robiResult, setRobiResult] = useState(null)
  const [sinclairLoading, setSinclairLoading] = useState(false)
  const [profileForm, setProfileForm] = useState({ bodyweight_kg: '', gender: 'M' })
  const [profileSaving, setProfileSaving] = useState(false)

  useEffect(() => {
    loadDashboardData()
  }, [])

  useEffect(() => {
    if (drawerSection !== 'stats') return
    const u = getCurrentUser()
    if (!u) return
    setProfileForm({
      bodyweight_kg: u.bodyweight_kg != null && u.bodyweight_kg !== '' ? String(u.bodyweight_kg) : '',
      gender: u.gender === 'F' ? 'F' : 'M',
    })
  }, [drawerSection])

  useEffect(() => {
    if (loading) return
    if (programs.length > 0) return
    const u = getCurrentUser()
    if (!u) return
    setProfileForm({
      bodyweight_kg: u.bodyweight_kg != null && u.bodyweight_kg !== '' ? String(u.bodyweight_kg) : '',
      gender: u.gender === 'F' ? 'F' : 'M',
    })
  }, [loading, programs.length])

  const loadDashboardData = async () => {
    try {
      setLoading(true)
      const [programResponse, workoutResponse, prResponse] = await Promise.all([
        getProgramsFromBackend(),
        getWorkoutLogs(),
        getPersonalRecords(),
      ])

      const completionEntries = programResponse.map((program) => [
        program.id,
        program.completion_data || { entries: {} },
      ])

      setPrograms(programResponse)
      setWorkoutLogs(workoutResponse)
      setPersonalRecords(prResponse)
      setCompletions(Object.fromEntries(completionEntries))
      setSaveMessage('')

      // Default active program = first one assigned. Most athletes have only
      // one program; the chip row (rendered only when length > 1) lets them
      // swap if they have several.
      if (programResponse.length > 0 && !activeProgramId) {
        setActiveProgramId(programResponse[0].id)
      }
    } catch (error) {
      console.error('Error loading athlete dashboard:', error)
      setSaveMessage(formatApiError(error, 'Could not load dashboard data.'))
    } finally {
      setLoading(false)
    }
  }

  // Seed the selected-day on first load once we know the active program's days
  // and their completion state.
  const activeProgram = useMemo(
    () => programs.find((p) => p.id === activeProgramId) || programs[0],
    [programs, activeProgramId],
  )

  const activeProgramNormalized = useMemo(
    () => (activeProgram ? normalizeProgramData(activeProgram.program_data, activeProgram.start_date) : null),
    [activeProgram],
  )

  const activeCompletionEntries = completions[activeProgram?.id]?.entries || {}

  useEffect(() => {
    if (!activeProgramNormalized) return
    if (selectedDayId) {
      const stillValid = activeProgramNormalized.days.some((d) => d.id === selectedDayId)
      if (stillValid) return
    }
    const defaultId = pickDefaultDayId(activeProgramNormalized.days, activeCompletionEntries)
    if (defaultId) setSelectedDayId(defaultId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeProgramNormalized, activeCompletionEntries])

  const completionCounts = useMemo(() => {
    if (!activeProgramNormalized) return {}
    const out = {}
    activeProgramNormalized.days.forEach((day) => {
      const entries = activeCompletionEntries[day.id] || {}
      const total = day.exercises?.length || 0
      const completed = Object.values(entries).filter((e) => e?.completed).length
      out[day.id] = { completed, total }
    })
    return out
  }, [activeProgramNormalized, activeCompletionEntries])

  const selectedDay = useMemo(
    () => activeProgramNormalized?.days.find((d) => d.id === selectedDayId),
    [activeProgramNormalized, selectedDayId],
  )

  const selectedDayCounts = completionCounts[selectedDayId] || { completed: 0, total: 0 }
  const todayName = WEEKDAY_NAMES[new Date().getDay()]
  const todayDate = new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

  // Encouragement math. Streak comes from workout logs (explicit date), lifetime
  // comes from every completed: true flag across every program.
  const streak = useMemo(() => computeStreak(workoutLogs), [workoutLogs])
  const lifetimeCompleted = useMemo(() => computeLifetimeCompletions(completions), [completions])

  const programsAssigned = programs.length
  const quickGlance = useMemo(() => {
    const totalPlannedExercises = programs.reduce((sum, program) => {
      const normalized = normalizeProgramData(program.program_data, program.start_date)
      const days = normalized?.days || []
      return sum + days.reduce((daySum, day) => daySum + ((day.exercises || []).length), 0)
    }, 0)
    const latestUpdatedAt = programs
      .map((program) => program.updated_at)
      .filter(Boolean)
      .sort()
      .at(-1)
    return {
      programsAssigned,
      totalPlannedExercises,
      activeProgramEndDate: activeProgram?.end_date || null,
      latestUpdatedAt,
    }
  }, [activeProgram?.end_date, programs, programsAssigned])

  // Milestone crossings become one-time humor toasts. The refs are seeded on
  // first render so page-load doesn't fire a celebration for counts the athlete
  // already had before opening the dashboard.
  const prevLifetimeRef = useRef(null)
  const prevStreakRef = useRef(null)

  // Get the current athlete id once so we can key milestone persistence by
  // user. Anonymous fallback keeps local dev / unauthenticated paths sane.
  const currentUserId = useMemo(() => getCurrentUser()?.id ?? 'anon', [])

  // Fire a milestone at most once per athlete per threshold -- persisting the
  // set in localStorage so unmark/remark (lifetime 1 -> 0 -> 1) can't trigger
  // the same celebration twice.
  const fireMilestoneOnce = (kind, crossed) => {
    if (!crossed) return
    if (hasMilestoneFired(currentUserId, kind, crossed.count)) return
    markMilestoneFired(currentUserId, kind, crossed.count)
    setEncouragement(crossed.message)
    setTimeout(() => setEncouragement(''), 5000)
  }

  useEffect(() => {
    if (loading) return
    if (prevLifetimeRef.current === null) { prevLifetimeRef.current = lifetimeCompleted; return }
    const crossed = crossedCompletionMilestone(prevLifetimeRef.current, lifetimeCompleted)
    prevLifetimeRef.current = lifetimeCompleted
    fireMilestoneOnce('completion', crossed)
  }, [lifetimeCompleted, loading])

  useEffect(() => {
    if (loading) return
    if (prevStreakRef.current === null) { prevStreakRef.current = streak; return }
    const crossed = crossedStreakMilestone(prevStreakRef.current, streak)
    prevStreakRef.current = streak
    fireMilestoneOnce('streak', crossed)
  }, [streak, loading])

  // Persist a single exercise's result. Writes locally (optimistic), then
  // PATCHes to the backend. Two safeguards against rapid-tap data loss:
  //
  //   1. Read from completionsRef, not from the closure-captured state, so
  //      a second save fired in the same render cycle sees the first save's
  //      optimistic update.
  //   2. Chain the PATCH onto saveChainRef so PATCHes are serialized per
  //      the order they were issued. If PATCH N finishes after PATCH N+1,
  //      the server wouldn't otherwise see N+1's work; serializing guarantees
  //      each request lands after the previous response has been applied.
  const handleSaveResult = async (programId, day, dayIndex, exerciseIndex, newResult) => {
    if (!programId) return
    const dayKey = getDayCompletionKey(day, dayIndex)
    const program = programs.find((p) => p.id === programId)

    // Snapshot the pre-save state so we can revert cleanly if the server
    // rejects the update (e.g., coach reassigned the program mid-save and
    // the athlete is no longer allowed to write). Without this, the card
    // would stay visually 'done' after a failed save and mislead the athlete.
    const priorCompletion = completionsRef.current[programId]

    // Optimistic local update, computed against the freshest state.
    const currentCompletion = priorCompletion || { entries: {} }
    const nextEntries = {
      ...(currentCompletion.entries || {}),
      [dayKey]: {
        ...(currentCompletion.entries?.[dayKey] || {}),
        [String(exerciseIndex)]: newResult,
      },
    }
    const nextCompletion = { entries: nextEntries }
    completionsRef.current = { ...completionsRef.current, [programId]: nextCompletion }
    setCompletions(completionsRef.current)

    setSaving(true)
    const exName = program?.program_data?.days?.[dayIndex]?.exercises?.[exerciseIndex]?.name || 'Exercise'

    // Reference identity of the optimistic state at submit time. If a later
    // save has replaced completionsRef.current[programId] before the response
    // arrives, we leave local state alone so we don't overwrite newer work
    // with stale server data.
    const submittedSnapshot = completionsRef.current[programId]

    // Streak is derived from workoutLogs, so marking an exercise done without
    // also logging a workout means the athlete's streak silently breaks even
    // though they trained. On the first completed=true of today, auto-POST a
    // minimal workout log so the streak stays true to behavior. No-ops if a
    // log for today already exists, or if we're merely unmarking done.
    const todayKey = todayLocalDateKey()
    const shouldAutoLogToday = newResult.completed && !workoutLogs.some(
      (log) => String(log.date).slice(0, 10) === todayKey,
    )

    // Queue the PATCH behind any in-flight save so responses can't arrive
    // out of order relative to their requests.
    saveChainRef.current = saveChainRef.current
      .catch(() => {}) // don't let a prior failure stop this save
      .then(async () => {
        try {
          const response = await updateProgramCompletion(programId, nextCompletion)
          if (completionsRef.current[programId] === submittedSnapshot) {
            completionsRef.current = { ...completionsRef.current, [programId]: response.completion_data }
            setCompletions(completionsRef.current)
          }
          if (shouldAutoLogToday) {
            try {
              const created = await createWorkoutLog({ date: todayKey, notes: '' })
              setWorkoutLogs((prev) => [created, ...prev])
            } catch (e) {
              // Don't fail the save just because the auto-log write failed.
              console.warn('auto-log skipped:', e?.message)
            }
          }
          setSaveMessage(newResult.completed ? `Logged — ${exName}` : `Updated — ${exName}`)
          setTimeout(() => setSaveMessage(''), 2200)
        } catch (error) {
          console.error('Error saving exercise result:', error)
          // Revert the optimistic update so the card reflects server truth
          // instead of staying falsely 'done'. Only revert if the ref still
          // holds OUR optimistic value (no later save has touched it).
          if (completionsRef.current[programId] === submittedSnapshot) {
            const reverted = { ...completionsRef.current }
            if (priorCompletion === undefined) {
              delete reverted[programId]
            } else {
              reverted[programId] = priorCompletion
            }
            completionsRef.current = reverted
            setCompletions(reverted)
          }
          setSaveMessage(formatApiError(error, 'Could not save result.'))
        }
      })

    try {
      await saveChainRef.current
    } finally {
      setSaving(false)
    }
  }

  const handleWorkoutSave = async () => {
    try {
      setSaving(true)
      await createWorkoutLog({ date: logForm.date, notes: logForm.notes })
      setLogForm((current) => ({ ...current, notes: '' }))
      await loadDashboardData()
      setSaveMessage('Workout log saved.')
      setTimeout(() => setSaveMessage(''), 2500)
      setDrawerSection(null)
    } catch (error) {
      console.error('Error saving workout log:', error)
      setSaveMessage(formatApiError(error, 'Could not save workout log.'))
    } finally {
      setSaving(false)
    }
  }

  const handlePrSave = async () => {
    if (!prForm.weight) {
      setSaveMessage('Enter a PR weight before saving.')
      return
    }
    try {
      setSaving(true)
      await createPersonalRecord(prForm)
      setPrForm((current) => ({ ...current, weight: '' }))
      await loadDashboardData()
      setSaveMessage('Personal record saved.')
      setTimeout(() => setSaveMessage(''), 2500)
      setDrawerSection(null)
    } catch (error) {
      console.error('Error saving personal record:', error)
      setSaveMessage(formatApiError(error, 'Could not save PR.'))
    } finally {
      setSaving(false)
    }
  }

  const handleSinclairSubmit = async () => {
    if (!sinclairForm.bodyweight_kg || !sinclairForm.total_kg) {
      setSaveMessage('Enter both bodyweight and total.')
      return
    }
    const payload = {
      bodyweight_kg: Number(sinclairForm.bodyweight_kg),
      total_kg: Number(sinclairForm.total_kg),
      gender: sinclairForm.gender,
    }
    try {
      setSinclairLoading(true)
      setSinclairResult(null)
      setRobiResult(null)
      // Sinclair + ROBI run off the same inputs -- fire them in parallel so the
      // athlete sees both cross-category scores with one tap.
      const [sinclair, robi] = await Promise.all([
        calculateSinclair(payload),
        calculateRobi(payload),
      ])
      setSinclairResult(sinclair)
      setRobiResult(robi)
      setSaveMessage('Calculated.')
      setTimeout(() => setSaveMessage(''), 2000)
    } catch (error) {
      console.error('Error calculating Sinclair/ROBI:', error)
      setSaveMessage('Could not calculate. Check inputs.')
    } finally {
      setSinclairLoading(false)
    }
  }

  const handleCompetitionProfileSave = async () => {
    if (!profileForm.bodyweight_kg) {
      setSaveMessage('Enter bodyweight (kg) to save your competition profile.')
      return
    }
    try {
      setProfileSaving(true)
      const data = await patchCurrentUserProfile({
        bodyweight_kg: Number(profileForm.bodyweight_kg),
        gender: profileForm.gender,
      })
      const programResponse = await getProgramsFromBackend()
      setPrograms(programResponse)
      const cls = data?.competitive_weight_class
      setSaveMessage(
        cls ? `Profile saved. IWF class: ${cls}.` : 'Profile saved.',
      )
      setTimeout(() => setSaveMessage(''), 4000)
    } catch (error) {
      console.error('Error saving competition profile:', error)
      setSaveMessage(formatApiError(error, 'Could not save profile.'))
    } finally {
      setProfileSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="dashboard-container">
        <div className="loading">Loading athlete workspace…</div>
      </div>
    )
  }

  if (!activeProgram) {
    const me = getCurrentUser()
    const noProgramSuffix = athleteProfileSuffix(me || {})
    return (
      <div className="dashboard-container athlete-dashboard">
        <div className="dashboard-header">
          <div className="dashboard-kicker">
            Athlete · <span className="username-highlight">{me?.username || '—'}</span>
            {noProgramSuffix ? <span className="athlete-inline-meta">{noProgramSuffix}</span> : null}
          </div>
          <h1>No program yet.</h1>
          <p className="dashboard-description">
            Your coach hasn't assigned a program. Check back after they build one for you.
          </p>
          <section className="section-card athlete-no-program-profile">
            <h3 className="athlete-drawer-subhead">Competition profile</h3>
            <p className="dashboard-description athlete-no-program-profile-copy">
              Bodyweight and sex category set your IWF-style class for the nav bar and coach roster.
            </p>
            <div className="form-grid compact-grid">
              <label className="field-stacked">
                <span>Bodyweight (kg)</span>
                <input
                  type="number"
                  inputMode="decimal"
                  className="form-input data"
                  value={profileForm.bodyweight_kg}
                  onChange={(e) => setProfileForm((c) => ({ ...c, bodyweight_kg: e.target.value }))}
                />
              </label>
              <label className="field-stacked">
                <span>Category</span>
                <select
                  className="form-input"
                  value={profileForm.gender}
                  onChange={(e) => setProfileForm((c) => ({ ...c, gender: e.target.value }))}
                >
                  <option value="M">Male</option>
                  <option value="F">Female</option>
                </select>
              </label>
            </div>
            <div className="athlete-drawer-actions athlete-no-program-profile-actions">
              <button type="button" className="save-btn" onClick={handleCompetitionProfileSave} disabled={profileSaving}>
                {profileSaving ? 'Saving…' : 'Save profile'}
              </button>
            </div>
            {saveMessage && (
              <div className={`save-message athlete-no-program-profile-message ${saveMessage.toLowerCase().includes('could') ? 'error' : 'success'}`}>
                {saveMessage}
              </div>
            )}
          </section>
        </div>
      </div>
    )
  }

  const activeProfileSuffix = athleteProfileSuffix(activeProgram)

  return (
    <div className="dashboard-container athlete-dashboard">
      <div className="athlete-hero">
        <div className="dashboard-kicker-row">
          <span className="dashboard-kicker">
            Athlete · <span className="username-highlight">{activeProgram.athlete_username}</span>
            {activeProfileSuffix ? <span className="athlete-inline-meta">{activeProfileSuffix}</span> : null}
          </span>
          {saving && <span className="status-pill">Saving…</span>}
        </div>
        <h1 className="athlete-hero-title">
          {todayName}, {todayDate}
        </h1>
        <p className="athlete-hero-meta">
          <span className="data">{selectedDayCounts.completed}</span> of{' '}
          <span className="data">{selectedDayCounts.total}</span>
          {' exercises done on '}
          <span className="athlete-hero-dayname">{selectedDay?.day || '—'}</span>
        </p>
        {(streak > 0 || lifetimeCompleted > 0) && (
          <div className="athlete-hero-stats" aria-label="Athlete streak and lifetime completions">
            {streak > 0 && (
              <span className="athlete-hero-stat">
                <span className="athlete-hero-stat-label">Streak</span>
                <span className="athlete-hero-stat-value data">{streak}</span>
                <span className="athlete-hero-stat-unit">day{streak === 1 ? '' : 's'}</span>
              </span>
            )}
            {lifetimeCompleted > 0 && (
              <span className="athlete-hero-stat">
                <span className="athlete-hero-stat-label">Lifts</span>
                <span className="athlete-hero-stat-value data">{lifetimeCompleted}</span>
                <span className="athlete-hero-stat-unit">logged</span>
              </span>
            )}
          </div>
        )}
        {saveMessage && (
          <div className={`save-message ${saveMessage.toLowerCase().includes('error') || saveMessage.toLowerCase().includes('could') ? 'error' : 'success'}`}>
            {saveMessage}
          </div>
        )}
        {encouragement && (
          <div className="encouragement-toast" role="status" aria-live="polite">
            <span className="encouragement-toast-kicker">Milestone</span>
            <span className="encouragement-toast-body">{encouragement}</span>
          </div>
        )}
        {!activeProfileSuffix && (
          <p className="athlete-profile-nudge">
            <span>Add your competition bodyweight in Stats &amp; tools to show your IWF class next to your name.</span>
            <button
              type="button"
              className="text-btn"
              onClick={() => setDrawerSection('stats')}
            >
              Open Stats &amp; tools
            </button>
          </p>
        )}
      </div>

      <section className="summary-grid athlete-quick-glance" aria-label="Athlete quick glance">
        <article className="home-metric section-card">
          <span className="label">Programs assigned</span>
          <span className="value data">{quickGlance.programsAssigned}</span>
        </article>
        <article className="home-metric section-card">
          <span className="label">Active block ends</span>
          <span className="value data">{quickGlance.activeProgramEndDate || 'TBD'}</span>
        </article>
        <article className="home-metric section-card">
          <span className="label">Planned exercises</span>
          <span className="value data">{quickGlance.totalPlannedExercises}</span>
        </article>
        <article className="home-metric section-card">
          <span className="label">Last update</span>
          <span className="value data">
            {quickGlance.latestUpdatedAt ? relativeTimeSince(quickGlance.latestUpdatedAt) : 'No updates yet'}
          </span>
        </article>
      </section>

      {programsAssigned > 1 && (
        <div className="program-chip-row" role="tablist" aria-label="Programs">
          {programs.map((program) => (
            <button
              key={program.id}
              type="button"
              role="tab"
              aria-selected={program.id === activeProgram.id}
              className={`program-chip ${program.id === activeProgram.id ? 'is-active' : ''}`}
              title={
                [program.athlete_username, athleteProfileSuffix(program).replace(/^ · /, '')]
                  .filter(Boolean)
                  .join(' · ') || undefined
              }
              onClick={() => { setActiveProgramId(program.id); setSelectedDayId(null) }}
            >
              {programTitleForDisplay(program.name) || 'Program'}
            </button>
          ))}
        </div>
      )}

      <WeekStrip
        days={activeProgramNormalized.days}
        completionCounts={completionCounts}
        selectedDayId={selectedDayId}
        onSelectDay={setSelectedDayId}
      />

      <section className="athlete-day-section">
        <h2 className="athlete-day-title">{selectedDay?.day || 'Day'}</h2>

        {(selectedDay?.exercises || []).length === 0 ? (
          <div className="empty-inline">Nothing programmed for this day — rest or accessory work.</div>
        ) : (
          <div className="athlete-exercise-list">
            {selectedDay.exercises.map((exercise, exerciseIndex) => {
              const dayKey = getDayCompletionKey(selectedDay, 0 /* idx unused once id exists */)
              const entryBag = activeCompletionEntries[dayKey] || activeCompletionEntries[selectedDay.id] || {}
              const result = entryBag[String(exerciseIndex)] || { completed: false, result: '', athlete_notes: '' }
              // Resolve the source day's original index on the program (needed
              // by the save handler's legacy fallback key).
              const originalDayIndex = activeProgramNormalized.days.findIndex((d) => d.id === selectedDay.id)
              return (
                <AthleteExerciseCard
                  key={`${selectedDay.id}-${exerciseIndex}`}
                  exercise={exercise}
                  result={result}
                  onSaveResult={(newResult) => handleSaveResult(activeProgram.id, selectedDay, originalDayIndex, exerciseIndex, newResult)}
                />
              )
            })}
          </div>
        )}
      </section>

      <div className="athlete-bottom-bar">
        <button
          type="button"
          className={`athlete-bottom-btn ${drawerSection === 'workout' ? 'is-active' : ''}`}
          onClick={() => setDrawerSection(drawerSection === 'workout' ? null : 'workout')}
        >
          + Log workout
        </button>
        <button
          type="button"
          className={`athlete-bottom-btn ${drawerSection === 'pr' ? 'is-active' : ''}`}
          onClick={() => setDrawerSection(drawerSection === 'pr' ? null : 'pr')}
        >
          + Log PR
        </button>
        <button
          type="button"
          className={`athlete-bottom-btn ${drawerSection === 'stats' ? 'is-active' : ''}`}
          onClick={() => setDrawerSection(drawerSection === 'stats' ? null : 'stats')}
        >
          Stats &amp; tools
        </button>
      </div>

      {drawerSection === 'workout' && (
        <section className="athlete-drawer section-card">
          <h3>Log workout</h3>
          <label className="field-stacked">
            <span>Date</span>
            <input type="date" className="form-input" value={logForm.date} onChange={(e) => setLogForm((c) => ({ ...c, date: e.target.value }))} />
          </label>
          <label className="field-stacked">
            <span>Notes</span>
            <textarea rows="2" className="notes-textarea" placeholder="how did it go"
                      value={logForm.notes} onChange={(e) => setLogForm((c) => ({ ...c, notes: e.target.value }))} />
          </label>
          <div className="athlete-drawer-actions">
            <button type="button" className="text-btn" onClick={() => setDrawerSection(null)}>Cancel</button>
            <button type="button" className="save-btn" onClick={handleWorkoutSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save log'}
            </button>
          </div>
          {workoutLogs.length > 0 && (
            <div className="athlete-drawer-history">
              <h4>Recent</h4>
              <ul>
                {workoutLogs.slice(0, 8).map((log) => (
                  <li key={log.id}>
                    <span className="data">{log.date}</span>
                    {log.notes && <span> — {log.notes}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {drawerSection === 'pr' && (
        <section className="athlete-drawer section-card">
          <h3>Log PR</h3>
          <div className="form-grid compact-grid">
            <label className="field-stacked">
              <span>Lift</span>
              <select className="form-input" value={prForm.lift_type}
                      onChange={(e) => setPrForm((c) => ({ ...c, lift_type: e.target.value }))}>
                <option value="snatch">Snatch</option>
                <option value="clean_jerk">Clean &amp; Jerk</option>
                <option value="total">Total</option>
              </select>
            </label>
            <label className="field-stacked">
              <span>Weight (kg)</span>
              <input type="number" inputMode="decimal" className="form-input data" value={prForm.weight}
                     onChange={(e) => setPrForm((c) => ({ ...c, weight: e.target.value }))} />
            </label>
            <label className="field-stacked">
              <span>Date</span>
              <input type="date" className="form-input" value={prForm.date}
                     onChange={(e) => setPrForm((c) => ({ ...c, date: e.target.value }))} />
            </label>
          </div>
          <div className="athlete-drawer-actions">
            <button type="button" className="text-btn" onClick={() => setDrawerSection(null)}>Cancel</button>
            <button type="button" className="save-btn" onClick={handlePrSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save PR'}
            </button>
          </div>
          {personalRecords.length > 0 && (
            <div className="athlete-drawer-history">
              <h4>Recent PRs</h4>
              <ul>
                {personalRecords.slice(0, 8).map((record) => (
                  <li key={record.id}>
                    <span className="data">{record.weight}kg</span>{' '}
                    {liftLabels[record.lift_type] || record.lift_type}{' · '}
                    <span>{record.date}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {drawerSection === 'stats' && (
        <section className="athlete-drawer section-card">
          <h3>Stats &amp; tools</h3>

          <h4 className="athlete-drawer-subhead">Competition profile</h4>
          <p className="dashboard-description athlete-stats-profile-lead">
            Saved to your account. This drives the weight-class label in the nav bar, coach roster, and program header.
          </p>
          <div className="form-grid compact-grid">
            <label className="field-stacked">
              <span>Bodyweight (kg)</span>
              <input
                type="number"
                inputMode="decimal"
                className="form-input data"
                value={profileForm.bodyweight_kg}
                onChange={(e) => setProfileForm((c) => ({ ...c, bodyweight_kg: e.target.value }))}
              />
            </label>
            <label className="field-stacked">
              <span>Category</span>
              <select
                className="form-input"
                value={profileForm.gender}
                onChange={(e) => setProfileForm((c) => ({ ...c, gender: e.target.value }))}
              >
                <option value="M">Male</option>
                <option value="F">Female</option>
              </select>
            </label>
          </div>
          <div className="athlete-drawer-actions">
            <button type="button" className="save-btn" onClick={handleCompetitionProfileSave} disabled={profileSaving}>
              {profileSaving ? 'Saving…' : 'Save competition profile'}
            </button>
          </div>

          <AthleteTrainingTrendCharts personalRecords={personalRecords} />

          <h4 className="athlete-drawer-subhead">Sinclair &amp; ROBI</h4>
          <div className="form-grid compact-grid">
            <label className="field-stacked">
              <span>Bodyweight (kg)</span>
              <input type="number" inputMode="decimal" className="form-input data" value={sinclairForm.bodyweight_kg}
                     onChange={(e) => setSinclairForm((c) => ({ ...c, bodyweight_kg: e.target.value }))} />
            </label>
            <label className="field-stacked">
              <span>Total (kg)</span>
              <input type="number" inputMode="decimal" className="form-input data" value={sinclairForm.total_kg}
                     onChange={(e) => setSinclairForm((c) => ({ ...c, total_kg: e.target.value }))} />
            </label>
            <label className="field-stacked">
              <span>Gender</span>
              <select className="form-input" value={sinclairForm.gender}
                      onChange={(e) => setSinclairForm((c) => ({ ...c, gender: e.target.value }))}>
                <option value="M">Male</option>
                <option value="F">Female</option>
              </select>
            </label>
          </div>
          <div className="athlete-drawer-actions">
            <button type="button" className="save-btn" onClick={handleSinclairSubmit} disabled={sinclairLoading}>
              {sinclairLoading ? 'Calculating…' : 'Calculate Sinclair & ROBI'}
            </button>
          </div>
          {sinclairResult && (
            <div className="sinclair-result">
              <span>Sinclair total: <span className="data">{sinclairResult.sinclair_total}</span></span>
              <span>Coefficient: <span className="data">{sinclairResult.coefficient}</span></span>
              {robiResult && (
                <>
                  <div className="sinclair-result-robi-hero">
                    <span className="sinclair-result-robi-label">ROBI</span>
                    <span className="sinclair-result-robi-value data">{robiResult.robi}</span>
                  </div>
                  <span>
                    Weight class:{' '}
                    <span className="data">{robiResult.weight_class} kg</span>
                  </span>
                  <span>
                    World record total:{' '}
                    <span className="data">{robiResult.world_record_total} kg</span>
                  </span>
                </>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  )
}

export default AthleteDashboard
