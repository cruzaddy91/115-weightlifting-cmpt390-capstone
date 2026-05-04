import { useEffect } from 'react'
import WorkoutDay from './WorkoutDay'
import { programTitleForDisplay } from '../utils/safeDisplay'

// Read-only render of what the athlete sees. Uses the existing WorkoutDay in
// non-coach mode but disables the completion + result writes so the modal is
// a true preview, not an interactive surface.
const ProgramPreview = ({ programData, programName, athleteUsername, athleteProfileSuffix = '', onClose }) => {
  useEffect(() => {
    const handler = (event) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  useEffect(() => {
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [])

  const days = programData?.days || []

  return (
    <div className="preview-overlay" role="dialog" aria-modal="true" aria-label="Athlete preview">
      <div className="preview-shell">
        <div className="preview-topbar">
          <div>
            <div className="preview-kicker">Athlete preview</div>
            <h2 className="preview-title">{programTitleForDisplay(programName) || 'Untitled program'}</h2>
            {athleteUsername && (
              <div className="preview-subtitle">
                Athlete · {athleteUsername}
                {athleteProfileSuffix ? <span className="athlete-inline-meta">{athleteProfileSuffix}</span> : null}
              </div>
            )}
          </div>
          <button type="button" className="text-btn" onClick={onClose} aria-label="Close preview">
            Close
          </button>
        </div>

        <div className="preview-body">
          {days.length === 0 ? (
            <div className="empty-inline">No days in this program yet.</div>
          ) : (
            <div className="day-stack">
              {days.map((day, dayIndex) => (
                <WorkoutDay
                  key={day.id ? `preview-${day.id}` : `preview-${dayIndex}`}
                  day={day}
                  dayIndex={dayIndex}
                  exercises={day.exercises || []}
                  onExercisesChange={() => {}}
                  onDayChange={() => {}}
                  onRemoveDay={() => {}}
                  canRemoveDay={false}
                  isCoach={false}
                  athleteResults={{}}
                  onResultChange={() => {}}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ProgramPreview
