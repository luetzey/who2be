import { expect, type Page } from '@playwright/test'

/**
 * Viewport-Helfer fuer die E2E-Journeys (Welle 7 / K2, Issue #431).
 *
 * `expectNoHorizontalScroll(page)` prueft die Regel aus
 * `docs/frontend/design-language.md` §4.4, Review-Checkliste Punkt 1 —
 * woertlich:
 *
 *   > Rendert die Aenderung bei 320px ohne horizontalen Scroll (ausser
 *   > bewusst gescrollten Containern wie Tabellen/Code-Bloecken)?
 *
 * Dieser eine Satz traegt beide Haelften der Zusicherung: die Regel und ihre
 * Ausnahme. Er wird hier deshalb zitiert, alles Weitere ist Begruendung dieses
 * Helfers, keine Norm.
 *
 * ## Warum die Fehlermeldung mehr sagt als „scrollWidth 412 > 320"
 *
 * Eine nackte Breitenmeldung kostet den Leser eine halbe Stunde Suche, weil
 * sie den Ort des Defekts verschweigt. Der Helfer sammelt deshalb die
 * Elemente, deren rechte Kante ueber den Viewport hinausragt, und meldet je
 * Fund einen CSS-artigen Selektor (Tag + id + erste Klassen + `data-testid`),
 * die rechte Kante in px, die Elementbreite und die computed `position` —
 * Letztere, weil absolut positionierte Dekoration anders zu bewerten ist als
 * ein zu breites Flex-Kind im Fluss. Ausgewiesen wird sie, nicht ausgeblendet:
 * eine Ausnahme fuer `position: absolute|fixed` wuerde echte Defekte
 * verschlucken.
 *
 * ## Bewusst scrollbare Bereiche (Tabellen!)
 *
 * Ein Element innerhalb eines Vorfahren mit computed `overflow-x`
 * `auto`/`scroll`/`hidden` kann den Body nicht verbreitern — der Vorfahre
 * fängt es ab. Solche Elemente werden deshalb nicht als Verursacher genannt.
 * Der Filter arbeitet ueber den **computed style**, nicht ueber Klassennamen:
 * der Tabellen-Wrapper in `apps/web/src/components/ui/table.tsx` traegt
 * `overflow-auto`, nicht `overflow-x-auto` — wer nach der x-Schreibweise
 * greppt, findet null Treffer und haelt den Wrapper faelschlich fuer fehlend.
 *
 * ## Grenze, die dieser Helfer NICHT abdeckt
 *
 * Ein `overflow-x: hidden` an einem Container versteckt einen echten
 * Ueberlauf: das Kind wird geklippt, der Body waechst gar nicht erst. Diese
 * Messung sieht am `documentElement` per Konstruktion nichts davon. Der Helfer
 * behauptet das auch nicht — er zeigt horizontalen Body-Scroll, und ein
 * versteckter Ueberlauf bleibt eine Sache fuer die visuelle Review-Checkliste.
 */

/**
 * Subpixel-Rundung (DPR-Emulation der Mobile-Profile, fraktionale
 * Layout-Breiten) erzeugt regelmaessig Differenzen unter 1px. Ein 1px-Puffer
 * haelt das aus, ohne einen realen Ueberlauf zu verschlucken: ein echter
 * Defekt liegt in der Groessenordnung ganzer Elemente, nicht eines Pixels.
 */
const TOLERANCE_PX = 1

interface Overflower {
  selector: string
  right: number
  width: number
  position: string
}

interface ScrollProbe {
  scrollWidth: number
  clientWidth: number
  offenders: Overflower[]
}

