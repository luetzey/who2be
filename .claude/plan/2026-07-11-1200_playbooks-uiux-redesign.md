# Playbooks UI/UX-Redesign — Übersicht & Detail (Design-Handoff)

_Stand: 2026-07-11 · Branch `claude/code-agent-setup-1pes6m`_

## Auftrag

Design-Handoff `Playbooks_UIUX_Verbesserung.zip` (README + HTML-Prototyp
„Playbooks – Finale Umsetzung", Screens 2a/2d/3a/3b) in `apps/web/` umsetzen:

- **Playbooks-Übersicht** (`PlaybooksPage`): von dichter `DataList`-Zeile zu
  ruhigen Karten-Zeilen mit Typ-Icon, sanftem Status (Dot statt Badge),
  sichtbaren Triggern, aufklappbarer Composite-Beziehung, „Teil von"-Marker;
  Filterleiste als Segmented-Control + Suche + „Filter"-Popover; zwei neue
  Leerzustände (Onboarding-Hero + gefilterter Leerzustand).
- **Playbook-Detail** (`PlaybookDetailPage`): vom Karten-Stapel zu Tabs
  **Bearbeiten / Beziehungen / Versionen** mit Hero (Typ-Icon + sanftes
  Status-Chip) und Review-Banner (ersetzt `BranchStatus`-Block, gleiche
  `BranchAction`s + Save-Indikator).

Verbindliche Leitplanken: `docs/frontend/design-language.md` +
CLAUDE.md §Frontend-Standards. Der Prototyp ist Referenz, kein Copy-Code.

## Entscheidungen (Design-Weichen, im Handoff bereits fixiert bzw. hier aufgelöst)

1. **Off-Scale-Werte des Prototyps** (z. B. `gap-[10px]`, `p-[3px]`,
   `rounded-[9px]`, `p-[13px_15px]`): Der Handoff schreibt selbst „keine
   ad-hoc px — Tokens verwenden". Wir runden auf die erlaubte Skala
   (Spacing `{1,2,3,4,6,8,12,16}`, Radii sm/md/lg/xl): Listen-Gap `gap-3`,
   Segmented-Padding `p-1`, Karten `rounded-xl`, Editor-/Versions-Zeilen
   `rounded-lg`.
2. **Klickbare Karte**: Stretched-Link-Pattern (Name-`Link` mit
   `after:absolute after:inset-0`, innere Links/Buttons `relative`) statt
   `div onClick` — tastaturbedienbar, kein a11y-Verstoß, `stopPropagation`
   entfällt größtenteils.
3. **„Teil von"-Marker**: Rückrichtung clientseitig aus den geladenen
   `compose_children` aller Listen-Playbooks abgeleitet (kein neuer
   API-Aufruf pro Zeile).
4. **Suche „Name oder Trigger"**: `useListFilters` bekommt einen optionalen
   `searchText`-Accessor (zusätzlicher Heuhaufen), Playbooks reichen die
   Trigger mit hinein. Andere Listen unverändert.
5. **Toolbar bleibt feature-lokal** (`PlaybookListToolbar`): nur Playbooks
   bekommt das neue Muster; Promotion nach `components/data/` erst, wenn
   eine zweite Liste es übernimmt (YAGNI). `ListFilterBar` bleibt für die
   anderen Listen unangetastet.
6. **VersionHistory** (geteilt): Funktion unverändert; Styling sanft
   angeglichen (Status als `StatusBadge`-Dot-Pill statt hartem `Badge`,
   Zeilen `rounded-lg`) — wirkt konsistent auf alle vier Detail-Pages.
7. **FeedbackPanel + Resource-Links** (im Handoff nicht erwähnt, heute auf
   der Seite): wandern in den Tab „Beziehungen" (Nutzungs-/Meta-Sicht) —
   keine Funktion entfällt.
8. **Review-Banner** erscheint, wenn Aktionen oder Draft/Review existieren;
   sonst trägt das Hero-Status-Chip allein.
9. **Danger-Zone**: kollabierte, dezente Zeile am Ende des Tabs „Bearbeiten".
10. **Keine Sub-Agent-Orchestrierung**: ein kohärentes Arbeitspaket mit
    überlappenden Dateien (i18n, Pages, geteilte Komponenten) — direkt
    sequenziell umsetzen.

## Arbeitspakete

### WP-1 Shared-Grundlagen
- `hooks/useListFilters.ts`: optionaler `searchText`-Accessor (+ Test).
- `components/data/BranchStatus.tsx`: `SaveIndicator` exportieren.
- `components/version/VersionHistory.tsx`: `Badge` → `StatusBadge`,
  Zeilen-Radius `rounded-lg` (+ Tests nachziehen).

### WP-2 Übersicht (`features/playbooks/`)
- `lib/typeMeta.tsx`: Typ → Lucide-Icon + Pill-Token-Klassen
  (workflow→catalog/`Workflow`, instructions→playbook/`ListOrdered`,
  checklist→resource/`ListChecks`, faq→persona/`MessageCircleQuestion`,
  snippet→tools/`Quote`, prompt→date/`Sparkles`).
- `components/PlaybookTypeIcon.tsx`: 40er-Chip (`rounded-lg`, Pill-Tint).
- `components/PlaybookListToolbar.tsx`: Segmented-Status (Alle /
  Braucht Aufmerksamkeit (+Zahl in Brand) / vorhandene Status), Suche
  (`Search`-Inset, X zum Leeren, `border-brand` bei aktivem Term),
  „Filter"-Button (`SlidersHorizontal`) → `Popover` mit Tag/Typ/Agent/
  Gruppieren-Selects + Agent-Chip + Reset.
- `components/PlaybookRow.tsx`: Karten-Zeile (Typ-Chip, Name+Soft-Status
  „Aktiv · v2", „Entwurf offen"-Brand-Pill, Beschreibung, `Zap`+Trigger-Chips
  max 3 + „+N", Tags rechts, Chevron; Composite-Footer mit `--ca`-Tint,
  Toggle + Kinder-Zeilen als Links; „Teil von"-Pill mit `Layers`).
- `pages/PlaybooksPage.tsx`: Header (H1 + Count-Pill + Description + Brand-CTA),
  Toolbar, Karten-Stack `gap-3`, Gruppierung (WP-D3) beibehalten,
  Onboarding-Hero (BookOpen im `--ca`-Quadrat, Typ-Hinweis-Chips) +
  gefilterter Leerzustand (Search-Icon, „Filter zurücksetzen").
- i18n `de.json`/`en.json` (neue Keys unter `playbooks:list.*`, `data:filter.*`).

### WP-3 Detail (`features/playbooks/`)
- `components/ReviewBanner.tsx`: Brand-Tint-Banner (`bg-brand/… border-brand/…`),
  links Branch-Zusammenfassung (Status-Dots „Aktiv: v2 → v3 wartet auf
  Review"), rechts SaveIndicator + `BranchAction`s.
- `components/PlaybookDetailTabs.tsx`: `role="tablist"`, Buttons mit Icon
  (`Pencil`/`Layers`/`GitBranch`), aktiver 2px-Brand-Unterstrich.
- `components/SubPlaybookFlow.tsx`: horizontaler Ausführungs-Flow
  (Nummern-Badge `--ca`, `ArrowRight`-Konnektoren, Kind-Links).
- `pages/PlaybookDetailPage.tsx`: Back-Link, Hero (TypeIcon 38→`size-10`,
  H1, Status-Pill mit Version, Description, Export rechts), ManagedNotice,
  ReviewBanner, Tabs:
  - **Bearbeiten**: `PlaybookEditorForm` (unverändert) + kollabierte
    Danger-Zone (role≠viewer, !locked).
  - **Beziehungen**: Verwendet-in (Avatar-Initialen-Links), `SubPlaybookFlow`,
    ComposedBy, Resource-Links (read-only), FeedbackPanel.
  - **Versionen**: `VersionHistory`.
- i18n-Keys `playbooks:detail.tabs.*`, Banner-Texte.

### WP-4 Tests + DoD
- Bestehende Tests nachziehen (PlaybooksPage.test, PlaybookDetailPage.test
  945 Z. — Tab-Umschaltung in Helpern, a11y-Tests beider Seiten).
- Neue Tests: PlaybookRow (Expand, Teil-von, Stretched-Link),
  PlaybookListToolbar (Segmented, Popover-Facetten, Reset),
  PlaybookDetailTabs (aria-selected/Panel-Wechsel), ReviewBanner (Aktionen),
  SubPlaybookFlow, useListFilters-searchText.
- DoD: `npm run lint`, `npx tsc --noEmit`, `npm run test:coverage`
  (Branches-Floor 79), `npm run build` — alle grün, lokal, vor Push.

## Out of Scope
- Andere Listen-/Detail-Seiten (Personas/Resources/System-Prompts) — nur
  die geteilte `VersionHistory`-Optik ändert sich dort mit.
- Mobile-Feinschliff über das responsive Verhalten der Primitives hinaus,
  Hover-Transition-Feinschliff (Prototyp-„Next Steps").
- Backend/API unverändert.
