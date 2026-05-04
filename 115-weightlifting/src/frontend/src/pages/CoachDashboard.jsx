import { useEffect, useMemo, useRef, useState } from 'react'
import WorkoutDay from '../components/WorkoutDay'
import SpreadsheetEditor from '../components/SpreadsheetEditor'
import ProgramPreview from '../components/ProgramPreview'
import ProgressRing from '../components/ProgressRing'
import {
  assignProgram,
  createProgram,
  getAthletes,
  getPersonalRecords,
  getProgramsFromBackend,
  updateProgram,
} from '../services/api'
import { countExercises, createEmptyDay, createEmptyWeek, generateDayId, normalizeProgramData } from '../utils/dataStructure'
import { formatApiError } from '../utils/errors'
import {
  PROGRAM_TEMPLATE_BLOCK_SHEETS,
  downloadTemplateXlsx,
  parseProgramFile,
} from '../utils/programTemplate'
import { clearDraft, readDraft, saveDraft } from '../utils/programDraft'
import { BLOCK_PRESETS, endDateForBlock, inferBlockKey } from '../utils/blockLength'
import { relativeTimeSince } from '../utils/relativeTime'
import { athleteProfileSuffix } from '../utils/athleteMeta'
import { getCurrentUser } from '../utils/auth'
import { programTitleForDisplay } from '../utils/safeDisplay'
import { propagateExerciseNamesAcrossWeeks } from '../utils/programPropagation'
import { buildRestDayExercises } from '../utils/restTemplate'
import AthleteTrainingTrendCharts from '../components/AthleteTrainingTrendCharts'
import CoachRosterAggregateCharts from '../components/CoachRosterAggregateCharts'

const WEEKDAY_TABS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const _normDay = (value) => String(value || '').trim().toLowerCase()
const BLOCK_WEEKS_BY_KEY = { '4wk': 4, '8wk': 8, '16wk': 16 }
const _weekOf = (exercise) => {
  const raw = String(exercise?.week ?? '').trim()
  if (!raw) return 1
  const n = Number.parseInt(raw, 10)
  return Number.isFinite(n) && n > 0 ? n : 1
}
const _maxWeekInProgram = (programData) => {
  let max = 1
  for (const day of (programData?.days || [])) {
    for (const ex of (day?.exercises || [])) {
      max = Math.max(max, _weekOf(ex))
    }
  }
  return max
}

const getDefaultForm = () => ({
  name: '',
  description: '',
  athlete_id: '',
  start_date: new Date().toISOString().split('T')[0],
  end_date: '',
})

const swap = (array, i, j) => {
  if (i < 0 || j < 0 || i >= array.length || j >= array.length) return array
  const next = [...array]
  const tmp = next[i]; next[i] = next[j]; next[j] = tmp
  return next
}

// Walk a program's completion_data and sum every completed: true flag. Used
// to show a block-level completion ring on each program row so the coach can
// glance-see which athletes are actually doing the work.
const summarizeProgramCompletion = (program, totalExercises) => {
  const entries = program?.completion_data?.entries || {}
  let completed = 0
  for (const dayKey in entries) {
    const bag = entries[dayKey] || {}
    for (const exIdx in bag) {
      if (bag[exIdx]?.completed) completed += 1
    }
  }
  return { completed, total: totalExercises }
}

