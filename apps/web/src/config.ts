// Zentrale Konfiguration der Web-App.
//
// Drei Quellen, in dieser Reihenfolge ausgewertet:
//
//   1. **Runtime** — `window.__WHO2BE_CONFIG__`, gesetzt von `/config.js`.
//      Im Container schreibt der nginx-Entrypoint diese Datei aus Env-Variablen
//      (`WHO2BE_API_BASE_URL` & Co.). Damit ist EIN Image fuer alle Umgebungen
//      gueltig — Deployments mit getrennten Subdomains (Caddy: `app.` / `api.` /
//      `mcp.`) setzen die Werte explizit.
//   2. **Build-Zeit** — `import.meta.env.VITE_*`. Bleibt fuer `npm run dev` und
//      die Tests der Weg; aeltere Images, die die Werte eingebacken haben,
//      funktionieren unveraendert weiter.
//   3. **Same-Origin** — im Production-Build der Default: API und Auth liegen
//      hinter demselben Origin, von dem die App geladen wurde (der nginx des
//      Web-Containers proxied `/v1/` und `/auth/v1/`, siehe `nginx.conf`).
//      Deshalb funktioniert `http://localhost:5173` und `http://<lan-ip>:5173`
//      ohne Konfiguration und ohne Rebuild — der frueher hier stehende harte
//      PROD-Fehler bei fehlender Env entfaellt: „derselbe Origin" kann nicht
//      die falsche Instanz sein.

interface Config {
  apiBaseUrl: string
  // Streamable-HTTP-Endpoint des MCP-Servers (ADR-0034). Optional via
  // VITE_MCP_URL / Runtime gesetzt; sonst aus der API-URL abgeleitet
  // (`api.` → `mcp.`).
  mcpUrl: string
  supabaseUrl: string
  supabaseAnonKey: string
  // Versteckt die Self-Service-Registrierung in der UI (Login-Link + die
  // `/signup`-Route). Spiegelt das Backend-`GOTRUE_DISABLE_SIGNUP`: GoTrue setzt
  // die echte Durchsetzung (signUp → 422), dieses Flag entfernt nur die
  // dann tote Signup-UI. Beide werden im Deploy gemeinsam gesetzt.
  signupDisabled: boolean
}

/** Von `/config.js` gesetzte Runtime-Werte. Leerstring = „nicht gesetzt". */
export interface RuntimeConfig {
  apiBaseUrl?: string
  mcpUrl?: string
  supabaseUrl?: string
  supabaseAnonKey?: string
  signupDisabled?: boolean
}

declare global {
  interface Window {
    __WHO2BE_CONFIG__?: RuntimeConfig
  }
}

function runtime(): RuntimeConfig {
  if (typeof window === 'undefined') return {}
  return window.__WHO2BE_CONFIG__ ?? {}
}

/** Origin, von dem die App geladen wurde — leer ausserhalb des Browsers. */
function sameOrigin(): string {
  if (typeof window === 'undefined') return ''
  return window.location?.origin ?? ''
}

/**
 * Runtime → Vite-Env → (Dev: Fallback | Prod: Same-Origin) → Fallback.
 *
 * `devFallback` gewinnt im Dev-Server bewusst vor Same-Origin: dort liefert
 * Vite auf :5173 aus, die API laeuft daneben auf :8000 — es gibt keinen Proxy.
 */
function read(name: string, runtimeValue: string | undefined, devFallback: string): string {
  if (runtimeValue !== undefined && runtimeValue !== '') {
    return runtimeValue
  }
  const fromEnv = import.meta.env[name] as string | undefined
  if (fromEnv !== undefined && fromEnv !== '') {
    return fromEnv
  }
  if (import.meta.env.PROD) {
    const origin = sameOrigin()
    if (origin !== '') {
      return origin
    }
  }
  return devFallback
}

// MCP-URL aus der API-Basis ableiten: Standard-Deploy nutzt die Subdomains
// `api.<domain>` / `mcp.<domain>` (Caddy, ADR-0034). Fehlt das `api.`-Präfix,
// wird `/mcp` an den Origin angehängt (Dev-/Same-Origin-Fallback).
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

/** Baut die Konfiguration aus den drei Quellen. Exportiert fuer die Tests. */
export function resolveConfig(): Config {
  const rt = runtime()
  const apiBaseUrl = read('VITE_API_BASE_URL', rt.apiBaseUrl, 'http://localhost:8000')
  const mcpUrlOverride = rt.mcpUrl ?? (import.meta.env.VITE_MCP_URL as string | undefined) ?? ''
  return {
    apiBaseUrl,
    mcpUrl: mcpUrlOverride !== '' ? mcpUrlOverride : deriveMcpUrl(apiBaseUrl),
    supabaseUrl: read('VITE_SUPABASE_URL', rt.supabaseUrl, 'http://localhost:54321'),
    // Self-hosted GoTrue validiert den Anon-Key nicht — er darf fuer
    // supabase-js nur nicht leer sein. Ein Supabase-Cloud-Deployment setzt
    // ihn ueber Runtime-Env bzw. Build-Arg.
    supabaseAnonKey:
      rt.supabaseAnonKey !== undefined && rt.supabaseAnonKey !== ''
        ? rt.supabaseAnonKey
        : ((import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) ?? '') ||
          'who2be-local-anon-key',
    signupDisabled:
      rt.signupDisabled ??
      (import.meta.env.VITE_WHO2BE_SIGNUP_DISABLED as string | undefined) === 'true',
  }
}

export const config: Config = resolveConfig()
