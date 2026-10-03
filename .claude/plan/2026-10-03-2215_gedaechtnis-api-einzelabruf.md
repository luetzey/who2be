# Gedaechtnis-API: Einzelabruf `GET /memories/{memory_id}` (t_ef8822fa)

Folge aus Review C5c-1 (t_7da03826, PR #805): `MemoryDetailSheet` loest
`?entry=<id>` heute ueber Listenabrufe auf; ein Netzfehler sieht dabei aus wie
ein fehlender Eintrag. Diese Karte liefert den API-Teil; der Web-Teil wird
eigene Karte (sonst > 8 Dateien, Karte erlaubt das ausdruecklich).

## Completion-Condition

- `GET /memories/{memory_id}` liefert `MemoryRead` eines sichtbaren Eintrags,
  mit derselben Sichtbarkeit wie `GET /memories`:
  - ab `viewer`: eigenes Nutzergedaechtnis,
  - ab `editor`: dazu Agentengedaechtnis aller Agenten des Workspace,
  - fremdes Nutzergedaechtnis nie, auch nicht fuer `admin` -> 404
    `memory_not_found` (kein 403, kein Existenz-Leak),
  - `viewer` + Agentengedaechtnis -> 404 `memory_not_found` (die Liste zeigt
    es ihm auch nicht),
  - agent-gebundener Token -> 403 `missing_capability`,
  - unbekannte ID -> 404 `memory_not_found`.
- Rot-Probe fuer fremdes Nutzergedaechtnis (Test wird rot, wenn die
  Besitzerbedingung fehlt) und fremden Workspace (Mandantentrennungs-Inventar
  `test_tenant_isolation_api.py`: neue Route steht in `PROBES`, V1/V2 + Gegenprobe).
- `docs/reference/openapi.json` und `tests/contract/openapi_surface.json`
  neu erzeugt, ADR-0053 6.4.1 REST-Tabelle um die Zeile ergaenzt.
- Python-DoD lokal gruen, CI 17/17.

## Entscheidungen (aus dem Repo belegt)

1. **Ein Pfad: `GET /memories/{memory_id}`**, keine Besitzer-Pfade
   (`/agents/{agent_id}/memories/{id}`, `/me/memories/{id}`). Grund: ein
   Deep-Link `?entry=<id>` kennt den Besitzer nicht; genau das ist der Anlass
   der Karte. Die Karte nennt die Besitzer-Pfade nur als Alternative („bzw.“).
   Weniger Oberflaeche, eine Sichtbarkeitsregel.
2. **Sichtbarkeit ueber `get_batch_targets`** (bestehende Repository-Abfrage:
   Agentengedaechtnis + eigenes Nutzergedaechtnis, fremdes filtert SQL). Der
   Service ergaenzt nur die Rollenregel (Agentengedaechtnis ab `editor`) wie
   `_visibility`. Kein neuer SQL-Pfad -> keine zweite Kopie der Regel.
3. **Unsichtbar = 404** auch fuer `viewer` + Agentengedaechtnis: eine Lese-
   Route verraet nicht mehr als die Liste (`batch` hat 403 nur fuer Schreiben).
4. **Antwort `MemoryRead`** wie die Listeneintraege (`MemoryPage.items`).
5. Route steht nach `/memories/counts` im Router (statischer Pfad zuerst).

## Dateien (8, ohne diese Plan-Datei)

1. apps/api/src/who2be_api/routers/memory.py
2. apps/api/src/who2be_api/services/memory_service.py
3. apps/api/tests/test_memory_list_counts_api.py
4. apps/api/tests/test_tenant_isolation_api.py
5. apps/api/tests/contract/openapi_surface.json
6. docs/reference/openapi.json
7. docs/adr/0053-lernschleife-gedaechtnis-faelle-prueffaelle.md
8. changelog.d/t-ef8822fa-memory-einzelabruf.added.md

Web (MemoryDetailSheet auf Einzelabruf, Netzfehler als ErrorAlert mit Retry):
Folgekarte, da client.ts, types.ts, MemoryDetailSheet(.test).tsx, i18n de/en
die 8er-Grenze sprengen.

## Schritte

- [x] Service `get_workspace_memory`
- [x] Router-Route
- [x] HTTP-Tests (Sichtbarkeit, Rechte, 404-Gleichheit)
- [x] Inventar-Eintrag Mandantentrennung
- [x] Rot-Proben (3/3 rot: Besitzerbedingung in `get_batch_targets` entfernt ->
      Einzelabruf-Test rot; Workspace-Bindung entfernt -> Mandantentrennungs-
      Lauf rot an V2 `GET /memories/{memory_id}`; viewer-Rollenregel entfernt ->
      Einzelabruf-Test rot)
- [x] openapi.json, Surface, ADR, Fragment
- [ ] DoD lokal, Push, danach PR
- [ ] Folgekarte Web
