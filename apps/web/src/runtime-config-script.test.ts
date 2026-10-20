// Prueft `docker/40-who2be-runtime-config.sh` direkt: das Skript wird mit
// `sh` ausgefuehrt, die erzeugte `/config.js` in einem frischen JS-Kontext
// ausgewertet. Belegt, dass Freitext (Hinweis/Banner) JSON-sicher landet —
// Anfuehrungszeichen, Backslashes, Zeilenumbrueche und `</script>` duerfen die
// Datei weder zerlegen noch Markup im Klartext hinterlassen (Karte t_27d7c6ad).
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { runInNewContext } from 'node:vm'

import { afterEach, describe, expect, it } from 'vitest'

import type { RuntimeConfig } from './config'

const SCRIPT = resolve(__dirname, '../docker/40-who2be-runtime-config.sh')

let dir: string | undefined

afterEach(() => {
  if (dir !== undefined) rmSync(dir, { recursive: true, force: true })
  dir = undefined
})

function generate(env: Record<string, string>): { source: string; config: RuntimeConfig } {
  dir = mkdtempSync(join(tmpdir(), 'who2be-rtcfg-'))
  const target = join(dir, 'config.js')
  execFileSync('sh', [SCRIPT], {
    env: { PATH: process.env.PATH ?? '/usr/bin:/bin', WHO2BE_RUNTIME_CONFIG_PATH: target, ...env },
    stdio: 'pipe',
  })
  const source = readFileSync(target, 'utf8')
  const sandbox: { window: { __WHO2BE_CONFIG__?: RuntimeConfig } } = { window: {} }
  runInNewContext(source, sandbox)
  return { source, config: sandbox.window.__WHO2BE_CONFIG__ ?? {} }
}

describe('40-who2be-runtime-config.sh — Freitext', () => {
  it('schreibt ohne Werte leere Texte und Level info', () => {
    const { config } = generate({})

    expect(config.launchMessageDe).toBe('')
    expect(config.launchMessageEn).toBe('')
    expect(config.noticeDe).toBe('')
    expect(config.noticeEn).toBe('')
    expect(config.noticeLevel).toBe('info')
  })

  it('uebernimmt Anfuehrungszeichen, Backslash, Umlaute und Zeilenumbrueche unveraendert', () => {
    const text = 'Wartung "heute" ab 22 Uhr \\ Neustart\nZeile 2: äöü — $HOME `id`'

    const { config } = generate({ WHO2BE_NOTICE_DE: text, WHO2BE_LAUNCH_MESSAGE_EN: text })

    expect(config.noticeDe).toBe(text)
    expect(config.launchMessageEn).toBe(text)
  })

  it('laesst kein </script> und kein Markup im Klartext in der Datei', () => {
    const text = '</script><script>alert(1)</script><b>fett</b>'

    const { source, config } = generate({ WHO2BE_NOTICE_EN: text })

    expect(source).not.toContain('</script>')
    expect(source).not.toContain('<b>')
    expect(source).toContain('\\u003c/script\\u003e')
    // Nach dem Auswerten ist der Text wieder exakt der Eingabewert.
    expect(config.noticeEn).toBe(text)
  })

  it('verwirft Wagenruecklaeufe (Windows-.env) statt sie in den Text zu schreiben', () => {
    const { config } = generate({ WHO2BE_LAUNCH_MESSAGE_DE: 'Zeile 1\r\nZeile 2\r' })

    expect(config.launchMessageDe).toBe('Zeile 1\nZeile 2')
  })

  it('entfernt Anfuehrungszeichen aus dem Level wie bei den uebrigen Schaltern', () => {
    const { config } = generate({ WHO2BE_NOTICE_LEVEL: 'warn"ing' })

    expect(config.noticeLevel).toBe('warning')
  })
})
