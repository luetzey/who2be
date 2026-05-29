# ADR 0022 — Block-Editor-Stack (BlockNote)

- Status: Akzeptiert
- Datum: 2026-05-29
- Kontext: Phase 2.2 (Resources mit Block-Editor)

## Kontext

Resources brauchen einen Notion-artigen Block-Editor im Web-UI: Bloecke
(Absatz, Ueberschrift, Listen, Code, Zitat), Slash-Menue, Drag-Handle und —
zentral fuer Block-Refs — **stabile Block-IDs**, auf die Playbooks zeigen.
Der urspruengliche Plan (§2.2.E) sah TipTap (low-level) mit selbstgebautem
Slash-Menue/Drag-Handle und einer eigenen `BlockId`-Extension vor.

## Entscheidung

Wir nutzen **BlockNote** (`@blocknote/core` + `@blocknote/react` +
`@blocknote/mantine`) statt TipTap-Eigenbau.

- **Native stabile Block-IDs:** jeder BlockNote-Block traegt eine `id` —
  die geplante eigene `BlockId`-Extension entfaellt. Diese ID ist der Anker
  fuer `playbook_resource_link.block_id`.
- **Out-of-the-box:** Slash-Menue, Drag-Handle, Block-Typen und Inline-Marks
  kommen mit — deutlich weniger Eigenbau als TipTap.
- **Isolations-Insel mit `@blocknote/mantine`:** der Editor ist eine gekapselte
  Komponente (`ResourceEditor.tsx`) mit eigenem Style-Scope und lokaler
  Inter-Schrift (gebuendelt, kein CDN → kein CSP-Eintrag noetig). Theme
  (light/dark) wird aus unserem `useTheme`-Context durchgereicht.
- **`@blocknote/shadcn` verworfen:** es verlangt das Deaktivieren von Portals
  in unseren geteilten `DropdownMenu`/`Popover`/`Select`-Primitives — zu
  invasiv fuer das Design-System.

**Bewusste Ausnahme vom Design-System:** Der Editor-Content ist eine
Drittanbieter-Insel und keine Token-/shadcn-Komponente. A11y-Gates (vitest-axe)
laufen gegen Toolbar/Picker, nicht gegen den BlockNote-Content; dessen
Inhaltsbarrierefreiheit wird manuell geprueft. Der Editor wird in Tests
gemockt, weil ProseMirror in jsdom nicht zuverlaessig mountet.

**Content-Format:** `resource_version.content` ist `{ description, blocks }`,
wobei `blocks` das BlockNote-Dokument (Array offener Block-Objekte) ist. Das
Pydantic-`ResourceBlock` ist `extra="allow"` (offenes Schema), mit einem
Gesamt-Byte-Limit als DoS-Grenze (F-01).

## Konsequenzen

- Schnellere, robustere Editor-UX ohne Eigenbau von Slash-Menue/Drag-Handle.
- Neue Dependencies (`@blocknote/*` + transitive Mantine-Pakete).
- Block-Refs sind trivial, weil Block-IDs nativ stabil sind.
- XSS-sicher: BlockNote rendert via React/ProseMirror, kein
  `dangerouslySetInnerHTML`.

## Alternativen

- **TipTap (Plan-Original)** — verworfen: mehr Eigenbau (Slash-Menue,
  Drag-Handle, BlockId-Extension) bei gleichem Ergebnis.
- **`@blocknote/shadcn`** — verworfen: Portal-Deaktivierung in geteilten
  Primitives zu invasiv.

## Referenzen

- Plan: `.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md` (§2.2.E)
- ADR-0014 (Frontend-Color-Space), ADR-0016 (Frontend-A11y-Gate)
