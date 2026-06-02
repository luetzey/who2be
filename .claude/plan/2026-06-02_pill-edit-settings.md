# Plan: Pill-Einstellungen (Edit-in-place) im BlockNote-Editor

**Stand:** 2026-06-02 · living document · **WP-1…WP-5 umgesetzt** (Frontend,
lint/tsc/test/build grün, 287 Vitest-Tests)
**Ziel:** Eine bestehende Inline-Pill lässt sich **bearbeiten** — Ziel/Parameter
ändern (Playbook/Resource neu wählen, Resource-Section-Anker setzen/entfernen,
Persona-Feld umstellen, Datums-Format wechseln) — und die Pill wird **in-place**
aktualisiert (kein Löschen + Neu-Einfügen). Gilt in allen Editoren mit Pills
(`SystemPromptEditor` + `PlaybookBodyEditor`), nur im editierbaren Modus.

Baut auf dem bereits gemergten Preview-Overlay auf (PR #85/#86) und der
vorhandenen Picker-Infrastruktur.

## Outcome / Completion-Condition (messbar)

- Im editierbaren Editor öffnet eine Edit-Aktion an der Pill den passenden
  Picker **vorbefüllt** mit den aktuellen Werten; bei Bestätigung ändert sich
  die Pill in-place (gleiche Position, neue `props`), `onChange` feuert.
- Read-only-Editoren (Detail-Ansichten) bieten **keine** Edit-Aktion (nur Preview).
- `tools-overview` (parameterlos) bietet keine Edit-Aktion.
- DoD Frontend grün: `npm run lint` (0 errors) · `npx tsc --noEmit` ·
  `npm test` · `npm run build`. **Kein Backend-Change** (Edit nutzt die schon
  vorhandenen List-Endpoints der Picker).

## Schlüssel-Erkenntnis (Recherche)

BlockNote `@blocknote/react@0.51`: Die Render-Props eines Custom-Inline-Specs
(`ReactCustomInlineContentRenderProps`) enthalten **`updateInlineContent(update)`**
— aktualisiert genau diese Inline-Instanz in-place. Damit ist Edit-in-place ohne
Positions-Suche möglich; die Pill baut beim Render einen schlanken Callback
`(props) => updateInlineContent({ type: 'placeholder', props })` und reicht ihn
nach außen.

## Design-Entscheidung (Fork 1 entschieden: A — Button im Overlay)

**Fork 1 — Einstieg/Trigger (UX): ✅ ENTSCHIEDEN → A (2026-06-02, User-OK).**
- **A (empfohlen):** „Bearbeiten"-Button im bestehenden Preview-Overlay (nur
  sichtbar wenn `editable` und Kind ≠ `tools-overview`). Eine kohärente
  Pill-Interaktion (Klick → Overlay: Vorschau + Bearbeiten), keine
  konkurrierende Klick-Semantik, wiederverwendet das gebaute Overlay.
- **B:** Doppelklick = Edit, Einfachklick = Preview. Kompakter, aber
  Doppelklick auf Inline-Atom ist wenig diskoverabel und kollidiert leicht mit
  Text-Selektion.
- **C:** Kleines Stift-Icon in der Pill (nur `editable`). Direkt sichtbar, aber
  vergrößert die Pill und verrauscht den Lesefluss im Editor.

**Fork 2 — Update-Mechanik (intern, weniger sichtbar):**
- **(empfohlen)** `updateInlineContent`-Callback im `placeholder-click`-Event-
  Detail mittragen; der Wrapper ruft ihn bei Picker-Bestätigung. Simpel,
  reuse der zentralen Picker-Instanzen.
- Alternativen: Modul-Registry (Pill-`updateInlineContent` per generierter ID),
  oder per-Pill gemounteter Picker. Beide aufwändiger/verrauschter.

→ **Plan unten ist auf A + empfohlene Mechanik geschrieben.** Bei anderer
Trigger-Wahl ändern sich v. a. WP-3/WP-4.

## Arbeitspakete (datei-bezogen)

### WP-1 — Pill: Edit-Callback nach außen reichen
`components/editor/system-prompt/PlaceholderBlock.tsx`
- `PlaceholderClickDetail` um `updateInlineContent: (props: PlaceholderProps) => void`
  erweitern.
- In der `render`-Funktion `updateInlineContent` aus den Render-Props ziehen und
  beim Dispatch des `placeholder-click`-Events mitgeben:
  `updateInlineContent: (props) => updateInlineContent({ type: 'placeholder', props })`.
- Keine Änderung am Klick-Verhalten selbst (weiterhin ein Event).

