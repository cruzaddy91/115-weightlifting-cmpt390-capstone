// Horizontal day cells with a per-day completion ring. Clicking a cell swaps
// the dashboard's selected day. Keyboard navigable (tab + Enter/Space).
// Scrolls horizontally on narrow screens so it never forces the viewport wide.

import ProgressRing from './ProgressRing'

const dayAbbrev = (dayName, fallbackIndex) => {
  if (!dayName) return `D${fallbackIndex + 1}`
  const trimmed = dayName.trim()
  if (/^day\s*\d+$/i.test(trimmed)) return trimmed.replace(/\s+/g, '').toUpperCase()
  return trimmed.slice(0, 3).toUpperCase()
}

const WeekStrip = ({ days, completionCounts, selectedDayId, onSelectDay }) => {
  return (
    <div className="week-strip" role="tablist" aria-label="Week days">
      {days.map((day, index) => {
        const counts = completionCounts[day.id] || { completed: 0, total: day.exercises?.length || 0 }
        const isActive = day.id === selectedDayId
        const isFull = counts.total > 0 && counts.completed === counts.total
        return (
          <button
            key={day.id || index}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={`week-strip-cell ${isActive ? 'is-active' : ''} ${isFull ? 'is-full' : ''}`}
            onClick={() => onSelectDay(day.id)}
          >
            <span className="week-strip-label">{dayAbbrev(day.day, index)}</span>
            <ProgressRing completed={counts.completed} total={counts.total} active={isActive} />
            <span className="week-strip-ratio data">
              {counts.completed}/{counts.total}
            </span>
          </button>
        )
      })}
    </div>
  )
}

export default WeekStrip
