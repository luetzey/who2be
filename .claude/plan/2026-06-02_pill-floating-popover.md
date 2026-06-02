# Plan: Pill-Overlays als schwebende Popover (nicht-blockierend)

**Stand:** 2026-06-02 · living document · **WP-1…WP-5 umgesetzt** (Frontend,
lint 0 errors / tsc -b / 287 Tests / build grün)
**Ziel:** Vorschau- und Bearbeiten-Overlay der Pills sind keine blockierenden
modalen Dialoge mehr, sondern an der Pill (bzw. am Caret beim Einfügen)
verankerte, nicht-blockierende **Popover** — wie BlockNotes Slash-Menü.
Korrigiert die Elevation (Layer-2 statt Layer-3, design-language §6) und füllt
die fehlende `Popover`-Primitive-Lücke.

Entscheidung (User-OK 2026-06-02): **Vorschau + Bearbeiten schwebend**, gebaut
mit **Radix Popover** (`modal={false}`).

## Outcome / Completion-Condition (messbar)

- Klick auf Pill → Vorschau erscheint als schwebende Sprechblase an der Pill,
  ohne Backdrop; Außenklick/Escape/Scroll schließt sie; Editor bleibt bedienbar.
- „Bearbeiten" → Picker erscheint als schwebendes Panel an derselben Pill.
- Slash-Einfügen → Picker erscheint als schwebendes Panel am Caret.
- DoD Frontend grün: lint (0 errors) · tsc · test · build.

## Recherche (verifiziert)

- `@radix-ui/react-popover@^1.1.15` installiert (WP-0 erledigt).
- `PopoverAnchor` akzeptiert `virtualRef: RefObject<Measurable>` —
  ein DOM-Knoten (Pill) **oder** ein virtuelles `{ getBoundingClientRect }`
  (Caret) erfüllt `Measurable`. Damit ein **gemeinsamer Anker** für alle Panels.
- Radix Popover ist `modal={false}` per Default → nicht-blockierend, kein
  Scroll-Lock/Focus-Trap, Dismiss (Außenklick/Escape) eingebaut; Content im
  Portal (kein overflow-Clipping — löst zugleich den Grund, warum Picker bisher
  Dialoge waren).
- Test-Setup polyfillt bereits `ResizeObserver`/`DOMRect` (Radix-Popper-tauglich).

## Anker-Modell (Kern)

Der Editor-Wrapper hält **einen** `anchorRef: RefObject<Measurable | null>`,
geteilt von Preview + allen Pickern (nur eines ist gleichzeitig offen):
- **Klick/Edit:** Preview-Listener setzt `anchorRef.current = event.target`
  (die Pill). „Bearbeiten" lässt den Anker stehen → Picker erscheint an der Pill.
- **Slash-Einfügen:** `handleOpenPicker` setzt `anchorRef.current` auf ein
  Caret-Measurable (`window.getSelection().getRangeAt(0).getBoundingClientRect()`,
  Fallback: `bn-container`) → Picker erscheint am Caret.

## Arbeitspakete

### WP-0 — Dependency (erledigt)
`@radix-ui/react-popover` installiert.

### WP-1 — Popover-Primitive
`components/ui/popover.tsx` (shadcn-Stil, cva-frei wie dialog.tsx):
`Popover`/`PopoverTrigger`/`PopoverAnchor`/`PopoverContent` (+ Re-Export in
`components/ui/index.ts` falls Barrel vorhanden). `PopoverContent` im Portal,
Token: `bg-popover text-popover-foreground shadow-popover rounded-lg border`,
`z-50`, `sideOffset`, `collisionPadding`, data-state-Animations (analog Dialog),
`outline-none`. A11y: `role` bleibt Radix-Default; Aufrufer geben `aria-label`.

### WP-2 — Vorschau: Dialog → Popover
`PlaceholderPreviewDialog.tsx` → umbenennen zu `PlaceholderPreviewPopover.tsx`
(Komponente `PlaceholderPreviewPopover`).
- Props zusätzlich `anchorRef` (gemeinsam mit Pickern).
- Listener setzt `anchorRef.current = event.target` + `setActive`.
- `<Popover open onOpenChange={close}><PopoverAnchor virtualRef={anchorRef}/>`
  `<PopoverContent aria-label="Platzhalter-Vorschau">…</PopoverContent></Popover>`.
- Inhalt unverändert (Loading/Error/Miss/Text via `LoadingState`/`ErrorAlert`),
  `max-h-[60vh] overflow-y-auto`; „Bearbeiten"-Button (editable, ≠ tools-overview)
  unten. testid `placeholder-preview-popover`.

### WP-3 — Picker: Dialog → Popover (alle vier)
`pickers/{Playbook,Resource,PersonaField,DateFormat}Picker.tsx`:
- Neues Prop `anchorRef?: RefObject<Measurable | null>`; `<Popover>` statt
  `<Dialog>`, `<PopoverContent className="w-80…">` (Panel-Breite, nicht winzige
  Bubble), `aria-label` statt `DialogTitle/Description`. Innenlayout (Suche,
  Liste, Radio, Footer, „Aktualisieren"/„Einfuegen", `initial`-Vorbefüllung)
  unverändert. `onOpenChange(false) → onCancel`.
- Alle bestehenden `data-testid` erhalten.

### WP-4 — Wrapper: gemeinsamer Anker + Caret
`SystemPromptEditor.tsx` + `PlaybookBodyEditor.tsx`:
- `const anchorRef = useRef<Measurable | null>(null)`.
- An Preview (`anchorRef`) und jeden Picker (`anchorRef`) durchreichen.
- `handleOpenPicker` (Slash-Insert) setzt vor `setOpenPicker` den Caret-Anker
  (Helper `caretMeasurable(containerRef.current)`).
- `handleStartEdit` unverändert (Anker steht bereits auf der Pill).

### WP-5 — Tests
- `PlaceholderPreviewPopover.test.tsx` (umbenannt): Host gibt `anchorRef`;
  testid `placeholder-preview-popover`; bestehende Fälle + Edit-Button-Fälle.
- Picker-Tests: `anchorRef={{ current: document.body }}` mitgeben; testids bleiben.
- Neuer Assert „nicht-blockierend": kein modaler Backdrop
  (`[data-radix-dialog-overlay]` nicht vorhanden) — optional/leichtgewichtig.
- DoD: lint/tsc/test/build grün.

## Edge-Cases / Risiken
- **Caret-Rect leer/0:** Fallback auf `bn-container`-Rect.
- **Großer Vorschau-Text:** `max-h` + intern scrollbar; floating-ui shift/flip
  via `collisionPadding`.
- **Mehrere Pills schnell hintereinander:** `anchorRef.current` + `setActive`
  je Klick → Repositionierung (autoUpdate).
- **A11y:** `PopoverContent` bekommt `aria-label`; Escape/Außenklick-Dismiss aus
  Radix; Fokus geht in den Picker (Suchfeld), ohne Trap (non-modal).
- **Kein Backend-Change.**

## Out of Scope
- Persona-Kontext für `persona-field`-Auflösung; Live-Vorschau im Picker.
