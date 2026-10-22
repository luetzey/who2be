import { describe, expect, it } from 'vitest'

import de from './locales/de.json'

// Guard gegen Ersatzumlaute in sichtbaren deutschen UI-Texten.
//
// Owner-Regel: die Oberflaeche schreibt echte Umlaute und ß
// (docs/frontend/design-language.md §Microcopy). Ersatzschreibungen wie
// „Zurueck“ oder „abschliessen“ rutschen trotzdem immer wieder durch, weil
// Code-Kommentare bewusst ASCII bleiben und der Unterschied im Diff kaum
// auffaellt. Ab hier faellt er auf.
//
// `common.errors.*` wird mit geprueft: die Schluessel sind die Wire-Werte des
// API-`reason` (ADR-0051) und bleiben unveraendert, die deutschen Web-Texte
// dazu schreiben echte Umlaute. Die API-Fehlertexte selbst (apps/api,
// packages/) bleiben laut Owner-Entscheidung 2026-10-22 ohne Umlaute.
//
// Bewusst NICHT geprueft:
// - `editor.slash.aliases.*`: Suchbegriffe fuer das Slash-Menue, keine
//   sichtbaren Texte. Dort hilft „gedaechtnis“ beim Tippen ohne Umlaut-Taste.
// - Interpolationen `{{…}}`: Variablennamen, kein Text.
const EXEMPT_PREFIXES = ['editor.slash.aliases.'] as const

// Woerter mit echtem ae/oe/ue/ss. Ein Wort ist erlaubt, wenn es nach dem
// Herausnehmen dieser Wortteile kein Ersatzmuster mehr enthaelt. So decken
// Wortteile auch Komposita ab („Speicherdauer“, „Schlussbestimmungen“).
// Neue Ausnahme? Hier eintragen, kleingeschrieben, so kurz wie moeglich,
// so lang wie noetig — „pass“ deckt „Passwort“, aber nicht „Passwoerter“.
const ALLOWED_PARTS = [
  // ue mit echtem u + e
  'tuell', // aktuell
  'nuell', // manuell
  'duell', // individuell
  'quell', // Quelle
  'zuerst',
  'true', // GoTrue
  'value',
  // ss nach kurzem Vokal. Laengere Wortteile zuerst: „schluss“ muss vor
  // „aussch“ greifen, sonst bleibt von „Ausschluss“ ein „luss“ uebrig.
  'schloss', // abgeschlossen
  'schluss',
  'schlüss',
  'adress',
  'aussage',
  'aussch', // Ausschnitt
  'dessen',
  'aussehen',
  'besser',
  'bewusst',
  'dass',
  'dossier',
  'fass', // Fassung, erfassen, Zusammenfassung
  'impressum',
  'klass',
  'kommission',
  'läss', // lässt, zuverlässig, zulässig, Fahrlässigkeit
  'lass',
  'mess', // Messung, messbar
  'missbrauch',
  'müss',
  'muss',
  'niss', // Ergebnisse, Ereignisse
  'pass', // Passwort, passen, anpassbar
  'prozess',
  'vergess',
  'wiss',
  // Englische Fachbegriffe im deutschen Text
  'address',
  'dismiss',
  'headless',
  'message',
  'missing',
  'progress',
  'session',
] as const

// ue nach a/e/ä ist ein Diphthong plus e (Dauer, neue, Steuer), nach q ein
// qu (Request, Sequenz). ss nach einem Konsonanten ist eine Fugenstelle
// (Bearbeitungsstand) — ß steht nie nach einem Konsonanten.
const SUBSTITUTE = [/ae/, /oe/, /(?<![aeäq])ue/, /(?<=[aeiouäöüy])ss/] as const

type Tree = { [key: string]: string | Tree }

export function findSubstitutes(tree: Tree, prefix = ''): string[] {
  const offenders: string[] = []
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (EXEMPT_PREFIXES.some((exempt) => `${path}.`.startsWith(exempt))) continue
    if (typeof value !== 'string') {
      offenders.push(...findSubstitutes(value, path))
      continue
    }
    const words = value.replace(/\{\{[^}]*\}\}/g, ' ').match(/[A-Za-zÄÖÜäöüß]+/g) ?? []
    for (const word of words) {
      let rest = word.toLowerCase()
      for (const part of ALLOWED_PARTS) rest = rest.split(part).join('|')
      if (SUBSTITUTE.some((pattern) => pattern.test(rest))) offenders.push(`${path}: ${word}`)
    }
  }
  return offenders
}

describe('de.json — echte Umlaute statt Ersatzschreibung', () => {
  it('enthaelt in sichtbaren Texten kein ae/oe/ue/ss als Umlaut-Ersatz', () => {
    const offenders = findSubstitutes(de as unknown as Tree)
    expect(
      offenders,
      `${offenders.length} Ersatzumlaute in de.json — echte Umlaute/ß schreiben oder ` +
        'das Wort mit Begruendung in ALLOWED_PARTS aufnehmen.',
    ).toEqual([])
  })

  it('faengt Ersatzumlaute und laesst echte Schreibungen durch', () => {
    const sample: Tree = {
      bad: { a: 'Zurueck', b: 'Draft abschliessen', c: 'Aenderung', d: 'hoechstens', e: 'Strasse' },
      good: { a: 'Neue Steuer, aktuell und manuell', b: 'Passwort vergessen, dass Wissen', c: 'Bearbeitungsstand {{value}}' },
      common: { errors: { x: 'Kann nicht geloescht werden.', y: 'Kann nicht gelöscht werden.' } },
      editor: { slash: { aliases: { memory: 'gedaechtnis' } } },
    }
    expect(findSubstitutes(sample)).toEqual([
      'bad.a: Zurueck',
      'bad.b: abschliessen',
      'bad.c: Aenderung',
      'bad.d: hoechstens',
      'bad.e: Strasse',
      'common.errors.x: geloescht',
    ])
  })
})
