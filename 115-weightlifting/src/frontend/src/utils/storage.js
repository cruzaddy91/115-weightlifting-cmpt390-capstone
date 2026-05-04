// Storage adapter for program data
// Supports localStorage (browser-only) and Supabase (cross-device)

const STORAGE_KEY = 'weightlifting_program_data'

// Check if Supabase is configured
const useSupabase = () => {
  return import.meta.env.VITE_SUPABASE_URL && import.meta.env.VITE_SUPABASE_ANON_KEY
}

// LocalStorage implementation
export const localStorageAdapter = {
  get: () => {
    try {
      const data = localStorage.getItem(STORAGE_KEY)
      return data ? JSON.parse(data) : null
    } catch (error) {
      console.error('Error reading from localStorage:', error)
      return null
    }
  },

  set: (data) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
      return true
    } catch (error) {
      console.error('Error saving to localStorage:', error)
      return false
    }
  }
}

// For now, we'll use localStorage
// To enable cross-device persistence, set up Supabase and configure environment variables
export const getStorage = () => {
  if (useSupabase()) {
    // Supabase implementation would go here
    // For now, fall back to localStorage
    return localStorageAdapter
  }
  return localStorageAdapter
}

