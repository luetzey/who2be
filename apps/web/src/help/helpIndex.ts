/**
 * Hilfe-Bereich: Loader, Frontmatter-Schema und Suche (Onboarding P4).
 *
 * Inhalt ist **Daten, kein Code**: jede Hilfe-Seite und jedes Tutorial ist je
 * Sprache eine Markdown-Datei unter `src/help/`, Dateiname `<slug>.<lang>.md`.
 * `import.meta.glob` bindet sie beim Build ein; eine neue Datei erscheint ohne
 * Code-Aenderung in Startseite, Suche und Routen.
 *
 * - Seiten: `src/help/<abschnitt>/<slug>.<lang>.md`, Frontmatter `title`,
 *   `description`, `section` (aus {@link HELP_SECTIONS}), `order`, `updated`
 *   (JJJJ-MM-TT), `audience` (`all` | `admin`).
 * - Tutorials: `src/help/tutorials/<id>.<lang>.md`, Frontmatter `tutorial`
 *   (= `<id>`), `title`, `description`, `duration` (Minuten). Je Schritt ein
 *   Abschnitt `## Titel [#<step_id>]`. Die Schritt-Definitionen (Typ, Seite,
 *   automatisch) liefert der Server (`GET /v1/me/tutorials`, ADR-0060); ob die
 *   step_ids beider Sprachen zum Katalog passen, prueft der Python-Test
 *   `packages/models/tests/test_tutorial_help_parity.py`.
 *
 * Der Text folgt dem ADR-0058-Dialekt: Ueberschriften `##`/`###` mit Anker
 * ` [#id]`, Listen, Code, Links. Kein HTML, keine Bilder, keine Tabellen, kein
 * `#` im Text (der Titel kommt aus dem Frontmatter).
 */

export const HELP_LOCALES = ['de', 'en'] as const
export type HelpLocale = (typeof HELP_LOCALES)[number]

/** Feste Abschnitte. Ein neuer Abschnitt ist bewusst eine Code-Aenderung. */
export const HELP_SECTIONS = [
  'erste-schritte',
  'bausteine',
  'agenten-verbessern',
  'konto-und-team',
] as const
export type HelpSection = (typeof HELP_SECTIONS)[number]

/** Ordner der Tutorials (kein Abschnitt). */
export const TUTORIALS_DIR = 'tutorials'

/** Slugs, die als feste Route unter `/help/` stehen (Tutorials, Altseite, Was ist neu). */
const RESERVED_SLUGS: readonly string[] = ['tutorials', 'placeholders', 'neu']

/**
 * Link-Ziele aus Hilfe-Markdown: nur `http(s)://`, relativ (`/…`, nicht `//…`)
 * oder Anker (`#…`). Alles andere (`javascript:`, `data:`, `mailto:`,
 * protokoll-relativ) faellt weg — der Text bleibt, der Link nicht.
 */
