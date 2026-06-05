# Build-Zeit-Isolation von Billing + Entitlement-Schreibquellen

**Status:** Plan (Verifikation abgeschlossen, Entscheidungen aus Nachtrag 1+2 eingearbeitet) — bereit zur Verteilung nach Trennschnitt-Bestätigung
**Datum:** 2026-06-05
**Vorgänger:** `2026-06-02-1819_followups-rls-mollie-auth-fsl.md` (Track J Mollie/Entitlement, auf `main`); `2026-06-03-2030_cloud-launch-readiness.md` (Track Cloud-Local-Dev-Tooling → `who2be-set-entitlement`).
**Methode:** Verifikations-Report + Gap-Analyse + datei-disjunkte Tracks (A–F).

> Leitprinzip (Nachtrag 1+2): **Die App erzeugt nie ein Entitlement — sie liest es nur.**
> Lizenz-/Billing-Grenzen werden zur **BUILD-ZEIT** durchgesetzt, nicht zur Laufzeit.
> Alles, was im On-Prem-Artefakt physisch vorhanden ist, gilt als missbrauchbar.

---

## 1. Verifikations-Report (Ist-Stand am Code, `file:line`)

Doku-Behauptung (CLAUDE.md / Notion) gegen den realen Code geprüft. Wo Doku ≠ Code,
**gewinnt der Code**.

| Punkt | Status | Beleg | Anmerkung |
|---|---|---|---|
| Cloud/On-Prem über `WHO2BE_EDITION` | **vorhanden** | `apps/api/src/who2be_api/core/config.py:89-92`; `licensing/edition.py:12-24` (`is_cloud/is_onprem`) | Default `onprem`. |
| Hexagonaler `EntitlementPort` | **vorhanden** | `licensing/port.py:15-18` (Protocol `resolve(org_id)`) | Sauber. |
| Cloud-Adapter (liest zentrale Tabelle) | **vorhanden** | `licensing/adapters/cloud.py:20-28` → `PgEntitlementRepository.fetch` | Reiner Read; Default `CLOUD_FREE_ENTITLEMENT`. |
| On-Prem-Adapter (K_pub, offline) | **vorhanden** | `licensing/adapters/onprem.py:35-57`; `licensing/crypto.py:44-87` | **Liest NICHT `org_entitlement`** — resolved live aus `WHO2BE_LICENSE_KEY`. |
| Adapter-Auflösung über Edition-Flag | **vorhanden** | `licensing/service.py:24-29` (`build_entitlement_port`) | Factory `is_cloud()` → Cloud- vs. On-Prem-Adapter. |
| Entitlement als Org-SSoT | **vorhanden** | `licensing/entitlement.py:1-11,55-128`; Tabelle `migrations/0030_org_entitlement.sql:10-26` | `is_active()`/`has_feature()`/`entity_limit()` als einzige Zugriffs-Wahrheit. |
| Mollie-Billing (Track J) | **vorhanden** | `licensing/adapters/mollie.py` (SDK-Import `:45`); `routers/billing.py:259-310` | Pull-after-Ping korrekt (s.u.). |
| Pull-after-Ping | **vorhanden/korrekt** | `licensing/adapters/mollie.py:454-507` (`handle_webhook` fetcht via API, `org_id` nur aus gefetchtem Objekt) | Webhook-Body wird nicht vertraut. |
| K_pub im Repo, K_priv NICHT | **vorhanden/korrekt** | `licensing/crypto.py:7,44-62` (verify-only); `licensing/keys/README.md`; Slot `keys/signing_key.pub` = `.gitkeep` | Signatur-Erzeugung nur in Tests (`tests/test_licensing_crypto.py:30-33`). |
| FSL-1.1-Lizenz (Track L) | **teilweise** | Root `pyproject.toml:6` `license = "FSL-1.1-Apache-2.0"`; `LICENSE.md`/`CONTRIBUTING.md` per `…1935`-Plan noch offen | Lizenztext-Ausführung ist eigener Track L, nicht hier. |
| Org/Workspace-Tenant-Layer | **vorhanden** | ADR-0019; `_resolve_org_id` `routers/billing.py:234-241` | — |
| Versionierung non-destruktiv (Status) | **vorhanden** | ADR-0020; CLAUDE.md (PUT auf Active → Draft, 409 bei vorhandenem Draft) | Aktive Versionen werden nicht in-place editiert (Risiko-Check §6). |
| **Build-Isolation Billing ↔ App** | **fehlt** | s. Gap §2 | Trennung heute **nur Runtime-404**. |
| **Einzige Entitlement-Schreibquelle** | **fehlt** | s. Gap §2 (CLI-Loch) | Mehrere Schreibwege, `source` ohne CHECK. |
| Signier-/Lizenz-Ausstellprozess (extern) | **fehlt** | kein Issuer-Tool im Repo (`scripts/` hat keinen) | Nur Test-Helfer signieren. On-Prem-Lizenz aktuell betrieblich nicht ausstellbar. |

