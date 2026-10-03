# Lernschleife C5a-2 (Web): Dashboard-Banner „Einträge zur Freigabe“ → /memory?tab=approval

Status: aktiv · Karte t_5c835da2 · Basis origin/main 1d4bc9b1 (#800, #806 gemergt)
Spec: gedaechtnisverwaltung-design-spec-2026-10.md §1, §11.1 (Dashboard-Zeile, vorrangig);
lernschleife-design-spec-2026-09-28.md §10 (Texte); Owner W1 = a.

## Outcome
Der Dashboard-Banner `attention.memories` zählt aus derselben Quelle wie der
Tab-Zähler „Zur Freigabe“ und verlinkt auf `/memory?tab=approval`.

## Akzeptanzkriterien (Karte)
- Zahl offener Einträge ohne Lernvorschläge, Link `/memory?tab=approval`; bei 0 kein Banner (Bestand: „Alles erledigt“, wenn auch sonst nichts ansteht).
- DE/EN mit echten Umlauten; 390 px ohne Overflow.
- Tests: Link-Ziel; viewer fragt nur `scope=user`; kein `subject_user_id`-Request. Rot-Probe je Zusicherung.
- DoD-Kommandos aus CONTRIBUTING.md; Changelog-Fragment.

## Entscheidungen (aus Repo belegt)
- **Nicht `kpis.pending_memories`.** `_ATTENTION_COUNTS` (dashboard_repository.py:131)
  zählt `agent_memory WHERE status='pending'` ohne Ausschluss von `lesson` UND
  über alle `scope=user` aller Mitglieder — also fremdes Nutzergedächtnis als
  Zahl, auch für viewer (ADR 3.1.1). Der Client nutzt das Feld für den Banner
  nicht mehr. Server-Korrektur ist API-Scope → Folgekandidat an @pm.
- Quelle = Tab-Zähler: `GET /memories/counts?status=pending` (Server schließt
  `lesson` dort aus, memory_repository.py:1989) + offene Vorschläge aus
  `GET /memory-proposals?status=pending`. Gemeinsame Funktion
  `countApprovalQueue` in `useMemoryApi.ts`, von `useMemoryTabCounts` und dem
  neuen `useApprovalCount` genutzt (Single Source of Truth).
- viewer: `scope=user` (wie `useApprovalQueue`), editor+: ohne `scope`
  (Server liefert Agentengedächtnis + eigenes Nutzergedächtnis). Rolle `null`:
  keine Anfrage.
- Zurückgehaltene zählen mit (gleiche Menge wie Tab-Zähler); der eigene
  `destructive`-Banner aus §10 hängt an der alten Frage 1 und ist nicht Teil der Karte.
- Fehler/Laden: Zahl unbekannt (`null`) → kein Memory-Banner und kein
  „Alles erledigt“ (sonst behauptete das Band „erledigt“ ohne Beleg).
- Texte (Spec §10 + Delta): Titel „{{count}} Einträge zur Freigabe“ /
  "{{count}} entries awaiting approval", Aktion „Freigeben“ / "Review".

## Dateien (7 inkl. Plan)
1. apps/web/src/features/memory/hooks/useMemoryApi.ts
2. apps/web/src/features/dashboard/pages/DashboardPage.tsx
3. apps/web/src/features/dashboard/pages/DashboardPage.test.tsx
4. apps/web/src/i18n/locales/de.json
5. apps/web/src/i18n/locales/en.json
6. changelog.d/t-5c835da2-lernschleife-c5a2-dashboard-banner.changed.md
7. dieser Plan

## Schritte
- [ ] Hook + Banner
- [ ] Tests + Rot-Proben (Link, scope=user, kein subject_user_id, kein Banner bei Fehler)
- [ ] DoD lokal (Node 22): tsc -b, lint, i18n:check, test:coverage, build, license:check
- [ ] 390 px messen
- [ ] Push, PR, CI
