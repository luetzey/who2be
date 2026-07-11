# Design-Refresh: Dashboard, System-Prompts, Agents, Resources, Feedback

**Datum:** 2026-07-11 · **Branch:** `claude/code-agent-setup-lmpt8u`
**Quelle:** Design-Mockups (`DashboardDesignVerbesserung_1.zip`) — reine Design-Hinweise.

## Leitprinzip (vom User)

> Auf der gesamten Seite immer **gleiche Komponenten** verwenden, nichts doppelt
> bauen, Elemente **seitenübergreifend** wiederverwenden, standardisierte Plätze.

Das ist zugleich der Repo-Standard (`design-language.md` §13, "keine Utility-Suppe",
"Single-Source pro Entscheidung"). Deshalb: **erst die geteilten Komponenten,
dann die Seiten** — Seiten komponieren nur, sie erfinden keine Karten neu.

## Ist-Zustand (bereits vorhanden — NICHT neu bauen)

- **Tokens** (`globals.css`): `--brand*`, `--status-{draft,review,active,inactive}`,
  `--pill-{playbook,resource,persona,date,tools,catalog}-{bg,fg}`, `--diff-*`,
  `--shadow-{card,popover,modal}`, Motion-Tokens. Deckungsgleich mit den Mockups.
- **Layout:** `AppShell` (Sidebar+Header wie Mockup), `PageHeader` (+`titleAddon`),
  `Container`, `Section`, `Stack`, `FormSection`.
- **Data:** `DataList`, `DataView`, `EmptyState`, `ErrorAlert`, `LoadingState`,
  `StatusBadge` (Dot+Label, `--status-*`), `ListFilterBar` (Segment-Tabs+Suche+Selects),
  `ManagedNotice`.
- **UI:** `Button` (Variante `brand`), `Badge`, `Card`, `Input`, `Textarea`,
  `Select`, `Checkbox`, `Dialog`, `DropdownMenu`, `Popover`, `Table`, `TagInput`.
- **Feature-Bausteine:** `VersionHistory`, `KpiCard`, `StatusDonut`, `ActivityRow`,
  `PlaybookRow` (einzige extrahierte Karten-Row — Vorbild).

**Lücke:** Entity-Listen (System-Prompts/Agents/Resources/Personae) rendern ihre
Row-JSX **inline dupliziert**; die Mockups heben sie auf **Karten** (Icon-Tile +
Shadow + Hover-Pop + Meta-Pills) — es fehlt eine geteilte Karten-Row + Detail-Gerüst.

## Phase A — Geteilte Komponenten (Fundament, zuerst, 1 Agent)

Neu in `components/` (mit Katalog-Showcase + vitest + a11y-Test, Barrels updaten):

1. **`EntityIcon`** — farbiges Rounded-Tile (`--pill-*` Ton) mit Lucide-Icon; Größen sm/md/lg.
2. **`MetaPill`** — Icon+Text-Pill mit Ton (persona/playbook/resource/date/tools/catalog);
   ersetzt die inline-Pills in Agent-/Resource-Karten & Editor.
