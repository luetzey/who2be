// editorProfiles.test.ts — Einsatzort-Profile (Editor-Paket P2).
//
// Laeuft mit dem ECHTEN BlockNote-Kern (kein Mock): `BlockNoteEditor.create`
// baut das ProseMirror-Dokument auch in jsdom; nur die Ansicht (Mantine,
// contenteditable) braucht den Browser (dafuer: e2e/editor-profiles.spec.ts).
//
// Kern ist der Bestandsschutz: BlockNote 0.56 hat keinen Lese-Fallback fuer
// Bloecke ausserhalb des Schemas. Deshalb bleibt das Schema voll, und dieser
// Test belegt, dass alter Inhalt mit Tabelle und Bild in jedem Editor oeffnet.

import { BlockNoteEditor, BlockNoteSchema, defaultBlockSpecs } from '@blocknote/core'
import { describe, expect, it } from 'vitest'

import {
  EDITOR_PROFILES,
  isBlockAllowed,
  sanitizeBlock,
  sanitizePastedBlocks,
  snapshotBlocks,
  type LooseBlock,
} from './editorProfiles'
import { buildSystemPromptSchema } from './system-prompt/PlaceholderBlock'

const TABLE: LooseBlock = {
  id: 'bestand-tabelle',
  type: 'table',
  content: {
    type: 'tableContent',
    columnWidths: [undefined, undefined],
    rows: [
      { cells: [[{ type: 'text', text: 'Stufe', styles: {} }], [{ type: 'text', text: 'Frist', styles: {} }]] },
      { cells: [[{ type: 'text', text: 'Eins', styles: { bold: true } }], [{ type: 'text', text: '3 Tage', styles: {} }]] },
    ],
  },
}
const IMAGE: LooseBlock = {
  id: 'bestand-bild',
  type: 'image',
  props: { url: 'https://who2be.de/logo.png', name: 'Logo' },
}
const PARAGRAPH: LooseBlock = {
  id: 'bestand-absatz',
  type: 'paragraph',
  content: [{ type: 'text', text: 'Text davor', styles: {} }],
}

// Die zwei Schemata, die es in den Editoren gibt: Default (Resource, Modi,
// Tool-Hinweise) und Default + Placeholder-Pill (Vorlage, Persona, Playbook).
const SCHEMAS = {
  'default (Resource, Modi, Tool-Hinweise)': undefined,
  'mit Pills (Vorlage, Persona-Profil, Playbook)': buildSystemPromptSchema(),
} as const

function createEditor(schema: unknown, initialContent: LooseBlock[]) {
  // `as never`: Typing-Grenze der generischen Schema-API von BlockNote.
  return BlockNoteEditor.create({
    ...(schema === undefined ? {} : { schema: schema as never }),
    initialContent: initialContent as never,
  }) as unknown as BlockNoteEditor & { document: LooseBlock[] }
}

describe('Bestand: alter Inhalt mit Tabelle und Bild oeffnet in jedem Editor', () => {
  for (const [name, schema] of Object.entries(SCHEMAS)) {
    it(`Schema ${name}: Tabelle und Bild bleiben unveraendert im Dokument`, () => {
      const editor = createEditor(schema, [PARAGRAPH, TABLE, IMAGE])
      const doc = editor.document
      expect(doc.map((b) => b.type)).toEqual(['paragraph', 'table', 'image'])
      const table = doc[1].content as { rows: { cells: { content: { text: string }[] }[] }[] }
      expect(table.rows[1].cells[0].content[0].text).toBe('Eins')
      expect(doc[2].props?.url).toBe('https://who2be.de/logo.png')
    })
  }

  it('Begruendung: ein Schema ohne `table` oeffnet Bestand mit Tabelle gar nicht', () => {
    // Belegt, warum P2 das Schema NICHT verkleinert (Spec §8.1, §10).
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { table, image, ...reduced } = defaultBlockSpecs
    const schema = BlockNoteSchema.create({ blockSpecs: reduced })
    expect(() => createEditor(schema, [PARAGRAPH, TABLE])).toThrow()
  })

  it('Einfuegen-Filter laesst eine Bestandstabelle im Playbook unangetastet', () => {
    const editor = createEditor(buildSystemPromptSchema(), [PARAGRAPH, TABLE])
    const before = snapshotBlocks(editor.document)
    sanitizePastedBlocks(editor as never, EDITOR_PROFILES.playbook, before)
    expect(editor.document.map((b) => b.type)).toEqual(['paragraph', 'table'])
  })
})