### WP-2 — Picker: Vorbefüll-/Edit-Modus
Alle vier Picker in `components/editor/system-prompt/pickers/`:
- Optionales Prop `initial?: PlaceholderProps` ergänzen.
- Bei `open && initial`: Vorauswahl setzen statt leer (statt des bisherigen
  Reset-auf-leer im `useEffect`).
  - `PlaybookPicker`: Playbook mit `id === initial.target_id` vorselektieren.
  - `ResourcePicker`: `target_id` an `#` splitten → Resource vorselektieren,
    bei vorhandenem `block_id` den Anker-Heading vorselektieren (nutzt die
    schon vorhandene Heading-Lade-Logik).
  - `PersonaFieldPicker` / `DateFormatPicker`: Radio-Option per `target_id`
    vorbelegen.
- Confirm-Button-Label kontextabhängig: „Einfuegen" (neu) vs. „Aktualisieren"
  (`initial` gesetzt). Reines Label, Confirm-Payload bleibt `PlaceholderProps`.
- Fehlt das vorbefüllte Ziel in der Liste (gelöscht/inaktiv): keine Vorauswahl,
  User wählt neu — defensiv, kein Crash.

### WP-3 — Preview-Overlay: Edit-Einstieg
`components/editor/system-prompt/PlaceholderPreviewDialog.tsx`
- Neue Props `editable?: boolean` und `onEdit?: (detail: PlaceholderClickDetail) => void`.
- Im `DialogFooter` einen „Bearbeiten"-Button rendern, **wenn** `editable`
  und `active.kind !== 'tools-overview'`. Klick: Overlay schließen +
  `onEdit(active)` mit dem aktuellen Detail (inkl. `updateInlineContent`).
- Read-only/`tools-overview`: kein Button (Verhalten unverändert).

### WP-4 — Wrapper: Edit-Flow verdrahten
`components/editor/system-prompt/SystemPromptEditor.tsx`
und `features/playbooks/components/PlaybookBodyEditor.tsx` (analog):
- `<PlaceholderPreviewDialog>` zusätzlich `editable={editable}` und
  `onEdit={handleStartEdit}` übergeben.
- Neuer State `pendingEdit: { detail: PlaceholderClickDetail } | null`.
- `handleStartEdit(detail)`: `pendingEdit` setzen + passenden Picker öffnen
  (`setOpenPicker(detail.kind)`), Picker erhält `initial={ kind, target_id, label }`.
- `handlePickerConfirm(props)` verzweigen:
  - wenn `pendingEdit`: `pendingEdit.detail.updateInlineContent(props)` aufrufen,
    `pendingEdit` zurücksetzen, Picker schließen (statt `insertInlineContent`).
  - sonst: bestehender Insert-Pfad.
- `handlePickerCancel`: `pendingEdit` ebenfalls zurücksetzen.
- `PlaybookBodyEditor`: nur `playbook`/`resource`-Picker vorhanden — Edit für
  andere Kinds kann dort nicht entstehen (nur diese Pills existieren); defensiv
  über das bestehende `ALLOWED_KINDS`-Gate.

### WP-5 — Tests
- `pickers/*.test.tsx`: je Picker ein Edit-Fall — `initial` vorbefüllt, Confirm
  liefert geänderte `props`, Button-Label „Aktualisieren". ResourcePicker:
  Edit mit `<uuid>#<block_id>` befüllt Resource + Anker.
- `PlaceholderPreviewDialog.test.tsx`: „Bearbeiten" nur bei `editable`; nicht
  bei `tools-overview`; Klick ruft `onEdit` mit dem Detail.
- `PlaceholderBlock.test.tsx` / Wrapper: `placeholder-click`-Detail trägt eine
  `updateInlineContent`-Funktion; Edit-Confirm ruft sie statt Insert
  (Mock-Editor / Mock-Callback).

## Edge-Cases / Risiken
- **Gelöschtes Ziel:** Vorbefüllung findet das alte Target nicht → unselektiert,
  Hinweis im Picker, Neuauswahl möglich.
- **Funktion im Event-Detail:** `updateInlineContent` wird durchs CustomEvent
  getragen (same-realm, unkritisch); Typ `PlaceholderClickDetail` deckt es ab.
- **A11y:** „Bearbeiten" als `Button`-Primitive (Fokusring inklusive); Picker
  sind bestehende Dialog-Primitives.
- **Kein Backend:** Edit ändert nur Editor-Inhalt; Persistenz läuft über den
  bestehenden Body-Save (`onChange` → Draft/Update), der Pills bereits synct.

## Out of Scope
- Live-Vorschau *im* Picker (nur Auswahl). Preview bleibt separat über das
  Overlay.
- Neue Pill-Kinds, neue Resolver, Persona-Kontext-Auswahl für `persona-field`.
