# ADR-0029 — Build-Zeit-Isolation von Billing + Edition-Adapter-Auflösung

- Status: Akzeptiert
- Datum: 2026-06-05
- Kontext: Who2Be — Strikte Trennung Kauf/Billing ↔ App-Editionen (Plan `.claude/plan/2026-06-05-1200_build-isolation-entitlement-sources.md`)

## Kontext

Who2Be liefert eine Codebasis als zwei Editionen (`WHO2BE_EDITION` = `cloud` |
`onprem`). Die Entitlement-**Read**-Seite ist bereits sauber hexagonal:
`EntitlementPort` (`licensing/port.py`) wird per `build_entitlement_port`
(`licensing/service.py:24-29`) nach Edition mit dem Cloud- bzw. On-Prem-Adapter
aufgelöst; die App liest nur das aufgelöste Entitlement.

Die Billing-**Write**-Seite ist dagegen **nicht** isoliert:

- `main.py:37,177,186,188` importiert und registriert die Billing-Routen
  **unbedingt**;
- `apps/api/pyproject.toml:20` deklariert `mollie-api-python` als **harte**
  Dependency → in jedem Image, auch On-Prem;
- die Trennung ist heute reine Laufzeit (`_require_cloud()` → 404,
  `routers/billing.py:89-91`);
- das Web-Bundle enthält `features/billing/*` in jedem Build und blendet nur zur
  Laufzeit aus (`BillingPanel.tsx:61`).

Frühere Doku (`licensing/__init__.py`, `.env.example`) postuliert „Ein Build, ein
Image — der Unterschied ist allein Runtime-Config". Das widerspricht der Leitlinie
des Auftrags: **Lizenz-/Billing-Grenzen werden zur Build-Zeit durchgesetzt; alles
im On-Prem-Artefakt gilt als missbrauchbar.** Diese ADR hebt die alte Behauptung
bewusst auf.

## Optionen

(Trade-offs ausführlich im Plan §4.)

- **A — Separates uv-Workspace-Paket `who2be-billing` (gewählt).** Billing-Write-
  Seite + Mollie-Dependency wandern in ein eigenes Paket; On-Prem-`uv sync`
  installiert es nicht; `main.py` registriert es optional und nur unter
  `is_cloud()`. Isolation ist durch Packaging **erzwungen** (Import löst nicht
  auf).
- **B — Optional-Dependency-Group + Conditional Import in `who2be-api`.** Nur das
  SDK wird ausgeschlossen; der Billing-**Quellcode** bleibt im Wheel/Image.
  Verfehlt die Leitlinie; nur als Teil-Maßnahme akzeptabel.
- **C — Zwei Docker-Targets, COPY schließt `billing/`-Verzeichnis aus.** Grenze
  nur per Pfad-Konvention (fragil), braucht zusätzlichen Import-Lint und faktisch
  zwei Build-Profile — ähnlicher Aufwand wie A ohne dessen erzwungene Grenze.

## Entscheidung

**Option A — ein Codebase, zwei Build-Profile.**

### Backend

- Neues Workspace-Member `who2be-billing` enthält die Write-Seite: Webhook-/
  Mollie-Webhook-/Checkout-Routen, `licensing/billing.py`, `licensing/plans.py`,
  `licensing/adapters/mollie.py`, `processed_event_repository.py`, den
  Cloud-`manual_override` (ADR-0028) und deklariert `mollie-api-python`.
- Abhängigkeitsrichtung **nur** `who2be-billing → who2be-api`; nie umgekehrt
  (Test erzwingt das).
- `main.py` importiert **nur** den `EntitlementPort`/Kern; Billing wird über
  `register_billing_if_present(app)` registriert — optionaler Import **und**
  `is_cloud()`. On-Prem: Paket nicht installiert → kein `mollie` importierbar,
  keine `/billing/*`-Write-Routen.
- Der reine **Read**-Endpunkt `GET …/billing/entitlement` bleibt im Kern (kein
  `plans`/`mollie`), unter Cloud-Guard.
- Build: ein Dockerfile, Cloud-Target `uv sync --group billing`, On-Prem ohne.

### Frontend

- `features/billing` wird zur **Build-Zeit** ausgeschlossen: `VITE_WHO2BE_EDITION`
  (Build-Flag) speist eine `define`-Konstante (`__CLOUD_BUILD__`); der
  On-Prem-Build tree-shaked den Billing-Zweig samt Import → kein Billing-Chunk im
  ausgelieferten JS. Der Runtime-`edition`-Check bleibt als Defense-in-Depth.

### Edition-Adapter-Auflösung (bestätigt)

Die bestehende `build_entitlement_port`-Auflösung über das Edition-Flag bleibt
der **einzige** Schalter zwischen den Editionen für die **Read**-Seite. Neu ist,
dass die **Write**-Seite zusätzlich build-getrennt ist — der Flag wählt zur
Laufzeit nur noch unter dem, was im Artefakt überhaupt vorhanden ist.

## Konsequenzen

- On-Prem-Artefakt enthält weder Mollie-SDK noch Billing-Routen/-Quellcode noch
  die Billing-UI. Ein Edition-Flip auf `cloud` bringt **keine** zusätzlichen
  Rechte (kein Writer vorhanden → Tabelle bleibt leer → `CLOUD_FREE`).
- Doku-Korrektur: „ein Build, ein Image" → „ein Codebase, zwei Build-Profile"
  (`licensing/__init__.py`, `.env.example`, `architecture.md`, `CLAUDE.md`).
- Neue Paketgrenze + optionale Plugin-Verdrahtung; CI baut/prüft beide Profile.
- Generalisiert auf einen späteren Marketplace-/Transaktions-Dienst: ein weiterer
  externer Writer in dieselbe Tabelle, ebenfalls außerhalb des ausgelieferten
  App-Artefakts.
- Nebenbefund (separat): der Cloud-**Read**-Adapter bleibt im On-Prem-Build; ohne
  Writer harmlos, optional später ebenfalls ausschließbar.

## Nachtrag 2026-07-20

Der Read-Endpunkt `GET …/billing/entitlement` ist bewusst **editionsneutral**
(kein Cloud-Guard): On-Prem liefert er `edition='onprem'` samt aufgelöstem
Entitlement. Die Zeile „unter Cloud-Guard" oben ist damit überholt.

Außerdem baut/prüft CI seit 2026-07-20 tatsächlich beide Profile: der Web-Job
ergänzt einen Cloud-Bundle-Build mit Positiv-Assert
(`VITE_WHO2BE_EDITION=cloud`), und ein Build-only-Step baut das Docker-Target
`runtime-cloud`.
