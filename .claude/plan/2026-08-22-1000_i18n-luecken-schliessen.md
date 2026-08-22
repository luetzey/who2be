# i18n-Luecken schliessen (Weg B) — Master-Plan

Datum: 2026-08-22 · Basis: `.claude/plan/2026-08-22-0900_i18n-bestandsaufnahme.md`
Freigabe: Nutzer waehlt Weg **B** (Frontend vollstaendig), C (API-Fehlertexte)
als Issue-Reminder statt Umsetzung.

## Ziel (Completion-Condition, messbar)

Nach diesem Plan gilt: **jeder String, den das Frontend selbst erzeugt, ist in
DE und EN vorhanden.** Nachweis:

1. `de.json` und `en.json` haben identische Key-Mengen (0 Diff, wie heute).
2. Der Scan „harte deutsche Strings in `src/`" faellt von **117 produktiv
   relevanten auf 0** (DEV-only `app/catalog` ausgenommen und begruendet).
3. Web-DoD gruen: `npm run lint`, `npx tsc -b`, `npm run test:coverage`,
   `npm run build`.

Ausdruecklich **nicht** im Scope: die 78 deutschen `detail`-Strings aus
`apps/api` (→ Issue, Weg C) und `app/catalog` (DEV-only Showcase).

## Constraints (Leitplanken)

- Keine Verhaltensaenderung ausser Sprache. Bestehende Tests assertieren
  deutsche Strings (`src/test/setup.ts` fixiert `de`) — die DE-Werte muessen
  **woertlich** erhalten bleiben, sonst brechen Tests zu Recht.
- Keine neuen `HTTPException`/SQL in `apps/api/**/services/` (hier ohnehin
  kein API-Change).
- Frontend-Konventionen: Keys im passenden Namespace, geteilte Begriffe nach
  `common`, keine Duplikate pro Feature (docs/frontend/i18n.md §Neue Strings).

## Wellen (datei-disjunkt)

### Welle 1 — WP-4: Sprach-Persistenz haerten
Dateien: `src/auth/SessionProvider.tsx` **oder** `src/i18n/useApplyStoredLocale.ts`

Problem (belegt): `@supabase/auth-js` `updateUser` setzt nur `session.user` und
behaelt den `access_token`; `SessionProvider.apply()` dedupliziert auf genau
diesen Token und verwirft `USER_UPDATED`. Der React-State behaelt die alte
`preferred_locale` — ein Altwert kann eine frische Wahl ueberschreiben.

Fix (bewusst in `useApplyStoredLocale`, nicht im SessionProvider): der
gespeicherte Wert wird **einmal pro Session angewandt**, nicht bei jeder
Aenderung von `stored`. Begruendung: der SessionProvider-Dedupe schuetzt den
teuren `fetchMe`-Pfad und soll nicht wegen einer Sprachpraeferenz aufgeweicht
werden; die Sprachwahl des Nutzers im laufenden Tab hat Vorrang vor einem
serverseitig gespeicherten Altwert. Ref-Guard auf die User-ID.

Test: `useApplyStoredLocale.test.ts(x)` — (a) wendet gespeicherte Sprache beim
ersten Auftauchen der Session an, (b) ueberschreibt eine spaetere manuelle Wahl
**nicht**, (c) wendet bei User-Wechsel erneut an.

### Welle 2 — WP-3: Rest-Seiten
Dateien: `features/dashboard/pages/DashboardPage.tsx` (8),
`features/settings/pages/AccountPage.tsx` (4),
`features/system-prompts/pages/SystemPromptDetailPage.tsx` (2),
`features/auth/pages/LoginPage.tsx` (2), `components/ui/dialog.tsx` (1 `sr-only`).

`features/agents/pages/AgentsPage.tsx` `createAgent({name:'Neuer Agent'})`
bleibt: das ist ein **Inhalts**-Default (Entity-Name), keine UI-Beschriftung.
Er folgt der Content-Sprache des Workspace, nicht der UI-Sprache — Aenderung
waere ADR-0045-Drift. Wird im Plan begruendet stehengelassen.

### Welle 3 — WP-2: Hooks, Toasts, zod
Dateien: `src/hooks/*.ts` (~10), `features/*/hooks/*.ts` (~12), `src/lib/*.ts` (2).

- Fehler-Fallbacks (`'Unbekannter Fehler.'` ×12, `'Auto-Save fehlgeschlagen.'`,
  `'Anlegen fehlgeschlagen.'`) → `common:errors.*`, ueber die
  i18n-Singleton-Instanz (`import i18n from '@/i18n'`), da Nicht-Komponenten.
- Erfolgs-Toasts (`'Persona angelegt.'`, `'Resource angelegt.'`,
  `'Externes Tool angelegt.'`, Token-Toast) → jeweiliger Feature-Namespace.
- zod-Messages (16) → `common:validation.*`, als Funktion aufgeloest, damit die
  Message zur Render-Zeit die aktive Sprache zieht (nicht zur Modul-Ladezeit).

Achtung: `cause.message` bleibt der **Server**-Text (deutsch) — das ist Weg C
und wird hier bewusst nicht angefasst.

### Welle 4 — WP-1: System-Prompt-Editor
Dateien: `components/editor/system-prompt/**` (21 Dateien, 47 Strings).
Neuer Namespace `editor` in beiden Locale-JSONs.

Betroffen: `slashMenu.ts` (7), alle Picker — Persona-Feld (8), Katalog-Scope (5),
Resources-Katalog-Scope (5), Resource (4), Playbook (3), Tool (3), Datum (2) —
`PlaceholderPreviewPopover.tsx` (5), `SystemPromptEditor.tsx` (2),
`PlaceholderBlock.tsx` (1), `usePlaceholderPreview.ts` (1).
`slashMenu.ts` ist ein Nicht-Komponenten-Modul → Singleton-Instanz oder `t`
durchreichen; Slash-Menu-Keywords (`gedaechtnis`, `langzeitgedaechtnis`) sind
Sucheingaben, die pro Sprache uebersetzt werden muessen.

## Verifikation je Welle

`npm run lint` · `npx tsc -b` · `npm run test:coverage` · `npm run build` —
lokal vor jedem Push, Ergebnis im PR mit exakten Zahlen.

## Abgrenzung → Issue (Weg C)

WP-5 „API-Fehlertexte zweisprachig" wird als GitHub-Issue angelegt, nicht
umgesetzt. Die Weiche (Fehler-**Codes** vs. serverseitiges `Accept-Language`)
ist eine Architektur-Entscheidung und gehoert in eine ADR.
