// Zentrale Konfiguration aus Vite-Env-Variablen.
//
// In Entwicklung/Tests fallen fehlende Werte auf Platzhalter zurueck, damit
// die App ohne gesetzte Env laeuft. In einem Production-Build ist eine
// fehlende Variable dagegen ein harter Fehler — sonst spraeche die UI still
// gegen eine falsche Instanz oder schickte Token an den falschen Host.

interface Config {
  apiBaseUrl: string
  supabaseUrl: string
  supabaseAnonKey: string
}

function read(name: string, devFallback: string): string {
  const value = import.meta.env[name] as string | undefined
  if (value !== undefined && value !== '') {
    return value
  }
  if (import.meta.env.PROD) {
    throw new Error(`Pflicht-Env ${name} ist im Production-Build nicht gesetzt.`)
  }
  return devFallback
}

export const config: Config = {
  apiBaseUrl: read('VITE_API_BASE_URL', 'http://localhost:8000'),
  supabaseUrl: read('VITE_SUPABASE_URL', 'http://localhost:54321'),
  supabaseAnonKey: read('VITE_SUPABASE_ANON_KEY', 'anon-key-placeholder'),
}
