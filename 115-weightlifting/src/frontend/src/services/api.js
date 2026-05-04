import axios from 'axios'
import {
  clearAuth,
  clearRefreshToken,
  getToken,
  setCurrentUser,
  setToken,
} from '../utils/auth'

// Empty baseURL means requests go to the current origin, which in dev is the
// Vite proxy (see vite.config.js) and in prod is wherever the app is served.
// This lets the httpOnly refresh cookie flow without SameSite=None hacks.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? ''

export const getApiBase = () => API_BASE

export const getAuthHeaders = () => {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const apiClient = axios.create({ baseURL: API_BASE, withCredentials: true })

apiClient.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let refreshInFlight = null

const refreshAccessToken = async () => {
  if (refreshInFlight) return refreshInFlight

  refreshInFlight = axios
    .post(`${API_BASE}/api/auth/token/refresh/`, {}, { withCredentials: true })
    .then(({ data }) => {
      setToken(data.access)
      return data.access
    })
    .finally(() => {
      refreshInFlight = null
    })

  return refreshInFlight
}

const handleAuthFailure = () => {
  clearAuth()
  if (typeof window !== 'undefined' && window.location && window.location.pathname !== '/login') {
    window.location.assign('/login')
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const status = error.response?.status

    if (status !== 401 || !original || original._retry) {
      if (status === 401) handleAuthFailure()
      return Promise.reject(error)
    }

    const url = original.url || ''
    if (url.includes('/api/auth/token/') || url.includes('/api/auth/register/')) {
      return Promise.reject(error)
    }

    original._retry = true
    try {
      const newAccess = await refreshAccessToken()
      original.headers = original.headers || {}
      original.headers.Authorization = `Bearer ${newAccess}`
      return apiClient(original)
    } catch (refreshError) {
      handleAuthFailure()
      return Promise.reject(refreshError)
    }
  }
)

export const getCurrentUserFromApi = async () => {
  const { data } = await apiClient.get('/api/auth/me/')
  return data
}

export const login = async (username, password) => {
  clearRefreshToken()
  const { data } = await axios.post(
    `${API_BASE}/api/auth/token/`,
    { username, password },
    { withCredentials: true }
  )
  setToken(data.access)

  try {
    const currentUser = await getCurrentUserFromApi()
    setCurrentUser(currentUser)
    return { ...data, user: currentUser }
  } catch (error) {
    // Only tear down auth on hard 401/403; transient server errors (5xx,
    // network flakes) should leave the freshly-acquired tokens in place so
    // the user can retry without re-entering their password.
    const status = error?.response?.status
    if (status === 401 || status === 403) {
      clearAuth()
    }
    throw error
  }
}

export const register = async (username, password, user_type, extraFields = {}) => {
  await axios.post(
    `${API_BASE}/api/auth/register/`,
    { username, password, user_type, ...extraFields },
    { withCredentials: true }
  )
}

export const refreshCurrentUser = async () => {
  const currentUser = await getCurrentUserFromApi()
  setCurrentUser(currentUser)
  return currentUser
}

/** Athletes only: persists bodyweight + gender; response includes competitive_weight_class. */
export const patchCurrentUserProfile = async (payload) => {
  const { data } = await apiClient.patch('/api/auth/me/', payload)
  setCurrentUser(data)
  return data
}

export const logout = async () => {
  try {
    await axios.post(
      `${API_BASE}/api/auth/logout/`,
      {},
      { headers: getAuthHeaders(), withCredentials: true }
    )
  } catch (_error) {
    /* ignore: local clear still happens below */
  }
  clearAuth()
}

export const getProgramsFromBackend = async () => {
  const { data } = await apiClient.get('/api/programs/')
  return data
}

export const createProgram = async (payload) => {
  const { data } = await apiClient.post('/api/programs/', payload)
  return data
}

export const updateProgram = async (programId, payload) => {
  const { data } = await apiClient.patch(`/api/programs/${programId}/`, payload)
  return data
}

export const assignProgram = async (programId, athleteId) => {
  const { data } = await apiClient.patch(
    `/api/programs/${programId}/assign/`,
    { athlete_id: athleteId }
  )
  return data
}

export const getHeadOrgSummary = async () => {
  const { data } = await apiClient.get('/api/auth/head/org-summary/')
  return data
}

export const getHeadOrgRoster = async () => {
  const { data } = await apiClient.get('/api/auth/head/roster/')
  return data
}

export const postHeadStaffInvite = async (username) => {
  const { data } = await apiClient.post('/api/auth/head/staff/', { username })
  return data
}

export const patchHeadStaffLink = async (userId, linked) => {
  const { data } = await apiClient.patch(`/api/auth/head/staff/${userId}/`, { linked })
  return data
}

export const patchHeadAthletePrimaryCoach = async (athleteId, primaryCoachId) => {
  const { data } = await apiClient.patch(`/api/auth/head/athletes/${athleteId}/`, {
    primary_coach_id: primaryCoachId,
  })
  return data
}

export const getAthletes = async ({ scope = 'mine', q = '', page = 1 } = {}) => {
  const { data } = await apiClient.get('/api/auth/athletes/', {
    params: { scope, q, page },
  })
  if (Array.isArray(data)) {
    return { results: data, count: data.length, page: 1, page_size: data.length, scope }
  }
  return {
    results: data.results || [],
    count: data.count ?? 0,
    page: data.page ?? page,
    page_size: data.page_size ?? (data.results || []).length,
    scope: data.scope ?? scope,
  }
}

export const getProgramCompletion = async (programId) => {
  const { data } = await apiClient.get(`/api/athletes/program-completion/${programId}/`)
  return data
}

export const updateProgramCompletion = async (programId, completion_data) => {
  const { data } = await apiClient.patch(
    `/api/athletes/program-completion/${programId}/`,
    { completion_data }
  )
  return data
}

export const createWorkoutLog = async (payload) => {
  const { data } = await apiClient.post('/api/athletes/workouts/', payload)
  return data
}

export const getWorkoutLogs = async (athleteId = null) => {
  const params = athleteId ? { athlete_id: athleteId } : undefined
  const { data } = await apiClient.get('/api/athletes/workouts/', { params })
  return data
}

export const createPersonalRecord = async (payload) => {
  const { data } = await apiClient.post('/api/athletes/prs/', payload)
  return data
}

export const getPersonalRecords = async (athleteId = null) => {
  const params = athleteId ? { athlete_id: athleteId } : undefined
  const { data } = await apiClient.get('/api/athletes/prs/', { params })
  return data
}

export const calculateSinclair = async (payload) => {
  const { data } = await apiClient.post('/api/analytics/sinclair/', payload)
  return data
}

export const calculateRobi = async (payload) => {
  const { data } = await apiClient.post('/api/analytics/robi/', payload)
  return data
}

export const getHeadProgramStyleOutcomes = async () => {
  const { data } = await apiClient.get('/api/analytics/head/program-style-outcomes/')
  return data
}

export const getHeadProgramNameOutcomes = async () => {
  const { data } = await apiClient.get('/api/analytics/head/program-name-outcomes/')
  return data
}

export const getHeadRecommendations = async () => {
  const { data } = await apiClient.get('/api/analytics/head/recommendations/')
  return data
}

export const getHeadModelStatus = async () => {
  const { data } = await apiClient.get('/api/analytics/head/model-status/')
  return data
}
