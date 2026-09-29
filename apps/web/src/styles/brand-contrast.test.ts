import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Kontrast-Waechter fuer die Brand-Tinte (design-language.md §11).
 *
 * Warum ein eigener Test: `vitest-axe` misst Kontrast in diesem Setup nicht.
 * Die Regel `color-contrast` ist in `src/test/a11y.ts` abgeschaltet, weil axe
 * dafuer `HTMLCanvasElement.getContext` braucht, das jsdom nicht hat — und
 * jsdom loest die Tailwind-Tokens aus `globals.css` ohnehin nicht auf.
 * Deshalb rechnet dieser Test die Token-Werte direkt aus der CSS-Datei nach:
 * OKLCH → lineares sRGB (Bjoern Ottosson), dann WCAG-2.1-Relativluminanz und
 * Kontrastverhaeltnis. Faellt ein Token-Wechsel unter 4,5:1, schlaegt er hier
 * fehl statt erst im Screenshot.
 */

const GLOBALS_CSS = readFileSync(resolve(__dirname, 'globals.css'), 'utf8')

const WCAG_AA_NORMAL_TEXT = 4.5

type Oklch = { l: number; c: number; h: number }

// Die vier Theme-Bloecke, die `--brand*` setzen. Der Dark-Block unter
// `prefers-color-scheme` ist in `@media` geschachtelt; `[^}]*` endet an der
// ersten schliessenden Klammer, also am Ende des inneren `:root`-Blocks.
const THEME_BLOCKS: Record<string, RegExp> = {
  'light (:root)': /^:root \{([^}]*)\}/m,
  'dark (prefers-color-scheme)': /@media \(prefers-color-scheme: dark\) \{\s*:root \{([^}]*)\}/,
  "light ([data-theme='light'])": /^:root\[data-theme='light'\] \{([^}]*)\}/m,
  "dark ([data-theme='dark'])": /^:root\[data-theme='dark'\] \{([^}]*)\}/m,
}

function block(name: string): string {
  const match = THEME_BLOCKS[name].exec(GLOBALS_CSS)
  if (!match) throw new Error(`Theme-Block ${name} nicht in globals.css gefunden`)
  return match[1]
}

function token(css: string, name: string): Oklch {
  const match = new RegExp(`${name}:\\s*oklch\\(([\\d.]+) ([\\d.]+) ([\\d.]+)\\);`).exec(css)
  if (!match) throw new Error(`Token ${name} fehlt oder ist kein oklch(L C h)`)
  return { l: Number(match[1]), c: Number(match[2]), h: Number(match[3]) }
}

/** OKLCH → lineares sRGB, auf den Gamut [0, 1] geklemmt. */
function toLinearSrgb({ l, c, h }: Oklch): [number, number, number] {
  const a = c * Math.cos((h * Math.PI) / 180)
  const b = c * Math.sin((h * Math.PI) / 180)
  const l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s_ = (l - 0.0894841775 * a - 1.291485548 * b) ** 3
  const clamp = (x: number) => Math.min(1, Math.max(0, x))
  return [
    clamp(4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_),
    clamp(-1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_),
    clamp(-0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_),
  ]
}

/** WCAG 2.1 relative luminance; OKLab liefert bereits lineares Licht. */
function luminance(color: Oklch): number {
  const [r, g, b] = toLinearSrgb(color)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrastRatio(a: Oklch, b: Oklch): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

describe('Brand-Tinte: Kontrast nach WCAG AA (design-language.md §11)', () => {
  it('rechnet bekannte Referenzpaare korrekt (Schwarz/Weiss = 21:1)', () => {
    const black = { l: 0, c: 0, h: 0 }
    const white = { l: 1, c: 0, h: 0 }
    expect(contrastRatio(black, white)).toBeCloseTo(21, 1)
    expect(contrastRatio(white, white)).toBeCloseTo(1, 5)
  })

  for (const name of Object.keys(THEME_BLOCKS)) {
    it(`${name}: --brand-foreground auf --brand und --brand-hover >= 4,5:1`, () => {
      const css = block(name)
      const fg = token(css, '--brand-foreground')
      expect(contrastRatio(fg, token(css, '--brand'))).toBeGreaterThanOrEqual(WCAG_AA_NORMAL_TEXT)
      expect(contrastRatio(fg, token(css, '--brand-hover'))).toBeGreaterThanOrEqual(
        WCAG_AA_NORMAL_TEXT,
      )
    })
  }
})

/**
 * Audit A6: `text-destructive` laeuft ueber das eigene Text-Token
 * `--destructive-text`, die Flaeche `--destructive` bleibt Flaechenfarbe.
 * Dunkel mass die Flaechenfarbe als Text 1,87:1 auf `--card`.
 */
describe('Destructive-Text: Kontrast nach WCAG AA (Audit A6, design-language.md §2.4)', () => {
  it('Tailwind-Namespace: text-destructive liest --destructive-text, nicht die Flaeche', () => {
    expect(GLOBALS_CSS).toMatch(/--text-color-destructive:\s*var\(--destructive-text\);/)
    expect(GLOBALS_CSS).toMatch(/--color-destructive:\s*var\(--destructive\);/)
  })

  for (const name of Object.keys(THEME_BLOCKS)) {
    // Hell ist `--muted` (0,97) knapp unter 4,5:1 — dort steht heute kein
    // destruktiver Text; der Hellwert bleibt bewusst unveraendert (Audit A6).
    const surfaces = name.startsWith('dark')
      ? ['--background', '--card', '--popover', '--muted']
      : ['--background', '--card', '--popover']
    it(`${name}: --destructive-text auf ${surfaces.join('/')} >= 4,5:1`, () => {
      const css = block(name)
      const fg = token(css, '--destructive-text')
      for (const surface of surfaces) {
        expect(
          contrastRatio(fg, token(css, surface)),
          `${surface} in ${name}`,
        ).toBeGreaterThanOrEqual(WCAG_AA_NORMAL_TEXT)
      }
    })

    it(`${name}: Flaeche --destructive-foreground auf --destructive >= 4,5:1`, () => {
      const css = block(name)
      expect(
        contrastRatio(token(css, '--destructive-foreground'), token(css, '--destructive')),
      ).toBeGreaterThanOrEqual(WCAG_AA_NORMAL_TEXT)
    })
  }

  it('hell: Text-Token ist identisch zur heutigen Flaechenfarbe (keine Aenderung im Light Mode)', () => {
    for (const name of ['light (:root)', "light ([data-theme='light'])"]) {
      const css = block(name)
      expect(token(css, '--destructive-text')).toEqual(token(css, '--destructive'))
    }
  })
})