**Doku-vs-Code-Abweichungen:**

1. `licensing/__init__.py` und `.env.example:41-44` behaupten **„Ein Build, ein Image — der
   Unterschied Cloud vs. On-Prem ist allein Runtime-Config".** Das ist die heutige Realität,
   steht aber im **direkten Widerspruch** zur Leitlinie aus Nachtrag 1+2 (Build-Zeit-Trennung).
   Diese Behauptung wird durch den Plan **bewusst aufgehoben** → „Ein **Codebase**, zwei
   **Build-Profile**" (ADR-0029, Doku-Update Track F).
2. `routers/billing.py:11-13` Docstring: „keine Billing-Logik im Kern" — stimmt für das
   *Mapping* (`licensing/billing.py`), aber der **Router + Mollie-SDK** sind sehr wohl im Kern-
   Build (`main.py`). Build-technisch also unzutreffend.
3. `migrations/0030`-Kommentar: `source` „'cloud' bzw. 'onprem'" — real schreibt der Code auch
   `'mollie'` (`adapters/mollie.py`) und `'manual'` (`core/set_entitlement.py:40`); die Spalte
   hat **keinen** CHECK (`migrations/0030_org_entitlement.sql:23`).

---

## 2. Gap-Analyse — wo der Code das Zielprinzip verletzt

### G-1 — Billing/Mollie ist physisch im On-Prem-Artefakt (Build-Isolation fehlt)
- `apps/api/src/who2be_api/main.py:37` importiert `billing` **hart**; `:177,186,188` registriert
  `billing.router` + `billing.webhook_router` + `billing.mollie_webhook_router` **unbedingt**.
- `apps/api/pyproject.toml:20` deklariert `mollie-api-python>=3.7` als **harte** Dependency →
  in **jedem** Image, auch On-Prem.
- `routers/billing.py:34` importiert `SdkMollieGateway`; `licensing/plans.py` (Tarif-/Preis-Daten)
  und `licensing/adapters/mollie.py` (Checkout) kompilieren ins On-Prem-Artefakt.
- Trennung heute ausschließlich Runtime: `_require_cloud()` → 404 (`routers/billing.py:89-91`).
- **Folge:** Der Kunde hat Mollie-Client, Checkout-Logik und die komplette Tarif-Struktur im
  ausgelieferten Build.

### G-2 — Web-Bundle enthält Billing-/Tarif-Interna (nur Runtime-Hide)
- `apps/web/src/features/billing/*` wird in **jeden** Build gebündelt; Ausblenden nur zur Laufzeit
  über den API-Wert `data.edition !== 'cloud'` (`features/billing/components/BillingPanel.tsx:61`),
  gespeist aus `GET …/billing/entitlement` (`hooks/useEntitlement.ts:37-39`).
- **Folge:** Mollie-/Tarif-/Checkout-Interna liegen im ausgelieferten On-Prem-JS offen.

