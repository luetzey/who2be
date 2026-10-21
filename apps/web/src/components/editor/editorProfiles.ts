// editorProfiles.ts — was jeder Einsatzort des Editors anbietet (Editor-Paket P2).
//
// Eine Tabelle statt verstreuter Konstanten: Einsatzort → Slash-Bloecke,
// Ueberschriftenebenen, Verweis-Pills, Tabelle ja/nein. Grundlage ist die
// Design-Spec §3.2 und ADR-0058 §3.2/§3.4 (Owner-Entscheidung Editor-W1 als
// Kompromiss C+B: Tabellen nur in der Resource).
//
// Das BlockNote-Schema bleibt in allen Editoren VOLL (inkl. `table` und
// Medienbloecken). BlockNote 0.56 hat keinen Lese-Fallback: Ein Block
// ausserhalb des Schemas laesst `initialContent` scheitern, der ganze Editor
// oeffnet dann nicht. Damit Bestand lesbar bleibt, sperren die Profile nur das
// NEU-Anlegen: Slash-Menue, Formatierungsleiste und Einfuegen.
//
// Keim fuer P4 (gemeinsamer Editor-Rahmen): die feste Werkzeugleiste liest
// spaeter dieselbe Tabelle.

import type { PlaceholderKind } from './system-prompt/PlaceholderBlock'

/** Einsatzorte des Editors. `plain` = Persona-Modi und Tool-Nutzungshinweise. */
export type EditorProfileId = 'system-prompt' | 'persona-profile' | 'playbook' | 'resource' | 'plain'

/** BlockNote-Slash-Keys der Bloecke, die ein Einsatzort anbieten darf. */
export type SlashBlockKey =
  | 'paragraph'
  | 'heading'
  | 'heading_2'
  | 'heading_3'
  | 'bullet_list'
  | 'numbered_list'
  | 'quote'
  | 'code_block'
  | 'table'

export interface EditorProfile {
  id: EditorProfileId
  /** Slash-Bloecke in Menue-Reihenfolge (Spec §3.3). */
  slashKeys: readonly SlashBlockKey[]
  /** Verweis-Pills des Einsatzorts; leer = Editor ohne Verweise. */
  pillKinds: ReadonlySet<PlaceholderKind>
}

// Slash-Key → BlockNote-Blocktyp (und Ueberschriftenebene).
const SLASH_KEY_BLOCK: Record<SlashBlockKey, { type: string; level?: number }> = {
  paragraph: { type: 'paragraph' },
  heading: { type: 'heading', level: 1 },
  heading_2: { type: 'heading', level: 2 },
  heading_3: { type: 'heading', level: 3 },
  bullet_list: { type: 'bulletListItem' },
  numbered_list: { type: 'numberedListItem' },
  quote: { type: 'quote' },
  code_block: { type: 'codeBlock' },
  table: { type: 'table' },
}

// „Basis“ nach Spec §3.2: Absatz, H2, H3, Aufzaehlung, nummerierte Liste,
// Zitat, Code-Block.
const BASE: readonly SlashBlockKey[] = [
  'paragraph',
  'heading_2',
  'heading_3',
  'bullet_list',
  'numbered_list',
  'quote',
  'code_block',
]

export const EDITOR_PROFILES: Readonly<Record<EditorProfileId, EditorProfile>> = {
  // Die Vorlage ist das ganze Dokument, deshalb auch H1 („Titel“).
  'system-prompt': {
    id: 'system-prompt',
    slashKeys: ['paragraph', 'heading', ...BASE.slice(1)],
    pillKinds: new Set<PlaceholderKind>([
      'playbook',
      'resource',
      'tool-ref',
      'persona-field',
      'persona-ref',
      'date',
      'playbooks-catalog',
      'resources-catalog',
      'tools-overview',
      'memory',
    ]),
  },
  // Kein Persona-Feld/-Ref/Datum/MCP-Tools: die Persona verweist nicht auf sich.
  'persona-profile': {
    id: 'persona-profile',
    slashKeys: BASE,
    pillKinds: new Set<PlaceholderKind>([
      'playbook',
      'resource',
      'playbooks-catalog',
      'resources-catalog',
      'tool-ref',
    ]),
  },
  playbook: {
    id: 'playbook',
    slashKeys: BASE,
    pillKinds: new Set<PlaceholderKind>(['playbook', 'resource', 'tool-ref']),
  },
  // Einziger Ort mit Tabelle (Editor-W1, ADR-0058 §3.4). Pills folgen mit P9.
  resource: {
    id: 'resource',
    slashKeys: [...BASE, 'table'],
    pillKinds: new Set<PlaceholderKind>(),
  },
  // Persona-Modi und Tool-Hinweise: Basis ohne Tabelle. Pills folgen mit P9.
  plain: {
    id: 'plain',
    slashKeys: BASE,
    pillKinds: new Set<PlaceholderKind>(),
  },
}