describe('Einsatzort-Profile', () => {
  it('Tabelle gibt es nur in der Resource', () => {
    for (const profile of Object.values(EDITOR_PROFILES)) {
      expect(isBlockAllowed(profile, 'table')).toBe(profile.id === 'resource')
      expect(isBlockAllowed(profile, 'image')).toBe(false)
      expect(isBlockAllowed(profile, 'numberedListItem')).toBe(true)
      expect(isBlockAllowed(profile, 'quote')).toBe(true)
      expect(isBlockAllowed(profile, 'codeBlock')).toBe(true)
    }
  })

  it('H1 nur in der Vorlage, H4 nirgends', () => {
    for (const profile of Object.values(EDITOR_PROFILES)) {
      expect(isBlockAllowed(profile, 'heading', { level: 1 })).toBe(profile.id === 'system-prompt')
      expect(isBlockAllowed(profile, 'heading', { level: 2 })).toBe(true)
      expect(isBlockAllowed(profile, 'heading', { level: 4 })).toBe(false)
    }
  })
})

describe('Einfuegen: nicht erlaubte Bloecke werden zu Text, ohne Textverlust', () => {
  it('eingefuegte Tabelle im Playbook wird je Zeile ein Absatz', () => {
    const editor = createEditor(buildSystemPromptSchema(), [PARAGRAPH])
    const before = snapshotBlocks(editor.document)
    editor.insertBlocks([{ ...TABLE, id: undefined } as never], 'bestand-absatz', 'after')
    sanitizePastedBlocks(editor as never, EDITOR_PROFILES.playbook, before)

    const doc = editor.document
    expect(doc.map((b) => b.type)).toEqual(['paragraph', 'paragraph', 'paragraph'])
    const text = (b: LooseBlock) => (b.content as { text: string }[]).map((c) => c.text).join('')
    expect(text(doc[1])).toBe('Stufe | Frist')
    expect(text(doc[2])).toBe('Eins | 3 Tage')
    // Inline-Stile der Zelle bleiben erhalten.
    expect((doc[2].content as { styles: { bold?: boolean } }[])[0].styles.bold).toBe(true)
  })

  it('eingefuegte Tabelle in der Resource bleibt Tabelle', () => {
    const editor = createEditor(undefined, [PARAGRAPH])
    const before = snapshotBlocks(editor.document)
    editor.insertBlocks([{ ...TABLE, id: undefined } as never], 'bestand-absatz', 'after')
    sanitizePastedBlocks(editor as never, EDITOR_PROFILES.resource, before)
    expect(editor.document.map((b) => b.type)).toEqual(['paragraph', 'table'])
  })

  it('Einfuegen in einen leeren Absatz (gleiche ID, neuer Typ) wird erkannt', () => {
    const editor = createEditor(undefined, [{ id: 'leer', type: 'paragraph', content: [] }])
    const before = snapshotBlocks(editor.document)
    editor.updateBlock('leer', { type: 'checkListItem' } as never)
    sanitizePastedBlocks(editor as never, EDITOR_PROFILES.plain, before)
    expect(editor.document[0].type).toBe('paragraph')
  })

  it('Bild wird Link mit Adresse, ohne Adresse faellt es weg', () => {
    expect(sanitizeBlock(EDITOR_PROFILES.plain, IMAGE)).toEqual([
      {
        type: 'paragraph',
        content: [
          {
            type: 'link',
            href: 'https://who2be.de/logo.png',
            content: [{ type: 'text', text: 'Logo', styles: {} }],
          },
        ],
        children: [],
      },
    ])
    expect(sanitizeBlock(EDITOR_PROFILES.plain, { type: 'image', props: { url: '' } })).toEqual([])
  })

  it('H1 ausserhalb der Vorlage wird H2, H5 wird H3, Kinder bleiben', () => {
    const child: LooseBlock = { type: 'divider' }
    const [h1] = sanitizeBlock(EDITOR_PROFILES.playbook, {
      type: 'heading',
      props: { level: 1 },
      content: [{ type: 'text', text: 'Titel', styles: {} }],
      children: [PARAGRAPH, child],
    })
    expect(h1.props).toEqual({ level: 2 })
    expect(h1.children).toEqual([PARAGRAPH])
    const [h5] = sanitizeBlock(EDITOR_PROFILES.playbook, { type: 'heading', props: { level: 5 } })
    expect(h5.props).toEqual({ level: 3 })
  })

  it('erlaubter Block bleibt dieselbe Referenz (kein unnoetiges Ersetzen)', () => {
    expect(sanitizeBlock(EDITOR_PROFILES.playbook, PARAGRAPH)[0]).toBe(PARAGRAPH)
  })
})