### G-3 — KRITISCH: Roher Entitlement-Schreibweg im On-Prem-Build (CLI-Loch)
- `apps/api/src/who2be_api/core/set_entitlement.py:83` schreibt `org_entitlement` **direkt**
  (`repo.upsert(..., source='manual', external_ref=None)`), **ohne** Ablaufdatum
  (`set_entitlement.py:48-55` setzt `expires_at=None`), beliebiger Plan (`free`/`pro`).
- Ausgeliefert als Console-Script: `apps/api/pyproject.toml` `[project.scripts]`
  `who2be-set-entitlement = "who2be_api.core.set_entitlement:cli"` (verifiziert via
  `grep`, Zeile 33 der api-pyproject).
- `org_entitlement.source` ist freier Text **ohne CHECK** (`migrations/0030_org_entitlement.sql:23`)
  → jeder beliebige Herkunfts-String wird akzeptiert.
- **Exploit-Pfad (real):** Der On-Prem-Adapter ignoriert die Tabelle, **aber** das On-Prem-Artefakt
  enthält den **Cloud-Read-Adapter** (`adapters/cloud.py`) *und* den Roh-Writer
  (`set_entitlement.py`) *und* `plans.py`. Ein Operator setzt `WHO2BE_EDITION=cloud`, ruft
  `who2be-set-entitlement <org> pro` auf → `CloudEntitlementAdapter` liest Pro aus der Tabelle →
  **Pro ohne Mollie, ohne signierte Lizenz.** Das gesamte On-Prem-Lizenzmodell ist damit
  wirkungslos.

### G-4 — Mehrere unkontrollierte Schreibquellen, kein Audit
- Schreibwege heute: Webhook (`source='cloud'`), Mollie (`source='mollie'`), CLI
  (`source='manual'`). Keine ist als nachvollziehbarer, **befristeter** Override modelliert;
  kein Urheber/Grund; kein Pflicht-`expires_at`. `EntitlementRepository.upsert`
  (`repositories/entitlement_repository.py:55-88`) kennt nur `source`+`external_ref`.

### G-5 — Kein betrieblicher On-Prem-Lizenz-Einspielpfad
- On-Prem nimmt den Key heute **nur** über `WHO2BE_LICENSE_KEY` (Env) entgegen
  (`adapters/onprem.py:36`). Es gibt kein verifikations-gegateates Install-Werkzeug, das einen
  gekauften Key prüft, bevor er wirkt (auch wenn die Verifikation bei jedem Read greift).

---

## 3. Zielmodell — Entitlement-Schreibquellen (eine Tabelle, ein Lesen)

`org_entitlement` bleibt die **einzige** SSoT, die die App liest (unverändert über den Port).
Es wird **nur** geschrieben — nie von der ausgelieferten Read-App, sondern von klar benannten,
build-getrennten Quellen:

| `source` | Edition | Wer schreibt | Pflichtfelder | Im On-Prem-Artefakt? |
|---|---|---|---|---|
| `mollie` | Cloud | Billing-Paket (Mollie-Pull) | `external_ref` (Subscription-ID) | **Nein** |
| `cloud` | Cloud | Billing-Paket (generischer HMAC-Webhook) | `external_ref` | **Nein** |
| `manual_override` | Cloud | Cloud-Ops-Override (Billing-Paket) | **`expires_at`**, `created_by`, `reason` | **Nein** |
| `signed_license` | On-Prem | **kein Tabellen-Write** — Adapter resolved live aus K_pub-verifiziertem Token | — | (n/a) |

- On-Prem entsteht ein Entitlement **ausschließlich** über den K_pub-Verifikationspfad
  (`verify_license_token` → `entitlement_from_license`). Es gibt im On-Prem-Build **keinen**
  Tabellen-Writer mehr.
- `manual_override` ist konzeptionell nur **eine weitere Quelle** neben Kauf — gleiche Tabelle,
  gleicher Read-Pfad, aber **befristet + auditiert**. Damit ist ein späterer **Marketplace**-Kauf
  strukturell identisch (eigene `source`, geschrieben von einem separaten Transaktions-Dienst,
  gelesen von der App) — der Plan verbaut diese Generalität nicht.