/** Blocktypen, die der Einsatzort neu anlegen darf. */
export function allowedBlockTypes(profile: EditorProfile): Set<string> {
  return new Set(profile.slashKeys.map((key) => SLASH_KEY_BLOCK[key].type))
}

/** Ueberschriftenebenen, die der Einsatzort neu anlegen darf (aufsteigend). */
export function allowedHeadingLevels(profile: EditorProfile): number[] {
  return profile.slashKeys
    .map((key) => SLASH_KEY_BLOCK[key].level)
    .filter((level): level is number => level !== undefined)
    .sort((a, b) => a - b)
}

/** Darf der Einsatzort den Block mit diesem Typ (und dieser Ebene) neu anlegen? */
export function isBlockAllowed(
  profile: EditorProfile,
  type: string,
  props?: Record<string, unknown>,
): boolean {
  if (!allowedBlockTypes(profile).has(type)) return false
  if (type !== 'heading') return true
  return allowedHeadingLevels(profile).includes(Number(props?.level ?? 1))
}

// --- Einfuegen (Paste) --------------------------------------------------------
//
// Beim Einfuegen legt BlockNote aus HTML/Markdown jeden Blocktyp des Schemas
// an, also auch Tabellen und Bilder. Weil das Schema voll bleibt, bauen wir
// NUR die eben eingefuegten Bloecke auf den Satz des Einsatzorts um. Text geht
// dabei nicht verloren:
//   - Tabelle → je Zeile ein Absatz, Zellen mit „ | “ getrennt.
//   - Medien (Bild, Video, Audio, Datei) → Absatz mit Link auf die Adresse,
//     ohne Adresse entfaellt der Block.
//   - Trennlinie → entfaellt.
//   - Ueberschrift einer nicht erlaubten Ebene → naechste erlaubte Ebene.
//   - jeder andere Block mit Text (Checkliste, Aufklappliste, …) → Absatz mit
//     demselben Inhalt.
// Kinder werden mitgenommen und ebenso umgebaut.

/** Minimale Block-Form, wie BlockNote sie liefert und annimmt. */
export interface LooseBlock {
  id?: string
  type: string
  props?: Record<string, unknown>
  content?: unknown
  children?: LooseBlock[]
}

const MEDIA_TYPES = new Set(['image', 'video', 'audio', 'file'])

interface TableCellLike {
  content?: unknown
}
interface TableContentLike {
  type: 'tableContent'
  rows: { cells: (TableCellLike | unknown[] | string)[] }[]
}

function isTableContent(content: unknown): content is TableContentLike {
  return (
    typeof content === 'object' &&
    content !== null &&
    (content as { type?: unknown }).type === 'tableContent' &&
    Array.isArray((content as { rows?: unknown }).rows)
  )
}

function cellInline(cell: TableCellLike | unknown[] | string): unknown[] {
  if (typeof cell === 'string') return cell === '' ? [] : [{ type: 'text', text: cell, styles: {} }]
  if (Array.isArray(cell)) return cell
  return Array.isArray(cell.content) ? cell.content : []
}

function tableToParagraphs(block: LooseBlock): LooseBlock[] {
  if (!isTableContent(block.content)) return []
  const separator = { type: 'text', text: ' | ', styles: {} }
  return block.content.rows
    .map((row) => {
      const content: unknown[] = []
      row.cells.forEach((cell, index) => {
        if (index > 0) content.push(separator)
        content.push(...cellInline(cell))
      })
      return { type: 'paragraph', content }
    })
    .filter((paragraph) => paragraph.content.some((part) => part !== separator))
}

function mediaToParagraph(block: LooseBlock): LooseBlock[] {
  const url = typeof block.props?.url === 'string' ? block.props.url : ''
  if (url === '') return []
  const name = typeof block.props?.name === 'string' && block.props.name !== '' ? block.props.name : url
  return [
    {
      type: 'paragraph',
      content: [{ type: 'link', href: url, content: [{ type: 'text', text: name, styles: {} }] }],
    },
  ]
}

