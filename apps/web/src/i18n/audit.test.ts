import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  extractKeyUsage,
  findDuplicateKeys,
  findOrphanKeys,
  findParityGaps,
  flattenKeys,
  mergeUsage,
  ORPHAN_IGNORE_PREFIXES,
  type LocaleTree,
} from './audit'
import de from './locales/de.json'
import en from './locales/en.json'
import baseline from './orphan-baseline.json'

// Pruefung der Locale-Sammeldateien (Karte P5).
//
// `de.json` und `en.json` sind Sammeldateien, an denen git in einer Welle
// dieses Repos OHNE Konfliktmarker falsch zusammengefuehrt hat: danach standen
// `auth.signup.captcha` und `auth.captcha` nebeneinander. Gefunden wurde das
// nur durch einen Cherry-pick-Gegencheck — das Ausbleiben von Konfliktmarkern
// hatte den Fehler gedeckt.
//
// Die Begruendung der drei Pruefungen und ihrer Grenzen steht im Docstring von
// `audit.ts`. Hier steht, wogegen sie gehalten werden: erst gegen Fixtures
// (inklusive der Nachstellung des Captcha-Falls), dann gegen die echten
// Locale-Dateien dieses Repos.

const here = path.dirname(fileURLToPath(import.meta.url))
const localesDir = path.join(here, 'locales')
const srcDir = path.join(here, '..')

/** Alle Quelldateien unter `src/`, ohne Tests und ohne die Locale-JSONs selbst. */
function sourceFiles(dir: string): string[] {
  const out: string[] = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      out.push(...sourceFiles(full))
    } else if (/\.tsx?$/.test(entry.name) && !/\.(test|spec)\.tsx?$/.test(entry.name)) {
      out.push(full)
    }
  }
  return out
}

const repoUsage = mergeUsage(
  sourceFiles(srcDir).map((file) => extractKeyUsage(fs.readFileSync(file, 'utf8'))),
)

describe('flattenKeys', () => {
  it('macht aus dem Baum punktgetrennte Pfade', () => {
    const tree: LocaleTree = { auth: { signup: { title: 'Registrieren' }, login: 'Anmelden' } }

    expect(flattenKeys(tree)).toEqual(['auth.signup.title', 'auth.login'])
  })
})

describe('findParityGaps', () => {
  it('meldet einen Schluessel, der nur in einer Locale steht', () => {
    const a: LocaleTree = { auth: { title: 'Anmelden', hinweis: 'Nur hier' } }
    const b: LocaleTree = { auth: { title: 'Sign in' } }

    expect(findParityGaps({ locale: 'de', tree: a }, { locale: 'en', tree: b })).toEqual([
      { key: 'auth.hinweis', missingIn: 'en' },
    ])
  })

  it('meldet in beiden Richtungen', () => {
    const a: LocaleTree = { nurDe: 'x' }
    const b: LocaleTree = { nurEn: 'y' }

    const findings = findParityGaps({ locale: 'de', tree: a }, { locale: 'en', tree: b })

    expect(findings).toEqual([
      { key: 'nurDe', missingIn: 'en' },
      { key: 'nurEn', missingIn: 'de' },
    ])
  })

  it('schweigt bei deckungsgleichen Baeumen', () => {
    const a: LocaleTree = { auth: { title: 'Anmelden' } }
    const b: LocaleTree = { auth: { title: 'Sign in' } }

    expect(findParityGaps({ locale: 'de', tree: a }, { locale: 'en', tree: b })).toEqual([])
  })
})

describe('findDuplicateKeys', () => {
  it('findet, was JSON.parse still verschluckt', () => {
    const raw = ['{', '  "auth": {', '    "title": "A",', '    "title": "B"', '  }', '}'].join('\n')

    // Der geparste Baum sieht makellos aus — genau das ist das Problem.
    expect(JSON.parse(raw)).toEqual({ auth: { title: 'B' } })
    expect(findDuplicateKeys(raw, 'de')).toEqual([
      { key: 'auth.title', locale: 'de', lines: [3, 4] },
    ])
  })

  it('haelt gleichnamige Schluessel in verschiedenen Zweigen auseinander', () => {
    const raw = JSON.stringify({ auth: { title: 'A' }, dashboard: { title: 'B' } }, null, 2)

    expect(findDuplicateKeys(raw, 'de')).toEqual([])
  })

  it('verwechselt Werte und Array-Eintraege nicht mit Schluesseln', () => {
    const raw = JSON.stringify(
      { a: { text: 'x', liste: ['x', 'x'] }, b: { text: 'x' } },
      null,
      2,
    )

    expect(findDuplicateKeys(raw, 'de')).toEqual([])
  })

  it('stolpert nicht ueber maskierte Anfuehrungszeichen im Wert', () => {
    const raw = '{\n  "a": "sagt \\"hallo\\": ja",\n  "b": "x"\n}'

    expect(findDuplicateKeys(raw, 'de')).toEqual([])
  })
})

