// slashMenu.ts — Slash-Menue und BlockNote-Dictionary der Editoren.
//
// Strategie: `getDefaultReactSlashMenuItems` liefert alle Default-Items.
// Wir filtern auf die Grundbloecke des Einsatzorts (`editorProfiles.ts`) und
// ergaenzen die Verweis-Items (Playbook, Resource, Werkzeug, Persona-Feld,
// Datum, …), die beim Klick einen Picker-Callback aufrufen.
//
// BlockNote-Slash-Menu-API (v0.56): `SuggestionMenuController` akzeptiert
// `getItems: (query: string) => Promise<DefaultReactSuggestionItem[]>`.
// Custom-Items haben dieselbe Form, aber ohne `key` (das Feld ist nur fuer
// Default-Items, die ihre Texte aus dem Dictionary holen). Aufeinander
// folgende Items mit gleichem `group` zeigt BlockNote als einen Abschnitt.

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
  type LucideIcon,
} from 'lucide-react'
import { createElement } from 'react'

import type { Dictionary } from '@blocknote/core'
import { filterSuggestionItems } from '@blocknote/core/extensions'
import { de as blockNoteDe, en as blockNoteEn } from '@blocknote/core/locales'
import type { DefaultReactSuggestionItem } from '@blocknote/react'
import { getDefaultReactSlashMenuItems, SuggestionMenuController } from '@blocknote/react'

import type { PlaceholderKind, PlaceholderProps } from './PlaceholderBlock'
import { EDITOR_PROFILES, type EditorProfile } from '../editorProfiles'
import i18n, { DEFAULT_LOCALE, isLocale, type Locale } from '@/i18n'

// Callback-Typ, den der Editor-Wrapper bereitstellt.
export type PickerOpenFn = (kind: PlaceholderKind) => void

// --- BlockNote-Dictionary nach UI-Sprache (Editor-Paket P1) ----------------
//
// BlockNote bringt die eigene Oberflaeche (Slash-Menue, Formatierungsleiste,
// Seitenmenue, Link-Leiste, Platzhalter) nur ueber `dictionary` in eine andere
// Sprache; ohne Angabe ist alles englisch. Es gibt keinen globalen Default,
// deshalb uebergibt jeder Editor das Ergebnis dieser Funktion an
// `useCreateBlockNote`. Grundlage ist das mitgelieferte de/en-Dictionary des
// MPL-Kerns (`@blocknote/core/locales`). Darueber legen wir die eigenen Texte
// aus `editor:` (Design-Spec §3.3 und §7.3): Gruppe „Text“ fuer die
// Grundbloecke, unsere Titel/Beschreibungen und den Platzhalter im leeren
// Absatz.
//
// Der Editor liest das Dictionary beim Anlegen. Ein Sprachwechsel greift
// darum beim naechsten Oeffnen des Editors, nicht mitten im Schreiben —
// ein Neuaufbau wuerde ungespeicherte Eingaben verwerfen.

/** BlockNote-Keys der Grundbloecke, die in der Gruppe „Text“ stehen. */
const TEXT_BLOCK_KEYS = {
  heading: 'heading',
  heading_2: 'heading2',
  heading_3: 'heading3',
  paragraph: 'paragraph',
  bullet_list: 'bullet',
  numbered_list: 'numbered',
  quote: 'quote',
  code_block: 'code',
} as const

// Diese Grundbloecke stehen im BlockNote-Standardmenue im selben Lauf wie die
// obigen; sie bekommen nur die Gruppe, nicht eigene Texte. Ohne sie zerfiele
// die Gruppe im Resource-Editor (Standardmenue) in zwei Abschnitte.
const TEXT_GROUP_ONLY_KEYS = ['toggle_list', 'check_list', 'divider'] as const

function resolveLocale(locale: string | undefined): Locale {
  return isLocale(locale) ? locale : DEFAULT_LOCALE
}

/**
 * Baut das BlockNote-Dictionary fuer die UI-Sprache.
 *
 * `withReferences` waehlt den Platzhalter im leeren Absatz: Editoren mit
 * Verweisen (System-Prompt, Persona-Profil, Playbook) nennen sie, der
 * einfache Editor nicht. Ohne `locale` gilt die aktive UI-Sprache.
 */