const CoachDashboard = () => {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')
  const [apiError, setApiError] = useState(null)
  const [programs, setPrograms] = useState([])
  const [athletes, setAthletes] = useState([])
  const [athleteSearch, setAthleteSearch] = useState('')
  const [athleteTotal, setAthleteTotal] = useState(0)
  const [editingProgramId, setEditingProgramId] = useState(null)
  const [assignmentDrafts, setAssignmentDrafts] = useState({})
  const [formData, setFormData] = useState(getDefaultForm())
  const [programData, setProgramData] = useState(createEmptyWeek())
  const [editorMode, setEditorMode] = useState('form') // 'form' | 'spreadsheet'
  const [activeCardWeek, setActiveCardWeek] = useState(1)
  const [customWeekCount, setCustomWeekCount] = useState(1)
  const [view, setView] = useState('list') // 'list' | 'editor'
  const [intensityMode, setIntensityMode] = useState('percent_1rm') // 'percent_1rm' | 'rpe' | 'weight'
  const [showPreview, setShowPreview] = useState(false)
  const [draftBadge, setDraftBadge] = useState(false) // shows briefly when a saved draft is restored
  const fileInputRef = useRef(null)
  /** 'auto' | sheet name from PROGRAM_TEMPLATE_BLOCK_SHEETS — which tab to read on upload */
  const [importSheetChoice, setImportSheetChoice] = useState('auto')
  const [coachAthletePrs, setCoachAthletePrs] = useState([])
  const [coachPrsLoading, setCoachPrsLoading] = useState(false)
  const [coachPrsError, setCoachPrsError] = useState(null)
  const [rosterPrsByAthlete, setRosterPrsByAthlete] = useState({})
  const [rosterPrsLoading, setRosterPrsLoading] = useState(false)
  const [rosterPrsError, setRosterPrsError] = useState(null)

  const rosterAthleteIds = useMemo(() => {
    const ids = new Set()
    for (const p of programs) {
      const aid = p.athlete_id
      if (aid == null || aid === '') continue
      const n = Number(aid)
      if (Number.isFinite(n) && n > 0) ids.add(n)
    }
    return [...ids].sort((a, b) => a - b)
  }, [programs])
  const rosterAthleteIdsKey = rosterAthleteIds.join(',')

  useEffect(() => { loadDashboardData() }, [])

  useEffect(() => {
    if (view !== 'editor') return
    const id = Number(formData.athlete_id)
    if (!id || Number.isNaN(id)) {
      setCoachAthletePrs([])
      setCoachPrsError(null)
      setCoachPrsLoading(false)
      return
    }
    let cancelled = false
    setCoachPrsLoading(true)
    setCoachPrsError(null)
    getPersonalRecords(id)
      .then((data) => {
        if (cancelled) return
        setCoachAthletePrs(Array.isArray(data) ? data : [])
        setCoachPrsLoading(false)
      })
      .catch((error) => {
        if (cancelled) return
        setCoachAthletePrs([])
        setCoachPrsError(formatApiError(error, 'Could not load PR history.'))
        setCoachPrsLoading(false)
      })
    return () => { cancelled = true }
  }, [view, formData.athlete_id])

  useEffect(() => {
    if (view !== 'list') return
    if (rosterAthleteIds.length === 0) {
      setRosterPrsByAthlete({})
      setRosterPrsError(null)
      setRosterPrsLoading(false)
      return
    }
    let cancelled = false
    setRosterPrsLoading(true)
    setRosterPrsError(null)
    Promise.all(
      rosterAthleteIds.map((id) =>
        getPersonalRecords(id).then((data) => ({ id, data: Array.isArray(data) ? data : [] })),
      ),
    )
      .then((pairs) => {
        if (cancelled) return
        const next = {}
        for (const { id, data } of pairs) next[id] = data
        setRosterPrsByAthlete(next)
        setRosterPrsLoading(false)
      })
      .catch((error) => {
        if (cancelled) return
        setRosterPrsByAthlete({})
        setRosterPrsError(formatApiError(error, 'Could not load roster PR data.'))
        setRosterPrsLoading(false)
      })
    return () => { cancelled = true }
  }, [view, rosterAthleteIdsKey])

  const rosterRecordsPerAthlete = useMemo(
    () => rosterAthleteIds.map((id) => rosterPrsByAthlete[id] || []),
    [rosterAthleteIds, rosterPrsByAthlete],
  )

  useEffect(() => {
    const handle = setTimeout(() => { refreshAthletes(athleteSearch) }, 300)
    return () => clearTimeout(handle)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [athleteSearch])

  // Autosave: persist form + programData to localStorage on every change
  // while the editor is open. Throttling is not necessary -- setItem is
  // synchronous and cheap at this payload size.
  useEffect(() => {
    if (view !== 'editor') return
    saveDraft(editingProgramId, {
      formData, programData, editorMode, intensityMode,
    })
  }, [view, editingProgramId, formData, programData, editorMode, intensityMode])

  const upcomingSummary = useMemo(() => ({
    dayCount: programData.days.length,
    exerciseCount: countExercises(programData),
  }), [programData])

  const currentBlockKey = useMemo(
    () => inferBlockKey(formData.start_date, formData.end_date),
    [formData.start_date, formData.end_date],
  )
  const editorWeekCount = useMemo(() => {
    const presetWeeks = BLOCK_WEEKS_BY_KEY[currentBlockKey] || 0
    const fromData = _maxWeekInProgram(programData)
    if (currentBlockKey === 'custom') {
      return Math.max(customWeekCount, fromData, 1)
    }
    return Math.max(presetWeeks, fromData, 1)
  }, [currentBlockKey, customWeekCount, programData])

  useEffect(() => {
    setActiveCardWeek((current) => Math.min(Math.max(current, 1), editorWeekCount))
  }, [editorWeekCount])
  useEffect(() => {
    if (currentBlockKey === 'custom') {
      setCustomWeekCount((current) => Math.max(current, _maxWeekInProgram(programData), 1))
    }
  }, [currentBlockKey, programData])

  const assignedAthleteUsername = useMemo(() => {
    const athleteIdNum = Number(formData.athlete_id)
    if (!athleteIdNum) return ''
    const hit = athletes.find((a) => a.id === athleteIdNum)
    return hit ? hit.username : ''
  }, [formData.athlete_id, athletes])

  const assignedAthleteProfileSuffix = useMemo(() => {
    const id = Number(formData.athlete_id)
    if (!id) return ''
    const fromRoster = athletes.find((a) => a.id === id)
    if (fromRoster && (fromRoster.bodyweight_kg != null || fromRoster.competitive_weight_class)) {
      return athleteProfileSuffix(fromRoster)
    }
    const prog = programs.find((p) => p.athlete_id === id)
    return athleteProfileSuffix(prog || {})
  }, [formData.athlete_id, athletes, programs])

  const loadDashboardData = async () => {
    try {
      setLoading(true)
      const programDataResponse = await getProgramsFromBackend()
      setPrograms(programDataResponse)
      await refreshAthletes(athleteSearch)
      setApiError(null)
    } catch (error) {
      console.error('Error loading coach dashboard:', error)
      setApiError(formatApiError(error, 'Could not load dashboard.'))
    } finally {
      setLoading(false)
    }
  }

  const refreshAthletes = async (term = '') => {
    try {
      const u = getCurrentUser()
      const scope = u?.user_type === 'head_coach' ? 'all' : 'mine'
      const { results, count } = await getAthletes({ scope, q: term })
      setAthletes(results)
      setAthleteTotal(count ?? results.length)
    } catch (error) {
      console.error('Error fetching athletes:', error)
    }
  }

  const applyDraftIfPresent = (programId, fallbackForm, fallbackProgramData) => {
    // New programs should always open as a clean template, not with stale
    // autosaved rows from prior sessions.
    if (programId == null) {
      return { form: fallbackForm, programData: fallbackProgramData, restored: false }
    }
    const storedDraft = readDraft(programId)
    if (!storedDraft || !storedDraft.draft) {
      return { form: fallbackForm, programData: fallbackProgramData, restored: false }
    }
    const { formData: df, programData: dp, editorMode: dem, intensityMode: dim } = storedDraft.draft
    if (dem === 'form' || dem === 'spreadsheet') setEditorMode(dem)
    if (dim === 'percent_1rm' || dim === 'rpe' || dim === 'weight') setIntensityMode(dim)
    return {
      form: df || fallbackForm,
      programData: dp || fallbackProgramData,
      restored: true,
    }
  }

  const openNewProgram = () => {
    clearDraft(null)
    const freshForm = getDefaultForm()
    const freshProgram = createEmptyWeek(freshForm.start_date)
    const { form, programData: prog, restored } = applyDraftIfPresent(null, freshForm, freshProgram)
    setEditingProgramId(null)
    setFormData(form)
    setProgramData(prog)
    setActiveCardWeek(1)
    setView('editor')
    setSaveMessage('')
    if (restored) {
      setDraftBadge(true)
      setTimeout(() => setDraftBadge(false), 3500)
    }
  }

  const openExistingProgram = (program) => {
    const fallbackForm = {
      name: program.name,
      description: program.description || '',
      athlete_id: String(program.athlete_id || ''),
      start_date: program.start_date,
      end_date: program.end_date || '',
    }
    const fallbackProgram = normalizeProgramData(program.program_data, program.start_date)
    const { form, programData: prog, restored } = applyDraftIfPresent(program.id, fallbackForm, fallbackProgram)
    setEditingProgramId(program.id)
    setFormData(form)
    setProgramData(prog)
    setActiveCardWeek(1)
    // Restore coach's prior intensity-mode choice if the program carries one
    // (and the autosaved draft didn't already override it).
    if (!restored && (prog.intensity_mode === 'percent_1rm' || prog.intensity_mode === 'rpe' || prog.intensity_mode === 'weight')) {
      setIntensityMode(prog.intensity_mode)
    }
    setView('editor')
    setSaveMessage('')
    if (restored) {
      setDraftBadge(true)
      setTimeout(() => setDraftBadge(false), 3500)
    }
  }

  const backToList = () => {
    setView('list')
    setSaveMessage('')
    setShowPreview(false)
  }

  const handleFormChange = (field, value) => {
    setFormData((current) => ({ ...current, [field]: value }))
    if (field === 'start_date') {
      setProgramData((current) => ({ ...current, week_start_date: value }))
    }
  }

  const handleBlockPreset = (weeks) => {
    const end = endDateForBlock(formData.start_date, weeks)
    setFormData((current) => ({ ...current, end_date: end }))
  }
  const handleBlockCustom = () => {
    setFormData((current) => ({ ...current, end_date: '' }))
  }
  const handleAddCustomWeek = () => {
    setCustomWeekCount((current) => current + 1)
  }
  const handleRemoveCustomWeek = () => {
    setCustomWeekCount((current) => {
      const nextWeekCount = Math.max(1, current - 1)
      setProgramData((programCurrent) => ({
        ...programCurrent,
        days: (programCurrent.days || []).map((day) => ({
          ...day,
          exercises: (day.exercises || []).filter((exercise) => _weekOf(exercise) <= nextWeekCount),
        })),
      }))
      return nextWeekCount
    })
  }

  // Program-data mutations (day-level)
  const handleDayChange = (dayIndex, nextDayName) => {
    setProgramData((current) => ({
      ...current,
      days: current.days.map((day, idx) => (idx === dayIndex ? { ...day, day: nextDayName } : day)),
    }))
  }

  const handleExercisesChange = (dayIndex, nextExercises) => {
    const normalizeWeekExercise = (exercise) => ({
      ...exercise,
      week: String(activeCardWeek),
    })
    setProgramData((current) => ({
      ...current,
      days: current.days.map((day, idx) => {
        if (idx !== dayIndex) return day
        const keepOthers = (day.exercises || []).filter((exercise) => _weekOf(exercise) !== activeCardWeek)
        const thisWeek = (nextExercises || []).map(normalizeWeekExercise)
        const merged = [...keepOthers, ...thisWeek]
        merged.sort((a, b) => _weekOf(a) - _weekOf(b))
        return { ...day, exercises: merged }
      }),
    }))
  }

  const handleAddDay = () => {
    setProgramData((current) => ({
      ...current,
      days: [...current.days, createEmptyDay(`Day ${current.days.length + 1}`)],
    }))
  }

  const handleRemoveDay = (dayIndex) => {
    const day = programData.days[dayIndex]
    const name = day?.day?.trim() || `Day ${dayIndex + 1}`
    const count = day?.exercises?.length || 0
    const message = count > 0
      ? `Remove "${name}" and ${count} exercise${count === 1 ? '' : 's'}? This cannot be undone.`
      : `Remove "${name}"? This cannot be undone.`
    const ok = typeof window === 'undefined' || window.confirm(message)
    if (!ok) return
    setProgramData((current) => ({
      ...current,
      days: current.days.filter((_, idx) => idx !== dayIndex),
    }))
  }

  const handleDuplicateDay = (dayIndex) => {
    setProgramData((current) => {
      const source = current.days[dayIndex]
      // Avoid the cluttered '(copy)' suffix. If the source uses the
      // 'Day N' convention, increment N relative to the next available
      // slot; otherwise keep the same text so the coach can rename inline.
      const positionalMatch = typeof source.day === 'string' && source.day.match(/^Day\s+(\d+)$/i)
      const nextDayName = positionalMatch
        ? `Day ${current.days.length + 1}`
        : source.day
      const cloned = {
        id: generateDayId(),
        day: nextDayName,
        exercises: (source.exercises || []).map((ex) => ({ ...ex })),
      }
      const next = [...current.days]
      next.splice(dayIndex + 1, 0, cloned)
      return { ...current, days: next }
    })
  }

  const handleMoveDay = (dayIndex, delta) => {
    setProgramData((current) => ({ ...current, days: swap(current.days, dayIndex, dayIndex + delta) }))
  }

  const handleResetToBlankTemplate = () => {
    const ok = typeof window === 'undefined' || window.confirm(
      'ATTENTION!\nReset to a blank 7-day template? This will clear all current rows in the editor until you publish.',
    )
    if (!ok) return
    setProgramData((current) => {
      const byDay = new Map((current.days || []).map((day) => [_normDay(day.day), day]))
      return {
        ...current,
        days: WEEKDAY_TABS.map((dayName) => {
          const existing = byDay.get(_normDay(dayName))
          return {
            id: existing?.id || generateDayId(),
            day: dayName,
            exercises: [],
          }
        }),
      }
    })
    setSaveMessage('Template reset: all day rows cleared in this editor.')
    setTimeout(() => setSaveMessage(''), 3500)
  }
  const handleApplyRestDay = (dayIndex) => {
    setProgramData((current) => ({
      ...current,
      days: current.days.map((day, idx) => (
        idx === dayIndex ? { ...day, exercises: buildRestDayExercises(editorWeekCount) } : day
      )),
    }))
    setSaveMessage(`Marked ${programData.days?.[dayIndex]?.day || 'day'} as Rest across ${editorWeekCount} week(s).`)
    setTimeout(() => setSaveMessage(''), 3200)
  }

  const handlePropagateExerciseNames = () => {
    if (editorWeekCount <= 1) {
      setSaveMessage('Add more than one week to use name propagation.')
      setTimeout(() => setSaveMessage(''), 2800)
      return
    }
    const next = propagateExerciseNamesAcrossWeeks(programData, {
      sourceWeek: 1,
      maxWeeks: editorWeekCount,
      overwriteNames: true,
    })
    setProgramData(next)
    setSaveMessage(`Copied Week 1 exercise names into Weeks 2-${editorWeekCount}. Prescriptions were left unchanged.`)
    setTimeout(() => setSaveMessage(''), 3800)
  }

  const handleDownloadTemplate = async () => {
    try {
      await downloadTemplateXlsx()
      setSaveMessage('Template downloaded. Fill it in and re-upload to autofill a new program.')
    } catch (e) {
      console.error('Template download failed:', e)
      setSaveMessage(e?.message || 'Template download failed.')
    }
    setTimeout(() => setSaveMessage(''), 4000)
  }

  const handleTemplateUploadClick = () => { fileInputRef.current?.click() }

  const handleTemplateFileChosen = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    try {
      setSaveMessage('')
      const parseOpts = importSheetChoice === 'auto' ? {} : { sheetName: importSheetChoice }
      const nextProgramData = await parseProgramFile(file, parseOpts)
      setProgramData(nextProgramData)
      const exercises = nextProgramData.days.reduce((t, d) => t + d.exercises.length, 0)
      const sheetNote = importSheetChoice === 'auto' ? '' : ` (${importSheetChoice})`
      setSaveMessage(
        `Loaded ${nextProgramData.days.length} day(s) / ${exercises} exercise(s) from ${file.name}${sheetNote}. Review and hit Save.`
      )
      setTimeout(() => setSaveMessage(''), 6000)
    } catch (error) {
      console.error('Template upload failed:', error)
      setSaveMessage(`Could not read ${file.name}: ${error.message || 'unknown error'}`)
    }
  }

  const toggleEditorMode = () => setEditorMode((c) => (c === 'form' ? 'spreadsheet' : 'form'))

  const handleSave = async () => {
    if (!formData.name || !formData.athlete_id) {
      setSaveMessage('Enter Program Name and athlete selection are required.')
      return
    }
    const payload = {
      ...formData,
      athlete_id: Number(formData.athlete_id),
      end_date: formData.end_date || null,
      program_data: {
        ...programData,
        week_start_date: formData.start_date,
        intensity_mode: intensityMode,
      },
    }
    const confirmationMessage = editingProgramId
      ? 'Publish these program updates? Your athlete will see the updated plan on their dashboard.'
      : 'Publish this program now? It will be saved to your coach dashboard and shared to your athlete dashboard.'
    const confirmed = typeof window === 'undefined' || window.confirm(confirmationMessage)
    if (!confirmed) return
    try {
      setSaving(true); setSaveMessage('')
      if (editingProgramId) {
        await updateProgram(editingProgramId, payload)
        setSaveMessage('Program updated.')
      } else {
        await createProgram(payload)
        setSaveMessage('Program created.')
      }
      clearDraft(editingProgramId) // discard autosave on successful commit
      await loadDashboardData()
      setTimeout(() => { setSaveMessage(''); backToList() }, 900)
    } catch (error) {
      console.error('Error saving program:', error)
      setSaveMessage(formatApiError(error, 'Error saving program. Check the fields and try again.'))
    } finally {
      setSaving(false)
    }
  }

  const handleAssign = async (programId) => {
    const athleteId = assignmentDrafts[programId]
    if (!athleteId) { setSaveMessage('Select an athlete before moving the program.'); return }
    try {
      await assignProgram(programId, Number(athleteId))
      setSaveMessage('Program updated for the selected athlete.')
      await loadDashboardData()
      setTimeout(() => setSaveMessage(''), 3000)
    } catch (error) {
      console.error('Error reassigning program:', error)
      setSaveMessage(formatApiError(error, 'Error reassigning program. Please try again.'))
    }
  }

  if (loading) {
    return (
      <div className="dashboard-container">
        <div className="loading">Loading coach workspace…</div>
      </div>
    )
  }

  return (
    <div className="dashboard-container coach-dashboard">
      {apiError && (
        <div className="api-status">
          <span className="api-error">API: {apiError}</span>
        </div>
      )}

      {view === 'list' ? (
        <ListView
          programs={programs}
          athletes={athletes}
          assignmentDrafts={assignmentDrafts}
          onAssignDraftChange={(programId, value) =>
            setAssignmentDrafts((current) => ({ ...current, [programId]: value }))
          }
          onAssignSubmit={handleAssign}
          onNewProgram={openNewProgram}
          onEditProgram={openExistingProgram}
          saveMessage={saveMessage}
          rosterRecordsPerAthlete={rosterRecordsPerAthlete}
          rosterAthleteCount={rosterAthleteIds.length}
          rosterPrsLoading={rosterPrsLoading}
          rosterPrsError={rosterPrsError}
        />
      ) : (
        <>
          <EditorView
            editingProgramId={editingProgramId}
            formData={formData}
            programData={programData}
            athletes={athletes}
            athleteSearch={athleteSearch}
            athleteTotal={athleteTotal}
            assignedAthleteUsername={assignedAthleteUsername}
            assignedAthleteProfileSuffix={assignedAthleteProfileSuffix}
            coachAthletePrs={coachAthletePrs}
            coachPrsLoading={coachPrsLoading}
            coachPrsError={coachPrsError}
            editorMode={editorMode}
            intensityMode={intensityMode}
            saving={saving}
            saveMessage={saveMessage}
            upcomingSummary={upcomingSummary}
            currentBlockKey={currentBlockKey}
            activeCardWeek={activeCardWeek}
            editorWeekCount={editorWeekCount}
            fileInputRef={fileInputRef}
            draftBadge={draftBadge}
            onBack={backToList}
            onFormChange={handleFormChange}
            onBlockPreset={handleBlockPreset}
            onBlockCustom={handleBlockCustom}
            onAthleteSearch={setAthleteSearch}
            onDayChange={handleDayChange}
            onExercisesChange={handleExercisesChange}
            onAddDay={handleAddDay}
            onRemoveDay={handleRemoveDay}
            onDuplicateDay={handleDuplicateDay}
            onMoveDay={handleMoveDay}
            onApplyRestDay={handleApplyRestDay}
            onAddCustomWeek={handleAddCustomWeek}
            onRemoveCustomWeek={handleRemoveCustomWeek}
            onSelectCardWeek={setActiveCardWeek}
            onResetToBlankTemplate={handleResetToBlankTemplate}
            onPropagateExerciseNames={handlePropagateExerciseNames}
            onDownloadTemplate={handleDownloadTemplate}
            onUploadClick={handleTemplateUploadClick}
            onUploadChosen={handleTemplateFileChosen}
            importSheetChoice={importSheetChoice}
            onImportSheetChoiceChange={setImportSheetChoice}
            onToggleEditorMode={toggleEditorMode}
            onIntensityModeChange={setIntensityMode}
            onProgramDataChange={setProgramData}
            onPreview={() => setShowPreview(true)}
            onSave={handleSave}
          />
          {showPreview && (
            <ProgramPreview
              programData={programData}
              programName={formData.name}
              athleteUsername={assignedAthleteUsername}
              athleteProfileSuffix={assignedAthleteProfileSuffix}
              onClose={() => setShowPreview(false)}
            />
          )}
        </>
      )}
    </div>
  )
}

