/**
 * Trigger werden im Backend als ein einzelner String persistiert
 * (`triggers: string | null`). Im UI fuehren wir sie als Pill-Liste —
 * deshalb wandeln wir an der Hook-Grenze zwischen String und Array um.
 *
 * Parser ist tolerant gegen die alte Eingabeform mit Anfuehrungszeichen
 * ("passwort vergessen", "reset link") und gegen ';' als Legacy-Separator
 * (WP-D1 — sonst rendert so ein Bestand als eine Riesen-Pill). Leere Pills
 * werden geschluckt. Kanonisch (joinTriggers, Backend-Normalisierung) ist
 * und bleibt kommagetrennt.
 */
export function splitTriggers(raw: string | null): string[] {
  if (raw === null) {
    return []
  }
  const trimmed = raw.trim()
  if (trimmed === '') {
    return []
  }
  return trimmed
    .split(/[,;]/)
    .map((entry) => entry.trim().replace(/^["']+|["']+$/g, '').trim())
    .filter((entry) => entry.length > 0)
}

export function joinTriggers(triggers: string[]): string | null {
  const cleaned = triggers.map((entry) => entry.trim()).filter((entry) => entry.length > 0)
  if (cleaned.length === 0) {
    return null
  }
  return cleaned.join(', ')
}
