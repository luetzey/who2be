# Lernschleife C6 (Web) — Auto-Freigabe-Matrix mit Warnliste (S4/S4a)

Karte: t_d0509c04. Basis: origin/main aa0cc0d5 (#796 gemergt, C2a #751 und
C2b #783 auf main). Norm: ADR-0053 4.1–4.3; Spec
`lernschleife-design-spec-2026-09-28.md` §4 (S4, S4a), Delta
`lernschleife-design-spec-phase-c-delta-2026-10.md` (geht vor),
Gedächtnisverwaltungs-Spec §11 (C6-Zeile, Variante „C6 vorne“).

## Outcome

Admins schalten unter Einstellungen → Workspace → Gedächtnis die eine
schaltbare Zelle (`user_fact` × `user_stated`). Einschalten geht nur über den
Dialog mit allen acht Punkten aus ADR 4.3 und einer Lese-Bestätigung.
Alle anderen Zellen stehen als „Immer prüfen“ ohne Bedienelement da.

## Vorentschiedene Weichen (Beleg)

- **Reihenfolge C6 vor C5a** (Board: Gate t_b8a53e6b startet C5a nach C6).
  Damit gilt Gedächtnis-Spec 11.2 „Alternative“: S4a **ohne** den Satz
  „Du kannst alles … auf einmal zurücknehmen“, S4 **ohne** Kennzahl-Link und
  Rücknahme-Link (Ziele C5b/C5c fehlen, keine toten Elemente). C5c ergänzt.
- **Schaltbarkeit aus Serverdaten:** `switchable_cells` aus
  `GET /memory-auto-policy`; die UI kodiert keine Sperrliste. Sperrgründe aus
  dem Locale (Delta S4: Server liefert kein `locked_reason`).
- **Nur admin** (Delta S4, ADR 6.4): Abschnitt nur für Admins, wie
  `MemoryGuardSection`. Antwortet der Server trotzdem 403 (Token-Sitzung),
  steht „Nur mit echter Anmeldung änderbar.“ statt einer Matrix.
- **Ablaufsatz** steht (C2b gemergt), 30 Tage fest (ADR 3.1.3).
- **Kein Schloss, kein Haken:** gesperrte Zelle `Eye` + „Immer prüfen“;
  Schalter ist ein eigener `role="switch"`-Button ohne Check-Icon.
- Keys im Namespace `learning.autoPolicy` (Delta-Vorschlag).
- Agent-Formular: nur Locale (`agents.form.memory.mode.auto`, `…help`), kein
  Link (spart eine Datei; Text nennt den Ort).

## Dateien (8 + Naben de/en + Changelog + Plan)

1. `apps/web/src/api/types.ts` — `MemoryAutoRow`, `MemoryAutoOrigin`,
   `MemoryAutoCell`, `MemoryAutoPolicy`, `MemoryAutoPolicyRead`.
2. `apps/web/src/api/client.ts` — `getMemoryAutoPolicy`,
   `updateMemoryAutoPolicy`.
3. `features/settings/components/MemoryApprovalSection.tsx` (neu).
4. `features/settings/components/AutoApprovalLimitsDialog.tsx` (neu,
   inkl. `AutoApprovalLimitsList` für die dauerhafte Fassung).
5. `features/settings/components/MemoryApprovalSection.test.tsx` (neu).
6. `features/settings/components/MemoryApprovalSection.a11y.test.tsx` (neu).
7. `features/settings/pages/WorkspaceSettingsPage.tsx` — Abschnitt über dem
   Wächter, Anker `#memory-approval` / `#memory-guard`.
8. `features/settings/pages/WorkspaceSettingsPage.test.tsx` — Stubs, Rolle.

## Akzeptanz / Tests (je mit Rot-Probe)

- Nie-Zellen haben keinen Schalter (Zählung `role=switch` = 1).
- Einschalten ohne Dialog unmöglich: Klick → Dialog, `<ol>` hat 8 Punkte,
  PUT erst nach Checkbox + Bestätigen; Abbrechen sendet nichts.
- Nicht-Admin: kein Abschnitt, kein Schalter, kein Request.
- Keine Wörter sicher/secure/safe (und geschützt/garantiert) in
  `learning.autoPolicy` und den geänderten Agent-Keys (de + en).
- Kein `lucide-lock`/`lucide-check` im gerenderten Abschnitt.

## Verifikation

Node 22.23.3: `npx tsc -b`, `npm run lint`, `npm run i18n:check`,
`npm run test:coverage`, `npm run build`, `npm run license:check`;
Screenshots 1280/390 hell/dunkel mit Overflow-Messung; CI all-green.