function nearestHeadingLevel(levels: number[], wanted: number): number {
  return levels.find((level) => level >= wanted) ?? levels[levels.length - 1]
}

/**
 * Baut einen eingefuegten Block auf den Satz des Einsatzorts um. Liefert den
 * Block unveraendert (gleiche Referenz), wenn er und alle Kinder erlaubt sind.
 * Ein Ergebnis mit mehreren Bloecken ersetzt den einen.
 */
export function sanitizeBlock(profile: EditorProfile, block: LooseBlock): LooseBlock[] {
  const children = block.children ?? []
  const sanitizedChildren = children.flatMap((child) => sanitizeBlock(profile, child))
  const childrenChanged =
    sanitizedChildren.length !== children.length ||
    sanitizedChildren.some((child, index) => child !== children[index])

  if (isBlockAllowed(profile, block.type, block.props)) {
    return childrenChanged ? [{ ...block, children: sanitizedChildren }] : [block]
  }

  let replacement: LooseBlock[]
  if (block.type === 'table') {
    replacement = tableToParagraphs(block)
  } else if (MEDIA_TYPES.has(block.type)) {
    replacement = mediaToParagraph(block)
  } else if (block.type === 'heading' && allowedHeadingLevels(profile).length > 0) {
    const level = nearestHeadingLevel(allowedHeadingLevels(profile), Number(block.props?.level ?? 1))
    replacement = [{ type: 'heading', props: { level }, content: block.content }]
  } else if (Array.isArray(block.content)) {
    replacement = [{ type: 'paragraph', content: block.content }]
  } else {
    replacement = []
  }

  if (replacement.length === 0) return sanitizedChildren
  const [first, ...rest] = replacement
  return [{ ...first, children: sanitizedChildren }, ...rest]
}

/** Minimale Editor-Schnittstelle fuer `sanitizePastedBlocks`. */
interface SanitizableEditor {
  document: LooseBlock[]
  replaceBlocks: (toRemove: string[], toInsert: LooseBlock[]) => unknown
}

/**
 * `pasteHandler` fuer `useCreateBlockNote`: BlockNote fuegt wie gewohnt ein,
 * danach baut der Handler die eben eingefuegten Bloecke auf den Satz des
 * Einsatzorts um. Der Typ ist bewusst lose — BlockNote ruft ihn mit seinem
 * generischen Editor auf.
 */
export function profilePasteHandler(profile: EditorProfile) {
  return ({
    editor,
    defaultPasteHandler,
  }: {
    editor: unknown
    defaultPasteHandler: () => boolean | undefined
  }): boolean | undefined => {
    const target = editor as SanitizableEditor
    const before = snapshotBlocks(target.document)
    const handled = defaultPasteHandler()
    sanitizePastedBlocks(target, profile, before)
    return handled
  }
}

/** Stand vor dem Einfuegen: Block-ID → Blocktyp (rekursiv). */
export type BlockSnapshot = Map<string, string>

export function snapshotBlocks(blocks: LooseBlock[], into: BlockSnapshot = new Map()): BlockSnapshot {
  for (const block of blocks) {
    if (block.id !== undefined) into.set(block.id, block.type)
    snapshotBlocks(block.children ?? [], into)
  }
  return into
}

/**
 * Baut alle Bloecke um, die eben eingefuegt wurden: neue ID, oder alte ID mit
 * neuem Typ (Einfuegen in einen leeren Absatz behaelt dessen ID). Bestehende
 * Bloecke bleiben unangetastet — auch eine Bestandstabelle in einem Playbook.
 */
export function sanitizePastedBlocks(
  editor: SanitizableEditor,
  profile: EditorProfile,
  before: BlockSnapshot,
): void {
  const walk = (blocks: LooseBlock[]) => {
    for (const block of blocks) {
      if (block.id !== undefined && before.get(block.id) !== block.type) {
        const sanitized = sanitizeBlock(profile, block)
        if (sanitized.length !== 1 || sanitized[0] !== block) {
          editor.replaceBlocks([block.id], sanitized)
        }
        continue
      }
      walk(block.children ?? [])
    }
  }
  walk(editor.document)
}
