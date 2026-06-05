import { ApiError } from '@/api/client'
import type { DeleteBlocker, DeleteBlockedBody } from '@/api/types'

// Feldnamen variieren je Referenz-Quelle (Persona-Block hat `agent_name`,
// Playbook-Block `persona_name`, Composites `name` …). Erste Treffer gewinnt.
const NAME_KEYS = ['name', 'agent_name', 'persona_name', 'playbook_name', 'resource_name'] as const
const ID_KEYS = ['id', 'agent_id', 'persona_id', 'playbook_id', 'resource_id'] as const

function pickString(rec: Record<string, unknown>, keys: readonly string[]): string | undefined {
  for (const key of keys) {
    const value = rec[key]
    if (typeof value === 'string' && value.length > 0) {
      return value
    }
  }
  return undefined
}

/**
 * Einzel-Element-Delete (Plan 2026-06-05). Liest die Verwender aus einem
 * 409-Body robust aus. Das Backend liefert `HTTPException.detail` als
 * `DeleteBlocked`: `{ message, blocked_by: { <quelle>: Record[] } }` — eine Map
 * Quelle->Records mit quellspezifischen Feldnamen. Defensiv: akzeptiert die
 * verschachtelte `detail.blocked_by`-Map ebenso wie eine flache Map oder ein
 * Array auf Top-Level und crasht bei Formatabweichungen nicht.
 */
export function extractDeleteBlockers(cause: unknown): DeleteBlocker[] {
  if (!(cause instanceof ApiError) || cause.status !== 409) {
    return []
  }
  const body = cause.body as DeleteBlockedBody | null | undefined
  const detail = typeof body?.detail === 'object' && body.detail !== null ? body.detail : undefined
  const blocked = detail?.blocked_by ?? body?.blocked_by
  if (blocked === null || typeof blocked !== 'object') {
    return []
  }
  // Normalfall: Map Quelle->Records. Abweichende Formate koennen ein flaches
  // Array liefern — dann gibt es keine Quelle.
  const groups: Array<[string | undefined, unknown]> = Array.isArray(blocked)
    ? [[undefined, blocked]]
    : Object.entries(blocked)
  const result: DeleteBlocker[] = []
  for (const [source, records] of groups) {
    if (!Array.isArray(records)) {
      continue
    }
    for (const entry of records) {
      if (entry === null || typeof entry !== 'object') {
        continue
      }
      const rec = entry as Record<string, unknown>
      result.push({
        id: pickString(rec, ID_KEYS),
        name: pickString(rec, NAME_KEYS),
        type: source,
      })
    }
  }
  return result
}

/** Lesbares Label fuer einen Blocker-Eintrag (Name, sonst ID, sonst Typ). */
export function blockerLabel(blocker: DeleteBlocker): string {
  return blocker.name ?? blocker.id ?? blocker.type ?? ''
}
