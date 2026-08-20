import type { APIRequestContext, Page } from '@playwright/test'
import type { Session } from '@supabase/supabase-js'

/**
 * Auth-/Seed-Helfer fuer die E2E-Journeys (ADR-0041 Phase 4).
 *
 * Env-Defaults spiegeln `.env.example` + docker-compose.yml: der Browser
 * spricht GoTrue ueber das Gateway auf :9999 (`VITE_SUPABASE_URL`), die API
 * liegt auf :8000. Der Compose-Stack hat `GOTRUE_DISABLE_SIGNUP=false` und
 * `GOTRUE_MAILER_AUTOCONFIRM=true` hart gesetzt — ein `POST /auth/v1/signup`
 * liefert deshalb direkt eine volle Session (kein zweiter Login-Call, kein
 * Service-Role-Key noetig).
 */
const AUTH_URL = process.env.E2E_AUTH_URL ?? 'http://localhost:9999'
const API_URL = process.env.E2E_API_BASE_URL ?? 'http://localhost:8000'

/** Exakter storageKey aus `src/lib/supabase.ts` (sessionStorage-Adapter). */
export const SESSION_STORAGE_KEY = 'who2be.auth.session'

export interface E2EUser {
  email: string
  password: string
  /** Roher supabase-js-Session-Body aus der Signup-Antwort. */
  session: Session
}

/**
 * Legt einen frischen GoTrue-User an. E-Mail ist pro Aufruf eindeutig
 * (fullyParallel-Worker duerfen nicht kollidieren).
 */
export async function createUser(request: APIRequestContext): Promise<E2EUser> {
  // Kein Special-Use-TLD (.test/.example): GoTrue akzeptiert die zwar beim
  // Signup, aber der pydantic-EmailStr-Validator der API (z. B. Invitations)
  // lehnt Special-Use-Domains ab — erster echter CI-Lauf 2026-08-20.
  const email = `e2e-${crypto.randomUUID()}@e2e.who2be.dev`
  const password = `pw-${crypto.randomUUID()}`
  const response = await request.post(`${AUTH_URL}/auth/v1/signup`, {
    data: { email, password },
  })
  if (!response.ok()) {
    throw new Error(`Signup fehlgeschlagen (${response.status()}): ${await response.text()}`)
  }
  const session = (await response.json()) as Session
  if (!session.access_token) {
    throw new Error(
      'Signup lieferte keine Session — GOTRUE_MAILER_AUTOCONFIRM im Stack pruefen.',
    )
  }
  return { email, password, session }
}

/**
 * Injiziert die Session VOR der ersten Navigation der Page: supabase-js liest
 * beim Bootstrap `sessionStorage[SESSION_STORAGE_KEY]` und uebernimmt den
 * rohen Session-JSON (kein Wrapper-Objekt — verifiziert gegen
 * `@supabase/auth-js`). Gilt fuer alle folgenden `page.goto(...)`.
 */
export async function loginAs(page: Page, user: E2EUser): Promise<void> {
  await page.addInitScript(
    ([key, json]) => {
      window.sessionStorage.setItem(key, json)
    },
    [SESSION_STORAGE_KEY, JSON.stringify(user.session)] as const,
  )
}

/**
 * `GET /v1/me` mit dem User-JWT: der erste Aufruf seedet lazy Personal-Org +
 * Workspace (User = admin, ON CONFLICT ⇒ idempotent) und liefert
 * `default_workspace_id`.
 */
export async function seedWorkspace(
  request: APIRequestContext,
  user: E2EUser,
): Promise<{ workspaceId: string }> {
  const me = await apiRequest<{ default_workspace_id: string }>(
    request,
    user.session.access_token,
    '/v1/me',
  )
  return { workspaceId: me.default_workspace_id }
}

/**
 * Kleiner authentifizierter Request-Helfer (Bearer-Header, JSON), analog
 * `src/api/client.ts::request` — wirft bei nicht-2xx mit Status + Body.
 */
export async function apiRequest<T>(
  request: APIRequestContext,
  token: string,
  path: string,
  init?: { method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'; data?: unknown },
): Promise<T> {
  const response = await request.fetch(`${API_URL}${path}`, {
    method: init?.method ?? 'GET',
    headers: { Authorization: `Bearer ${token}` },
    data: init?.data,
  })
  if (!response.ok()) {
    throw new Error(
      `${init?.method ?? 'GET'} ${path} → ${response.status()}: ${await response.text()}`,
    )
  }
  const body = await response.text()
  return (body === '' ? undefined : JSON.parse(body)) as T
}
