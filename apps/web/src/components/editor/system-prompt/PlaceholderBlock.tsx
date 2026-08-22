// PlaceholderBlock — Custom-Inline-Block fuer System-Prompt-Templates (Welle 5).
// Rendert als farbige Pill mit Lucide-Icon + Label. Read-only inline; Klick
// oeffnet den Edit-Picker via Callback (gesteuert vom SystemPromptEditor-Wrapper).
// Spec wird via `createReactInlineContentSpec` aus @blocknote/react gebaut und
// in das Custom-Schema des SystemPromptEditor eingebunden.

import { BlockNoteSchema, defaultInlineContentSpecs } from '@blocknote/core'
import { createReactInlineContentSpec } from '@blocknote/react'
import {
  BookOpen,
  Brain,
  Calendar,
  FileText,
  Library,
  Plug,
  Table,
  User,
  UserCog,
  Wrench,
} from 'lucide-react'

import { cn } from '@/lib/utils'
import i18n from '@/i18n'

// ---------------------- Typen ------------------------------------------------

export type PlaceholderKind =
  | 'playbook'
  | 'resource'
  | 'persona-field'
  | 'persona-ref'
  | 'playbooks-catalog'
  | 'resources-catalog'
  | 'date'
  | 'tools-overview'
  | 'tool-ref'
  | 'memory'

export interface PlaceholderProps {
  kind: PlaceholderKind
  /** UUID fuer playbook/resource, Feldname fuer persona-field, '' fuer date */
  target_id: string
  /** Sichtbares Label im Editor, z. B. "Playbook: Reset-Mail" */
  label: string
}

/**
 * Name des CustomEvents, das eine Pill beim Klick auf ihrem DOM-Knoten
 * dispatcht (bubbelt zum `bn-container`). Der Editor-Wrapper haengt dort einen
 * nativen Listener auf und oeffnet das Preview-Overlay. Entkoppelt die
 * statische BlockNote-Render-Funktion vom React-State des Wrappers.
 */
export const PLACEHOLDER_CLICK_EVENT = 'placeholder-click'

/** Detail-Payload des `placeholder-click`-CustomEvents. */
export interface PlaceholderClickDetail {
  kind: PlaceholderKind
  target_id: string
  label: string
  /**
   * Aktualisiert genau diese Pill-Instanz in-place (Wrapper um BlockNotes
   * Render-Prop `updateInlineContent`). Der Edit-Flow ruft ihn nach
   * Picker-Bestaetigung, statt die Pill zu loeschen und neu einzufuegen.
   */
  updateInlineContent: (props: PlaceholderProps) => void
}

// ---------------------- Icon + Farbe je Kind ---------------------------------

interface KindMeta {
  icon: React.FC<{ className?: string }>
  pillClass: string
  labelPrefix: string
}