3. **`EntityCard`** (`components/data/`) — **Kern der Wiederverwendung.** Karten-Row:
   `EntityIcon` + Titel-`Link` + Slug-/Version-`Badge` + `StatusBadge` (+ pendingDraft)
   + Beschreibung + `meta`-Slot (MetaPills/Tags/„verlinkt in N") + `actions`-Slot
   (Chevron | Split-Button „Kopieren" | „Einrichten") + `expandable`-Slot
   (Sub-Playbooks/Sub-Resources). Genutzt von System-Prompts, Agents, Resources
   (und optional Personae). Ersetzt die 4 duplizierten inline-Rows.
4. **`Tabs`** (`components/ui/`) — Underline-Tabbar (Radix falls vorhanden, sonst schlank).
   Für ALLE Detail-Seiten (Bearbeiten/Versionen, Konfiguration/Werkzeuge/Verbindung,
   Bearbeiten/Sub-Resources/Verwendung/Versionen).
5. **`AttentionBanner`** (`components/data/`) — brand-soft/destructive Banner: Icon+Titel+
   Text+Actions. Für Review-/Entwurf-Hinweise auf Detail-Seiten UND das Dashboard-
   „Braucht deine Aufmerksamkeit"-Band. Ersetzt/ergänzt `StatusActionBar`-Optik.
6. **`DetailHeader`** (`components/data/` oder `layout/`) — Back-Link + `EntityIcon` +
   Titel + Slug/Status/Tags + `actions`. Für alle Detail-Seiten identisch.
7. **`VersionHistory` prüfen/erweitern** — Diff-Expand (`--diff-*`) + Status-Timeline
   („Warum aktiv?"/Historie) wie Mockup, falls noch nicht vorhanden.
8. **`UsedByList`/„verlinkt in N"** — geteilte Backlink-Liste (aus `ResourceUsedByList`
   + `ComposedByList` verallgemeinern), Zeile = MetaPill-Stil.

DoD Phase A: `npm run lint && npx tsc --noEmit && npm test && npm run build` grün,
**committen + pushen** (Fundament liegt vor Phase B im Branch).

## Phase B — Seiten (parallel, je 1 Agent, disjunkte Feature-Ordner)

Jede Seite **komponiert nur** die Phase-A-Bausteine — keine neuen Karten.

- **B1 Dashboard** — Attention-Band (`AttentionBanner`), Schnellstart-Actions,
  KPI-Strip (`KpiCard`), Status-Verteilung (Balken statt/neben Donut), Aktivitäts-
  Feed (`ActivityRow`).
- **B2 System-Prompts** — Liste auf `EntityCard` (Icon `ScrollText`, Slug/Version/Status,
  „Verwendet von N Agents"); Detail: `DetailHeader`+`AttentionBanner`(Review)+`Tabs`
  (Bearbeiten/Versionen)+`VersionHistory`+Platzhalter-Hilfe.
- **B3 Agents** — Liste auf `EntityCard` (Icon `Bot`, Status, Meta = Persona/Template/
  Playbooks, Action = Split „Kopieren" | „Einrichten"); Detail: `DetailHeader`+
  Zusammensetzung-Card+`Tabs` (Konfiguration/Werkzeuge & Rechte/Verbindung).
- **B4 Resources** — Liste auf `EntityCard` (Icon `FileText`, Tags, „Verlinkt in N",
  Sub-Resources-Expand); Detail: `Tabs` (Bearbeiten/Sub-Resources/Verwendung/Versionen).
- **B5 Feedback** — Inbox mit KPI-Tiles + Filter-Selects + Item-Liste (Status-Segment);
  Nutzungs-Übersicht (`UsedByList`-Stil); **neue `Feedback-Detail`-Kurationsseite**
  (Nutzung/Ergebnis + Signale + Notiz + Einzel-Ereignisse) via `get_feedback`.

Page-Agents: **kein `git commit`** (disjunkte Dateien im selben Tree); scoped
`tsc`/vitest zur Selbstkontrolle.

## Phase C — Konsolidierung (1 Agent + ich)

Voller DoD über `apps/web` (lint/tsc/test/build), Integrationsfehler beheben,
Screenshots via `run`/Playwright, **ein sauberer Commit + Push + Draft-PR**.

## Entscheidungen (User bestätigt 2026-07-11)

1. **Personae mitziehen: JA** → zusätzliches Paket B6 (Personae-Liste + Detail auf
   `EntityCard`/`DetailHeader`/`Tabs`, Playbooks-Karten angleichen).
2. **Feedback-Detail als neue Route: JA** → Paket B5 legt die Kurationsseite via
   `get_feedback` an; Agent prüft zuerst den API-Endpunkt und meldet zurück statt
   zu raten, falls er fehlt.
