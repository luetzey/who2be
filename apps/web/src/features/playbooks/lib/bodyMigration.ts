// bodyMigration.ts — Plain → BlockNote-Migration fuer den Playbook-Body (Welle 5).
//
// Wandelt den Legacy-Plain-Text-Body in BlockNote-Paragraphen UND hebt die
// bereits verlinkten Relationen (Composes + Resource-Links) als Inline-Pills
// in den Body. Hintergrund (KRITISCH): der Backend-Sync ist set-replace —
// wuerde der erste blocknote-Save die Relationen NICHT als Pills enthalten,
// wuerde er sie loeschen. Darum stellt die Migration die bestehenden
// Relationen als Pill-Paragraph voran.

import type { Playbook, ResourceBlock, ResourceLink } from '@/api/types'
import type { PlaceholderProps } from '@/components/editor/system-prompt/PlaceholderBlock'

interface PlaceholderInline {
  type: 'placeholder'
  props: PlaceholderProps
}

interface TextInline {
  type: 'text'
  text: string
  styles: Record<string, never>
}

type InlineContent = PlaceholderInline | TextInline

function paragraph(content: InlineContent[]): ResourceBlock {
  return {
    id: crypto.randomUUID(),
    type: 'paragraph',
    props: {
      textColor: 'default',
      backgroundColor: 'default',
      textAlignment: 'left',
    },
    content,
    children: [],
  } as unknown as ResourceBlock
}

// Wandelt einen Composite-Kind-Playbook in eine Playbook-Pill.
function playbookPill(child: Playbook): PlaceholderInline {
  return {
    type: 'placeholder',
    props: {
      kind: 'playbook',
      target_id: child.id,
      label: `Playbook: ${child.name}`,
    },
  }
}

// Wandelt einen Resource-Link in eine Resource-Pill. Block-Scope-Links
// tragen den Anker `<uuid>#<block_id>` und ein Section-Label.
function resourcePill(link: ResourceLink): PlaceholderInline {
  const scope = link.link_scope ?? (link.block_id !== null ? 'block' : 'resource')
  if (scope === 'block' && link.block_id !== null) {
    const section = link.section_preview ?? link.preview ?? ''
    const label =
      section.trim().length > 0
        ? `Resource: ${link.resource_name} › ${truncate(section)}`
        : `Resource: ${link.resource_name}`
    return {
      type: 'placeholder',
      props: {
        kind: 'resource',
        target_id: `${link.resource_id}#${link.block_id}`,
        label,
      },
    }
  }
  return {
    type: 'placeholder',
    props: {
      kind: 'resource',
      target_id: link.resource_id,
      label: `Resource: ${link.resource_name}`,
    },
  }
}

function truncate(text: string): string {
  const trimmed = text.trim()
  return trimmed.length > 40 ? `${trimmed.slice(0, 40)}…` : trimmed
}

// Plain-Text → Paragraphen-Bloecke (deterministisch, verlustbehaftet bei
// Formatierung — wie der Legacy-`plainTextToBlocks`).
function plainTextToParagraphs(body: string): ResourceBlock[] {
  if (body.trim() === '') return []
  return body.split(/\n\n+/).map((text) =>
    paragraph([{ type: 'text', text, styles: {} }]),
  )
}

/**
 * Baut die initialen BlockNote-Bloecke fuer die Migration plain → blocknote.
 *
 * Reihenfolge: zuerst ein Pill-Paragraph mit allen bestehenden Relationen
 * (Composes-Kinder als Playbook-Pills, Resource-Links als Resource-Pills) —
 * mit Leerzeichen getrennt —, danach der konvertierte Plain-Body. So bleiben
 * die Relationen beim ersten blocknote-Save erhalten (set-replace-Sync).
 *
 * Sind keine Relationen vorhanden, entfaellt der Pill-Paragraph.
 */
export function buildMigratedBody(
  plainBody: string,
  composes: Playbook[],
  resourceLinks: ResourceLink[],
): ResourceBlock[] {
  const pills: InlineContent[] = []
  composes.forEach((child) => {
    pills.push(playbookPill(child))
    pills.push({ type: 'text', text: ' ', styles: {} })
  })
  resourceLinks.forEach((link) => {
    pills.push(resourcePill(link))
    pills.push({ type: 'text', text: ' ', styles: {} })
  })

  const blocks: ResourceBlock[] = []
  if (pills.length > 0) {
    blocks.push(paragraph(pills))
  }
  blocks.push(...plainTextToParagraphs(plainBody))

  // BlockNote braucht mindestens einen Block.
  if (blocks.length === 0) {
    blocks.push(paragraph([{ type: 'text', text: '', styles: {} }]))
  }
  return blocks
}
