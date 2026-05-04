const formatFieldErrors = (data) => {
  if (!data || typeof data !== 'object') return null
  if (data.detail) return String(data.detail)

  const parts = []
  for (const [field, value] of Object.entries(data)) {
    if (Array.isArray(value)) {
      parts.push(`${field}: ${value.join(', ')}`)
    } else if (typeof value === 'string') {
      parts.push(`${field}: ${value}`)
    }
  }
  return parts.length > 0 ? parts.join(' | ') : null
}

export const formatApiError = (err, fallback = 'Request failed.') => {
  if (!err) return fallback
  const status = err.response?.status
  // 429 carries a DRF throttle message in err.response.data.detail; surface
  // it prominently so users don't think the button is broken when it's
  // actually the server telling them to slow down.
  if (status === 429) {
    const retryAfter = err.response?.headers?.['retry-after']
    const detail = err.response?.data?.detail
    if (retryAfter) return `Too many requests — try again in ${retryAfter}s.`
    if (detail) return String(detail)
    return 'Too many requests — please wait a minute and try again.'
  }
  const data = err.response?.data
  if (typeof data === 'string' && data) return data
  const fromData = formatFieldErrors(data)
  if (fromData) return fromData
  return err.message || fallback
}