export function buildEditorDictionary(
  { withReferences }: { withReferences: boolean },
  locale: string | undefined = i18n.resolvedLanguage,
): Dictionary {
  const lng = resolveLocale(locale)
  const base = lng === 'de' ? blockNoteDe : blockNoteEn
  const t = i18n.getFixedT(lng, 'editor')

  const slashMenu = { ...base.slash_menu }
  const textGroup = t('slash.group.text')
  for (const [bnKey, ownKey] of Object.entries(TEXT_BLOCK_KEYS)) {
    const key = bnKey as keyof typeof slashMenu
    slashMenu[key] = {
      ...slashMenu[key],
      title: t(`slash.block.${ownKey}.title`),
      subtext: t(`slash.block.${ownKey}.subtext`),
      group: textGroup,
    }
  }
  for (const key of TEXT_GROUP_ONLY_KEYS) {
    slashMenu[key] = { ...slashMenu[key], group: textGroup }
  }
  // Das mitgelieferte DE-Dictionary gibt `toggle_heading` die Gruppe
  // „Unterüberschrift“, den uebrigen Unterueberschriften „Unterüberschriften“.
  // BlockNote zeigt dadurch zwei Abschnitte. Wir gleichen auf die Gruppe des
  // Nachbarn an (in EN ist sie dort schon gleich).
  slashMenu.toggle_heading = { ...slashMenu.toggle_heading, group: slashMenu.toggle_heading_2.group }

  const placeholder = withReferences ? t('placeholder.withReferences') : t('placeholder.plain')

  return {
    ...base,
    slash_menu: slashMenu,
    placeholders: {
      ...base.placeholders,
      default: placeholder,
      emptyDocument: placeholder,
    },
  }
}

// Reihenfolge der Mac-Symbole nach Apple-Konvention (⌃⌥⇧⌘).
const MAC_MODIFIER_ORDER = ['⌃', '⌥', '⇧', '⌘']
const MAC_MODIFIER_SYMBOL: Record<string, string> = { Ctrl: '⌃', Alt: '⌥', Shift: '⇧', '⌘': '⌘' }

/**
 * Formatiert das Kuerzel rechts im Slash-Menue in der UI-Sprache.
 *
 * BlockNote liefert es als `Ctrl-Alt-2` bzw. auf macOS `⌘-Alt-2` und ignoriert
 * dabei das Dictionary. Spec §3.3: „Strg Alt 2“, auf macOS „⌥⌘2“.
 */
export function formatShortcutBadge(badge: string, locale?: string): string {
  const parts = badge.split('-')
  const key = parts.pop() ?? ''
  if (parts.includes('⌘')) {
    const symbols = parts.map((part) => MAC_MODIFIER_SYMBOL[part] ?? part)
    symbols.sort((a, b) => MAC_MODIFIER_ORDER.indexOf(a) - MAC_MODIFIER_ORDER.indexOf(b))
    return `${symbols.join('')}${key}`
  }
  const t = i18n.getFixedT(resolveLocale(locale ?? i18n.resolvedLanguage), 'editor')
  const names: Record<string, string> = {
    Ctrl: t('slash.key.ctrl'),
    Shift: t('slash.key.shift'),
    Alt: t('slash.key.alt'),
  }
  return [...parts.map((part) => names[part] ?? part), key].join(' ')
}

/** Uebersetzt die Kuerzel-Badges einer Item-Liste (siehe formatShortcutBadge). */
export function localizeShortcutBadges<T extends { badge?: string }>(items: T[]): T[] {
  return items.map((item) =>
    item.badge === undefined || item.badge === ''
      ? item
      : { ...item, badge: formatShortcutBadge(item.badge) },
  )
}

/**
 * Die Grundbloecke des Einsatzorts aus dem BlockNote-Standardmenue, in der
 * Reihenfolge des Profils (Spec §3.3) und mit Kuerzeln in der UI-Sprache.
 * Alles andere (Tabelle ausserhalb der Resource, Medien, Checkliste, H4–H6,
 * Emoji, …) fehlt ganz (Editor-Paket P2).
 */
