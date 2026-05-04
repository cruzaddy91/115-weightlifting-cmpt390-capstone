// Tiny relative-time formatter. Keeps the capstone dep-free (no date-fns /
// moment) by handling just the coarse "N unit ago" shape, which is all the
// program row needs.
const MINUTE = 60
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
const WEEK = 7 * DAY
const MONTH = 30 * DAY
const YEAR = 365 * DAY

export const relativeTimeSince = (iso, now = Date.now()) => {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const seconds = Math.max(0, Math.floor((now - then) / 1000))
  if (seconds < 45) return 'just now'
  if (seconds < 90) return '1 min ago'
  if (seconds < HOUR) return `${Math.round(seconds / MINUTE)} min ago`
  if (seconds < 90 * MINUTE) return '1 hr ago'
  if (seconds < DAY) return `${Math.round(seconds / HOUR)} hr ago`
  if (seconds < 2 * DAY) return 'yesterday'
  if (seconds < WEEK) return `${Math.round(seconds / DAY)} days ago`
  if (seconds < 2 * WEEK) return '1 week ago'
  if (seconds < MONTH) return `${Math.round(seconds / WEEK)} weeks ago`
  if (seconds < 2 * MONTH) return '1 month ago'
  if (seconds < YEAR) return `${Math.round(seconds / MONTH)} months ago`
  if (seconds < 2 * YEAR) return '1 year ago'
  return `${Math.round(seconds / YEAR)} years ago`
}
