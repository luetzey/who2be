import { describe, expect, it } from 'vitest'

import de from './locales/de.json'
import en from './locales/en.json'

// Paritaets-Gate fuer `common.errors` (Issue #493).
//
// Unter `common.errors` IST der Schluessel der Wire-Wert des `reason` aus der
// API-Antwort (ADR-0051) — anders als in allen anderen Namespaces, wo ein Key
// nur ein Label adressiert. `translateServerError` in `src/api/client.ts`
// uebersetzt `common:errors.<reason>` mit `defaultValue: detail`; fehlt der
// englische Schluessel, faellt die Uebersetzung still auf den DEUTSCHEN
// Servertext zurueck. Ein Loch erzeugt hier also die falsche Sprache statt
// eines sichtbaren rohen Keys — und faellt ohne dieses Gate niemandem auf.
//
// Sechs Wellen von #402 haben genau diese Bedingung von Hand nachgezaehlt
// (12 → 56 Schluessel). Ab hier zaehlt der Test.
//
// Bewusst NICHT geprueft: andere Namespaces (dort ist der Key kein Wire-Wert),
// die Uebersetzungsqualitaet, ob ein Schluessel ueberhaupt benutzt wird, und
// die Vollstaendigkeit gegenueber `ProblemReason` — Gate-Gruende tragen
// absichtlich keinen Locale-Key, damit ihre spezifischen `detail`-Meldungen
// erhalten bleiben (DECISIONS 2026-09-07). Das Python-Pendant, das die
// Titel-Tabelle haelt, ist `apps/api/tests/test_error_taxonomy.py`.
// Die Billing-Strings liegen laut ADR-0029 bewusst in
// `src/features/billing/i18n.ts` und gehoeren nicht hierher.

const deErrorKeys = Object.keys(de.common.errors)
const enErrorKeys = Object.keys(en.common.errors)

/** Schluessel aus `from`, die in `to` fehlen — sortiert, damit die Meldung stabil ist. */
function missingFrom(from: readonly string[], to: readonly string[]): string[] {
  const present = new Set(to)
  return from.filter((key) => !present.has(key)).sort()
}

describe('common.errors — Locale-Paritaet de/en', () => {
  it('en.json traegt jeden Fehlergrund aus de.json', () => {
    const missing = missingFrom(deErrorKeys, enErrorKeys)

    expect(
      missing,
      `common.errors: ${missing.length} Schluessel fehlen in en.json — ${missing.join(', ')}. ` +
        'Englische Oberflaechen bekommen fuer diese Gruende still den deutschen Servertext.',
    ).toEqual([])
  })

  it('de.json traegt jeden Fehlergrund aus en.json', () => {
    const missing = missingFrom(enErrorKeys, deErrorKeys)

    expect(
      missing,
      `common.errors: ${missing.length} Schluessel fehlen in de.json — ${missing.join(', ')}. ` +
        'de ist Default und Fallback (siehe src/i18n/index.ts) — ein Loch hier trifft jede Sprache.',
    ).toEqual([])
  })
})