function profileBlockItems(editor: unknown, profile: EditorProfile): DefaultReactSuggestionItem[] {
  // `as any` noetig, weil `getDefaultReactSlashMenuItems` den Default-Schema-
  // Editor erwartet, unser Editor aber das Custom-Placeholder-Schema traegt —
  // reine Typing-Grenze der BlockNote-Custom-Schema-API, laufzeitkompatibel.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const defaults = getDefaultReactSlashMenuItems(editor as any)
  const order: readonly string[] = profile.slashKeys
  const keyOf = (item: DefaultReactSuggestionItem) =>
    // DefaultReactSuggestionItem hat `key` nur bei Default-Items.
    (item as DefaultReactSuggestionItem & { key?: string }).key ?? ''
  return localizeShortcutBadges(
    defaults
      .filter((item) => order.includes(keyOf(item)))
      .sort((a, b) => order.indexOf(keyOf(a)) - order.indexOf(keyOf(b))),
  )
}

/**
 * Slash-Menue des Editors ohne Verweise (Resource, Modi, Tool-Hinweise). Als
 * Kind von `BlockNoteView` mit `slashMenu={false}` einsetzen. Texte und
 * Gruppen kommen aus dem Dictionary; nur die Kuerzel liefert BlockNote an ihm
 * vorbei.
 */
export function ProfileSlashMenu({ editor, profile }: { editor: unknown; profile: EditorProfile }) {
  return createElement(SuggestionMenuController, {
    triggerCharacter: '/',
    getItems: (query: string) =>
      Promise.resolve(filterSuggestionItems(profileBlockItems(editor, profile), query)),
  })
}

// --- Verweis-Items -----------------------------------------------------------

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

/** Gruppe im Slash-Menue (Spec §3.3): Verweise auf Inhalte bzw. Agent-Kontext. */
type ReferenceGroup = 'refs' | 'context'

interface ReferenceItemSpec {
  kind: PlaceholderKind
  /** Schluessel unter `editor:slash.*` (Titel, Beschreibung, Aliase). */
  key: string
  group: ReferenceGroup
  icon: LucideIcon
}

// Reihenfolge = Reihenfolge im Menue. Eine Gruppe steht zusammen, sonst zeigt
// BlockNote ihre Ueberschrift zweimal.
const REFERENCE_ITEMS: readonly ReferenceItemSpec[] = [
  { kind: 'playbook', key: 'playbook', group: 'refs', icon: BookOpen },
  { kind: 'resource', key: 'resource', group: 'refs', icon: FileText },
  { kind: 'tool-ref', key: 'toolRef', group: 'refs', icon: Plug },
  { kind: 'persona-field', key: 'personaField', group: 'context', icon: User },
  { kind: 'persona-ref', key: 'personaRef', group: 'context', icon: UserCog },
  { kind: 'date', key: 'date', group: 'context', icon: Calendar },
  { kind: 'playbooks-catalog', key: 'playbooksCatalog', group: 'context', icon: Table },
  { kind: 'resources-catalog', key: 'resourcesCatalog', group: 'context', icon: Library },
  { kind: 'tools-overview', key: 'toolsOverview', group: 'context', icon: Wrench },
  { kind: 'memory', key: 'memory', group: 'context', icon: Brain },
]

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
  // Einsatzort (editorProfiles.ts): welche Grundbloecke und welche Verweis-
  // Pills das Menue anbietet. Das gemeinsame Schema (alle Kinds, alle Bloecke)
  // bleibt unveraendert — wir filtern nur die Slash-Items. Leere Gruppen
  // fallen damit von selbst weg.
  profile: EditorProfile = EDITOR_PROFILES['system-prompt'],
): DefaultReactSuggestionItem[] {
  // Grundbloecke; Texte und Gruppe „Text“ kommen aus dem Dictionary.
  const filtered = profileBlockItems(editor, profile)

  const groupLabel: Record<ReferenceGroup, string> = {
    refs: i18n.t('editor:slash.group.refs'),
    context: i18n.t('editor:slash.group.context'),
  }

  const customItems: DefaultReactSuggestionItem[] = REFERENCE_ITEMS.filter((spec) =>
    profile.pillKinds.has(spec.kind),
  ).map((spec) => ({
    title: i18n.t(`editor:slash.${spec.key}.title`),
    subtext: i18n.t(`editor:slash.${spec.key}.subtext`),
    group: groupLabel[spec.group],
    icon: createElement(spec.icon, { size: 18 }),
    onItemClick: () => {
      openPicker(spec.kind)
    },
    aliases: aliasesFor(spec.key),
  }))

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
