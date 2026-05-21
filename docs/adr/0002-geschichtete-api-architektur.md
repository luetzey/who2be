# ADR-0002 — Geschichtete Architektur in apps/api

- Status: Akzeptiert
- Datum: 2026-05-21
- Kontext: Who2Be MVP (PROJ-19)

## Kontext

Die API-Geschaeftslogik (CRUD, Versionierung, Owner-Pruefung) soll von
FastAPI und vom Datenbank-Treiber entkoppelt bleiben, damit der Kern isoliert
testbar ist und ein DB- oder Framework-Wechsel lokal bleibt.

## Optionen

- **A — Geschichtet (routers → services → repositories):** Klare Trennung,
  Domain-Modelle in `packages/models`. Etwas mehr Dateien/Indirektion.
- **B — Flach (Logik direkt in den Routern):** Wenig Boilerplate, aber
  Geschaeftslogik mit HTTP- und SQL-Details vermischt — bricht Separation of
  Concerns, schlecht testbar.
- **C — Voller Ports-and-Adapters/Hexagonal:** Maximale Entkopplung, aber fuer
  einen MVP dieser Groesse Over-Engineering.

## Entscheidung

Option A. `routers` (HTTP-Adapter) → `services` (Use Cases) → `repositories`
(Datenzugriff), Domain-Modelle in `packages/models`. Abhaengigkeiten verlaufen
strikt nach innen. Services haengen von einem Repository-`Protocol` ab (DIP),
nicht von der Postgres-Implementierung. `fastapi` lebt nur in `routers`/`main`,
`asyncpg` nur in `repositories`/`core/db`.

## Konsequenzen

- Kern (Modelle, Services) ist framework-frei und mit Fake-Repos schnell
  unit-testbar.
- Etwas mehr Struktur/Dateien — bewusst akzeptiert fuer Testbarkeit und
  saubere Grenzen.
- Das `Protocol` muss gepflegt werden, wenn sich Repository-Signaturen aendern.
