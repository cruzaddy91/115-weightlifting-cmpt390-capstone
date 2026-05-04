/**
 * Build a short suffix for kicker lines: " · 71 kg · 64.0 kg BW"
 * Accepts program objects (athlete_* fields) or /me / athletes list rows.
 */
export function athleteProfileSuffix(profile) {
  if (!profile || typeof profile !== 'object') return ''
  const cls =
    profile.competitive_weight_class
    ?? profile.athlete_competitive_weight_class
    ?? null
  const bwRaw = profile.bodyweight_kg ?? profile.athlete_bodyweight_kg ?? null
  const parts = []
  if (cls) parts.push(cls)
  if (bwRaw != null && bwRaw !== '') {
    const n = Number(bwRaw)
    if (!Number.isNaN(n)) parts.push(`${n} kg BW`)
  }
  if (!parts.length) return ''
  return ` · ${parts.join(' · ')}`
}