const AssignedAthleteBadge = ({ username, profileSuffix }) => {
  if (!username) {
    return (
      <span className="assigned-athlete assigned-athlete-empty">
        No athlete assigned yet
      </span>
    )
  }
  return (
    <span className="assigned-athlete">
      Assigned to <span className="assigned-athlete-name username-highlight">@{username}</span>
      {profileSuffix ? <span className="athlete-inline-meta">{profileSuffix}</span> : null}
    </span>
  )
}

// --------------------------------------------------------------------------
// List view -- programs grouped by athlete. Each athlete is a collapse-default
// container with a glance-view of progress; expand reveals their programs
// sorted newest-first; each program is its own collapse-default row that
// shows extra detail when expanded and links into the full editor.
// --------------------------------------------------------------------------

// One program inside an athlete group. Collapsed: name + date range + pct ring
// only. Expanded: progress breakdown + Edit + Reassign controls.
const ProgramRow = ({ program, athletes, assignmentDrafts, onAssignDraftChange, onAssignSubmit, onEditProgram }) => {
  const [isOpen, setIsOpen] = useState(false)
  const normalized = normalizeProgramData(program.program_data, program.start_date)
  const exerciseCount = countExercises(normalized)
  const progress = summarizeProgramCompletion(program, exerciseCount)
  const pct = progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0
  return (
    <div className={`program-row ${isOpen ? 'is-open' : ''}`}>
      <button
        type="button"
        className="program-row-head"
        onClick={() => setIsOpen((v) => !v)}
        aria-expanded={isOpen}
      >
        <div className="program-row-ring" aria-label={`${progress.completed} of ${progress.total} exercises completed`}>
          <ProgressRing completed={progress.completed} total={progress.total} size={38} strokeWidth={3} />
          <span className="program-row-ring-pct data">{pct}%</span>
        </div>
        <span className="program-row-head-main">
          <span className="program-row-title">{programTitleForDisplay(program.name) || 'Program'}</span>
          <span className="program-row-dates">
            <span className="data">{program.start_date}</span>
            {program.end_date && (
              <>
                <span className="program-row-dot">→</span>
                <span className="data">{program.end_date}</span>
              </>
            )}
          </span>
        </span>
        <span className="program-row-chevron" aria-hidden="true">{isOpen ? '▾' : '▸'}</span>
      </button>
      {isOpen && (
        <div className="program-row-body">
          <div className="program-row-meta">
            <span><span className="data">{progress.completed}</span>/<span className="data">{progress.total}</span> done</span>
            <span className="program-row-dot">·</span>
            <span><span className="data">{normalized.days.length}</span> days</span>
            <span className="program-row-dot">·</span>
            <span><span className="data">{exerciseCount}</span> exercises</span>
            {program.updated_at && (
              <>
                <span className="program-row-dot">·</span>
                <span className="program-row-updated">updated {relativeTimeSince(program.updated_at)}</span>
              </>
            )}
          </div>
          <div className="program-row-actions">
            <button type="button" className="save-btn" onClick={() => onEditProgram(program)}>
              Open program →
            </button>
            <select
              value={assignmentDrafts[program.id] ?? ''}
              onChange={(event) => onAssignDraftChange(program.id, event.target.value)}
              className="form-input program-row-reassign-select"
              aria-label="Select athlete"
            >
              <option value="">Select athlete…</option>
              {athletes.map((athlete) => (
                <option key={athlete.id} value={athlete.id}>{athlete.username}</option>
              ))}
            </select>
            {assignmentDrafts[program.id] && (
              <button type="button" className="text-btn program-row-reassign-go" onClick={() => onAssignSubmit(program.id)}>
                Go
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// One athlete container. Collapsed: name + program count + aggregate ring.
// Expanded: their programs, newest start_date first.
const AthleteGroup = ({ athleteUsername, programs, athletes, assignmentDrafts,
  onAssignDraftChange, onAssignSubmit, onEditProgram }) => {
  const [isOpen, setIsOpen] = useState(false)
  const profileSuffix = useMemo(() => athleteProfileSuffix(programs[0] || {}), [programs])
  // Aggregate totals across every program in this athlete's bucket so the
  // collapsed header shows a single "how's this athlete doing overall" read.
  const { totalCompleted, totalExercises, mostRecent } = programs.reduce(
    (acc, p) => {
      const normalized = normalizeProgramData(p.program_data, p.start_date)
      const exerciseCount = countExercises(normalized)
      const summary = summarizeProgramCompletion(p, exerciseCount)
      acc.totalCompleted += summary.completed
      acc.totalExercises += summary.total
      if (!acc.mostRecent || (p.updated_at && p.updated_at > acc.mostRecent)) acc.mostRecent = p.updated_at
      return acc
    },
    { totalCompleted: 0, totalExercises: 0, mostRecent: null },
  )
  const pct = totalExercises > 0 ? Math.round((totalCompleted / totalExercises) * 100) : 0
  return (
    <div className={`athlete-group ${isOpen ? 'is-open' : ''}`}>
      <button
        type="button"
        className="athlete-group-head"
        onClick={() => setIsOpen((v) => !v)}
        aria-expanded={isOpen}
      >
        <div className="athlete-group-ring">
          <ProgressRing completed={totalCompleted} total={totalExercises} size={44} strokeWidth={3} />
          <span className="athlete-group-ring-pct data">{pct}%</span>
        </div>
        <span className="athlete-group-main">
          <span className="athlete-group-name-row">
            <span className="athlete-group-name username-highlight">@{athleteUsername}</span>
            {profileSuffix ? <span className="athlete-inline-meta">{profileSuffix}</span> : null}
          </span>
          <span className="athlete-group-meta">
            <span className="data">{programs.length}</span> program{programs.length === 1 ? '' : 's'}
            <span className="program-row-dot">·</span>
            <span className="data">{totalCompleted}</span>/<span className="data">{totalExercises}</span> exercises done
            {mostRecent && (
              <>
                <span className="program-row-dot">·</span>
                <span>updated {relativeTimeSince(mostRecent)}</span>
              </>
            )}
          </span>
        </span>
        <span className="athlete-group-chevron" aria-hidden="true">{isOpen ? '▾' : '▸'}</span>
      </button>
      {isOpen && (
        <div className="athlete-group-body">
          {programs.map((program) => (
            <ProgramRow
              key={program.id}
              program={program}
              athletes={athletes}
              assignmentDrafts={assignmentDrafts}
              onAssignDraftChange={onAssignDraftChange}
              onAssignSubmit={onAssignSubmit}
              onEditProgram={onEditProgram}
            />
          ))}
        </div>
      )}
    </div>
  )
}

const ListView = ({
  programs,
  athletes,
  assignmentDrafts,
  onAssignDraftChange,
  onAssignSubmit,
  onNewProgram,
  onEditProgram,
  saveMessage,
  rosterRecordsPerAthlete,
  rosterAthleteCount,
  rosterPrsLoading,
  rosterPrsError,
}) => {
  // Bucket programs by athlete, newest-first within each bucket, then sort
  // the groups alphabetically by athlete username so the roster is stable
  // between renders.
  const groupsByAthlete = programs.reduce((acc, program) => {
    const key = program.athlete_id ?? 'unassigned'
    if (!acc[key]) {
      acc[key] = {
        athleteId: key,
        athleteUsername: program.athlete_username || 'unassigned',
        programs: [],
      }
    }
    acc[key].programs.push(program)
    return acc
  }, {})
  const groups = Object.values(groupsByAthlete)
  groups.forEach((group) => {
    group.programs.sort((a, b) => {
      // Start date descending -> most-recent block surfaces first.
      const aStart = a.start_date || ''
      const bStart = b.start_date || ''
      if (aStart !== bStart) return bStart.localeCompare(aStart)
      return (b.updated_at || '').localeCompare(a.updated_at || '')
    })
  })
  groups.sort((a, b) => a.athleteUsername.localeCompare(b.athleteUsername))

  return (
    <>
      <div className="dashboard-header">
        <div className="dashboard-kicker-row">
          <span className="dashboard-kicker">Coach</span>
          <button type="button" className="save-btn" onClick={onNewProgram}>+ New program</button>
        </div>
        <h1>Your athletes</h1>
        <p className="dashboard-description">
          Each athlete's programs are collapsed by default. Tap to expand, then tap a program to open it.
        </p>
        {saveMessage && (
          <div className={`save-message ${saveMessage.toLowerCase().includes('error') || saveMessage.toLowerCase().includes('could') ? 'error' : 'success'}`}>
            {saveMessage}
          </div>
        )}
      </div>

      {programs.length === 0 ? (
        <div className="empty-state">
          <p>No programs yet.</p>
          <p className="section-subtitle">Click <strong>+ New program</strong> to build your first one, or download the Excel template (Instructions + 4 / 8 / 16 Week tabs) and import the tab you filled.</p>
        </div>
      ) : (
        <>
          <CoachRosterAggregateCharts
            recordsPerAthlete={rosterRecordsPerAthlete}
            athleteCount={rosterAthleteCount}
            loading={rosterPrsLoading}
            error={rosterPrsError}
          />
          <div className="athlete-groups-list">
            {groups.map((group) => (
              <AthleteGroup
                key={group.athleteId}
                athleteUsername={group.athleteUsername}
                programs={group.programs}
                athletes={athletes}
                assignmentDrafts={assignmentDrafts}
                onAssignDraftChange={onAssignDraftChange}
                onAssignSubmit={onAssignSubmit}
                onEditProgram={onEditProgram}
              />
            ))}
          </div>
        </>
      )}
    </>
  )
}

// --------------------------------------------------------------------------
// Editor view -- clean focused program builder with all seven power features.
// --------------------------------------------------------------------------
const EditorView = ({
  editingProgramId, formData, programData, athletes, athleteSearch, athleteTotal,
  assignedAthleteUsername, assignedAthleteProfileSuffix,
  coachAthletePrs, coachPrsLoading, coachPrsError,
  editorMode, intensityMode, saving, saveMessage, upcomingSummary, currentBlockKey,
  activeCardWeek, editorWeekCount,
  fileInputRef, draftBadge,
  importSheetChoice, onImportSheetChoiceChange,
  onBack, onFormChange, onBlockPreset, onBlockCustom, onAthleteSearch, onDayChange, onExercisesChange,
  onAddDay, onRemoveDay, onDuplicateDay, onMoveDay, onApplyRestDay,
  onAddCustomWeek, onRemoveCustomWeek,
  onSelectCardWeek,
  onResetToBlankTemplate,
  onPropagateExerciseNames,
  onDownloadTemplate, onUploadClick, onUploadChosen,
  onToggleEditorMode, onIntensityModeChange, onProgramDataChange, onPreview, onSave,
}) => {
  const [propagateNamesChecked, setPropagateNamesChecked] = useState(false)
  const dayCount = programData.days.length
  const coachPrChartsIntro = !formData.athlete_id
    ? ''
    : (
      <>
        PR history for{' '}
        {assignedAthleteUsername
          ? <span className="username-highlight">@{assignedAthleteUsername}</span>
          : 'this athlete'}{' '}
        (read-only). Same visualizations as the athlete stats drawer: monthly bests, estimated peak
        rhythm on competition totals, and a six-month rolling peak. Forecasts are planning hints
        only, not a physiological model.
      </>
    )
  return (
    <>
      <div className="editor-topbar">
        <button type="button" className="text-btn editor-back-btn" onClick={onBack} aria-label="Back to programs">
          ← Programs
        </button>
        <div className="editor-tool-group">
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv,.ods,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv"
            onChange={onUploadChosen}
            style={{ display: 'none' }}
            aria-hidden="true"
          />
          <div className="editor-tool-row editor-tool-row-primary">
            <button type="button" className="tool-btn" onClick={onDownloadTemplate} title="Download the .xlsx template to fill in your program offline">
              <span className="tool-btn-icon">⬇</span>
              <span className="tool-btn-label">Download Template</span>
            </button>
            <button type="button" className="tool-btn" onClick={onUploadClick} title="Upload a filled-in .xlsx to autofill this program">
              <span className="tool-btn-icon">⬆</span>
              <span className="tool-btn-label">Upload Program</span>
            </button>
            <label className="import-sheet-control" title="Auto uses the 4 Week tab when this template has it. Pick 8 Week or 16 Week if you only filled that tab; side-by-side blocks on one tab are merged into one program.">
              <span className="import-sheet-control-label">Import worksheet</span>
              <select
                className="form-input import-sheet-select"
                value={importSheetChoice}
                onChange={(e) => onImportSheetChoiceChange(e.target.value)}
              >
                <option value="auto">Auto (4 Week tab when present)</option>
                {PROGRAM_TEMPLATE_BLOCK_SHEETS.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="editor-tool-row editor-tool-row-secondary">
            <button type="button" className="tool-btn" onClick={onToggleEditorMode}
                    title={editorMode === 'form' ? 'Switch to spreadsheet view (Excel-like grid)' : 'Switch to card view (day-by-day cards)'}>
              <span className="tool-btn-icon">{editorMode === 'form' ? '⊞' : '☰'}</span>
              <span className="tool-btn-label">{editorMode === 'form' ? 'Spreadsheet View' : 'Card View'}</span>
            </button>
            <button type="button" className="tool-btn" onClick={onPreview}
                    title="See this program from the athlete's perspective">
              <span className="tool-btn-label">Preview as Athlete</span>
            </button>
          </div>
        </div>
      </div>

      {draftBadge && (
        <div className="draft-badge">Restored unsaved draft from this browser.</div>
      )}

      <div className="editor-header">
        <div className="editor-title-block">
          <input
            type="text"
            placeholder="Enter Program Name"
            value={formData.name}
            onChange={(event) => onFormChange('name', event.target.value)}
            className="editor-title-input"
            aria-label="Enter Program Name"
          />
          <AssignedAthleteBadge username={assignedAthleteUsername} profileSuffix={assignedAthleteProfileSuffix} />
        </div>
        <div className="editor-summary">
          <span className="data">{upcomingSummary.dayCount}</span> days
          <span className="program-row-dot">·</span>
          <span className="data">{upcomingSummary.exerciseCount}</span> exercises
        </div>
      </div>

      {saveMessage && (
        <div className={`save-message ${saveMessage.toLowerCase().includes('error') || saveMessage.toLowerCase().includes('could') ? 'error' : 'success'}`}>
          {saveMessage}
        </div>
      )}

      <div className="section-card editor-meta-card">
        <div className="form-row">
          <input
            type="search"
            placeholder={athleteSearch
              ? `Filter athletes (${athleteTotal} match${athleteTotal === 1 ? '' : 'es'})`
              : 'Filter athletes by name'}
            value={athleteSearch}
            onChange={(event) => onAthleteSearch(event.target.value)}
            className="form-input"
            aria-label="Search athletes"
          />
          <select
            value={formData.athlete_id}
            onChange={(event) => onFormChange('athlete_id', event.target.value)}
            className="form-input"
            aria-label="Select athlete"
          >
            <option value="">Select athlete…</option>
            {athletes.map((athlete) => (
              <option key={athlete.id} value={athlete.id}>{athlete.username}</option>
            ))}
          </select>
        </div>
        <textarea
          placeholder="Program description (optional)"
          value={formData.description}
          onChange={(event) => onFormChange('description', event.target.value)}
          className="notes-textarea"
          rows="2"
        />

        <div className="form-grid compact-grid editor-date-grid">
          <label className="field-stacked">
            <span>Start</span>
            <input
              type="date"
              value={formData.start_date}
              onChange={(event) => onFormChange('start_date', event.target.value)}
              className="form-input"
            />
          </label>
          <label className="field-stacked">
            <span>End</span>
            <input
              type="date"
              value={formData.end_date}
              onChange={(event) => onFormChange('end_date', event.target.value)}
              className="form-input"
            />
          </label>
          <div className="field-stacked">
            <span>Week of</span>
            <span className="data field-value">{programData.week_start_date || formData.start_date}</span>
          </div>
        </div>

        <div className="block-length-picker">
          <span className="block-length-label">Block length</span>
          <div className="block-length-options" role="radiogroup" aria-label="Block length preset">
            {BLOCK_PRESETS.map((preset) => (
              <button
                key={preset.key}
                type="button"
                role="radio"
                aria-checked={currentBlockKey === preset.key}
                className={`block-length-chip ${currentBlockKey === preset.key ? 'is-active' : ''}`}
                onClick={() => onBlockPreset(preset.weeks)}
              >
                {preset.label}
              </button>
            ))}
            <button
              type="button"
              className={`block-length-chip ${currentBlockKey === 'custom' ? 'is-active' : ''} block-length-chip-custom`}
              onClick={onBlockCustom}
              role="radio"
              aria-checked={currentBlockKey === 'custom'}
            >
              Custom
            </button>
          </div>
        </div>

        <div className="intensity-mode-picker">
          <span className="block-length-label">Intensity mode</span>
          <div className="block-length-options" role="radiogroup" aria-label="Intensity mode">
            {[
              { key: 'percent_1rm', label: '% 1RM' },
              { key: 'rpe',         label: 'RPE' },
              { key: 'weight',      label: 'Weight' },
            ].map((mode) => (
              <button
                key={mode.key}
                type="button"
                role="radio"
                aria-checked={intensityMode === mode.key}
                className={`block-length-chip ${intensityMode === mode.key ? 'is-active' : ''}`}
                onClick={() => onIntensityModeChange(mode.key)}
                title={`Show only ${mode.label} in the prescription grid (hidden data is preserved)`}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <section className="section-card coach-athlete-pr-charts" aria-labelledby="coach-athlete-pr-heading">
        <h3 id="coach-athlete-pr-heading" className="coach-athlete-pr-charts-title">Athlete PR trends</h3>
        {!formData.athlete_id ? (
          <p className="section-subtitle coach-athlete-pr-charts-hint">
            Choose an athlete above to load charts. Data comes from their PR log; the backend only returns athletes you manage.
          </p>
        ) : coachPrsLoading ? (
          <div className="loading coach-athlete-pr-charts-loading">Loading PR history…</div>
        ) : coachPrsError ? (
          <>
            <p className="section-subtitle coach-athlete-pr-charts-error" role="alert">{coachPrsError}</p>
            <p className="section-subtitle coach-athlete-pr-charts-policy">
              If you picked someone who has never been on a saved program with you, save this program once so the server can authorize PR reads, then reopen the editor or switch athlete and back.
            </p>
          </>
        ) : (
          <AthleteTrainingTrendCharts
            personalRecords={coachAthletePrs}
            intro={coachPrChartsIntro}
            audience="coach"
          />
        )}
      </section>

      <div className="section-title-row">
        <h3>Weekly structure</h3>
        <div className="editor-structure-actions editor-structure-actions-stack">
          <div className="editor-structure-actions-row">
            {editorMode === 'form' && (
              <button type="button" className="text-btn" onClick={onAddDay}>+ Add day</button>
            )}
            <button type="button" className="text-btn reset-template-btn" onClick={onResetToBlankTemplate}>
              Reset blank template
            </button>
          </div>
          <label className="editor-propagate-toggle">
            <input
              type="checkbox"
              checked={propagateNamesChecked}
              onChange={(event) => {
                const checked = event.target.checked
                setPropagateNamesChecked(checked)
                if (checked) onPropagateExerciseNames()
              }}
            />
            <span>Repeat Week 1 exercise names across weeks</span>
            <span
              className="editor-propagate-help"
              tabIndex={0}
              aria-label="Propagation help"
              role="button"
              aria-describedby="propagation-help-tooltip"
            >
              ?
              <span id="propagation-help-tooltip" role="tooltip" className="editor-propagate-tooltip">
                <strong className="editor-propagate-tooltip-lead">Copies only exercise names.</strong>
                {' '}
                Uses <span className="editor-propagate-tooltip-key">Week 1</span> as the source and repeats names across each day for the other weeks.
                {' '}
                <span className="editor-propagate-tooltip-key">Sets, reps, percent/RPE/weight, tempo, rest, and notes</span> are left unchanged.
              </span>
            </span>
          </label>
        </div>
      </div>

      {editorMode === 'spreadsheet' ? (
        <SpreadsheetEditor
          programData={programData}
          onChange={onProgramDataChange}
          intensityMode={intensityMode}
          blockPresetKey={currentBlockKey}
          weekCount={editorWeekCount}
          onAddCustomWeek={onAddCustomWeek}
          onRemoveCustomWeek={onRemoveCustomWeek}
          onBlockPresetSelect={onBlockPreset}
          onBlockCustomSelect={onBlockCustom}
        />
      ) : (
        <>
          {currentBlockKey === 'custom' && (
            <div className="coach-week-controls" aria-label="Custom week controls">
              <span className="coach-week-counter">
                Week count: <strong>{editorWeekCount}</strong>
              </span>
              <button type="button" className="text-btn" onClick={onAddCustomWeek}>+ Add week</button>
              <button type="button" className="text-btn" onClick={onRemoveCustomWeek} disabled={editorWeekCount <= 1}>− Remove week</button>
            </div>
          )}
          <div className="coach-week-tabs" role="tablist" aria-label="Program week tabs">
            {Array.from({ length: editorWeekCount }).map((_, idx) => {
              const week = idx + 1
              return (
                <button
                  key={week}
                  type="button"
                  role="tab"
                  aria-selected={activeCardWeek === week}
                  className={`program-chip ${activeCardWeek === week ? 'is-active' : ''}`}
                  onClick={() => onSelectCardWeek(week)}
                >
                  Week {week}
                </button>
              )
            })}
          </div>
          <div className="day-stack">
          {programData.days.map((day, dayIndex) => (
            <WorkoutDay
              key={day.id || `day-fallback-${dayIndex}`}
              day={day}
              dayIndex={dayIndex}
              dayCount={dayCount}
              exercises={(day.exercises || []).filter((exercise) => {
                const raw = String(exercise?.week ?? '').trim()
                if (!raw) return activeCardWeek === 1
                const n = Number.parseInt(raw, 10)
                return Number.isFinite(n) ? n === activeCardWeek : activeCardWeek === 1
              })}
              intensityMode={intensityMode}
              onExercisesChange={(nextExercises) => onExercisesChange(dayIndex, nextExercises)}
              onDayChange={(nextDayName) => onDayChange(dayIndex, nextDayName)}
              onRemoveDay={() => onRemoveDay(dayIndex)}
              onDuplicateDay={() => onDuplicateDay(dayIndex)}
              onMoveDayUp={() => onMoveDay(dayIndex, -1)}
              onMoveDayDown={() => onMoveDay(dayIndex, 1)}
              onApplyRestDay={() => onApplyRestDay(dayIndex)}
              canRemoveDay={programData.days.length > 1}
              isCoach
            />
          ))}
          </div>
        </>
      )}
      <div className="editor-publish-footer">
        <button
          type="button"
          className="save-btn publish-btn"
          onClick={onSave}
          disabled={saving || !formData.name || !formData.athlete_id}
        >
          {saving ? 'Publishing…' : 'Publish Program'}
        </button>
      </div>
    </>
  )
}

export default CoachDashboard