// Token-basierte Pill-Tinten (siehe styles/globals.css §Pill-Kategorie-Tinten).
// bg + fg je Kind als semantische Tokens; Border via fg-Opacity — keine rohen
// Palette-Stufen (Frontend-Standards: Token statt Rohwert).
const KIND_META: Record<PlaceholderKind, KindMeta> = {
  playbook: {
    icon: BookOpen,
    pillClass: 'bg-pill-playbook text-pill-playbook-fg border-pill-playbook-fg/25',
    labelPrefix: i18n.t('editor:pill.playbook'),
  },
  resource: {
    icon: FileText,
    pillClass: 'bg-pill-resource text-pill-resource-fg border-pill-resource-fg/25',
    labelPrefix: i18n.t('editor:pill.resource'),
  },
  'persona-field': {
    icon: User,
    pillClass: 'bg-pill-persona text-pill-persona-fg border-pill-persona-fg/25',
    labelPrefix: i18n.t('editor:pill.persona'),
  },
  'persona-ref': {
    icon: UserCog,
    pillClass: 'bg-pill-persona text-pill-persona-fg border-pill-persona-fg/25',
    labelPrefix: i18n.t('editor:pill.personaRef'),
  },
  'playbooks-catalog': {
    icon: Table,
    pillClass: 'bg-pill-catalog text-pill-catalog-fg border-pill-catalog-fg/25',
    labelPrefix: i18n.t('editor:pill.playbooksCatalog'),
  },
  'resources-catalog': {
    icon: Library,
    pillClass: 'bg-pill-catalog text-pill-catalog-fg border-pill-catalog-fg/25',
    labelPrefix: i18n.t('editor:pill.resourcesCatalog'),
  },
  date: {
    icon: Calendar,
    pillClass: 'bg-pill-date text-pill-date-fg border-pill-date-fg/25',
    labelPrefix: i18n.t('editor:pill.date'),
  },
  'tools-overview': {
    icon: Wrench,
    pillClass: 'bg-pill-tools text-pill-tools-fg border-pill-tools-fg/25',
    labelPrefix: i18n.t('editor:pill.toolsOverview'),
  },
  // Teilt die `pill-tools`-Tinte mit `tools-overview` (gleiche Domaene —
  // externe/MCP-Werkzeuge) statt einen neuen Token einzufuehren (Design-
  // Sprache §13.3: Token-Aenderung nur bei genuinem Bedarf). `Plug` grenzt
  // die Einzel-Tool-Bindung visuell vom `Wrench`-Uebersichts-Pill ab.
  'tool-ref': {
    icon: Plug,
    pillClass: 'bg-pill-tools text-pill-tools-fg border-pill-tools-fg/25',
    labelPrefix: i18n.t('editor:pill.toolRef'),
  },
  // Teilt ebenfalls die `pill-tools`-Tinte (gleiche Domaene — Agenten-
  // Faehigkeiten/Kontext). `Brain` grenzt den Gedaechtnis-Hinweis visuell von
  // Wrench (Uebersicht) und Plug (Einzel-Tool) ab.
  memory: {
    icon: Brain,
    pillClass: 'bg-pill-tools text-pill-tools-fg border-pill-tools-fg/25',
    labelPrefix: i18n.t('editor:pill.memory'),
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
        values: [
          'playbook',
          'resource',
          'persona-field',
          'persona-ref',
          'playbooks-catalog',
          'resources-catalog',
          'date',
          'tools-overview',
          'tool-ref',
          'memory',
        ] as const,
      },
      target_id: { default: '' as string },
      label: { default: '' as string },
    },
  },
  {
    render: ({ inlineContent, updateInlineContent }) => {
      const kind = inlineContent.props.kind as PlaceholderKind
      const target_id = inlineContent.props.target_id as string
      const label = inlineContent.props.label as string
      const meta = KIND_META[kind]
      const Icon = meta.icon

      // Klick/Tastatur dispatcht ein bubbelndes CustomEvent, das der Editor-
      // Wrapper abfaengt, um das Preview-Overlay zu oeffnen. stopPropagation
      // verhindert, dass BlockNote den Klick als Cursor-Platzierung interpretiert.
      const dispatchPreview = (node: HTMLSpanElement) => {
        const detail: PlaceholderClickDetail = {
          kind,
          target_id,
          label,
          // In-place-Update dieser Pill — vom Edit-Flow im Wrapper genutzt.
          updateInlineContent: (props) =>
            updateInlineContent({ type: 'placeholder', props }),
        }
        node.dispatchEvent(
          new CustomEvent<PlaceholderClickDetail>(PLACEHOLDER_CLICK_EVENT, {
            detail,
            bubbles: true,
          }),
        )
      }
      const handleClick = (event: React.MouseEvent<HTMLSpanElement>) => {
        event.preventDefault()
        event.stopPropagation()
        dispatchPreview(event.currentTarget)
      }
      const handleKeyDown = (event: React.KeyboardEvent<HTMLSpanElement>) => {
        if (event.key !== 'Enter' && event.key !== ' ') return
        event.preventDefault()
        event.stopPropagation()
        dispatchPreview(event.currentTarget)
      }

      return (
        <span
          data-testid={`placeholder-pill-${kind}`}
          role="button"
          tabIndex={0}
          onClick={handleClick}
          onKeyDown={handleKeyDown}
          className={cn(
            'inline-flex cursor-pointer items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs leading-none font-medium transition-opacity select-none hover:opacity-80',
            // A11y: sichtbarer, token-basierter Fokus-Ring (Design-Sprache §13 —
            // "Focus-Ring nie wegklassen"), da die Pill fokussierbar ist.
            'ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none',
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
