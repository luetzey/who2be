import { createClient } from '@supabase/supabase-js'

import { config } from '../config'

// persistSession: false -> die Session lebt nur im Speicher, nichts landet
// im localStorage (react-conventions: Auth-Token nicht im localStorage).
export const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey, {
  auth: {
    persistSession: false,
    autoRefreshToken: false,
  },
})
