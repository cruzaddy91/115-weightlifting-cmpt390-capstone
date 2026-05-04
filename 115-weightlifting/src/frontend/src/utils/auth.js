const AUTH_TOKEN_KEY = 'weightlifting_auth_token'
const AUTH_REFRESH_KEY = 'weightlifting_refresh_token' // legacy; cleared on load
const AUTH_USER_KEY = 'weightlifting_current_user'

export const getToken = () => localStorage.getItem(AUTH_TOKEN_KEY)
export const setToken = (token) => localStorage.setItem(AUTH_TOKEN_KEY, token)
export const clearToken = () => localStorage.removeItem(AUTH_TOKEN_KEY)

// Refresh tokens now live in an httpOnly cookie (wl_refresh) set by the
// backend on /api/auth/token/ and /api/auth/token/refresh/. They intentionally
// cannot be read from JavaScript, which eliminates the XSS exfil risk of
// localStorage-stored refresh tokens. The helpers below are kept as no-ops /
// legacy-cleaners so older clients still prune stale values.
export const getRefreshToken = () => null
export const setRefreshToken = () => {}
export const clearRefreshToken = () => localStorage.removeItem(AUTH_REFRESH_KEY)

export const getCurrentUser = () => {
  const rawUser = localStorage.getItem(AUTH_USER_KEY)
  if (!rawUser) return null

  try {
    return JSON.parse(rawUser)
  } catch (error) {
    console.error('Failed to parse current user from storage:', error)
    localStorage.removeItem(AUTH_USER_KEY)
    return null
  }
}

export const setCurrentUser = (user) => {
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user))
}

export const clearCurrentUser = () => localStorage.removeItem(AUTH_USER_KEY)

export const clearAuth = () => {
  clearToken()
  clearRefreshToken()
  clearCurrentUser()
}

export const isAuthenticated = () => !!getToken() && !!getCurrentUser()
export const getUserType = () => getCurrentUser()?.user_type || null
