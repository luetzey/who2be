// Längenschätzung für die Editor-Fußzeile (Editor-Paket P3, Spec §3.1).
//
// Gezählt wird nur der Text dieses Dokuments, ohne eingebettete Inhalte:
// Verweis-Pills (Inline-Typ `placeholder`) zählen 0 Zeichen. Damit niemand
// die Zahl für die Agenten-Fassung hält, sagt der Tooltip das ausdrücklich.
//
// Festlegungen (Karte t_2c66a927, vom PM übernommen):
// - Zeichen = Unicode-Codepoints nach NFC. „ä“ zählt 1, egal ob als ein
//   Zeichen oder als a + Trema gespeichert; Emoji außerhalb der BMP zählen 1.
// - Nicht-leere Blöcke werden wie in `blocksToPlainText` mit einem Umbruch
//   getrennt. Kinder, Tabellenzellen und Linktext zählen mit; Tabellenzellen
//   einer Zeile werden mit „ | “ verbunden.
// - Token = Zeichen / 4, auf 10 gerundet. Nicht-leerer Text ergibt mindestens
//   10, damit nie „≈ 0 Token“ neben Text steht.
// - Ab LONG_TOKEN_THRESHOLD geschätzten Token gilt der Text als lang.

import { CONTENT_BUDGETS } from './contentBudgets.generated'

/** Ab dieser Token-Schätzung zeigt die Fußzeile „· lang“ (Spec §3.1). */
export const LONG_TOKEN_THRESHOLD = 8000

/** Grobe Faustregel: etwa vier Zeichen je Token. */
export const CHARS_PER_TOKEN = 4

export interface LengthEstimate {
  /** Unicode-Codepoints des Textes nach NFC, ohne Pills. */
  chars: number
  /** Geschätzte Token, auf 10 gerundet (0 nur bei leerem Text). */
  tokens: number
  /** `tokens >= LONG_TOKEN_THRESHOLD`. */
  long: boolean
}

interface NodeLike {
  type?: unknown
  text?: unknown
  content?: unknown
  children?: unknown
  rows?: unknown
  cells?: unknown
}

/** Inline-Typ der Verweis-Pills (ADR-0058 3.2, `PlaceholderBlock.tsx`). */
const PILL_TYPE = 'placeholder'

function isNode(value: unknown): value is NodeLike {
  return value !== null && typeof value === 'object'
}

function inlineText(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .map((node) => {
      if (typeof node === 'string') return node
      if (!isNode(node) || node.type === PILL_TYPE) return ''
      if (typeof node.text === 'string') return node.text
      return inlineText(node.content)
    })
    .join('')
}

function tableLines(content: NodeLike): string[] {
  if (!Array.isArray(content.rows)) return []
  return content.rows.map((row) => {
    const cells = isNode(row) && Array.isArray(row.cells) ? row.cells : []
    return cells
      .map((cell) => (isNode(cell) && !Array.isArray(cell) ? inlineText(cell.content) : inlineText(cell)))
      .join(' | ')
  })
}

function blockLines(blocks: unknown): string[] {
  if (!Array.isArray(blocks)) return []
  const lines: string[] = []
  for (const block of blocks) {
    if (!isNode(block)) continue
    const content = block.content
    if (isNode(content) && !Array.isArray(content) && content.type === 'tableContent') {
      lines.push(...tableLines(content))
    } else {
      lines.push(inlineText(content))
    }
    lines.push(...blockLines(block.children))
  }
  return lines
}

/** Der gezählte Text: nicht-leere Zeilen, mit `\n` verbunden. */
export function estimateText(blocks: unknown): string {
  return blockLines(blocks)
    .filter((line) => line.length > 0)
    .join('\n')
}

/** Zeichenzahl als Codepoints nach NFC. */
export function countChars(text: string): number {
  return Array.from(text.normalize('NFC')).length
}

/** Token-Schätzung aus der Zeichenzahl (Zeichen/4, auf 10 gerundet, min. 10). */
export function estimateTokens(chars: number): number {
  if (chars <= 0) return 0
  return Math.max(10, Math.round(chars / CHARS_PER_TOKEN / 10) * 10)
}

