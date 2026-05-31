// PlaceholderBlock — Custom-Inline-Block fuer System-Prompt-Templates (Welle 5).
// Rendert als farbige Pill mit Lucide-Icon + Label. Read-only inline; Klick
// oeffnet den Edit-Picker via Callback (gesteuert vom SystemPromptEditor-Wrapper).
// Spec wird via `createReactInlineContentSpec` aus @blocknote/react gebaut und
// in das Custom-Schema des SystemPromptEditor eingebunden.

import { BlockNoteSchema, defaultInlineContentSpecs } from '@blocknote/core'
import { createReactInlineContentSpec } from '@blocknote/react'
import { BookOpen, Calendar, FileText, User } from 'lucide-react'

import { cn } from '@/lib/utils'

// ---------------------- Typen ------------------------------------------------

export type PlaceholderKind = 'playbook' | 'resource' | 'persona-field' | 'date'

export interface PlaceholderProps {
  kind: PlaceholderKind
  /** UUID fuer playbook/resource, Feldname fuer persona-field, '' fuer date */
  target_id: string
  /** Sichtbares Label im Editor, z. B. "Playbook: Reset-Mail" */
  label: string
}

// ---------------------- Icon + Farbe je Kind ---------------------------------

interface KindMeta {
  icon: React.FC<{ className?: string }>
  pillClass: string
  labelPrefix: string
}

const KIND_META: Record<PlaceholderKind, KindMeta> = {
  playbook: {
    icon: BookOpen,
    pillClass: 'bg-blue-100 text-blue-800 border-blue-200',
    labelPrefix: 'Playbook',
  },
  resource: {
    icon: FileText,
    pillClass: 'bg-green-100 text-green-800 border-green-200',
    labelPrefix: 'Resource',
  },
  'persona-field': {
    icon: User,
    pillClass: 'bg-purple-100 text-purple-800 border-purple-200',
    labelPrefix: 'Persona',
  },
  date: {
    icon: Calendar,
    pillClass: 'bg-amber-100 text-amber-800 border-amber-200',
    labelPrefix: 'Datum',
  },
}

// ---------------------- BlockNote Custom-Inline-Spec -------------------------

/**
 * `PlaceholderInlineSpec` ist die BlockNote-Spec fuer den Placeholder-Inline-
 * Block. Sie wird in das Custom-Schema des `SystemPromptEditor` eingebunden.
 * Die Pill rendert das Label + Icon read-only; Klick delegiert an einen
 * externen Callback, der ueber das `data-placeholder-click`-CustomEvent vom
 * Editor-Wrapper abgefangen wird.
 */
export const PlaceholderInlineSpec = createReactInlineContentSpec(
  {
    type: 'placeholder' as const,
    content: 'none' as const,
    propSchema: {
      kind: {
        default: 'playbook' as PlaceholderKind,
        values: ['playbook', 'resource', 'persona-field', 'date'] as const,
      },
      target_id: { default: '' as string },
      label: { default: '' as string },
    },
  },
  {
    render: ({ inlineContent }) => {
      const kind = inlineContent.props.kind as PlaceholderKind
      const label = inlineContent.props.label as string
      const meta = KIND_META[kind]
      const Icon = meta.icon

      return (
        <span
          data-testid={`placeholder-pill-${kind}`}
          className={cn(
            'inline-flex cursor-pointer items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs leading-none font-medium transition-opacity select-none hover:opacity-80',
            meta.pillClass,
          )}
        >
          <Icon className="h-3 w-3 shrink-0" />
          {label !== '' ? label : meta.labelPrefix}
        </span>
      )
    },
  },
)

// ---------------------- Custom-Schema ----------------------------------------

/**
 * `buildSystemPromptSchema` erzeugt das reduzierte BlockNote-Schema fuer den
 * System-Prompt-Editor: nur Paragraph, Heading (h1-h3), BulletList + der
 * Placeholder-Inline-Block. Keine Tables/Images/Audio/CheckLists.
 *
 * Hinweis: BlockNoteSchema.create mit `blockSpecs` erfordert den kompletten
 * Spec-Record — wir uebergeben nur die gewuenschten Bloecke aus
 * `defaultBlockSpecs` statt alle.
 */
export function buildSystemPromptSchema() {
  return BlockNoteSchema.create({
    inlineContentSpecs: {
      ...defaultInlineContentSpecs,
      placeholder: PlaceholderInlineSpec,
    },
  })
}

export type SystemPromptSchema = ReturnType<typeof buildSystemPromptSchema>
