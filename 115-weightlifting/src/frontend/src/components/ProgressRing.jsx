// Completion ring used by the athlete WeekStrip (per day) and the coach
// program list (per program). Same visual vocabulary in both places so the
// coach instantly recognizes progress the way the athlete sees it.
//
// stroke-dashoffset is what animates when completion changes; the transition
// lives in App.css so we can apply it to every ring in the app at once.

const ProgressRing = ({ completed = 0, total = 0, size = 38, active = false, strokeWidth = 3 }) => {
  const radius = (size / 2) - strokeWidth
  const circumference = 2 * Math.PI * radius
  const pct = total > 0 ? Math.min(1, completed / total) : 0
  const dashOffset = circumference * (1 - pct)
  const stroke = active ? 'var(--neon-cyan)' : pct === 1 ? 'var(--success)' : 'var(--line-strong)'
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" className="progress-ring">
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(95,228,255,0.14)" strokeWidth={strokeWidth} />
      <circle
        cx={size / 2} cy={size / 2} r={radius}
        fill="none"
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={dashOffset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
    </svg>
  )
}

export default ProgressRing
