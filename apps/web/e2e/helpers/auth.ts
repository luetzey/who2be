import { createHmac } from 'node:crypto'

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
  // Admin-Aktionen (Promote, Invitations, Tokens) verlangen aal2
  // (`core/security.require_aal2`, docs/mfa-admin.md) — eine frische
  // Signup-Session ist aal1. Der Helper geht den ECHTEN Weg: TOTP-Faktor
  // einschreiben + Challenge verifizieren, GoTrue liefert die aal2-Session.
  const aal2Session = await enrollTotpAal2(request, session)
  return { email, password, session: aal2Session }
}

/** RFC-4648-Base32-Decode (GoTrue-TOTP-Secret, ohne Padding). */
function base32Decode(input: string): Buffer {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  let bits = 0
  let value = 0
  const out: number[] = []
  for (const char of input.replace(/=+$/, '').toUpperCase()) {
    const idx = alphabet.indexOf(char)
    if (idx === -1) throw new Error(`Ungueltiges Base32-Zeichen: ${char}`)
    value = (value << 5) | idx
    bits += 5
    if (bits >= 8) {
      out.push((value >>> (bits - 8)) & 0xff)
      bits -= 8
    }
  }
  return Buffer.from(out)
}

/** RFC-6238-TOTP (SHA-1, 30-s-Fenster, 6 Stellen) — dependency-frei. */
export function totpCode(secret: string, atMs: number = Date.now()): string {
  const counter = Math.floor(atMs / 1000 / 30)
  const msg = Buffer.alloc(8)
  msg.writeBigUInt64BE(BigInt(counter))
  const digest = createHmac('sha1', base32Decode(secret)).update(msg).digest()
  const offset = digest[digest.length - 1] & 0x0f
  const code =
    ((digest[offset] & 0x7f) << 24) |
    (digest[offset + 1] << 16) |
    (digest[offset + 2] << 8) |
    digest[offset + 3]
  return String(code % 1_000_000).padStart(6, '0')
}

/**
 * TOTP-Faktor einschreiben und verifizieren: enroll -> challenge -> verify.
 * GoTrue antwortet auf den Verify mit einer frischen Session (`aal=aal2`).
 */
async function enrollTotpAal2(request: APIRequestContext, session: Session): Promise<Session> {
  const headers = { Authorization: `Bearer ${session.access_token}` }
  const enroll = await request.post(`${AUTH_URL}/auth/v1/factors`, {
    headers,
    data: { factor_type: 'totp', friendly_name: 'e2e-totp' },
  })
  if (!enroll.ok()) {
    throw new Error(`TOTP-Enroll fehlgeschlagen (${enroll.status()}): ${await enroll.text()}`)
  }
  const factor = (await enroll.json()) as { id: string; totp: { secret: string } }
  const challenge = await request.post(`${AUTH_URL}/auth/v1/factors/${factor.id}/challenge`, {
    headers,
  })
  if (!challenge.ok()) {
    throw new Error(
      `TOTP-Challenge fehlgeschlagen (${challenge.status()}): ${await challenge.text()}`,
    )
  }
  const { id: challengeId } = (await challenge.json()) as { id: string }
  const verify = await request.post(`${AUTH_URL}/auth/v1/factors/${factor.id}/verify`, {
    headers,
    data: { challenge_id: challengeId, code: totpCode(factor.totp.secret) },
  })
  if (!verify.ok()) {
    throw new Error(`TOTP-Verify fehlgeschlagen (${verify.status()}): ${await verify.text()}`)
  }
  return (await verify.json()) as Session
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
