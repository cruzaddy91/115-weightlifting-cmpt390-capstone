import { describe, expect, it } from 'vitest'
import { formatApiError } from '../utils/errors'

describe('formatApiError', () => {
  it('prefers server-supplied detail', () => {
    expect(
      formatApiError({ response: { data: { detail: 'Bad creds' } } })
    ).toBe('Bad creds')
  })

  it('joins DRF field errors', () => {
    expect(
      formatApiError({
        response: { data: { coach_signup_code: ['Invalid coach signup code.'] } },
      })
    ).toContain('coach_signup_code: Invalid coach signup code.')
  })

  it('handles multi-field DRF payloads', () => {
    const out = formatApiError({
      response: { data: { username: ['required'], password: ['too short'] } },
    })
    expect(out).toContain('username: required')
    expect(out).toContain('password: too short')
  })

  it('falls back to err.message when response is missing', () => {
    expect(formatApiError({ message: 'Network Error' })).toBe('Network Error')
  })

  it('uses fallback when no data is available', () => {
    expect(formatApiError({}, 'Oops.')).toBe('Oops.')
    expect(formatApiError(null, 'Oops.')).toBe('Oops.')
  })

  it('returns plain-string error bodies directly', () => {
    expect(
      formatApiError({ response: { data: 'Service Unavailable' } })
    ).toBe('Service Unavailable')
  })
})
