import { useMemo, useRef } from 'react'
import { BlockNoteView } from '@blocknote/mantine'
import {
  BasicTextStyleButton,
  BlockTypeSelect,
  blockTypeSelectItems,
  CreateLinkButton,
  DragHandleMenu,
  FormattingToolbar,
  FormattingToolbarController,
  RemoveBlockItem,
  SideMenu,
  SideMenuController,
  TableColumnHeaderItem,
  TableRowHeaderItem,
  useBlockNoteEditor,
  useCreateBlockNote,
  useDictionary,
} from '@blocknote/react'
import type { Block, PartialBlock } from '@blocknote/core'

import { useTheme } from '@/app/theme-context'
import type { ResourceBlock } from '@/api/types'

import {
  EDITOR_PROFILES,
  isBlockAllowed,
  profilePasteHandler,
  type EditorProfile,
  type EditorProfileId,
} from './editorProfiles'
import { buildEditorDictionary, ProfileSlashMenu } from './system-prompt/slashMenu'

// --- Formatierungsleiste und Seitenmenue je Einsatzort (Editor-Paket P2) -----
//
// Die schwebende BlockNote-Leiste zeigt nur, was sich als Markdown abbilden
// laesst (ADR-0058 §3.2, Spec §3.1): Blocktyp, Fett, Kursiv, Code, Link. Es
// fehlen Unterstreichen, Durchgestrichen als Knopf (bleibt per Kuerzel),
// Ausrichten, Farben, Einruecken/Ausruecken (bleibt per Tab), Zellen
// verbinden und die Datei-Knoepfe. Die Blocktyp-Auswahl bietet nur die Bloecke
// des Einsatzorts an. Das Seitenmenue verliert „Farben“.
// Als Kinder von `BlockNoteView` mit `formattingToolbar={false}` und
// `sideMenu={false}` einsetzen.

export function ProfileFormattingToolbar({ profile }: { profile: EditorProfile }) {
  const editor = useBlockNoteEditor()
  const items = useMemo(
    () => blockTypeSelectItems(editor).filter((item) => isBlockAllowed(profile, item.type, item.props)),
    [editor, profile],
  )
  return (
    <FormattingToolbarController
      formattingToolbar={() => (
        <FormattingToolbar>
          <BlockTypeSelect key="blockTypeSelect" items={items} />
          <BasicTextStyleButton key="boldStyleButton" basicTextStyle="bold" />
          <BasicTextStyleButton key="italicStyleButton" basicTextStyle="italic" />
          <BasicTextStyleButton key="codeStyleButton" basicTextStyle="code" />
          <CreateLinkButton key="createLinkButton" />
        </FormattingToolbar>
      )}
    />
  )
}

export function ProfileSideMenu() {
  return (
    <SideMenuController
      sideMenu={(props) => (
        <SideMenu {...props} dragHandleMenu={ProfileDragHandleMenu} />
      )}
    />
  )
}

function ProfileDragHandleMenu() {
  const dict = useDictionary()
  return (
    <DragHandleMenu>
      <RemoveBlockItem>{dict.drag_handle.delete_menuitem}</RemoveBlockItem>
      {/* Kopfzeile/-spalte gibt es nur an Tabellen; sonst rendern sie nichts. */}
      <TableRowHeaderItem>{dict.drag_handle.header_row_menuitem}</TableRowHeaderItem>
      <TableColumnHeaderItem>{dict.drag_handle.header_column_menuitem}</TableColumnHeaderItem>
    </DragHandleMenu>
  )
}

interface BlockNoteEditorProps {
  initialBlocks: ResourceBlock[]
  editable?: boolean
  onChange?: (blocks: ResourceBlock[]) => void
  /** Einsatzort (editorProfiles.ts). `resource` ist der einzige mit Tabelle. */
  profile?: Extract<EditorProfileId, 'resource' | 'plain'>
}

// Geteilte BlockNote-Insel (ADR-0022) fuer Resource-Body, Persona-Modi und
// Tool-Hinweise. `portalElements.default = document.body` hebt Slash-/Side-/Drag-Menue
// auf `document.body`, damit kein `overflow:hidden`-Ancestor (Card, Section)
// das Popover beschneidet (Phase 3-fixes Track 2). Theme-Surfaces fuer die
// Popover-Layer kommen aus styles/globals.css §BlockNote-Insel.
//
// Das Schema bleibt der volle BlockNote-Default: Bestand mit Tabelle oder Bild
// muss auch in Modi und Tool-Hinweisen oeffnen (kein Lese-Fallback in
// BlockNote 0.56). Das Profil sperrt nur das Neu-Anlegen.
export function BlockNoteEditor({
  initialBlocks,
  editable = true,
  onChange,
  profile: profileId = 'plain',
}: BlockNoteEditorProps) {
  const { resolved } = useTheme()
  const profile = EDITOR_PROFILES[profileId]
  const editor = useCreateBlockNote({
    initialContent:
      initialBlocks.length > 0 ? (initialBlocks as unknown as PartialBlock[]) : undefined,
    // BlockNote-Oberflaeche in der UI-Sprache (Editor-Paket P1).
    dictionary: buildEditorDictionary({ withReferences: false }),
    // Eingefuegte Tabellen/Medien ausserhalb der Resource werden zu Text (P2).
    pasteHandler: profilePasteHandler(profile),
  })
  const portalElements = useMemo(() => ({ default: document.body }), [])
  // Welle 4-Fix: BlockNote normalisiert beim Mount sein Dokument (ergaenzt
  // Block-IDs, Default-Props, leeren Standard-Paragraph). Dabei feuert
  // `onChange` einmal mit dem normalisierten Stand, der NICHT identisch zu
  // `initialBlocks` ist. Wuerden wir das durchreichen, wertet der
  // `useAutoSaveDraft`-Hook im Parent das als User-Edit und PATCH-t den
  // Draft sofort — beim reinen Oeffnen einer Active-Version legt der Server
  // dadurch eine neue Draft-Version an, ohne dass der User getippt hat.
  // Loesung: `onChange` erst propagieren, nachdem der Editor mindestens
  // einmal vom User fokussiert wurde (Klick / Tab-Stop). Programmatische
  // Mount-Normalisierungen werden geschluckt.
  const userInteractedRef = useRef(false)

  return (
    <div
      className="bn-container rounded-md border bg-background py-2"
      data-testid="blocknote-editor"
      data-editor-profile={profile.id}
      onFocusCapture={() => {
        userInteractedRef.current = true
      }}
    >
      <BlockNoteView
        editor={editor}
        editable={editable}
        theme={resolved}
        portalElements={portalElements}
        onChange={() => {
          if (!userInteractedRef.current) {
            return
          }
          onChange?.(editor.document as unknown as ResourceBlock[])
        }}
        // Slash-Menue, Leiste und Seitenmenue nach Einsatzort (P2).
        slashMenu={false}
        formattingToolbar={false}
        sideMenu={false}
      >
        <ProfileSlashMenu editor={editor} profile={profile} />
        <ProfileFormattingToolbar profile={profile} />
        <ProfileSideMenu />
      </BlockNoteView>
    </div>
  )
}

export type { Block }
