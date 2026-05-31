// Liquid-Token-Migration fuer System-Prompt-Templates (Welle 5).
//
// Wandelt einen Plain-Text-Body mit Liquid-Tokens (Pre-Welle-5-Format,
// z. B. "Hallo {{ persona.name }}") in BlockNote-Inline-Content. Bekannte
// Tokens werden zu typisierten Placeholder-Inline-Blocks (Pills) — die
// anderen bleiben als Klartext stehen, weil ihnen kein BlockNote-
// Placeholder-Kind entspricht (z. B. {{ playbooks }}, {{ triggers }}).
// Der User kann sie nach der Migration im Slash-Menue manuell ersetzen.

import type { PlaceholderKind } from '@/components/editor/system-prompt/PlaceholderBlock'

interface PlaceholderInline {
  type: 'placeholder'
  props: {
    kind: PlaceholderKind
    target_id: string
    label: string
  }
}

interface TextInline {
  type: 'text'
  text: string
  styles: Record<string, never>
}

export type InlineContent = PlaceholderInline | TextInline

interface LiquidMapping {
  kind: PlaceholderKind
  target_id: string
  label: string
}

// Nur Tokens, die ein 1:1-Aequivalent unter den Welle-5-Placeholders haben.
// Erweiterbar, sobald wir mehr Backend-Placeholder-Kinds einfuehren.
const LIQUID_MAP: Record<string, LiquidMapping> = {
  'persona.name': {
    kind: 'persona-field',
    target_id: 'name',
    label: 'Persona: Name',
  },
  'persona.description': {
    kind: 'persona-field',
    target_id: 'description',
    label: 'Persona: Beschreibung',
  },
}

const LIQUID_RE = /\{\{\s*([\w.]+)\s*\}\}/g

/**
 * Tokenisiert `body` an Liquid-Tokens. Bekannte Tokens werden zu
 * `placeholder`-Inline-Blocks, alle anderen Segmente (inkl. unbekannter
 * Tokens) bleiben Text. Bei leerem Input wird ein einzelner leerer
 * Text-Run zurueckgegeben, weil BlockNote ein Paragraph mit leerer
 * `content`-Liste nicht akzeptiert.
 */
export function liquidBodyToInline(body: string): InlineContent[] {
  const out: InlineContent[] = []
  let lastIdx = 0
  LIQUID_RE.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = LIQUID_RE.exec(body)) !== null) {
    if (match.index > lastIdx) {
      out.push({
        type: 'text',
        text: body.slice(lastIdx, match.index),
        styles: {},
      })
    }
    const mapped = LIQUID_MAP[match[1]]
    if (mapped !== undefined) {
      out.push({ type: 'placeholder', props: mapped })
    } else {
      out.push({ type: 'text', text: match[0], styles: {} })
    }
    lastIdx = LIQUID_RE.lastIndex
  }
  if (lastIdx < body.length) {
    out.push({ type: 'text', text: body.slice(lastIdx), styles: {} })
  }
  if (out.length === 0) {
    out.push({ type: 'text', text: '', styles: {} })
  }
  return out
}