async function probe(page: Page): Promise<ScrollProbe> {
  // Erst nach links scrollen: die Rechtecke aus `getBoundingClientRect()` sind
  // viewport-relativ, ein bereits verschobener Scroll-Offset wuerde sie
  // verzerren.
  await page.evaluate(() => window.scrollTo(0, window.scrollY))

  return page.evaluate((tolerance: number) => {
    const root = document.documentElement
    const limit = root.clientWidth + tolerance

    function describe(element: Element): string {
      const parts = [element.tagName.toLowerCase()]
      if (element.id) parts.push(`#${element.id}`)
      const testid = element.getAttribute('data-testid')
      if (testid) parts.push(`[data-testid="${testid}"]`)
      const className = typeof element.className === 'string' ? element.className.trim() : ''
      if (className) {
        // Nur die ersten Klassen: Tailwind-Utility-Ketten werden sonst
        // laenger als die eigentliche Meldung.
        const classes = className.split(/\s+/).slice(0, 4)
        parts.push(`.${classes.join('.')}`)
        if (className.split(/\s+/).length > classes.length) parts.push('…')
      }
      return parts.join('')
    }

    /**
     * Ein Vorfahre mit `overflow-x` ungleich `visible` begrenzt die Breite
     * seines Teilbaums — sein Inhalt kann das Dokument nicht verbreitern.
     * Genau das ist der bewusst scrollbare Bereich (Tabellen, Code-Bloecke).
     */
    function isClippedByAncestor(element: Element): boolean {
      let parent = element.parentElement
      while (parent && parent !== root) {
        const overflowX = window.getComputedStyle(parent).overflowX
        if (overflowX === 'auto' || overflowX === 'scroll' || overflowX === 'hidden') {
          return true
        }
        parent = parent.parentElement
      }
      return false
    }

    const offenders: Overflower[] = []
    for (const element of Array.from(document.body.querySelectorAll('*'))) {
      const rect = element.getBoundingClientRect()
      if (rect.width === 0 && rect.height === 0) continue
      if (rect.right <= limit) continue
      if (isClippedByAncestor(element)) continue
      offenders.push({
        selector: describe(element),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
        position: window.getComputedStyle(element).position,
      })
    }

    // Breitester Ueberstand zuerst — der ist fast immer die Ursache, der Rest
    // sind seine Kinder.
    offenders.sort((a, b) => b.right - a.right)

    return { scrollWidth: root.scrollWidth, clientWidth: root.clientWidth, offenders }
  }, TOLERANCE_PX)
}

function formatFailure(label: string, result: ScrollProbe): string {
  const head =
    `Horizontaler Body-Scroll bei ${result.clientWidth}px Viewport` +
    `${label ? ` (${label})` : ''}: scrollWidth ${result.scrollWidth} > clientWidth ` +
    `${result.clientWidth} (+${result.scrollWidth - result.clientWidth}px).`

  if (result.offenders.length === 0) {
    return (
      `${head}\n` +
      'Kein einzelnes Element ragt ueber den Viewport hinaus — die Breite kommt ' +
      'dann aus einem Margin, einer Grid-/Flex-Spur oder einem bereits ' +
      'geklippten Teilbaum. Naechster Schritt: im Trace die Layout-Boxen des ' +
      'Hauptcontainers ansehen.'
    )
  }

  const list = result.offenders
    .slice(0, 5)
    .map((o) => `  - ${o.selector}\n      rechte Kante ${o.right}px, Breite ${o.width}px, position: ${o.position}`)
    .join('\n')
  const rest =
    result.offenders.length > 5 ? `\n  … und ${result.offenders.length - 5} weitere (meist Kinder des ersten).` : ''

  return `${head}\nUeberlaufende Elemente (breitester Ueberstand zuerst):\n${list}${rest}`
}

/**
 * Schlaegt fehl, wenn das Dokument horizontal scrollbar ist — und benennt
 * dabei, WAS ueberlaeuft.
 *
 * @param label Kurzer Ort-Hinweis fuer die Fehlermeldung (z. B. die Route).
 *   Ohne ihn ist bei mehreren Aufrufen pro Test nicht erkennbar, welcher
 *   gefallen ist.
 */
export async function expectNoHorizontalScroll(page: Page, label = ''): Promise<void> {
  const result = await probe(page)
  expect(result.scrollWidth, formatFailure(label, result)).toBeLessThanOrEqual(
    result.clientWidth + TOLERANCE_PX,
  )
}

/**
 * Nur fuer den Selbsttest des Helfers (`scroll-guard.spec.ts`): liefert die
 * Rohmessung, damit die Gegenprobe pruefen kann, dass der Helfer den
 * Verursacher tatsaechlich *benennt* — und nicht bloss irgendetwas meldet.
 */
export async function measureHorizontalOverflow(page: Page): Promise<ScrollProbe> {
  return probe(page)
}