---

## 4. Trennschnitt-Optionen Backend (Nachtrag 2 §1 — 2–3 Varianten mit Trade-offs)

Gemeinsames Ziel: `main.py` importiert **nur** den `EntitlementPort`; Mollie-Dependency + Billing-
Routen sind im On-Prem-Artefakt **nicht vorhanden**.

### Option A — Separates uv-Workspace-Paket `who2be-billing` (EMPFEHLUNG)
- Neues Workspace-Member (z. B. `apps/billing/`), das `mollie-api-python` deklariert und enthält:
  `routers/billing.py` (Webhook + Mollie-Webhook + Checkout), `licensing/billing.py`,
  `licensing/plans.py`, `licensing/adapters/mollie.py`, `repositories/processed_event_repository.py`,
  den Cloud-`manual_override` (Track D).
- Abhängigkeitsrichtung **nur** `who2be-billing → who2be-api` (für `get_pool`, `security`,
  `EntitlementRepository`, `Entitlement`); **nie** umgekehrt.
- `main.py` registriert Billing **optional**: `register_billing_if_present(app)` versucht
  `import who2be_billing` und ruft dessen `include_routers(app)` nur, wenn das Paket installiert
  **und** `is_cloud()`. On-Prem-`uv sync` installiert das Paket nicht → Import schlägt fehl →
  keine Routen, kein `mollie` importierbar.
- Build: ein Dockerfile, zwei Profile — Cloud-Target `uv sync --group billing`, On-Prem-Target ohne.
- **Trade-off:** + stärkste, durch Packaging *erzwungene* Isolation (Import kann nicht auflösen);
  + passt zur Port/Adapter-Architektur; + generalisiert auf Marketplace/Transaktions-Dienst.
  − neue Paketgrenze + optionale Plugin-Verdrahtung; hebt „ein Image" auf „ein Dockerfile, zwei
  Profile".

### Option B — Optional-Dependency-Group `[billing]` + Conditional Import (in `who2be-api`)
- `mollie-api-python` wandert in eine optionale uv-Group; `main.py` importiert die Billing-Routen
  guarded (try/except ImportError). On-Prem `uv sync` ohne die Group → SDK fehlt → Routen nicht
  registriert.
