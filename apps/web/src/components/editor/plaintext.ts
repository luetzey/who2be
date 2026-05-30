import type { ResourceBlock } from '@/api/types'

// Plaintext-Bruecke fuer die BlockNote-Insel (Phase 3-fixes Track 2). Der
// System-Prompt der Persona wird im Editor erfasst, aber im Backend weiterhin
// als `string` persistiert. Konversion ist bewusst minimal: Text jeder
// Inline-Node konkatenieren, Bloecke mit `\n` trennen. Reicht fuer reine
// Prompt-Eingaben — kein Markdown-Roundtrip noetig.

interface InlineLike {
  text?: unknown
  content?: unknown
}

export function blocksToPlainText(blocks: ResourceBlock[]): string {
  return blocks
    .map((block) => inlineToText((block as { content?: unknown }).content))
    .filter((line) => line.length > 0)
    .join('\n')
}

export function plainTextToBlocks(text: string): ResourceBlock[] {
  if (text.length === 0) {
    return []
  }
  return text.split('\n').map((line, index) => ({
    id: `pt-${index}`,
    type: 'paragraph',
    content: line.length > 0 ? [{ type: 'text', text: line, styles: {} }] : [],
  })) as unknown as ResourceBlock[]
}

function inlineToText(content: unknown): string {
  if (typeof content === 'string') {
    return content
  }
  if (!Array.isArray(content)) {
    return ''
  }
  return content
    .map((node) => {
      if (node === null || typeof node !== 'object') {
        return ''
      }
      const inline = node as InlineLike
      if (typeof inline.text === 'string') {
        return inline.text
      }
      return inlineToText(inline.content)
    })
    .join('')
}
