import { useId, useState } from 'react'
import { createEmptyExercise } from '../utils/dataStructure'
import { EXERCISE_LIBRARY } from '../utils/exerciseLibrary'

// Column schema in the card view mirrors the xlsx template 1:1 so whatever a
// coach sees here round-trips to the uploaded / downloaded sheet without loss.
// Three intensity fields on purpose -- coach fills in whichever they prefer
// (% 1RM / RPE / Weight). The intensity-mode prop lets the coach hide two of
// the three at once for a calmer grid.

const syncIntensity = (exercise) => ({
  ...exercise,
  intensity: exercise.percent_1rm || exercise.rpe || exercise.weight || '',
})

const cloneExercise = (exercise) => ({ ...exercise })

const swap = (array, i, j) => {
  if (i < 0 || j < 0 || i >= array.length || j >= array.length) return array
  const next = [...array]
  const tmp = next[i]
  next[i] = next[j]
  next[j] = tmp
  return next
}

const WorkoutDay = ({
  day,
  dayIndex,
  dayCount,
  exercises,
  onExercisesChange,
  onDuplicateDay,
  onMoveDayUp,
  onMoveDayDown,
  isCoach,
  athleteResults,
  onResultChange,
  onDayChange,
  onRemoveDay,
  onApplyRestDay,
  canRemoveDay = false,
  intensityMode = 'percent_1rm',
}) => {
  // Collapse-by-default matches the rest of the app: the coach opens only
  // the day(s) they're editing, and reloading the editor never leaves a
  // previously-open day stuck open.
  const [isExpanded, setIsExpanded] = useState(false)
  const datalistId = useId()

  const handleAddExercise = () => {
    onExercisesChange([...exercises, createEmptyExercise()])
  }

  const handleExerciseChange = (index, field, value) => {
    const nextExercises = [...exercises]
    const nextExercise = { ...nextExercises[index], [field]: value }
    if (field === 'percent_1rm' || field === 'rpe' || field === 'weight') {
      nextExercises[index] = syncIntensity(nextExercise)
    } else {
      nextExercises[index] = nextExercise
    }
    onExercisesChange(nextExercises)
  }

  const handleRemoveExercise = (index) => {
    const name = exercises[index]?.name?.trim()
    const label = name ? `"${name}"` : 'this exercise'
    const ok = typeof window === 'undefined' || window.confirm(`Remove ${label}? This cannot be undone.`)
    if (!ok) return
    onExercisesChange(exercises.filter((_, exerciseIndex) => exerciseIndex !== index))
  }

  const handleDuplicateExercise = (index) => {
    const next = [...exercises]
    next.splice(index + 1, 0, cloneExercise(exercises[index]))
    onExercisesChange(next)
  }

  const handleMoveExerciseUp = (index) => {
    onExercisesChange(swap(exercises, index, index - 1))
  }

  const handleMoveExerciseDown = (index) => {
    onExercisesChange(swap(exercises, index, index + 1))
  }

  const getAthleteResult = (exerciseIndex) => {
    if (!athleteResults) return null
    return athleteResults[String(exerciseIndex)] || null
  }

  const handleAthleteResultChange = (exerciseIndex, field, value) => {
    if (onResultChange) onResultChange(exerciseIndex, field, value)
  }

  return (
    <div className="workout-day section-card">
      <div className="day-header">
        <div className="day-heading-group">
          <button type="button" className="text-btn day-collapse-btn" onClick={() => setIsExpanded((c) => !c)}
                  title={isExpanded ? 'Collapse day' : 'Expand day'}>
            {isExpanded ? '▾' : '▸'}
          </button>
          {isCoach ? (
            <input
              type="text"
              value={day.day}
              onChange={(event) => onDayChange?.(event.target.value)}
              className="day-title-input"
              placeholder={`Day ${dayIndex + 1}`}
            />
          ) : (
            <h3>{day.day}</h3>
          )}
          <span className="day-exercise-count">
            <span className="data">{exercises.length}</span> {exercises.length === 1 ? 'exercise' : 'exercises'}
          </span>
        </div>
        {isCoach && (
          <div className="day-header-actions">
            <button type="button" className="icon-btn" onClick={onMoveDayUp} disabled={dayIndex === 0}
                    aria-label="Move day up" title="Move day up">↑</button>
            <button type="button" className="icon-btn" onClick={onMoveDayDown} disabled={dayIndex >= (dayCount ?? Infinity) - 1}
                    aria-label="Move day down" title="Move day down">↓</button>
            <button type="button" className="icon-btn" onClick={onDuplicateDay}
                    aria-label="Duplicate day" title="Duplicate day">⎘</button>
            {canRemoveDay && (
              <div className="day-destructive-actions">
                <button type="button" className="text-btn day-remove-btn" onClick={onRemoveDay}>
                  Remove day
                </button>
                <button type="button" className="text-btn day-rest-btn" onClick={onApplyRestDay}>
                  Set Rest Day
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {isCoach && (
        <datalist id={datalistId}>
          {EXERCISE_LIBRARY.map((name) => <option key={name} value={name} />)}
        </datalist>
      )}

      {isExpanded && (
        <div className="day-content">
          {exercises.length === 0 && (
            <div className="empty-inline day-empty">No exercises for this day yet.</div>
          )}

          {exercises.map((exercise, index) => {
            const athleteResult = getAthleteResult(index)
            const isCompleted = athleteResult?.completed || false

            return isCoach ? (
              <CoachExerciseRow
                key={`coach-${index}`}
                exercise={exercise}
                isFirst={index === 0}
                isOnly={exercises.length === 1}
                isLast={index === exercises.length - 1}
                datalistId={datalistId}
                intensityMode={intensityMode}
                onChange={(field, value) => handleExerciseChange(index, field, value)}
                onRemove={() => handleRemoveExercise(index)}
                onDuplicate={() => handleDuplicateExercise(index)}
                onMoveUp={() => handleMoveExerciseUp(index)}
                onMoveDown={() => handleMoveExerciseDown(index)}
              />
            ) : (
              <AthleteExerciseRow
                key={`athlete-${index}`}
                exercise={exercise}
                isFirst={index === 0}
                isCompleted={isCompleted}
                result={athleteResult}
                onResultChange={(field, value) => handleAthleteResultChange(index, field, value)}
              />
            )
          })}

          {isCoach && (
            <button type="button" onClick={handleAddExercise} className="text-btn add-exercise-btn">
              + Add exercise
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------
// Coach input row -- one exercise with reorder / duplicate / delete controls.
// Intensity mode controls which of % 1RM / RPE / Weight is visible. Data in
// the hidden fields is preserved, just not shown.
// --------------------------------------------------------------------------
const CoachExerciseRow = ({
  exercise,
  isFirst,
  isOnly,
  isLast,
  datalistId,
  intensityMode,
  onChange,
  onRemove,
  onDuplicate,
  onMoveUp,
  onMoveDown,
}) => (
  <div className={`exercise-row ${isFirst ? 'exercise-row-first' : ''}`}>
    <div className="exercise-row-header">
      <input
        type="text"
        placeholder="Exercise name (Snatch, Clean & Jerk + OHS)"
        value={exercise.name || ''}
        onChange={(event) => onChange('name', event.target.value)}
        className="exercise-name-input"
        aria-label="Exercise name"
        list={datalistId}
        autoComplete="off"
      />
      <div className="exercise-row-controls">
        <button type="button" className="icon-btn" onClick={onMoveUp} disabled={isFirst}
                aria-label="Move exercise up" title="Move up">↑</button>
        <button type="button" className="icon-btn" onClick={onMoveDown} disabled={isLast}
                aria-label="Move exercise down" title="Move down">↓</button>
        <button type="button" className="icon-btn" onClick={onDuplicate}
                aria-label="Duplicate exercise" title="Duplicate">⎘</button>
        <button type="button" className="icon-btn icon-btn-danger" onClick={onRemove} disabled={isOnly}
                aria-label="Remove exercise" title="Remove">×</button>
      </div>
    </div>

    <div className="exercise-prescription-grid">
      <Field label="Sets" value={exercise.sets} onChange={(v) => onChange('sets', v)} placeholder="5" width="5ch" />
      <Field label="Reps" value={exercise.reps} onChange={(v) => onChange('reps', v)} placeholder="2 or 1+1" width="8ch" />
      {intensityMode === 'percent_1rm' && (
        <Field label="% 1RM" value={exercise.percent_1rm} onChange={(v) => onChange('percent_1rm', v)} placeholder="75%" width="7ch" />
      )}
      {intensityMode === 'rpe' && (
        <Field label="RPE" value={exercise.rpe} onChange={(v) => onChange('rpe', v)} placeholder="8" width="5ch" />
      )}
      {intensityMode === 'weight' && (
        <Field label="Weight" value={exercise.weight} onChange={(v) => onChange('weight', v)} placeholder="100kg" width="8ch" />
      )}
      <Field label="Tempo" value={exercise.tempo} onChange={(v) => onChange('tempo', v)} placeholder="3-1-X-1" width="8ch" />
      <Field label="Rest" value={exercise.rest} onChange={(v) => onChange('rest', v)} placeholder="2min" width="6ch" />
    </div>

    <textarea
      placeholder="Coach notes (cues, technique reminders, warmup detail)"
      value={exercise.notes || ''}
      onChange={(event) => onChange('notes', event.target.value)}
      className="notes-textarea exercise-notes"
      rows="2"
      aria-label="Coach notes"
    />
  </div>
)

const Field = ({ label, value, onChange, placeholder, width }) => (
  <label className="field-inline" style={{ minWidth: width }}>
    <span>{label}</span>
    <input
      type="text"
      value={value || ''}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className="field-inline-input data"
    />
  </label>
)

// --------------------------------------------------------------------------
// Athlete view -- read-only prescription + completed + actual-result.
// Shows whichever of % 1RM / RPE / Weight were actually prescribed.
// --------------------------------------------------------------------------
const AthleteExerciseRow = ({ exercise, isFirst, isCompleted, result, onResultChange }) => {
  const intensityTokens = []
  if (exercise.percent_1rm) intensityTokens.push(exercise.percent_1rm)
  else if (exercise.intensity) intensityTokens.push(exercise.intensity)
  if (exercise.rpe) intensityTokens.push(`RPE ${exercise.rpe}`)
  if (exercise.weight) intensityTokens.push(exercise.weight)
  const intensityLabel = intensityTokens.length > 0 ? intensityTokens.join(' · ') : null

  return (
    <div className={`exercise-row athlete-row ${isFirst ? 'exercise-row-first' : ''} ${isCompleted ? 'exercise-row-completed' : ''}`}>
      <div className="exercise-row-header">
        <h4 className="athlete-exercise-title">{exercise.name || 'Exercise'}</h4>
        <label className="completed-checkbox">
          <input
            type="checkbox"
            checked={isCompleted}
            onChange={(event) => onResultChange('completed', event.target.checked)}
          />
          <span>Done</span>
        </label>
      </div>

      <div className="athlete-prescription">
        <span className="prescription-cell">
          <span className="label">Sets × Reps</span>
          <span className="value data">{exercise.sets || '—'} × {exercise.reps || '—'}</span>
        </span>
        {intensityLabel && (
          <span className="prescription-cell">
            <span className="label">Intensity</span>
            <span className="value data">{intensityLabel}</span>
          </span>
        )}
        {exercise.tempo && (
          <span className="prescription-cell">
            <span className="label">Tempo</span>
            <span className="value data">{exercise.tempo}</span>
          </span>
        )}
        {exercise.rest && (
          <span className="prescription-cell">
            <span className="label">Rest</span>
            <span className="value data">{exercise.rest}</span>
          </span>
        )}
      </div>

      {exercise.notes && (
        <div className="coach-notes">
          <strong>Coach notes:</strong> {exercise.notes}
        </div>
      )}

      <div className="athlete-result">
        <input
          type="text"
          className="form-input"
          placeholder="Actual result (75x2)"
          value={result?.result || ''}
          onChange={(event) => onResultChange('result', event.target.value)}
          aria-label="Actual result"
        />
        <textarea
          placeholder="How did it feel? (optional)"
          value={result?.athlete_notes || ''}
          onChange={(event) => onResultChange('athlete_notes', event.target.value)}
          className="athlete-notes"
          rows="1"
          aria-label="Athlete notes"
        />
      </div>
    </div>
  )
}

export default WorkoutDay
