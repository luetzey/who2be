import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Audit A12 (Rest): Status-Knoten „● v1 active\" im BranchStatus (Resource-,
 * Tool-, Playbook-Detail). Vorher `text-brand` auf `bg-brand/10`: im Browser
 * hell 2,38:1 (#f3821d auf #fef3e8). Text braucht 4,5:1, der Punkt als
 * Grafik nach WCAG 1.4.11 3:1. Jetzt erben Text und Punkt `text-foreground`.
 *
 * Wie `brand-contrast.test.ts` rechnet dieser Test aus den Tokens in
 * `globals.css`; `bg-brand/10` wird wie im Browser als 10-%-Ueberblendung im
 * gamma-kodierten sRGB auf die Flaeche gelegt (Karte und Seite).
 */

const GLOBALS_CSS = readFileSync(resolve(__dirname, 'globals.css'), 'utf8')
const BRANCH_STATUS = readFileSync(resolve(__dirname, '../components/data/BranchStatus.tsx'), 'utf8')

const THEME_BLOCKS: Record<string, RegExp> = {
  'light (:root)': /^:root \{([^}]*)\}/m,
  'dark (prefers-color-scheme)': /@media \(prefers-color-scheme: dark\) \{\s*:root \{([^}]*)\}/,
  "light ([data-theme='light'])": /^:root\[data-theme='light'\] \{([^}]*)\}/m,
  "dark ([data-theme='dark'])": /^:root\[data-theme='dark'\] \{([^}]*)\}/m,
}

type Oklch = { l: number; c: number; h: number }
type Srgb = [number, number, number]

function block(name: string): string {
  const match = THEME_BLOCKS[name].exec(GLOBALS_CSS)
  if (!match) throw new Error(`Theme-Block ${name} nicht gefunden`)
  return match[1]
}

function token(css: string, name: string): Oklch {
  const match = new RegExp(`${name}:\\s*oklch\\(([\\d.]+) ([\\d.]+) ([\\d.]+)\\);`).exec(css)
  if (!match) throw new Error(`Token ${name} fehlt`)
  return { l: Number(match[1]), c: Number(match[2]), h: Number(match[3]) }
}

const encode = (x: number) => (x <= 0.0031308 ? 12.92 * x : 1.055 * x ** (1 / 2.4) - 0.055)
const decode = (x: number) => (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4)

function toSrgb({ l, c, h }: Oklch): Srgb {
  const a = c * Math.cos((h * Math.PI) / 180)
  const b = c * Math.sin((h * Math.PI) / 180)
  const l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s_ = (l - 0.0894841775 * a - 1.291485548 * b) ** 3
  const clamp = (x: number) => Math.min(1, Math.max(0, x))
  return [
    encode(clamp(4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_)),
    encode(clamp(-1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_)),
    encode(clamp(-0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_)),
  ]
}

const over = (fg: Srgb, alpha: number, bg: Srgb): Srgb =>
  [0, 1, 2].map((i) => fg[i] * alpha + bg[i] * (1 - alpha)) as Srgb
const luminance = ([r, g, b]: Srgb) => 0.2126 * decode(r) + 0.7152 * decode(g) + 0.0722 * decode(b)
function contrast(a: Srgb, b: Srgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const WCAG_AA_TEXT = 4.5

function nodeSurface(css: string, base: string): Srgb {
  return over(toSrgb(token(css, '--brand')), 0.1, toSrgb(token(css, base)))
}

describe('BranchStatus-Knoten: Kontrast nach WCAG (Audit A12)', () => {
  it('der aktuelle Knoten nutzt bg-brand/10 mit text-foreground (Werte dieses Tests)', () => {
    expect(BRANCH_STATUS).toMatch(/'border-brand\/40 bg-brand\/10 text-foreground'/)
    expect(BRANCH_STATUS).not.toMatch(/bg-brand\/10 text-brand'/)
  })

  it('Referenz: der alte Wert text-brand auf bg-brand/10 faellt hell unter 3:1', () => {
    const css = block('light (:root)')
    const ratio = contrast(toSrgb(token(css, '--brand')), nodeSurface(css, '--card'))
    expect(ratio).toBeLessThan(3)
  })

  for (const name of Object.keys(THEME_BLOCKS)) {
    for (const base of ['--card', '--background']) {
      it(`${name}: text-foreground auf bg-brand/10 ueber ${base} >= 4,5:1`, () => {
        const css = block(name)
        expect(contrast(toSrgb(token(css, '--foreground')), nodeSurface(css, base))).toBeGreaterThanOrEqual(
          WCAG_AA_TEXT,
        )
      })
    }
  }
})
