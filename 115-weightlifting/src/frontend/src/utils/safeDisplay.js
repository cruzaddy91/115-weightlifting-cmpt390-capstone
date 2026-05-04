/**
 * Coach-supplied program titles are plain text, but legacy or hostile values
 * can still carry angle-bracket markup. Strip tag-shaped runs and stray brackets
 * so chips and headings never read like HTML-injection probes.
 */
export function programTitleForDisplay(raw) {
  if (raw == null) return ''
  const trimmed = String(raw).trim()
  if (!trimmed) return ''
  // Names are plain text at the API; strip every bracket so nothing reads as markup.
  let s = trimmed.replace(/</g, '').replace(/>/g, '')
  s = s.replace(/\s+/g, ' ').trim()
  return s
}
