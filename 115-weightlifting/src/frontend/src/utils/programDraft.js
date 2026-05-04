// Lightweight draft persistence for the coach program editor.
// One localStorage key per program id (or 'new' for unsaved drafts) so editing
// program A and bouncing to program B does not corrupt either draft.

const DRAFT_PREFIX = 'wl_program_draft_'
const MAX_DRAFT_AGE_MS = 1000 * 60 * 60 * 24 * 14 // 14 days

const keyFor = (programId) => `${DRAFT_PREFIX}${programId ?? 'new'}`

export const saveDraft = (programId, draft) => {
  if (typeof window === 'undefined' || !window.localStorage) return
  try {
    const payload = { savedAt: Date.now(), draft }
    window.localStorage.setItem(keyFor(programId), JSON.stringify(payload))
  } catch (_error) {
    /* storage full / privacy mode -- fail silently */
  }
}

export const readDraft = (programId) => {
  if (typeof window === 'undefined' || !window.localStorage) return null
  try {
    const raw = window.localStorage.getItem(keyFor(programId))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    if (typeof parsed.savedAt === 'number' && Date.now() - parsed.savedAt > MAX_DRAFT_AGE_MS) {
      window.localStorage.removeItem(keyFor(programId))
      return null
    }
    return parsed
  } catch (_error) {
    return null
  }
}

export const clearDraft = (programId) => {
  if (typeof window === 'undefined' || !window.localStorage) return
  try {
    window.localStorage.removeItem(keyFor(programId))
  } catch (_error) {
    /* ignore */
  }
}

// For testing / manual reset.
export const clearAllDrafts = () => {
  if (typeof window === 'undefined' || !window.localStorage) return
  try {
    const toRemove = []
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i)
      if (key && key.startsWith(DRAFT_PREFIX)) toRemove.push(key)
    }
    toRemove.forEach((k) => window.localStorage.removeItem(k))
  } catch (_error) {
    /* ignore */
  }
}
