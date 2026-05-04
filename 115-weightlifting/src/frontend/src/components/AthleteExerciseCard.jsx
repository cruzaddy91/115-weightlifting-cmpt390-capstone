import { useEffect, useState } from 'react'

// One-exercise card tuned for at-the-gym use on a phone. Collapsed, the row
// shows status + name + prescription; tapping it expands a compact quick-log
// form: weight hit, feel (Hard / Solid / Easy), optional note, Save. Saved
// results collapse the card with a tiny caption ('hit 105kg · felt Solid').

const FEEL_OPTIONS = [
  { key: 'hard',  label: 'Hard' },
  { key: 'solid', label: 'Solid' },
  { key: 'easy',  label: 'Easy' },
]

// Keep feel labels out of the free-text athlete_notes field. A small prefix
// like 'felt: solid — <rest of their note>' lets us surface the pill in the
// header without a new backend column.
const FEEL_PREFIX = 'felt:'

const parseNotesForFeel = (notes) => {
  const s = String(notes || '').trim()
  if (!s.toLowerCase().startsWith(FEEL_PREFIX)) return { feel: '', rest: s }
  const remainder = s.slice(FEEL_PREFIX.length).trim()
  const [firstWord, ...restParts] = remainder.split(/\s+/)
  const feelKey = (firstWord || '').toLowerCase().replace(/[^a-z]/g, '')
  if (!FEEL_OPTIONS.some((f) => f.key === feelKey)) return { feel: '', rest: s }
  let rest = restParts.join(' ').trim()
  if (rest.startsWith('—')) rest = rest.slice(1).trim()
  return { feel: feelKey, rest }
}

const serializeNotesWithFeel = (feelKey, rest) => {
  const trimmedRest = (rest || '').trim()
  if (!feelKey) return trimmedRest
  const prefix = `${FEEL_PREFIX} ${feelKey}`
  return trimmedRest ? `${prefix} — ${trimmedRest}` : prefix
}

// Render the intensity prescription in a single compact line so the collapsed
// card stays scannable. Prefers % 1RM, then RPE, then weight -- matches the
// coach-side legacy intensity derivation.
const prescriptionSummary = (exercise) => {
  const sets = exercise.sets || '—'
  const reps = exercise.reps || '—'
  const intensity = exercise.percent_1rm || exercise.rpe && `RPE ${exercise.rpe}` || exercise.weight || exercise.intensity || ''
  return intensity ? `${sets}×${reps} @ ${intensity}` : `${sets}×${reps}`
}

const AthleteExerciseCard = ({ exercise, result, onSaveResult }) => {
  const isDone = !!result?.completed
  // Always mount collapsed. The athlete opens only what they need as they go,
  // and reloading the page never restores a previously expanded card.
  const [isExpanded, setIsExpanded] = useState(false)
  const parsed = parseNotesForFeel(result?.athlete_notes || '')
  const [weightInput, setWeightInput] = useState(result?.result || '')
  const [feel, setFeel] = useState(parsed.feel)
  const [noteInput, setNoteInput] = useState(parsed.rest)

  // Re-sync local inputs whenever the server-backed `result` changes while the
  // card is collapsed. Without this, a refresh or coach-side edit would leave
  // the card showing the athlete's old typed values instead of the authoritative
  // state. We skip re-sync while the card is expanded so we don't yank text
  // out from under the athlete mid-edit.
  const resultKey = `${result?.completed ? '1' : '0'}|${result?.result || ''}|${result?.athlete_notes || ''}`
  useEffect(() => {
    if (isExpanded) return
    const p = parseNotesForFeel(result?.athlete_notes || '')
    setWeightInput(result?.result || '')
    setFeel(p.feel)
    setNoteInput(p.rest)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resultKey])

  const handleToggle = () => setIsExpanded((c) => !c)

  // Emit the full result object in one call so the parent can persist to
  // the backend with a complete picture rather than reading possibly-stale
  // state after three separate onResultChange dispatches.
  const handleSave = () => {
    onSaveResult({
      result: weightInput.trim(),
      athlete_notes: serializeNotesWithFeel(feel, noteInput),
      completed: true,
    })
    setIsExpanded(false)
  }

  const handleUnmark = () => {
    onSaveResult({
      result: weightInput.trim(),
      athlete_notes: serializeNotesWithFeel(feel, noteInput),
      completed: false,
    })
    setIsExpanded(true)
  }

  return (
    <div className={`athlete-exercise-card ${isDone ? 'is-done' : ''}`}>
      <button
        type="button"
        className="athlete-exercise-head"
        aria-expanded={isExpanded}
        onClick={handleToggle}
      >
        <span className={`athlete-exercise-status ${isDone ? 'is-done' : ''}`} aria-hidden="true">
          {isDone ? '✓' : ''}
        </span>
        <span className="athlete-exercise-main">
          <span className="athlete-exercise-name">{exercise.name || 'Exercise'}</span>
          <span className="athlete-exercise-prescription data">
            {prescriptionSummary(exercise)}
            {exercise.tempo && <span className="athlete-exercise-extra"> · tempo {exercise.tempo}</span>}
            {exercise.rest && <span className="athlete-exercise-extra"> · rest {exercise.rest}</span>}
          </span>
          {isDone && !isExpanded && (weightInput || feel) && (
            <span className="athlete-exercise-summary">
              {weightInput && <>hit <span className="data">{weightInput}</span></>}
              {weightInput && feel && ' · '}
              {feel && <>felt {FEEL_OPTIONS.find((f) => f.key === feel)?.label}</>}
            </span>
          )}
        </span>
        <span className="athlete-exercise-chevron" aria-hidden="true">
          {isExpanded ? '▾' : '▸'}
        </span>
      </button>

      {isExpanded && (
        <div className="athlete-exercise-body">
          {exercise.notes && (
            <div className="athlete-exercise-coach-note">
              <strong>Coach:</strong> {exercise.notes}
            </div>
          )}

          <div className="athlete-quicklog">
            <label className="athlete-quicklog-field">
              <span>Weight you hit</span>
              <input
                type="text"
                inputMode="decimal"
                className="form-input data"
                placeholder={exercise.weight || '105kg'}
                value={weightInput}
                onChange={(event) => setWeightInput(event.target.value)}
                aria-label="Actual weight hit"
              />
            </label>

            <div className="athlete-quicklog-field">
              <span>How did it feel?</span>
              <div className="feel-pills" role="radiogroup" aria-label="Effort feel">
                {FEEL_OPTIONS.map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    role="radio"
                    aria-checked={feel === option.key}
                    className={`feel-pill ${feel === option.key ? 'is-active' : ''}`}
                    onClick={() => setFeel(feel === option.key ? '' : option.key)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <label className="athlete-quicklog-field athlete-quicklog-note">
              <span>Note (optional)</span>
              <input
                type="text"
                className="form-input"
                placeholder="anything worth remembering"
                value={noteInput}
                onChange={(event) => setNoteInput(event.target.value)}
                aria-label="Athlete note"
              />
            </label>

            <div className="athlete-quicklog-actions">
              {isDone ? (
                <>
                  <button type="button" className="text-btn" onClick={handleUnmark}>
                    Mark not done
                  </button>
                  <button type="button" className="save-btn" onClick={handleSave}>
                    Update
                  </button>
                </>
              ) : (
                <button type="button" className="save-btn athlete-quicklog-save" onClick={handleSave}>
                  Mark done
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default AthleteExerciseCard
