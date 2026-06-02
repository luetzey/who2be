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

import { BookOpen, Calendar, FileText, Table, User, UserCog, Wrench } from 'lucide-react'
import { createElement } from 'react'

import type { DefaultReactSuggestionItem } from '@blocknote/react'
import { getDefaultReactSlashMenuItems } from '@blocknote/react'

import type { PlaceholderKind, PlaceholderProps } from './PlaceholderBlock'

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
      title: 'Playbook',
      subtext:
        'Bettet ein Playbook fest ein — immer geladen, nicht getriggert. ' +
        'Bei einem Composite-Playbook wird die vollständige Sub-Playbook-Sequenz gerendert.',
      group: 'Placeholder',
      icon: createElement(BookOpen, { size: 18 }),
      onItemClick: () => {
        openPicker('playbook')
      },
      aliases: ['playbook', 'pb', 'standard'],
    },
    {
      kind: 'resource',
      title: 'Resource',
      subtext: 'Verlinkt eine spezifische Resource',
      group: 'Placeholder',
      icon: createElement(FileText, { size: 18 }),
      onItemClick: () => {
        openPicker('resource')
      },
      aliases: ['resource', 'res', 'datei'],
    },
    {
      kind: 'persona-field',
      title: 'Persona-Feld',
      subtext:
        'Bettet ein Persona-Feld ein: Name, Beschreibung, das vollständige Profil ' +
        '(inkl. Body und Modi) oder nur die Modi — empfohlen für den System-Prompt-Bootstrap.',
      group: 'Placeholder',
      icon: createElement(User, { size: 18 }),
      onItemClick: () => {
        openPicker('persona-field')
      },
      aliases: ['persona', 'name', 'beschreibung', 'profil', 'profile', 'modi', 'modes'],
    },
    {
      kind: 'persona-ref',
      title: 'Persona laden (MCP)',
      subtext:
        'Bettet keinen Inhalt ein, sondern weist den Agenten an, seine Persona zur ' +
        'Laufzeit selbst via get_persona(...) zu laden und ihre Modi anzuwenden.',
      group: 'Placeholder',
      icon: createElement(UserCog, { size: 18 }),
      onItemClick: () => {
        openPicker('persona-ref')
      },
      aliases: ['persona laden', 'get_persona', 'mcp persona', 'persona-ref', 'referenz'],
    },
    {
      kind: 'playbooks-catalog',
      title: 'Playbook-Katalog',
      subtext:
        'Fügt eine Tabelle der zugeordneten Playbooks ein (Name, Trigger, Aufruf, ' +
        'Beschreibung) — briefs den Agenten, was er wann via fetch_playbook(...) laden kann.',
      group: 'Placeholder',
      icon: createElement(Table, { size: 18 }),
      onItemClick: () => {
        openPicker('playbooks-catalog')
      },
      aliases: ['katalog', 'playbooks', 'tabelle', 'uebersicht', 'catalog'],
    },
    {
      kind: 'date',
      title: 'Datum',
      subtext: 'Aktuelles Datum beim Rendern',
      group: 'Placeholder',
      icon: createElement(Calendar, { size: 18 }),
      onItemClick: () => {
        openPicker('date')
      },
      aliases: ['datum', 'date', 'heute'],
    },
    {
      kind: 'tools-overview',
      title: 'MCP-Tools',
      subtext: 'Fuegt eine Uebersicht der MCP-Werkzeuge ein, die der Agent nutzen kann',
      group: 'Placeholder',
      icon: createElement(Wrench, { size: 18 }),
      onItemClick: () => {
        openPicker('tools-overview')
      },
      aliases: ['mcp', 'tools', 'werkzeuge', 'tools-overview'],
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
