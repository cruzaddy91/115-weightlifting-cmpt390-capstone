// Block presets match the official Excel template tab names (4 / 8 / 16 Week).
// Coaches pick a preset to set the program end date; "Custom" is any other span.

export const BLOCK_PRESETS = [
  { key: '4wk',  label: '4 Week',  weeks: 4 },
  { key: '8wk',  label: '8 Week',  weeks: 8 },
  { key: '16wk', label: '16 Week', weeks: 16 },
]

export const endDateForBlock = (startDateISO, weeks) => {
  if (!startDateISO || !Number.isFinite(weeks) || weeks <= 0) return ''
  const start = new Date(`${startDateISO}T00:00:00`)
  if (Number.isNaN(start.getTime())) return ''
  // Block of N weeks runs from Monday week 1 to Sunday week N, so we add
  // N*7 - 1 days from the start date.
  const end = new Date(start)
  end.setDate(end.getDate() + weeks * 7 - 1)
  return end.toISOString().split('T')[0]
}

export const inferBlockKey = (startDateISO, endDateISO) => {
  if (!startDateISO || !endDateISO) return 'custom'
  const start = new Date(`${startDateISO}T00:00:00`)
  const end = new Date(`${endDateISO}T00:00:00`)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 'custom'
  const diffDays = Math.round((end - start) / (1000 * 60 * 60 * 24)) + 1
  const match = BLOCK_PRESETS.find((b) => b.weeks * 7 === diffDays)
  return match ? match.key : 'custom'
}
