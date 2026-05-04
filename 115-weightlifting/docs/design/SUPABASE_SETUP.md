# Supabase Setup for Cross-Device Persistence

This guide will help you set up Supabase to enable data persistence across different devices and browsers.

## Step 1: Create Supabase Account and Project

1. Go to https://supabase.com
2. Sign up for a free account
3. Create a new project
4. Wait for the project to finish setting up (takes a few minutes)

## Step 2: Create Database Table

1. In your Supabase dashboard, go to "Table Editor"
2. Click "New Table"
3. Name it `programs`
4. Add the following columns:
   - `id` (uuid, primary key, default: `gen_random_uuid()`)
   - `data` (jsonb, not null)
   - `created_at` (timestamp, default: `now()`)
   - `updated_at` (timestamp, default: `now()`)
5. Click "Save"

## Step 3: Enable Row Level Security (RLS)

1. Go to "Authentication" > "Policies"
2. For the `programs` table, create a new policy:
   - Policy name: "Allow public read and write"
   - Allowed operation: ALL
   - Policy definition: `true` (this allows anyone to read/write - fine for MVP)
   - Click "Save"

## Step 4: Get Your Credentials

1. Go to "Settings" > "API"
2. Copy your:
   - Project URL (under "Project URL")
   - Anon/Public key (under "Project API keys" > "anon" > "public")

## Step 5: Install Supabase Client

```bash
cd frontend
npm install @supabase/supabase-js
```

## Step 6: Configure Environment Variables

1. Create a `.env` file in the `frontend` directory:
   ```
   VITE_SUPABASE_URL=your_project_url_here
   VITE_SUPABASE_ANON_KEY=your_anon_key_here
   ```

2. Add `.env` to `.gitignore` (don't commit your keys!)

## Step 7: Update Storage Adapter

The storage adapter in `frontend/src/utils/storage.js` needs to be updated to use Supabase. Here's the implementation:

```javascript
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

let supabase = null
if (supabaseUrl && supabaseAnonKey) {
  supabase = createClient(supabaseUrl, supabaseAnonKey)
}

// Use a single row with id = 'current' for simplicity
const PROGRAM_ID = 'current'

export const supabaseAdapter = {
  get: async () => {
    if (!supabase) return null
    
    try {
      const { data, error } = await supabase
        .from('programs')
        .select('data')
        .eq('id', PROGRAM_ID)
        .single()
      
      if (error) {
        if (error.code === 'PGRST116') {
          // No row found
          return null
        }
        throw error
      }
      
      return data?.data || null
    } catch (error) {
      console.error('Error reading from Supabase:', error)
      return null
    }
  },

  set: async (data) => {
    if (!supabase) return false
    
    try {
      const { error } = await supabase
        .from('programs')
        .upsert({
          id: PROGRAM_ID,
          data: data,
          updated_at: new Date().toISOString()
        }, {
          onConflict: 'id'
        })
      
      if (error) throw error
      return true
    } catch (error) {
      console.error('Error saving to Supabase:', error)
      return false
    }
  }
}
```

Then update the `getStorage` function to use Supabase when available:

```javascript
export const getStorage = () => {
  if (useSupabase() && supabase) {
    return supabaseAdapter
  }
  return localStorageAdapter
}
```

## Step 8: Update API Service

Update `frontend/src/services/api.js` to use async storage methods:

```javascript
// Get current week's program
export const getWeekProgram = async () => {
  try {
    const storage = getStorage()
    const data = await storage.get()
    return data
  } catch (error) {
    console.error('Error loading program:', error)
    return null
  }
}

// Save week's program
export const saveWeekProgram = async (programData) => {
  try {
    const storage = getStorage()
    const success = await storage.set(programData)
    if (success) {
      return { success: true, data: programData }
    }
    throw new Error('Failed to save program')
  } catch (error) {
    console.error('Error saving program:', error)
    throw error
  }
}
```

## Testing

1. Start your dev server: `npm run dev`
2. Create a program as the coach
3. Open the app in a different browser/device
4. You should see the same program as the athlete

## Notes

- The free tier of Supabase is generous and should be sufficient for this MVP
- Data is stored in a single row (id = 'current') for simplicity
- For production, you'd want proper authentication and multiple program support
- The current implementation allows public read/write - fine for MVP but not for production

