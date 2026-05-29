import type { ResourceBlock } from '@/api/types'

const PREVIEW_LEN = 120
const SECTION_PREVIEW_LEN = 200

// Sammelt rekursiv alle `text`-Felder eines BlockNote-Blocks ein — gespiegelt
// vom Backend (`block_plain_text`). Nur Klartext, kein HTML/Styles.
export function blockPlainText(block: ResourceBlock): string {
  const parts: string[] = []
  const walk = (node: unknown): void => {
    if (Array.isArray(node)) {
      node.forEach(walk)
      return
    }
    if (node !== null && typeof node === 'object') {
      const record = node as Record<string, unknown>
      if (typeof record.text === 'string') {
        parts.push(record.text)
      }
      walk(record.content)
      walk(record.children)
    }
  }
  walk((block as Record<string, unknown>).content)
  walk((block as Record<string, unknown>).children)
  return parts.join('')
}

export function blockPreview(block: ResourceBlock): string {
  const text = blockPlainText(block).trim()
  if (text.length === 0) {
    return `(${block.type})`
  }
  return text.length > PREVIEW_LEN ? `${text.slice(0, PREVIEW_LEN)}…` : text
}

// Phase 3-B: BlockNote nutzt `type='heading'` mit `props.level: 1|2|3`.
// Verschiedene Schema-Varianten (z. B. Legacy `heading_1`) tolerieren wir
// pragmatisch — der Backend-Validation-Check passiert spaeter in Track A.
export function isHeadingBlock(block: ResourceBlock): boolean {
  if (block.type === 'heading') {
    return true
  }
  if (typeof block.type === 'string' && block.type.startsWith('heading_')) {
    return true
  }
  return false
}

function headingLevel(block: ResourceBlock): number {
  const props = (block as { props?: { level?: unknown } }).props
  if (props !== undefined && typeof props.level === 'number') {
    return props.level
  }
  if (typeof block.type === 'string' && block.type.startsWith('heading_')) {
    const suffix = block.type.slice('heading_'.length)
    const level = Number.parseInt(suffix, 10)
    if (Number.isFinite(level)) {
      return level
    }
  }
  return 1
}

/**
 * Plain-Text-Vorschau einer Heading-"Section": alle Bloecke vom Anker-
 * Heading (exklusiv) bis zum naechsten Heading desselben Levels oder
 * niedrigeren Levels (exklusiv). Wird vom `ResourceBlockLinkPicker`
 * genutzt, um neben dem Heading kontextuelle 200 Zeichen anzuzeigen.
 *
 * Liefert leeren String, wenn der Anker nicht gefunden wird.
 */
export function sectionPreview(blocks: ResourceBlock[], anchorId: string): string {
  const anchorIndex = blocks.findIndex((b) => b.id === anchorId)
  if (anchorIndex === -1) {
    return ''
  }
  const anchor = blocks[anchorIndex]
  if (!isHeadingBlock(anchor)) {
    return ''
  }
  const level = headingLevel(anchor)
  const sectionTexts: string[] = []
  for (let i = anchorIndex + 1; i < blocks.length; i += 1) {
    const candidate = blocks[i]
    if (isHeadingBlock(candidate) && headingLevel(candidate) <= level) {
      break
    }
    const text = blockPlainText(candidate).trim()
    if (text.length > 0) {
      sectionTexts.push(text)
    }
  }
  const joined = sectionTexts.join(' ').trim()
  if (joined.length === 0) {
    return ''
  }
  return joined.length > SECTION_PREVIEW_LEN
    ? `${joined.slice(0, SECTION_PREVIEW_LEN)}…`
    : joined
}