describe('extractKeyUsage', () => {
  it('liest statische Aufrufe in beiden Anfuehrungszeichen', () => {
    const usage = extractKeyUsage(`t('auth.title'); t("dashboard.greeting")`)

    expect([...usage.literals].sort()).toEqual(['auth.title', 'dashboard.greeting'])
  })

  it('normalisiert die Namespace-Trennung mit Doppelpunkt', () => {
    expect([...extractKeyUsage(`t('common:status.active')`).literals]).toEqual([
      'common.status.active',
    ])
  })

  it('macht aus einem dynamischen Aufruf einen Praefix', () => {
    const usage = extractKeyUsage('t(`common:status.${status}`)')

    expect([...usage.prefixes]).toEqual(['common.status'])
    expect([...usage.literals]).toEqual([])
  })

  it('erfasst als Datum herumgereichte Schluessel (labelKey)', () => {
    const usage = extractKeyUsage(`const item = { labelKey: 'layout.nav.agents' }`)

    expect(usage.literals.has('layout.nav.agents')).toBe(true)
  })

  it('erfasst Schluessel in einer Record-Tabelle', () => {
    // `const LABEL = { added: 'diff.added' }` + spaeter `t(LABEL[op])`.
    const usage = extractKeyUsage(`const LABEL = { added: 'diff.added', removed: 'diff.removed' }`)

    expect(usage.literals.has('diff.added')).toBe(true)
    expect(usage.literals.has('diff.removed')).toBe(true)
  })

  it('haelt Dateinamen und Versionsnummern nicht fuer Schluessel', () => {
    const usage = extractKeyUsage(`import x from './setup.ts'; const v = '1.2.3'`)

    expect([...usage.literals]).toEqual([])
  })

  it('erfasst i18nKey der Trans-Komponente', () => {
    expect(extractKeyUsage(`<Trans i18nKey="legal.intro" />`).literals.has('legal.intro')).toBe(
      true,
    )
  })
})

describe('findOrphanKeys', () => {
  const usage = extractKeyUsage(`t('auth.title')`)

  it('meldet einen Schluessel, auf den niemand zeigt', () => {
    const tree: LocaleTree = { auth: { title: 'A', tot: 'B' } }

    expect(findOrphanKeys(tree, usage, 'de')).toEqual([{ key: 'auth.tot', locale: 'de' }])
  })

  it('akzeptiert ein Literal ohne Namespace-Praefix', () => {
    // `useTranslation('auth')` + `t('title')` adressiert `auth.title`.
    const tree: LocaleTree = { auth: { title: 'A' } }

    expect(findOrphanKeys(tree, extractKeyUsage(`t('title')`), 'de')).toEqual([])
  })

  it('spricht einen ganzen Teilbaum durch einen dynamischen Praefix frei', () => {
    const tree: LocaleTree = { common: { status: { active: 'A', archived: 'B' } } }

    expect(findOrphanKeys(tree, extractKeyUsage('t(`common:status.${s}`)'), 'de')).toEqual([])
  })

  it('laesst ignorierte Teilbaeume aus', () => {
    const tree: LocaleTree = { common: { errors: { rate_limited: 'Zu viele Anfragen' } } }

    expect(findOrphanKeys(tree, usage, 'de', ORPHAN_IGNORE_PREFIXES)).toEqual([])
  })
})

