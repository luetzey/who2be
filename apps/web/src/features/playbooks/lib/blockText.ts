import type { ResourceBlock } from '@/api/types'

const PREVIEW_LEN = 120

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
