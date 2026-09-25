/**
 * `npm run i18n:check` — Locale-Dateien auf Paritaet, Duplikate und Waisen pruefen.
 *
 * Die Pruefungen selbst laufen ohnehin in der Vitest-Suite mit
 * (`src/i18n/audit.test.ts`) und damit im CI-Job `web`. Dieses Skript gibt es
 * fuer den Fall dazwischen: eine schnelle, lesbare Ausgabe beim Aufloesen eines
 * Konflikts, ohne die Suite zu starten. Es zeigt **alle** Waisen, auch die aus
 * `orphan-baseline.json` — beim Aufraeumen will man den Bestand sehen, nicht
 * nur den Zuwachs.
 *
 * Lauf: `npm run i18n:check` (via vite-node, damit die JSON-Imports und das
 * TypeScript ohne Build-Schritt funktionieren).
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  extractKeyUsage,
  findDuplicateKeys,
  findOrphanKeys,
  findParityGaps,
  mergeUsage,
  ORPHAN_IGNORE_PREFIXES,
  type LocaleTree,
} from '../src/i18n/audit'

const here = path.dirname(fileURLToPath(import.meta.url))
const srcDir = path.resolve(here, '../src')
const localesDir = path.join(srcDir, 'i18n/locales')
const baselinePath = path.join(srcDir, 'i18n/orphan-baseline.json')

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

function readLocale(locale: string): { raw: string; tree: LocaleTree } {
  const raw = fs.readFileSync(path.join(localesDir, `${locale}.json`), 'utf8')
  return { raw, tree: JSON.parse(raw) as LocaleTree }
}

const de = readLocale('de')
const en = readLocale('en')
const usage = mergeUsage(
  sourceFiles(srcDir).map((file) => extractKeyUsage(fs.readFileSync(file, 'utf8'))),
)
const baseline = new Set<string>(JSON.parse(fs.readFileSync(baselinePath, 'utf8')) as string[])

let failed = false

function section(title: string, lines: readonly string[], hard: boolean): void {
  if (lines.length === 0) {
    console.log(`✓ ${title}`)
    return
  }
  console.log(`${hard ? '✗' : '·'} ${title} — ${lines.length}`)
  for (const line of lines) console.log(`    ${line}`)
  if (hard) failed = true
}

const parity = findParityGaps({ locale: 'de', tree: de.tree }, { locale: 'en', tree: en.tree })
section(
  'Schluesselgleichheit de/en',
  parity.map((f) => `${f.key} fehlt in ${f.missingIn}.json`),
  true,
)

for (const [locale, file] of [
  ['de', de],
  ['en', en],
] as const) {
  const duplicates = findDuplicateKeys(file.raw, locale)
  section(
    `Keine doppelten Schluessel in ${locale}.json`,
    duplicates.map((f) => `${f.key} — Zeilen ${f.lines.join(', ')}`),
    true,
  )
}

for (const [locale, file] of [
  ['de', de],
  ['en', en],
] as const) {
  const orphans = findOrphanKeys(file.tree, usage, locale, ORPHAN_IGNORE_PREFIXES)
  const fresh = orphans.filter((f) => !baseline.has(f.key))
  section(
    `Keine neuen verwaisten Schluessel in ${locale}.json`,
    fresh.map((f) => f.key),
    true,
  )
  const known = orphans.length - fresh.length
  if (known > 0) {
    console.log(`  (${known} bekannte Waisen aus orphan-baseline.json — Altbestand, kein Fehler)`)
  }
}

if (failed) {
  console.error(
    '\nEine Pruefung ist fehlgeschlagen. Nach einer Konfliktaufloesung ist die\n' +
      'wahrscheinlichste Ursache ein stiller Fehlmerge: git hat zwei Staende\n' +
      'nebeneinandergelegt, ohne einen Konflikt zu melden. Den Nettodiff lesen,\n' +
      'nicht auf das Ausbleiben von Konfliktmarkern vertrauen.',
  )
  process.exit(1)
}

console.log('\nAlle i18n-Pruefungen in Ordnung.')
