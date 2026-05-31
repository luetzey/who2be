/**
 * Vertrag: HTTP 409 + Content-Type application/problem+json bei
 * Promote-Validation-Fail (Welle 4, Spec).
 *
 * {
 *   "type": "https://who2be.dev/errors/promote-validation-failed",
 *   "missing": ["description", "body"]
 * }
 *
 * `ApiError.body` enthaelt den geparsten JSON-Body wenn der Client
 * `application/problem+json` oder `application/json` gelesen hat.
 */

import { ApiError } from '@/api/client'

/** Feldnamen-Uebersetzung DE (intern → lesbarer Label). */
const FIELD_LABELS: Record<string, string> = {
  name: 'Name',
  description: 'Beschreibung',
  body: 'Inhalt',
  persona_id: 'Persona',
  system_prompt_template_id: 'System-Prompt-Template',
  type: 'Typ',
  tags: 'Tags',
  triggers: 'Trigger',
}

export function translateField(field: string): string {
  return FIELD_LABELS[field] ?? field
}

/**
 * Versucht, den `missing`-Array aus einem 409 problem+json zu lesen.
 * Gibt `null` zurueck, wenn es kein Promote-Validation-Fail ist.
 */
export function extractMissingFields(cause: unknown): string[] | null {
  if (!(cause instanceof ApiError) || cause.status !== 409) {
    return null
  }
  const body = cause.body
  if (
    body !== null &&
    typeof body === 'object' &&
    'missing' in body &&
    Array.isArray((body as { missing: unknown }).missing)
  ) {
    const missing = (body as { missing: unknown[] }).missing
    const fields = missing.filter((f): f is string => typeof f === 'string')
    if (fields.length > 0) {
      return fields
    }
  }
  return null
}

/**
 * Formatiert die fehlenden Felder als lesbare DE-Liste.
 * Beispiel: ["description", "body"] → "Beschreibung, Inhalt"
 */
export function formatMissingFields(fields: string[]): string {
  return fields.map(translateField).join(', ')
}