- **Trade-off:** + minimaler Umbau, keine Paketspaltung. − **Billing-Quellcode** (Router, `mollie.py`,
  `plans.py`) **bleibt im Wheel/Image** — nur das SDK fehlt. **Verletzt die Leitlinie** („alles
  physisch im Artefakt = missbrauchbar"). Nur als Teil-Maßnahme für die SDK-Dependency akzeptabel,
  **nicht** als Gesamtlösung.

### Option C — Zwei Docker-Build-Targets, ein Dockerfile, COPY schließt `billing/`-Verzeichnis aus
- Billing bleibt Quell-Unterpaket `who2be_api/billing/`; das On-Prem-Target kopiert/installiert
  dieses Verzeichnis nicht (Wheel-Exclude + COPY-Exclude). `main.py` importiert guarded.
- **Trade-off:** + kein Paket-Refactor. − Grenze nur per Pfad-Konvention (fragil, leicht versehentlich
  importiert) → braucht zusätzlichen Import-Lint-Guard; − Hatch-Wheel braucht effektiv zwei Profile,
  also ähnlicher Aufwand wie A ohne dessen erzwungene Grenze.

**Empfehlung: Option A.** Der Plan ist auf A geschrieben; B/C sind dokumentierte Alternativen. Eine
Bestätigung von A ist die einzige offene Vorab-Entscheidung (§7 Q1).

---

## 5. Umsetzungsplan — datei-disjunkte Tracks

> Gemeinsamer DoD (Python): `uv run ruff check . && uv run mypy . && uv run pytest -q` grün, lokal
> verifiziert. Bugfix = erst reproduzierender failing Test. (Web): `npm run lint && npx tsc
> --noEmit && npm test && npm run build`. Conventional Commits, Draft-PR nach `main`, Branch von
> `main`. Reihenfolge: **A → {B, C}; B → D; E + F parallel.**

### Track A — Schema + Write-Source-Vertrag (Fundament)
**Ziel:** `org_entitlement` kennt eine geschlossene Source-Taxonomie + Audit/Befristung für Override.
**Dateien:**
- **neu** `apps/api/src/who2be_api/migrations/0040_entitlement_write_sources.sql`:
  - `ADD COLUMN created_by uuid` (nullable), `ADD COLUMN reason text` (nullable).
  - Bestehende `source='manual'`-Zeilen migrieren (Bestand prüfen; voraussichtlich keine in Prod →
    dokumentieren; sonst → `manual_override` mit gesetztem `expires_at` Backfill).
  - `CHECK (source IN ('cloud','mollie','signed_license','manual_override'))`.
  - `CHECK (source <> 'manual_override' OR (expires_at IS NOT NULL AND created_by IS NOT NULL))`.
  - Idempotent, nächste freie Nummer (nach `0039`).
- `apps/api/src/who2be_api/repositories/entitlement_repository.py`: `upsert(...)` um optionale
  `created_by`/`reason` erweitern (Default `None`); `fetch` **unverändert**. Protocol mitziehen.
**DoD:** Integrationstest beweist beide CHECKs (Override ohne `expires_at`/`created_by` → DB-Fehler;
fremder `source`-String → DB-Fehler). ruff/mypy/pytest grün.

### Track B — Backend-Build-Isolation: Billing als optionales Paket (Option A)
**Ziel:** Mollie-Dependency + Billing-Routen nicht im On-Prem-Artefakt; `main.py` kennt nur den Port.
**Abhängigkeit:** Track A (Repo-Vertrag).
**Dateien:**
- **neu** Paket `apps/billing/` (uv-Member `who2be-billing`, eigenes `pyproject.toml` mit
  `mollie-api-python`), Inhalt verschoben aus `who2be_api`:
  `routers/billing.py` (Write-Endpunkte: `/v1/billing/webhook`, `/v1/billing/mollie/webhook`,
  `…/billing/checkout`), `licensing/billing.py`, `licensing/plans.py`,
  `licensing/adapters/mollie.py`, `repositories/processed_event_repository.py`.
  Export `include_routers(app)`.
- `apps/api/src/who2be_api/main.py`: harte Billing-Imports raus (`:37,177,186,188`); stattdessen
  `register_billing_if_present(app)` (optional-import + `is_cloud()`).
- **READ-Endpunkt** `GET …/billing/entitlement` (`routers/billing.py:214-231`) bleibt im **Kern**
  (reiner Read, keine `plans`/`mollie`), unter Cloud-Guard → Web kann Plan/Verbrauch zeigen. Wird in
  einen schlanken Kern-Router `routers/entitlement.py` ausgelagert.
- `apps/api/pyproject.toml`: `mollie-api-python` entfernen; verschobene Module entfernen.
- Root `pyproject.toml`: Workspace-Member `apps/billing`; optionale Group/Source für `who2be-billing`;
  mypy-`overrides` für `mollie.*` ins Billing-Paket ziehen.
- `apps/api/Dockerfile` (+ ggf. neues Cloud-Profil) und `docker-compose.yml`: Cloud-Build
  `uv sync --group billing`, On-Prem ohne.
- **neu** Test `apps/api/tests/test_no_billing_in_core.py`: `who2be_api` importiert **nie**
  `who2be_billing`; `import mollie` schlägt im Kern-only-Env fehl.
**DoD:** On-Prem-Build: `mollie` nicht importierbar, keine `/billing/*`-Write-Routen. Cloud-Build:
Routen registriert, bestehende Billing-Tests grün. `security-reviewer` (Webhook/Pull/Key bleibt
unverändert, nur verschoben).

### Track C — On-Prem-Lizenz-Einspielpfad + Entfernung des Roh-Set-CLI
**Ziel:** Kein Roh-Tabellen-Writer im On-Prem-Build; gekaufter Key nur über Verifikationspfad.
**Abhängigkeit:** keine harte (kann parallel zu B; Override-Verlagerung koordiniert mit D).
**Dateien:**
- `apps/api/src/who2be_api/core/set_entitlement.py`: **löschen** (Roh-Write entfällt). Console-Script
  `who2be-set-entitlement` aus `apps/api/pyproject.toml` `[project.scripts]` entfernen.
- **neu** `apps/api/src/who2be_api/core/license_cli.py` + Script `who2be-license`:
  `install <key>` verifiziert via `verify_license_token(key, K_pub)` (refuse unsigniert/ungültig,
  Exit≠0) und **persistiert den signierten Token** (Env-Datei bzw. Single-Row-`onprem_license`),
  den `OnPremEntitlementAdapter` liest **und bei jedem Read erneut verifiziert** → Persistenz ist
  kein Grant. **Kein** `org_entitlement`-Write. Ships in On-Prem (Kern).
- `apps/api/src/who2be_api/licensing/adapters/onprem.py`: optional persistierten Token lesen (Env
  bleibt Fallback); Verifikationslogik unverändert.
- Doku: `licensing/keys/README.md` um den Install-Flow ergänzen.
**DoD:** `who2be-set-entitlement` existiert im On-Prem-Build nicht mehr; `who2be-license install`
weist unsignierte/fremd-signierte Keys ab (Test); valider Key wird verifiziert + persistiert; Read
verifiziert erneut. `security-reviewer`.

### Track D — Cloud Manual-Override (kontrollierter Ausnahmepfad)
**Ziel:** EIN bewusst gebauter, befristeter, auditierter Override — nur Cloud, im Billing-Paket.
**Abhängigkeit:** Track A (Schema) + Track B (Paket-Platzierung).
**Dateien (im `who2be-billing`-Paket):**
- **neu** Override-Schreiber (Admin-Endpunkt `POST /v1/workspaces/{ws}/billing/override` **oder**
  Cloud-Ops-CLI), der `repo.upsert(..., source='manual_override', created_by=<acting>, reason=<text>)`
  mit **Pflicht-`expires_at`** (relative Dauer, z. B. „Pro 1 Monat") schreibt. `require_role(admin)`.
- Tests: fehlendes `expires_at` → abgelehnt; Audit-Felder persistiert; nur Cloud registriert.
**DoD:** Override nur in Cloud verfügbar (On-Prem-Artefakt enthält ihn nicht, da im Billing-Paket);
abgelaufener Override → `is_active()` false ohne Sonderlogik (greift über `expires_at`).
`security-reviewer`.

### Track E — Web-Build-Isolation der Billing-UI
**Ziel:** `features/billing` nicht im On-Prem-Web-Bundle (nicht nur ausgeblendet).
**Abhängigkeit:** keine.
**Dateien:**
- `apps/web/src/config.ts`: `VITE_WHO2BE_EDITION` (Build-Zeit, Default `onprem`) ergänzen.
- `apps/web/vite.config.ts`: `define`-Konstante (z. B. `__CLOUD_BUILD__`) aus dem Edition-Flag, damit
  Rollup den `false`-Zweig samt statischem Billing-Import **tree-shaked**.
- `apps/web/src/features/settings/pages/OrgSettingsPage.tsx`: Billing-Slot nur unter `__CLOUD_BUILD__`
  rendern; Import von `@/features/billing` in den eliminierbaren Zweig (dynamischer Import) verlagern.
- `apps/web/src/features/billing/*`: Runtime-`edition`-Check als Defense-in-Depth behalten.
- `apps/web/Dockerfile`: Build-Arg `VITE_WHO2BE_EDITION` (Cloud-Target = `cloud`).
- **neu** Build-Assertion-Test: nach `npm run build` (onprem) sind `mollie`/`checkout`/`billing`-
  Strings **nicht** im `dist`-Bundle.
**DoD:** On-Prem-Bundle ohne Billing-Chunk (Assertion grün); Cloud-Bundle zeigt Panel; lint/tsc/test/
build grün.

### Track F — ADRs + Doku (doc-only, parallel)
**Ziel:** Entscheidungen festschreiben, widersprüchliche Doku korrigieren.
**Dateien:**
- **neu** `docs/adr/0028-entitlement-write-sources-override.md` (s. Anhang).
- **neu** `docs/adr/0029-build-time-billing-isolation.md` (s. Anhang).
- `apps/api/src/who2be_api/licensing/__init__.py` + `.env.example` (Edition-Block): „ein Build, ein
  Image" → „ein Codebase, zwei Build-Profile" korrigieren; `VITE_WHO2BE_EDITION` dokumentieren.
- `docs/architecture.md` + `CLAUDE.md` (Edition-/Licensing-Abschnitt) + `docs/licensing/plans.md`:
  Schreibquellen-Taxonomie + Build-Trennschnitt aufnehmen.
**DoD:** ADRs „Akzeptiert"; Doku konsistent zum Code; Querverweise gesetzt.

---

## 6. Risiken & Nebenbefunde (separat, nicht hier mitlösen)

- **R-1 Versionierungs-Immutability (Nebenbefund, nur melden):** Aktive Versionen werden laut
  CLAUDE.md/ADR-0020 **nicht** in-place editiert (PUT auf Active erzeugt Draft, 409 bei vorhandenem
  Draft). Beim Verifizieren kein in-place-Write auf aktive Versionen gefunden — **kein akuter
  Verstoß**, aber nicht tief auditiert. Falls gewünscht: eigener Audit-Track.
- **R-2 Cloud-Adapter im On-Prem-Build:** Selbst nach Entfernen aller Writer enthält On-Prem noch den
  `CloudEntitlementAdapter` (reiner Read). Harmlos ohne Writer (leere Tabelle → `CLOUD_FREE`), aber
  für maximale Sauberkeit könnte auch die Cloud-Read-Auflösung build-ausgeschlossen werden — als
  Folge-Entscheidung notiert, **nicht** im Kern dieses Plans.
- **R-3 Billing liest Identität:** Der Mollie-Checkout liest `organization.name` + `auth.users.email`
  (`routers/billing.py:153-165`). Im Paket-Schnitt (Track B) bleibt das ein Read über `who2be-api`;
  kein Schreibzugriff auf App-Interna. Minor — dokumentieren.
- **R-4 Datenmigration `source='manual'`:** Bestand vor `0040` prüfen; Backfill-Strategie in der
  Migration festhalten (sonst bricht der neue CHECK).

## 7. Offene Fragen (Entscheidung vor Implementierung)

- **Q1 — Trennschnitt bestätigen:** Option **A** (separates `who2be-billing`-Paket) wie empfohlen?
  (B/C dokumentiert, aber B verfehlt die Leitlinie.)
- **Q2 — On-Prem-Token-Persistenz:** Soll `who2be-license install` den verifizierten Token in eine
  **Datei** oder eine **`onprem_license`-Tabelle** schreiben (beide re-verifizieren beim Read), oder
  bei reinem `WHO2BE_LICENSE_KEY`-Env bleiben und das CLI nur **validieren** (kein Persist)?
- **Q3 — Override-Form:** Cloud-`manual_override` als **Admin-HTTP-Endpoint** (Self-Service im
  Workspace) oder als **Cloud-Ops-CLI** (nur Betreiber)? Beeinflusst `created_by`-Quelle.

---

## Anhang — ADR-Stubs
Vollständige ADRs siehe `docs/adr/0028-*.md` und `docs/adr/0029-*.md` (in Track F angelegt; Kerntexte
hier referenziert, nicht dupliziert).

## Notes
**2026-06-05** — V1.0: Anlage nach Code-Verifikation. Kern-Findings: Build-Isolation fehlt (G-1/G-2),
CLI-Loch (G-3, `core/set_entitlement.py:83`), kein Ausstell-/Einspielpfad (G-5). Trennschnitt-Optionen
A/B/C, Empfehlung A. Tracks A–F datei-disjunkt.
