import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

// Import des Helfers ist hier der Pruefgegenstand: er muss das Timeout setzen.
import './a11y'
import { A11Y_TEST_TIMEOUT_MS } from './a11y-timeout'

// Haelt das zentrale axe-Timeout aus `a11y.ts` fest (#975).
//
// 1. Der Helfer hebt das Test-Timeout auch im Projekt `unit` — diese Datei
//    liegt bewusst ausserhalb von `*.a11y.test.tsx`.
// 2. Waechter: jede Testdatei ausserhalb des a11y-Projekts, die axe aufruft,
//    holt axe ueber den Helfer. Wer `vitest-axe` direkt importiert, laeuft
//    wieder mit 5 s — genau der Fall, der main rot gemacht hat.

const here = path.dirname(fileURLToPath(import.meta.url))
const srcDir = path.join(here, '..')

const A11Y_PROJECT_FILE = /\.a11y\.test\.tsx$/
const TEST_FILE = /\.(test|spec)\.tsx?$/
const AXE_CALL = /(?<![\w.$])axe\(/
const HELPER_IMPORT = /from\s+['"](?:@\/test\/a11y|(?:\.\.?\/)+(?:test\/)?a11y)['"]/

/** Ruft die Datei axe auf, ohne es ueber den Helfer zu beziehen? */
function bypassesHelper(source: string): boolean {
  return AXE_CALL.test(source) && !HELPER_IMPORT.test(source)
}

function testFiles(dir: string): string[] {
  const out: string[] = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) out.push(...testFiles(full))
    else if (TEST_FILE.test(entry.name)) out.push(full)
  }
  return out
}

describe('a11y-Helfer: Test-Timeout', () => {
  it('hebt das Timeout der importierenden Datei auf A11Y_TEST_TIMEOUT_MS', ({ task }) => {
    expect(task.timeout).toBe(A11Y_TEST_TIMEOUT_MS)
    expect(A11Y_TEST_TIMEOUT_MS).toBeGreaterThan(5000)
  })
})

describe('a11y-Helfer: Waechter', () => {
  it('erkennt axe-Aufrufe ohne Helfer-Import', () => {
    const viaPackage = "import { axe } from 'vitest-axe'\nit('don't', async () => { await axe(c) })"
    expect(bypassesHelper(viaPackage)).toBe(true)
  })

  it('akzeptiert den Helfer per Alias und relativ', () => {
    const body = "\nit('der Nutzer's Ansicht', async () => { expect(await axe(c)).toHaveNoViolations() })"
    expect(bypassesHelper("import { axe } from '@/test/a11y'" + body)).toBe(false)
    expect(bypassesHelper("import { axe } from '../../test/a11y'" + body)).toBe(false)
    expect(bypassesHelper("import { axe } from './a11y'" + body)).toBe(false)
  })

  it('ignoriert Dateien ohne axe-Aufruf', () => {
    expect(bypassesHelper("it('rendert', () => { relax(); maxe(1); obj.axe(2) })")).toBe(false)
  })

  it('jede axe-Testdatei ausserhalb von *.a11y.test.tsx nutzt den Helfer', () => {
    const files = testFiles(srcDir).filter((f) => !A11Y_PROJECT_FILE.test(f))
    const axeFiles = files.filter((f) => AXE_CALL.test(fs.readFileSync(f, 'utf8')))
    const offenders = axeFiles
      .filter((f) => bypassesHelper(fs.readFileSync(f, 'utf8')))
      .map((f) => path.relative(srcDir, f))

    // Untergrenze gegen eine leere Suche (Pfadfehler): am 2026-10-19 waren es 25.
    expect(axeFiles.length).toBeGreaterThanOrEqual(20)
    expect(offenders).toEqual([])
  })
})