// --- Wörter für die Richtwerte (ADR-0063, Builder schlank B5) ---------------
//
// Gleiche Regel wie die Schreibantwort der API (`content_budgets.count_words`):
// ein Wort ist eine durch Leerraum getrennte Folge mit mindestens einem
// Buchstaben oder einer Ziffer. Codeblöcke zählen nicht, Überschriften-Anker
// gibt es im Blockbaum nicht. Anders als bei den Zeichen zählt eine Pill hier
// als EIN Wort, denn die API sieht sie als Token `{{kind:id}}`.

/** Steht im Wort-Text für eine Pill (ein Wort, wie `{{kind:id}}` in der API). */
const PILL_WORD = '{{pill}}'
const WORD_CHAR = /[\p{L}\p{N}]/u

function inlineWords(content: unknown): string {
  if (typeof content === 'string') return content
  if (!Array.isArray(content)) return ''
  return content
    .map((node) => {
      if (typeof node === 'string') return node
      if (!isNode(node)) return ''
      if (node.type === PILL_TYPE) return PILL_WORD
      if (typeof node.text === 'string') return node.text
      return inlineWords(node.content)
    })
    .join('')
}

function wordLines(blocks: unknown): string[] {
  if (!Array.isArray(blocks)) return []
  const lines: string[] = []
  for (const block of blocks) {
    if (!isNode(block) || block.type === 'codeBlock') continue
    const content = block.content
    if (isNode(content) && !Array.isArray(content) && content.type === 'tableContent') {
      const rows = Array.isArray(content.rows) ? content.rows : []
      for (const row of rows) {
        const cells = isNode(row) && Array.isArray(row.cells) ? row.cells : []
        lines.push(
          cells
            .map((cell) => (isNode(cell) && !Array.isArray(cell) ? inlineWords(cell.content) : inlineWords(cell)))
            .join(' | '),
        )
      }
    } else {
      // Die API zählt den Markdown-Text; dort steht vor jedem Eintrag einer
      // nummerierten Liste „1.“, und das enthält eine Ziffer, ist also ein Wort.
      const marker = block.type === 'numberedListItem' ? '1. ' : ''
      lines.push(marker + inlineWords(content))
    }
    lines.push(...wordLines(block.children))
  }
  return lines
}

/** Wörter eines BlockNote-Dokuments nach der Zählregel der API (ADR-0063 §3). */
export function countWords(blocks: unknown): number {
  return wordLines(blocks)
    .join('\n')
    .split(/\s+/)
    .filter((token) => WORD_CHAR.test(token)).length
}

/** Hilfe-Abschnitt „Wie lang darf eine Persona sein?“ (Kurzlink, `/help/*` löst ihn auf). */
export const LENGTH_HELP_HREF = '/help/persona#laenge'

/** Elemente mit Richtwert in der Fußzeile bzw. auf der Moduskarte. */
export type BudgetElement = 'profile' | 'mode' | 'mode_count' | 'playbook_body'

/** `true`, wenn `value` die Warnschwelle erreicht (bei `strict`: überschreitet), wie die API. */
export function overBudget(element: BudgetElement, value: number): boolean {
  const budget: { warn: number; strict: boolean } = CONTENT_BUDGETS[element]
  return budget.strict ? value > budget.warn : value >= budget.warn
}

/** Ganze Zahl mit Tausendertrennung; DE mit geschütztem Leerzeichen („1 450“, wie die API). */
export function formatCount(value: number, language: string): string {
  if (language.startsWith('de')) {
    return new Intl.NumberFormat('de').format(value).replace(/\./g, '\u00a0')
  }
  return new Intl.NumberFormat(language).format(value)
}

/** Längenschätzung eines BlockNote-Dokuments für die Fußzeile. */
export function estimateLength(blocks: unknown): LengthEstimate {
  const chars = countChars(estimateText(blocks))
  const tokens = estimateTokens(chars)
  return { chars, tokens, long: tokens >= LONG_TOKEN_THRESHOLD }
}
