// Zentrale Konfiguration aus Vite-Env-Variablen.
//
// In Entwicklung/Tests fallen fehlende Werte auf Platzhalter zurueck, damit
// die App ohne gesetzte Env laeuft. In einem Production-Build ist eine
// fehlende Variable dagegen ein harter Fehler — sonst spraeche die UI still
// gegen eine falsche Instanz oder schickte Token an den falschen Host.

interface Config {
  apiBaseUrl: string
  // Streamable-HTTP-Endpoint des MCP-Servers (ADR-0034). Optional via
  // VITE_MCP_URL gesetzt; sonst aus der API-URL abgeleitet (`api.` → `mcp.`).
  mcpUrl: string
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

// MCP-URL aus der API-Basis ableiten: Standard-Deploy nutzt die Subdomains
// `api.<domain>` / `mcp.<domain>` (Caddy, ADR-0034). Fehlt das `api.`-Präfix,
// wird `/mcp` an den Origin angehängt (Dev-Fallback).
function deriveMcpUrl(apiBaseUrl: string): string {
  try {
    const url = new URL(apiBaseUrl)
    url.hostname = url.hostname.replace(/^api\./, 'mcp.')
    url.pathname = '/mcp'
    url.search = ''
    return url.toString().replace(/\/$/, '')
  } catch {
    return `${apiBaseUrl.replace(/\/$/, '')}/mcp`
  }
}

const apiBaseUrl = read('VITE_API_BASE_URL', 'http://localhost:8000')
const mcpUrlOverride = (import.meta.env.VITE_MCP_URL as string | undefined) ?? ''

export const config: Config = {
  apiBaseUrl,
  mcpUrl: mcpUrlOverride !== '' ? mcpUrlOverride : deriveMcpUrl(apiBaseUrl),
  supabaseUrl: read('VITE_SUPABASE_URL', 'http://localhost:54321'),
  supabaseAnonKey: read('VITE_SUPABASE_ANON_KEY', 'anon-key-placeholder'),
}