export function safeHelpHref(value: string): string | null {
  const href = value.trim()
  if (/^https?:\/\/[^\s]+$/i.test(href)) return href
  if (/^\/(?!\/)[^\s\\]*$/.test(href)) return href
  if (/^#[^\s]+$/.test(href)) return href
  return null
}

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/
const DATE = /^\d{4}-\d{2}-\d{2}$/
const ANCHOR_HEADING = /^(#{2,3})\s+(.+?)\s+\[#([a-z0-9]+(?:-[a-z0-9]+)*)\]\s*$/
const ANY_HEADING = /^(#{1,6})\s/
const FENCE = /^(```|~~~)/

const PAGE_KEYS = ['title', 'description', 'section', 'order', 'updated', 'audience'] as const
const TUTORIAL_KEYS = ['tutorial', 'title', 'description', 'duration'] as const

/** Ein Abschnitt unter einer `##`/`###`-Ueberschrift mit Anker. */
export interface HelpBlock {
  id: string
  level: 2 | 3
  title: string
  /** Markdown unter der Ueberschrift bis zur naechsten Anker-Ueberschrift. */
  body: string
}

interface HelpEntryBase {
  slug: string
  locale: HelpLocale
  title: string
  description: string
  /** Text vor der ersten Ueberschrift. */
  intro: string
  blocks: HelpBlock[]
  /** Kompletter Markdown-Text ohne Frontmatter (fuer „Für Agenten kopieren“). */
  body: string
}

export interface HelpPage extends HelpEntryBase {
  kind: 'page'
  section: HelpSection
  order: number
  updated: string
  audience: 'all' | 'admin'
}

export interface HelpTutorial extends HelpEntryBase {
  kind: 'tutorial'
  durationMinutes: number
}

export type HelpEntry = HelpPage | HelpTutorial

export interface HelpIndex {
  pages: HelpPage[]
  tutorials: HelpTutorial[]
  /** Ein Befund je Problem; leer = Inhalt gueltig. */
  errors: string[]
}

/** Zerlegt `---\nkey: value\n---\n` in Felder und Body. */
export function parseFrontmatter(raw: string): { data: Record<string, string>; body: string } | null {
  const text = raw.replace(/\r\n/g, '\n')
  const match = /^---\n([\s\S]*?)\n---\n?([\s\S]*)$/.exec(text)
  if (match === null) return null
  const data: Record<string, string> = {}
  for (const line of match[1].split('\n')) {
    if (line.trim() === '' || line.trimStart().startsWith('#')) continue
    const sep = line.indexOf(':')
    if (sep <= 0) return null
    const key = line.slice(0, sep).trim()
    let value = line.slice(sep + 1).trim()
    if (/^(["']).*\1$/.test(value)) value = value.slice(1, -1)
    if (key in data) return null
    data[key] = value
  }
  return { data, body: match[2] }
}

/** Zerlegt den Body in Einleitung und Anker-Abschnitte; meldet Dialekt-Verstoesse. */
export function splitBlocks(body: string): { intro: string; blocks: HelpBlock[]; problems: string[] } {
  const problems: string[] = []
  const blocks: HelpBlock[] = []
  const intro: string[] = []
  let current: { id: string; level: 2 | 3; title: string; lines: string[] } | null = null
  let inFence = false
  for (const line of body.split('\n')) {
    if (FENCE.test(line.trim())) inFence = !inFence
    if (!inFence) {
      const anchored = ANCHOR_HEADING.exec(line)
      if (anchored !== null) {
        if (current !== null) {
          blocks.push({ ...current, body: current.lines.join('\n').trim() })
        }
        current = {
          id: anchored[3],
          level: anchored[1].length as 2 | 3,
          title: anchored[2],
          lines: [],
        }
        continue
      }
      if (ANY_HEADING.test(line)) {
        problems.push(`Überschrift ohne Anker oder auf falscher Ebene: "${line.trim()}"`)
      }
      if (/<\/?[a-zA-Z][^>]*>/.test(line)) problems.push(`HTML ist nicht erlaubt: "${line.trim()}"`)
      if (/!\[[^\]]*\]\(/.test(line)) problems.push(`Bilder ist nicht erlaubt: "${line.trim()}"`)
      if (/^\s*\|.*\|\s*$/.test(line)) problems.push(`Tabellen sind nicht erlaubt: "${line.trim()}"`)
    }
    if (current === null) intro.push(line)
    else current.lines.push(line)
  }
  if (current !== null) blocks.push({ ...current, body: current.lines.join('\n').trim() })
  const seen = new Set<string>()
  for (const block of blocks) {
    if (seen.has(block.id)) problems.push(`Anker doppelt: #${block.id}`)
    seen.add(block.id)
  }
  return { intro: intro.join('\n').trim(), blocks, problems }
}

/**
 * `./bausteine/persona.de.md` (Glob-Schluessel relativ zu `src/help/`) bzw.
 * `…/help/bausteine/persona.de.md` → Ordner, Slug, Sprache.
 */
function parsePath(path: string): { dir: string; slug: string; locale: string } | null {
  const relative = path.replace(/^(?:.*\/help\/|\.\/)/, '')
  const match = /^(?:(.+)\/)?([^/]+)\.([a-z]{2})\.md$/.exec(relative)
  if (match === null) return null
  return { dir: match[1] ?? '', slug: match[2], locale: match[3] }
}

function unknownKeys(data: Record<string, string>, allowed: readonly string[]): string[] {
  return Object.keys(data).filter((key) => !allowed.includes(key))
}

function required(data: Record<string, string>, keys: readonly string[]): string[] {
  return keys.filter((key) => (data[key] ?? '') === '')
}

/**
 * Baut den Index aus `Pfad → Rohtext`. Ungueltige Dateien landen in `errors`
 * und NICHT im Index — die Oberflaeche zeigt nur gueltigen Inhalt, der
 * Inhaltstest wird rot.
 */
export function buildHelpIndex(files: Record<string, string>): HelpIndex {
  const pages: HelpPage[] = []
  const tutorials: HelpTutorial[] = []
  const errors: string[] = []

  for (const [path, raw] of Object.entries(files).sort(([a], [b]) => a.localeCompare(b))) {
    const fail = (message: string) => errors.push(`${path}: ${message}`)
    const parsed = parsePath(path)
    if (parsed === null) {
      fail('Dateiname muss <slug>.<sprache>.md sein')
      continue
    }
    const { dir, slug, locale } = parsed
    if (!(HELP_LOCALES as readonly string[]).includes(locale)) {
      fail(`unbekannte Sprache "${locale}"`)
      continue
    }
    if (!SLUG.test(slug)) {
      fail(`Slug "${slug}" ist kein Kleinbuchstaben-Slug`)
      continue
    }
    if (dir !== TUTORIALS_DIR && RESERVED_SLUGS.includes(slug)) {
      fail(`Slug "${slug}" ist für eine Route reserviert`)
      continue
    }
    const front = parseFrontmatter(raw)
    if (front === null) {
      fail('Frontmatter fehlt oder ist kein key: value-Block')
      continue
    }
    const { data, body } = front
    const { intro, blocks, problems } = splitBlocks(body)
    const base = {
      slug,
      locale: locale as HelpLocale,
      title: data.title ?? '',
      description: data.description ?? '',
      intro,
      blocks,
      body: body.trim(),
    }
    const before = errors.length
    problems.forEach(fail)

    if (dir === TUTORIALS_DIR) {
      unknownKeys(data, TUTORIAL_KEYS).forEach((key) => fail(`unbekanntes Feld "${key}"`))
      required(data, TUTORIAL_KEYS).forEach((key) => fail(`Pflichtfeld "${key}" fehlt`))
      if (data.tutorial !== undefined && data.tutorial !== slug) {
        fail(`tutorial "${data.tutorial}" passt nicht zum Dateinamen "${slug}"`)
      }
      const duration = Number(data.duration)
      if (data.duration !== undefined && !(Number.isInteger(duration) && duration > 0)) {
        fail('duration muss eine ganze Zahl (Minuten) > 0 sein')
      }
      if (blocks.length === 0) fail('Tutorial ohne Schritt-Abschnitt (## Titel [#step-id])')
      if (blocks.some((block) => block.level !== 2)) {
        fail('Schritte sind Abschnitte der Ebene ## (keine ###)')
      }
      if (errors.length === before) {
        tutorials.push({ ...base, kind: 'tutorial', durationMinutes: duration })
      }
      continue
    }

    unknownKeys(data, PAGE_KEYS).forEach((key) => fail(`unbekanntes Feld "${key}"`))
    required(data, PAGE_KEYS).forEach((key) => fail(`Pflichtfeld "${key}" fehlt`))
    const section = data.section as HelpSection
    if (data.section !== undefined && !(HELP_SECTIONS as readonly string[]).includes(section)) {
      fail(`section "${data.section}" ist kein fester Abschnitt`)
    }
    if (data.section !== undefined && dir !== data.section) {
      fail(`liegt in "${dir}", section sagt "${data.section}"`)
    }
    const order = Number(data.order)
    if (data.order !== undefined && !Number.isInteger(order)) fail('order muss eine ganze Zahl sein')
    if (data.updated !== undefined && !DATE.test(data.updated)) fail('updated muss JJJJ-MM-TT sein')
    if (data.audience !== undefined && data.audience !== 'all' && data.audience !== 'admin') {
      fail('audience muss all oder admin sein')
    }
    if (errors.length === before) {
      pages.push({
        ...base,
        kind: 'page',
        section,
        order,
        updated: data.updated,
        audience: data.audience as 'all' | 'admin',
      })
    }
  }

  errors.push(...checkConsistency(pages, tutorials))
  pages.sort((a, b) => a.order - b.order || a.slug.localeCompare(b.slug))
  return { pages, tutorials, errors }
}

/** Interne Hilfe-Links im Text: `/help/<slug>` oder `/help/<slug>#<anker>`. */
export function internalHelpLinks(markdown: string): Array<{ slug: string; anchor: string | null }> {
  const links: Array<{ slug: string; anchor: string | null }> = []
  for (const match of markdown.matchAll(/\]\((\/help\/[^)\s]*)\)/g)) {
    const target = /^\/help\/(?:tutorials\/)?([a-z0-9-]+)(?:#([a-z0-9-]+))?$/.exec(match[1])
    if (target === null) links.push({ slug: match[1], anchor: null })
    else links.push({ slug: target[1], anchor: target[2] ?? null })
  }
  return links
}

/** DE/EN-Paritaet, Slugs eindeutig, interne Links loesen auf. */
function checkConsistency(pages: HelpPage[], tutorials: HelpTutorial[]): string[] {
  const errors: string[] = []
  const entries: HelpEntry[] = [...pages, ...tutorials]
  for (const locale of HELP_LOCALES) {
    const other = HELP_LOCALES.find((candidate) => candidate !== locale)
    for (const entry of entries.filter((e) => e.locale === locale)) {
      const twin = entries.find(
        (e) => e.kind === entry.kind && e.slug === entry.slug && e.locale === other,
      )
      if (twin === undefined) {
        errors.push(`${entry.kind} "${entry.slug}" fehlt in ${other}`)
        continue
      }
      const ids = entry.blocks.map((block) => block.id).join(',')
      const twinIds = twin.blocks.map((block) => block.id).join(',')
      if (locale === 'de' && ids !== twinIds) {
        errors.push(`${entry.kind} "${entry.slug}": Anker DE [${ids}] ≠ EN [${twinIds}]`)
      }
    }
    const localPages = pages.filter((page) => page.locale === locale)
    const slugs = localPages.map((page) => page.slug)
    for (const slug of new Set(slugs)) {
      if (slugs.filter((s) => s === slug).length > 1) errors.push(`Slug "${slug}" doppelt (${locale})`)
    }
    for (const entry of entries.filter((e) => e.locale === locale)) {
      for (const match of entry.body.matchAll(/\]\(([^)]*)\)/g)) {
        if (safeHelpHref(match[1]) === null) {
          errors.push(`${entry.slug}.${locale}: Link "${match[1]}" ist nicht erlaubt`)
        }
      }
      for (const link of internalHelpLinks(entry.body)) {
        const target = entries.find((e) => e.slug === link.slug && e.locale === locale)
        if (target === undefined) {
          errors.push(`${entry.slug}.${locale}: Link auf unbekannte Seite "${link.slug}"`)
        } else if (link.anchor !== null && !target.blocks.some((b) => b.id === link.anchor)) {
          errors.push(`${entry.slug}.${locale}: Anker "#${link.anchor}" fehlt in "${link.slug}"`)
        }
      }
    }
  }
  return errors
}

/** Sprache der Oberflaeche auf eine Hilfe-Sprache abbilden (Fallback `de`). */
export function toHelpLocale(language: string | undefined): HelpLocale {
  const base = (language ?? '').slice(0, 2)
  return (HELP_LOCALES as readonly string[]).includes(base) ? (base as HelpLocale) : 'de'
}

/** Klartext fuer die Suche: Markdown-Zeichen und Anker raus. */
function plain(text: string): string {
  return text
    .replace(/\s\[#[a-z0-9-]+\]/g, ' ')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[`*_>#-]/g, ' ')
    .toLowerCase()
}

export const SEARCH_MIN_LENGTH = 2

/**
 * Clientseitige Volltextsuche (Titel vor Beschreibung vor Text). Jedes Wort
 * der Anfrage muss vorkommen. Kein Server-Aufruf, keine Protokollierung.
 */
export function searchHelp(index: HelpIndex, locale: HelpLocale, query: string): HelpEntry[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  if (query.trim().length < SEARCH_MIN_LENGTH || words.length === 0) return []
  const entries: HelpEntry[] = [...index.tutorials, ...index.pages].filter(
    (entry) => entry.locale === locale,
  )
  const scored: Array<{ entry: HelpEntry; score: number }> = []
  for (const entry of entries) {
    const title = entry.title.toLowerCase()
    const description = entry.description.toLowerCase()
    const text = plain(`${entry.intro}\n${entry.blocks.map((b) => `${b.title}\n${b.body}`).join('\n')}`)
    let score = 0
    let all = true
    for (const word of words) {
      if (title.includes(word)) score += 3
      else if (description.includes(word)) score += 2
      else if (text.includes(word)) score += 1
      else all = false
    }
    if (all) scored.push({ entry, score })
  }
  return scored.sort((a, b) => b.score - a.score).map(({ entry }) => entry)
}

const files = import.meta.glob<string>('./**/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
})

/** Der ausgelieferte Hilfe-Index, einmal beim Laden des Moduls gebaut. */
export const helpIndex: HelpIndex = buildHelpIndex(files)

/** Seite in der Sprache suchen (Slug aus der URL wird nur so aufgeloest). */
export function findPage(index: HelpIndex, locale: HelpLocale, slug: string): HelpPage | null {
  return index.pages.find((page) => page.locale === locale && page.slug === slug) ?? null
}

/** Tutorial-Text in der Sprache suchen. */
export function findTutorial(
  index: HelpIndex,
  locale: HelpLocale,
  id: string,
): HelpTutorial | null {
  return index.tutorials.find((t) => t.locale === locale && t.slug === id) ?? null
}