describe('Nachstellung des Fehlmerges aus dieser Welle', () => {
  // Der Baum, wie er nach dem stillen Fehlmerge aussah: `auth.captcha` ist der
  // Stand des einen Zweigs, `auth.signup.captcha` der des anderen. Beide sind
  // in beiden Sprachen vorhanden und keiner steht doppelt in seiner Datei —
  // Paritaet und Duplikat-Pruefung sind also gruen. Nur der Code verweist auf
  // genau einen der beiden.
  const deNachMerge: LocaleTree = {
    auth: {
      signup: {
        title: 'Registrieren',
        captcha: 'Bitte bestaetige, dass du kein Roboter bist.',
      },
      captcha: 'Bitte bestaetige, dass du kein Roboter bist.',
    },
  }
  const enNachMerge: LocaleTree = {
    auth: {
      signup: {
        title: 'Sign up',
        captcha: 'Please confirm that you are not a robot.',
      },
      captcha: 'Please confirm that you are not a robot.',
    },
  }
  // Die Oberflaeche liest den verschachtelten Schluessel.
  const codeUsage = extractKeyUsage(`t('auth.signup.title'); t('auth.signup.captcha')`)

  it('die Paritaets-Pruefung allein faengt ihn NICHT', () => {
    expect(
      findParityGaps({ locale: 'de', tree: deNachMerge }, { locale: 'en', tree: enNachMerge }),
    ).toEqual([])
  })

  it('die Duplikat-Pruefung allein faengt ihn NICHT', () => {
    expect(findDuplicateKeys(JSON.stringify(deNachMerge, null, 2), 'de')).toEqual([])
  })

  it('die Waisen-Pruefung faengt ihn — der konkurrierende Schluessel wird benannt', () => {
    expect(findOrphanKeys(deNachMerge, codeUsage, 'de')).toEqual([
      { key: 'auth.captcha', locale: 'de' },
    ])
    expect(findOrphanKeys(enNachMerge, codeUsage, 'en')).toEqual([
      { key: 'auth.captcha', locale: 'en' },
    ])
  })

  it('der doppelte Schluessel in EINER Datei wird ebenfalls erkannt', () => {
    // Die andere Form, die derselbe Fehlmerge annehmen kann: beide Zweige
    // schreiben denselben Pfad, git haengt beide Zeilen hintereinander.
    const raw = [
      '{',
      '  "auth": {',
      '    "signup": {',
      '      "captcha": "Bitte bestaetigen.",',
      '      "captcha": "Bitte bestaetige, dass du kein Roboter bist."',
      '    }',
      '  }',
      '}',
    ].join('\n')

    expect(findDuplicateKeys(raw, 'de')).toEqual([
      { key: 'auth.signup.captcha', locale: 'de', lines: [4, 5] },
    ])
  })
})

describe('die echten Locale-Dateien dieses Repos', () => {
  it('de.json und en.json tragen dieselben Schluessel', () => {
    const findings = findParityGaps(
      { locale: 'de', tree: de as LocaleTree },
      { locale: 'en', tree: en as LocaleTree },
    )

    expect(
      findings,
      `Locale-Paritaet verletzt:\n${findings
        .map((f) => `  ${f.key} fehlt in ${f.missingIn}.json`)
        .join('\n')}`,
    ).toEqual([])
  })

  it.each(['de', 'en'])('%s.json vergibt keinen Schluessel doppelt', (locale: string) => {
    const raw = fs.readFileSync(path.join(localesDir, `${locale}.json`), 'utf8')
    const findings = findDuplicateKeys(raw, locale)

    expect(
      findings,
      `Doppelte Schluessel in ${locale}.json (JSON.parse behaelt still den letzten):\n${findings
        .map((f) => `  ${f.key} — Zeilen ${f.lines.join(', ')}`)
        .join('\n')}`,
    ).toEqual([])
  })

  it.each([
    ['de', de],
    ['en', en],
  ])(
    '%s.json traegt keinen NEUEN Schluessel, auf den der Code nicht zeigt',
    (locale: string, tree: unknown) => {
      const known = new Set<string>(baseline as string[])
      const findings = findOrphanKeys(
        tree as LocaleTree,
        repoUsage,
        locale,
        ORPHAN_IGNORE_PREFIXES,
      ).filter((f) => !known.has(f.key))

      expect(
        findings,
        `Neue verwaiste Schluessel in ${locale}.json — kein Code verweist darauf.\n` +
          'Entweder ist der Schluessel tot (loeschen) oder eine Oberflaeche liest einen\n' +
          'konkurrierenden Schluessel, weil ein Merge still zwei Staende nebeneinander\n' +
          `gelegt hat:\n${findings.map((f) => `  ${f.key}`).join('\n')}`,
      ).toEqual([])
    },
  )

  it('die Baseline schrumpft nur — kein Eintrag darin ist inzwischen benutzt', () => {
    // Ratchet-Gegenrichtung: wird ein Schluessel wieder angebunden oder
    // geloescht, soll er aus `orphan-baseline.json` verschwinden. Sonst waechst
    // eine Liste heran, die niemand mehr liest — genau die stille Erosion, die
    // ein Ratchet verhindern soll (analog zum Coverage-Floor, ADR-0041).
    const current = new Set(
      findOrphanKeys(de as LocaleTree, repoUsage, 'de', ORPHAN_IGNORE_PREFIXES).map((f) => f.key),
    )
    const stale = (baseline as string[]).filter((key) => !current.has(key))

    expect(
      stale,
      'Diese Eintraege stehen in src/i18n/orphan-baseline.json, sind aber keine Waisen\n' +
        `mehr. Bitte aus der Baseline streichen:\n${stale.map((k) => `  ${k}`).join('\n')}`,
    ).toEqual([])
  })
})
