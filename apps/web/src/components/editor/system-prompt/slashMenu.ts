// slashMenu.ts — Custom-Slash-Menue fuer den SystemPromptEditor (Welle 5).
//
// Strategie: `getDefaultReactSlashMenuItems` liefert alle Default-Items.
// Wir filtern auf Paragraph, Heading, Bulleted-List und ergaenzen vier
// Custom-Items (Playbook, Resource, Persona-Feld, Datum), die beim Klick
// einen Picker-Modal-Callback aufrufen.
//
// BlockNote-Slash-Menu-API (v0.51): `SuggestionMenuController` akzeptiert
// `getItems: (query: string) => Promise<DefaultReactSuggestionItem[]>`.
// Custom-Items haben dieselbe Form, aber ohne `key` (das Feld ist nur fuer
// Default-Items, die i18n-Lookup machen). Wir nutzen `title` + `group` als
// visuelle Identitaet.

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
import { createElement } from 'react'

import type { DefaultReactSuggestionItem } from '@blocknote/react'
import { getDefaultReactSlashMenuItems } from '@blocknote/react'

import type { PlaceholderKind, PlaceholderProps } from './PlaceholderBlock'
import i18n from '@/i18n'

// Erlaubte Default-Item-Keys (Paragraph, Heading, Bulleted-List).
const ALLOWED_KEYS = new Set(['paragraph', 'heading_1', 'heading_2', 'heading_3', 'bullet_list'])

// Callback-Typ, den der Editor-Wrapper bereitstellt.
export type PickerOpenFn = (kind: PlaceholderKind) => void

/**
 * Gibt die gefilterte + erweiterte Item-Liste fuer das Slash-Menue zurueck.
 * Muss in eine `getItems`-Closure gepackt werden:
 *   `getItems={(q) => Promise.resolve(buildSlashMenuItems(editor, openPicker, q))}`
 *
 * `editor` ist als `unknown` getypt, weil der Custom-Schema-Typ zu komplex
 * fuer direkte Zuweisung an den generischen BlockNoteEditor-Typ ist.
 * `getDefaultReactSlashMenuItems` akzeptiert intern `any`.
 */
// Slash-Menu-Aliase sind SUCHEINGABEN — was der Nutzer tippt, um ein Item zu
// finden. Sie muessen darum der UI-Sprache folgen (ein englischer Nutzer tippt
// „memory", kein „gedaechtnis"). Im Locale-JSON stehen sie als
// Komma-Liste, damit Uebersetzer keine JSON-Arrays pflegen muessen.
function aliasesFor(key: string): string[] {
  return i18n
    .t(`editor:slash.aliases.${key}`)
    .split(',')
    .map((alias) => alias.trim())
    .filter((alias) => alias !== '')
}

