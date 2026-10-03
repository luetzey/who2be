# Lernschleife C5c-1 (Web): Detail-Sheet, Verlauf, Rollback, Bearbeiten, Löschen

Status: aktiv · Karte t_7da03826 · Basis origin/main 1a0d4f48 (C5b-2 #804 gemergt)
Spec: gedaechtnisverwaltung-design-spec-2026-10.md §7, §13.5, §14, §15, §16 (C5c);
Delta S3 (Ereignisarten, Rollback „vor dieser Änderung“), Spec S3 (Verlauf als `<ol>`).
Schnitt: PM 2026-10-03, Option A (C5c-1 = diese Karte, 12 Dateien; Not-Aus und
Agent-Seiten-Sheet = C5c-2 t_fcbecc46).

## Outcome
Aus „Einträge“ (Chevron je Zeile) und „Zur Freigabe“ (Verlauf-Button in der
aufgeklappten Zeile) öffnet sich ein Detail-Sheet (`?entry=<id>`). Es zeigt Fakt,
Status, Herkunft (Kanal vom Server getrennt von „Laut Agent“), Auslieferung und
den Verlauf; es bietet je Status Freigeben/Ablehnen, Bestätigen, Wieder
aktivieren, Bearbeiten, Löschen und je Verlaufsereignis „Stand vor dieser
Änderung wiederherstellen“ (Rollback per `event_id`).

## Akzeptanzkriterien (Karte)
- Rollback sendet die gewählte `event_id`.
- Löschdialog: „Eintrag und sein Verlauf werden dauerhaft entfernt. Das lässt
  sich nicht rückgängig machen.“ (ON DELETE CASCADE, Migration 0091, M5).
- „Wieder aktivieren“ nur bei `expired`.
- Fremdes Nutzergedächtnis nie sichtbar (auch nicht per Deep-Link).
- i18n de/en mit echten Umlauten, keine toten Knöpfe.
- Screenshots 1280/390 hell+dunkel mit Overflow-Messwert; e2e-mobile grün; CI 17/17.

## Entscheidungen (aus Repo/Spec belegt)
- **Besitzer-Pfad** je Eintrag: `scope=user` → `/me/memories/{id}/…`, sonst
  `/agents/{agent_id}/memories/{id}/…` (Muster `confirmMemory`, C5b-1).
- **Kein `GET` für einen einzelnen Eintrag** in der API. Das Sheet bekommt den
  Eintrag beim Öffnen aus der Liste über den Router-State (`location.state.memory`).
  Ein frischer Deep-Link sucht ihn seitenweise über `GET /memories` (alle
  Status, die Sicht des Servers), höchstens 10 Seiten zu 50 (= Ladegrenze der
  Liste). Nicht gefunden → „Diesen Eintrag gibt es nicht mehr oder du darfst ihn
  nicht sehen.“ Ein `GET /memories/{id}` wäre die saubere Lösung → Hinweis an @pm.
- Fremdes Nutzergedächtnis: zusätzlich clientseitig `visibleToMe` (wie die Listen).
- Verlauf: API liefert älteste zuerst → Anzeige neueste zuerst, `<ol>`; > 20 →
  „Ältere laden“. Rollback-Knopf an jedem Ereignis mit `before`, dessen Stand
  sich vom aktuellen unterscheidet (sonst wäre er ein toter Knopf).
- Rollback-Dialog liegt in `MemoryHistory.tsx` (Schnitt A), Diff „jetzt → danach“
  inkl. Statuswechsel, Wort-Diff aus `MemoryRow` (`ChangeDiff`, jetzt exportiert).
- Akteur: Mensch über `GET /members` (E-Mail, „dir“ für die eigene Person),
  Agent über `useAgents` mit `Bot`-Icon, `system` = „Automatisch“.
  `auto_activated` nennt die Regel aus `after.kind × after.origin`.
- `MemoryRow` (S1′) setzt `?entry` selbst über eine kleine Router-Komponente, so
  bleibt `ApprovalQueue.tsx` unberührt; außerhalb eines Routers fehlt der Knopf.
- `MemoryList` bekommt `detailLinks?`; ohne Prop (Agent-Seite) kein Chevron.
- Aktualisierung nach Änderungen im Sheet: `MemoryPage` erhöht einen Zähler →
  Tab-Zähler, `EntriesTab` lädt neu, `ApprovalQueue` wird per `key` neu gemountet.
- Fokus: beim Öffnen auf den Sheet-Titel; beim Schließen zurück zum Auslöser,
  sonst (Deep-Link) auf die Tab-Überschrift (§15).
- Sheet: Desktop `side=right` `sm:max-w-lg`, unter md `side=bottom` volle Höhe,
  Kopf sticky, ein Scroller (`overscroll-contain`), kein innerer Scroller.

## Dateien (Zählregel: alle außer Plan, Grenze 12)
1. apps/web/src/api/types.ts — MemoryEventKind/ActorKind/EventRead, MemoryRollbackInput
2. apps/web/src/api/client.ts — getMemoryHistory, rollbackMemory, updateMyMemory, deleteMyMemory
3. apps/web/src/api/client.contract.test.ts — neue Pfade
4. apps/web/src/components/memory/MemoryDetailSheet.tsx (neu)
5. apps/web/src/components/memory/MemoryHistory.tsx (neu, mit RollbackDialog)
6. apps/web/src/features/memory/pages/MemoryPage.tsx — Host für `?entry=`
7. apps/web/src/components/memory/MemoryList.tsx — Chevron S2′, StatusLine exportiert
8. apps/web/src/components/memory/MemoryRow.tsx — Verlauf-Button S1′, ChangeDiff exportiert
9. apps/web/src/i18n/locales/de.json
10. apps/web/src/i18n/locales/en.json
11. apps/web/src/components/memory/MemoryDetailSheet.test.tsx (neu)
12. changelog.d/t-7da03826-memory-detail-sheet.added.md

## Verifikation
- Node 22 (mise): `npm run lint`, `npx tsc -b`, `npm run test:coverage`,
  `npm run build`, `npm run license:check`, `npm run i18n:check`
- Rot-Proben: event_id im Body; Löschtext; reactivate nur bei expired; fremder
  Nutzerfakt (State und Scan) → notVisible; Agent-Seite ohne Chevron.
- Screenshots 1280/390 hell+dunkel mit scrollWidth<=clientWidth (Scratch, nicht
  committet); e2e mobile lokal.

## Fortschritt
- [x] Umsetzung (12 Dateien wie oben). Abweichung: statt `onOpenDetail?` heißt das
  Prop `detailLinks?: boolean`; der Chevron ist ein echter Link (`?entry=` plus
  Router-State), keine Callback-Kette.
- [x] Tests: `MemoryDetailSheet.test.tsx` 16 Fälle inkl. axe; Contract-Test um 4 Pfade.
  Rot-Proben (alle rot): event_id, Löschtext, reactivate≠expired, fremder
  Nutzerfakt, toter Wiederherstellen-Knopf, Chevron ohne `detailLinks`,
  Contract-Pfad.
- [x] DoD web (Node 22.23.3 via mise): lint 0 Fehler, `tsc -b`, test:coverage
  244/244 Dateien, 1800/1800 Tests (Statements 87,67 %, Branches 81,75 %),
  Skip-Budget 0, build, license:check, i18n:check.
  Lokaler Befund: Node 22.23.3 aktiviert Webstorage → ~190 fremde Tests rot
  (`localStorage.getItem` undefined), auch auf unverändertem main. Lokal mit
  `NODE_OPTIONS=--no-experimental-webstorage` gelaufen; Repo-Setup unberührt.
- [ ] Screenshots 1280/390 hell+dunkel: offen. Skript liegt in Scratch
  (`c5c1shots/shots.mjs`); der Dev-Server zielte auf API :8000 statt auf den
  Stack (:57800), VITE-API-URL muss gesetzt werden.
- [ ] PR / CI
