import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearAllDrafts, clearDraft, readDraft, saveDraft } from '../utils/programDraft'

describe('programDraft', () => {
  beforeEach(() => {
    clearAllDrafts()
    vi.useRealTimers()
  })

  it('saves and reads a draft keyed by program id', () => {
    saveDraft(42, { name: 'Block 1' })
    const stored = readDraft(42)
    expect(stored).toBeTruthy()
    expect(stored.draft).toEqual({ name: 'Block 1' })
    expect(typeof stored.savedAt).toBe('number')
  })

  it("keys 'new' drafts separately from existing-program drafts", () => {
    saveDraft(null, { name: 'Fresh draft' })
    saveDraft(7, { name: 'Edit draft' })
    expect(readDraft(null).draft).toEqual({ name: 'Fresh draft' })
    expect(readDraft(7).draft).toEqual({ name: 'Edit draft' })
  })

  it('returns null for a missing draft', () => {
    expect(readDraft(999)).toBeNull()
  })

  it('clearDraft removes a specific entry without touching others', () => {
    saveDraft(1, { name: 'A' })
    saveDraft(2, { name: 'B' })
    clearDraft(1)
    expect(readDraft(1)).toBeNull()
    expect(readDraft(2).draft).toEqual({ name: 'B' })
  })

  it('evicts drafts older than the max age', () => {
    const realNow = Date.now
    const ancient = realNow() - 1000 * 60 * 60 * 24 * 30 // 30 days ago
    Date.now = () => ancient
    saveDraft(5, { name: 'old' })
    Date.now = realNow
    expect(readDraft(5)).toBeNull()
  })
})