export function buildSlashMenuItems(
  editor: unknown,
  openPicker: PickerOpenFn,
  query: string,
  // Optionaler Filter: nur Placeholder-Items dieser Kinds anbieten. Ohne
  // Param bleibt das Verhalten wie bisher (alle Items). Der Playbook-Body-
  // Editor uebergibt z. B. `new Set(['playbook', 'resource'])`, damit dort
  // keine Persona-Feld-/Datum-/MCP-Tools-Pills angeboten werden. Das
  // gemeinsame PlaceholderBlock-Schema (alle Kinds) bleibt unveraendert —
  // wir filtern nur die Slash-Items.
  allowedKinds?: Set<PlaceholderKind>,
): DefaultReactSuggestionItem[] {
  // `as any` noetig, weil `getDefaultReactSlashMenuItems` den Default-Schema-
  // Editor erwartet, unser Editor aber das Custom-Placeholder-Schema traegt —
  // reine Typing-Grenze der BlockNote-Custom-Schema-API, laufzeitkompatibel.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const defaults = getDefaultReactSlashMenuItems(editor as any)

  // Gefilterte Defaults
  const filtered = defaults.filter((item) => {
    // DefaultReactSuggestionItem hat `key` nur bei Default-Items. Wir filtern
    // ueber `title` weil `key` nicht im React-Typ sicher ist.
    const asAny = item as DefaultReactSuggestionItem & { key?: string }
    return asAny.key !== undefined && ALLOWED_KEYS.has(asAny.key)
  })

  // Custom-Placeholder-Items. `kind` traegt das Filter-Kriterium fuer
  // `allowedKinds`; es wird unten wieder abgestreift (BlockNote kennt kein
  // `kind`-Feld auf SuggestionItems).
  const customItemsWithKind: (DefaultReactSuggestionItem & {
    kind: PlaceholderKind
  })[] = [
    {
      kind: 'playbook',
      title: i18n.t('editor:slash.playbook.title'),
      subtext: i18n.t('editor:slash.playbook.subtext'),
      group: i18n.t('editor:slash.group'),
      icon: createElement(BookOpen, { size: 18 }),
      onItemClick: () => {
        openPicker('playbook')
      },
      aliases: aliasesFor('playbook'),
    },
    {
      kind: 'resource',
      title: i18n.t('editor:slash.resource.title'),
      subtext: i18n.t('editor:slash.resource.subtext'),
      group: i18n.t('editor:slash.group'),
      icon: createElement(FileText, { size: 18 }),
      onItemClick: () => {
        openPicker('resource')
      },
      aliases: aliasesFor('resource'),
    },
    {
      kind: 'persona-field',
      title: i18n.t('editor:slash.personaField.title'),
      subtext: i18n.t('editor:slash.personaField.subtext'),
      group: i18n.t('editor:slash.group'),
      icon: createElement(User, { size: 18 }),
      onItemClick: () => {
        openPicker('persona-field')
      },
      aliases: aliasesFor('personaField'),
    },
    {
      kind: 'persona-ref',
      title: i18n.t('editor:slash.personaRef.title'),
      subtext: i18n.t('editor:slash.personaRef.subtext'),
      group: i18n.t('editor:slash.group'),
      icon: createElement(UserCog, { size: 18 }),
      onItemClick: () => {
        openPicker('persona-ref')
      },
      aliases: aliasesFor('personaRef'),
    },
    {
      kind: 'playbooks-catalog',
      title: i18n.t('editor:slash.playbooksCatalog.title'),
      subtext: i18n.t('editor:slash.playbooksCatalog.subtext'),
      group: i18n.t('editor:slash.group'),
      icon: createElement(Table, { size: 18 }),
      onItemClick: () => {
        openPicker('playbooks-catalog')
      },
      aliases: aliasesFor('playbooksCatalog'),
    },
    {
      kind: 'resources-catalog',
      title: i18n.t('editor:slash.resourcesCatalog.title'),
      subtext: i18n.t('editor:slash.resourcesCatalog.subtext'),
      group: i18n.t('editor:slash.group'),
      icon: createElement(Library, { size: 18 }),
      onItemClick: () => {
        openPicker('resources-catalog')
      },
      aliases: aliasesFor('resourcesCatalog'),
    },
    {
      kind: 'date',
      title: i18n.t('editor:slash.date.title'),
      subtext: i18n.t('editor:slash.date.subtext'),
      group: i18n.t('editor:slash.group'),
      icon: createElement(Calendar, { size: 18 }),
      onItemClick: () => {
        openPicker('date')
      },
      aliases: aliasesFor('date'),
    },
    {
      kind: 'tools-overview',
      title: i18n.t('editor:slash.toolsOverview.title'),
      subtext: i18n.t('editor:slash.toolsOverview.subtext'),
      group: i18n.t('editor:slash.group'),
      icon: createElement(Wrench, { size: 18 }),
      onItemClick: () => {
        openPicker('tools-overview')
      },
      aliases: aliasesFor('toolsOverview'),
    },
    {
      kind: 'memory',
      title: i18n.t('editor:slash.memory.title'),
      subtext: i18n.t('editor:slash.memory.subtext'),
      group: i18n.t('editor:slash.group'),
      icon: createElement(Brain, { size: 18 }),
      onItemClick: () => {
        openPicker('memory')
      },
      aliases: aliasesFor('memory'),
    },
    {
      kind: 'tool-ref',
      title: i18n.t('editor:slash.toolRef.title'),
      subtext: i18n.t('editor:slash.toolRef.subtext'),
      group: i18n.t('editor:slash.group'),
      icon: createElement(Plug, { size: 18 }),
      onItemClick: () => {
        openPicker('tool-ref')
      },
      aliases: aliasesFor('toolRef'),
    },
  ]

  // `allowedKinds` filtert die Custom-Items; `kind` wird danach abgestreift
  // (BlockNote kennt kein `kind`-Feld auf SuggestionItems).
  const customItems: DefaultReactSuggestionItem[] = customItemsWithKind
    .filter((item) => allowedKinds === undefined || allowedKinds.has(item.kind))
    .map((item) => {
      const rest = { ...item } as Partial<typeof item>
      delete rest.kind
      return rest as DefaultReactSuggestionItem
    })

  const allItems = [...filtered, ...customItems]

  // Filtern nach Query (case-insensitive auf title + aliases)
  if (query.trim() === '') return allItems
  const q = query.toLowerCase()
  return allItems.filter((item) => {
    if (item.title.toLowerCase().includes(q)) return true
    if (item.aliases?.some((a) => a.toLowerCase().includes(q))) return true
    return false
  })
}

// Re-export des Picker-Callback-Typs und PlaceholderProps fuer Konsumenten.
export type { PlaceholderKind, PlaceholderProps }
