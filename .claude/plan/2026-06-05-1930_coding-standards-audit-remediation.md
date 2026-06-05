# Plan — Coding-Standards-Audit & Remediation (komplette Codebase)

**Datum:** 2026-06-05
**Status:** Welle 0 (`cbd106d`) + Welle 1 (#166) + Welle 2 (#167) gemergt;
Welle 3/WP-3.1 umgesetzt auf `claude/serene-lamport-ueQxe` (Draft-PR offen).
WP-3.2 (DEFERRED/YAGNI) + WP-3.3 (optional, vor Public-Switch) bleiben offen.
**Branch:** `claude/serene-lamport-ueQxe`
**Anlass:** Vollständige Prüfung der Codebase gegen das Notion-Composite
[`Coding-Standards`](https://www.notion.so/367be5372ab881938a8accf264e66209)
(V1.5) und seine 9 Atomics, plus die repo-spezifischen Konkretisierungen in
`CLAUDE.md`, Skills `python-conventions`/`react-conventions` und
`docs/frontend/design-language.md`.

## Geprüfte Standards (Makro → Mikro)

1. Architektur-Standards · 2. Deployment-Standards (Single Codebase) ·
3. Design-Prinzipien · 4. Frontend-Standards · 5. Clean-Code-Style ·
6. Security-Standards · 7. Test-Strategie & QA · 8. Licensing-Standards
(Entitlements) · 9. OSS-License-Compliance

## Methodik

- Qualitäts-Gates lokal gefahren: `ruff check`, `ruff format --check`,
  `mypy .`, `pytest -q` (mit/ohne `--group billing`), `eslint`,
  `tsc --noEmit`.
- Drei tiefe Pattern-Audits (Frontend / Security / Architektur+Clean-Code+
  Deployment+Licensing+OSS) über die gesamte Codebase.

## Gesamtbefund

**Die Codebase ist in sehr gutem Zustand.** Keine High-Severity-Verstöße in
Architektur, Security oder Licensing. Die offenen Punkte sind überwiegend
**Gate-Lücken** (Standards lokal erfüllt, aber von CI nicht erzwungen → Drift
möglich) und **Frontend-Primitive-Reinheit** in einer nicht-gegateten
Editor-Ecke. Eine echte inhaltliche Lücke gegen die Standards: **kein
OSS-Lizenz-Scan** (nur CVE-Audit).

### Bereits sauber verifiziert (kein Handlungsbedarf)

| Standard | Ergebnis |
|---|---|
| **Security-Standards** (alle 8 Punkte) | PASS — Server-seitige Authz (`require_role`/`get_current_workspace`), Secrets nur server-seitig (Web nur `VITE_`-Public), Auth-Token in `sessionStorage`/In-Memory (kein localStorage), kein `dangerouslySetInnerHTML` (BlockNote-JSON), Security-Header zentral im Caddyfile, Webhook-Signaturen (HMAC + `compare_digest`), parametrisiertes SQL durchgängig, Tenant-Scoping + Postgres-RLS (Migration 0036/0037) als Defense-in-Depth. |
| **Architektur-Standards** | PASS — saubere 4-Schichten (Router→Service→Repository→DB), kein SQL in Handlern, Repos als `Protocol`, Hexagonal-Adapter (`EntitlementPort` Cloud/On-Prem), 31 ADRs. |
| **Deployment-Standards** | PASS — `core/config.py` als zentrale `BaseSettings` (kein verstreutes `os.getenv`), Logs nur nach stdout (ADR-0007), Edition-Flag zur Laufzeit, Billing dynamisch importiert (ADR-0029), RLS-Symmetrie Cloud/On-Prem. |
| **Design-Prinzipien** | STRONG — SRP/DIP eingehalten, keine God-Klassen >1000 Z. mit Mehrfachverantwortung, keine Funktion >80 Z., DRY-Wiederholung minimal & bewusst. |
| **Licensing-Standards** | PASS — `Entitlement` als SSoT, Feature→Mapping nur aus Provider-Metadaten (kein Hardcode), nur `K_pub` im Repo (kein Private Key), Offline-Verifikation. |
| **Test-Strategie & QA** | PASS (inhaltlich) — 90 Python-/87 Web-Testdateien, 560 passed/158 skipped, A11y-Gate (axe) in CI. Siehe aber WP-0.2 (Collection-Robustheit). |
| **Clean-Code-Style** | PASS (inhaltlich) — `mypy strict` fehlerfrei, keine bare `except`, sprechende Namen. Siehe aber WP-0.1 (Format-Drift). |
| **Frontend-Standards** (6 von 8 Kat.) | PASS — Design-Tokens (kein `#hex`/`px` im JSX), Layout-Primitives, keine Cross-Feature-Deep-Imports, UX-States via `components/data/*`, A11y (aria-label, focus-visible), keine Utility-Suppe (cva/cn). |

---

## Arbeitspakete

Vier Wellen, nach Aufwand/Nutzen geordnet. **Welle 0 und 1** sind die echten
Standard-Lücken (Gates), **Welle 2** ist Frontend-Primitive-Reinheit, **Welle 3**
ist optionales Housekeeping. Empfehlung: je Welle ein eigener Draft-PR
(reviewbar), alle auf `claude/serene-lamport-ueQxe`.

---

### Welle 0 — Gate-Hygiene (Clean-Code-Style + Test-Strategie & QA)

Standards lokal erfüllt, aber von CI nicht erzwungen → Drift sammelt sich an.

#### WP-0.1 — Format-Drift beheben + CI-Format-Gate · **Severity: Medium**

- **Befund:** `ruff format --check .` würde **27 Dateien** reformatieren — davon
  **11 in Produktiv-`src`** (u.a. `apps/api/src/who2be_api/core/migrations.py`,
  `licensing/license.py`, `repositories/{account,agent,workspace_member}_repository.py`,
  `routers/{gdpr,members,resource_composition}.py`,
  `services/{gdpr_export_service,resource_composition_service,version_diff}.py`)
  und **16 in Tests**. CLAUDE.md führt `ruff format` als Pflicht-Befehl, **CI
  fährt es aber nicht** (`ci.yml` hat nur `ruff check`, Z. 35).
- **Standard:** Clean-Code-Style „Repo-Styleguide einhalten" / DoD.
- **Aktion:**
  1. `uv run ruff format .` ausführen (27 Dateien angleichen).
  2. In `.github/workflows/ci.yml` (Python-Job, nach „Lint") einen Step
     `Format check` mit `uv run ruff format --check .` ergänzen.
- **DoD:** `ruff format --check .` grün; CI bricht künftig bei Format-Drift.

#### WP-0.2 — Billing-Tests gegen fehlende Gruppe absichern · **Severity: Low**

- **Befund:** `pytest -q` **ohne** `--group billing` bricht bei der **Collection**
  ab (`ModuleNotFoundError: who2be_billing`) statt sauber zu skippen —
  4 Module: `packages/billing/tests/test_{mollie_adapter,mollie_endpoint,plans,webhook}.py`.
  CLAUDE.md beschreibt den On-Prem-Kern-Lauf ohne Billing als gültig.
- **Standard:** Test-Strategie & QA (Suite muss im Kern-Profil lauffähig sein);
  Deployment-Standards (Core ohne Cloud-Modul betreibbar).
- **Aktion:** In den 4 Modulen `pytest.importorskip("who2be_billing")` am
  Dateikopf ergänzen (vor den `who2be_billing`-Imports).
- **DoD:** `uv run pytest -q` (ohne Gruppe) läuft grün durch (Billing-Tests
  skipped); mit `--group billing` weiterhin alle aktiv.

#### WP-0.3 — ESLint-Warnings auf Null · **Severity: Low**

- **Befund:** 0 Errors, **3 Warnings**:
  `components/editor/system-prompt/PlaceholderBlock.test-utils.tsx:27`
  und `components/forms/LanguageSelect.tsx:9`
  (`react-refresh/only-export-components`) sowie
  `features/auth/pages/InvitationAcceptPage.tsx:78`
  (`react-hooks/exhaustive-deps`).
- **Standard:** Clean-Code-Style (Boy-Scout-Rule); DoD „lint grün".
- **Aktion:** Konstanten/Utils aus den beiden Komponenten-Dateien in eigene
  Nicht-Komponenten-Module auslagern; `runAccept` in `InvitationAcceptPage`
  via `useCallback` stabilisieren und in die Dep-Liste aufnehmen (Verhalten
  unverändert).
- **DoD:** `npm run lint` ohne Warnings; `npm test` grün.

#### WP-0.4 — `uv.lock` ↔ `pyproject.toml` rekonziliieren · **Severity: Low**

- **Befund:** Im committeten `uv.lock` weicht `requires-dist` von den
  `pyproject.toml`-Specifiern ab (`uvicorn` Lock `>=0.49.0` vs. pyproject
  `>=0.34`; `fastmcp` Lock `>=3.4.1` vs. `>=2.3`) — Dependabot-Drift.
- **Standard:** Deployment-Standards „Explizite Abhängigkeiten" (12-Factor II),
  reproduzierbarer Build.
- **Aktion:** `uv lock` ausführen, abgeglichenen `uv.lock` committen. (Falls die
  höheren Mindestversionen gewollt sind: stattdessen die `pyproject.toml`-Specifier
  anheben — Entscheidung dokumentieren.)
- **DoD:** `uv lock --check` (bzw. `uv sync` ohne Lock-Änderung) sauber.

---

### Welle 1 — OSS-License-Compliance (echte Standard-Lücke) · **Severity: Medium**

Der einzige Standard mit einer inhaltlichen Lücke statt nur einer Gate-Lücke.

#### WP-1.1 — Lizenz-Scan in CI ergänzen

- **Befund:** Der CI-`audit`-Job (`ci.yml` Z. 94–120) prüft nur **Vulnerabilities**
  (`pip-audit`, `npm audit`), **keine Lizenzen**. Der Standard verlangt
  „Scan-Pflicht bei jedem Dependency-Add" mit Fokus auf AGPL/Copyleft/unbekannt.
  Projekt-Lizenz ist **FSL-1.1-Apache-2.0** (source-available, → Apache 2.0) —
  eingezogenes (A)GPL/Copyleft wäre beim Redistribuieren ein Risiko.
  Aktuell stichprobenartig keine Copyleft-Deps gefunden (FastAPI/uvicorn MIT,
  asyncpg/mollie BSD, structlog Apache-2.0) — aber **nicht automatisiert
  abgesichert**.
- **Standard:** OSS-License-Compliance (Scan-Pflicht, AGPL-Falle,
  Kompatibilität).
- **Aktion:** Im `audit`-Job zwei Steps ergänzen, beide **fail-closed**:
  - Python: `uv export ... | pip-licenses`-Äquivalent bzw.
    `uv tool run pip-licenses --format=json` mit Deny-Liste
    (`GPL`, `AGPL`, `LGPL`, `MPL`?, `UNKNOWN`/leer) → bei Treffer Exit ≠ 0.
  - Web: `license-checker-rseidelsohn --onlyAllow "MIT;Apache-2.0;BSD-2-Clause;
    BSD-3-Clause;ISC;0BSD;CC0-1.0;Unlicense"` (Allow-Liste) → fail bei Verstoß.
  - Bewusste Ausnahmen über eine kurze Allow-/Override-Datei pflegen.
- **DoD:** CI-Job rot bei Copyleft/AGPL/unbekannter Lizenz; aktueller Stand grün.

#### WP-1.2 — Policy + ADR dokumentieren

- **Aktion:** `docs/adr/0032-oss-license-policy.md` anlegen (Allow-Liste,
  Deny-Liste, AGPL-Begründung im SaaS+On-Prem-Kontext, Override-Prozess) und in
  CONTRIBUTING.md auf den Scan + die Policy verweisen.
- **Optional (WP-1.3):** SBOM-Artefakt im CI generieren
  (`cyclonedx-py` für Python, `@cyclonedx/cyclonedx-npm` für Web) und als
  Build-Artefakt hochladen — für formale Bill-of-Materials.
- **DoD:** ADR vorhanden, in `docs/adr` referenziert; CONTRIBUTING.md aktualisiert.

---

### Welle 2 — Frontend-Standards: Primitive-Reinheit + Gate-Lücke ✅ UMGESETZT

Eine nicht-gegatete Editor-Ecke verletzt zwei Frontend-Standards.

**Umsetzung (Draft-PR):** Radix-`RadioGroup`-Primitive unter `@/components/ui/`
ergänzt; die 4 Radio-Picker (`Catalog`/`DateFormat`/`PersonaField`/
`ResourcesCatalogScope`) darauf umgestellt (rohe `<input>`/`<label>` weg).
Daten-Logik aus `PlaybookPicker`/`ResourcePicker`/`PlaceholderPreviewPopover`
in Hooks `usePlaybookSearch`/`useResourceSearch`/`usePlaceholderPreview`
(`system-prompt/hooks/`) extrahiert (kein `useApi()` mehr in der UI). ESLint-
Roh-HTML-Gate auf alle `src/components/**` ausgeweitet (außer `components/ui/**`).
DoD lokal grün: lint 0 Errors, `tsc` 0, 376 Tests, Build, License-Gate.

#### WP-2.1 — Rohe Radio-Inputs durch UI-Primitive ersetzen · **Severity: Medium**

- **Befund:** 5 Picker unter `components/editor/system-prompt/pickers/` nutzen
  rohe `<input type="radio">` + `<label>`:
  `CatalogScopePicker.tsx:88–101`, `DateFormatPicker.tsx`,
  `PersonaFieldPicker.tsx`, `ResourcesCatalogScopePicker.tsx:131,142`
  (und Geschwister). Frontend-Standard: „alle interaktiven Elemente durch die
  Primitives" (konsistente Fokus-/Hover-/Disabled-States).
- **Standard:** Frontend-Standards „Komponenten als Bibliothek" / Primitive-Reinheit.
- **Aktion:** `RadioGroup`/`RadioGroupItem`-Primitive in `@/components/ui/`
  ergänzen (`npx shadcn add radio-group`, Radix-basiert, cva-konform) und die
  5 Picker darauf umstellen.
- **DoD:** keine rohen `<input>`/`<label>` mehr in `pickers/`; `npm test`
  (Picker-Tests) + `tsc` + `build` grün; Fokus-/Tastatur-Verhalten geprüft.

#### WP-2.2 — API-Calls aus UI-Pickern in Hooks heben · **Severity: Medium**

- **Befund:** 3 Komponenten holen direkt Daten statt reine Präsentation zu sein:
  `pickers/ResourcePicker.tsx:76,109,140` (`useApi`, `listResources`,
  `getResource`), `pickers/PlaybookPicker.tsx:35,48–49`,
  `PlaceholderPreviewPopover.tsx:87,94–95`.
- **Standard:** Frontend-Standards „UI-Schichtung & Primitive-Reinheit"
  (Datenholen gehört nicht in tief verschachtelte UI-Komponenten).
- **Aktion:** Daten-Logik in Custom-Hooks unter
  `components/editor/system-prompt/hooks/` (bzw. Feature-`hooks/`) extrahieren
  (`useResourceSearch`, `usePlaybookSearch`, `usePlaceholderPreview`); Picker
  bleiben Präsentation, bekommen Daten/Callbacks per Props.
- **DoD:** keine `useApi()`-Aufrufe mehr in den 3 Dateien; bestehende Tests
  grün; Verhalten unverändert (`data-testid` beibehalten).

#### WP-2.3 — ESLint-`no-restricted-syntax`-Gate erweitern · **Severity: Medium**

- **Befund:** Das Roh-HTML-Verbot greift nur in
  `features/**`, `components/{layout,data}/**`, `app/**` — die Editor-Ecke
  `components/editor/**` ist **ungegated** (Ursache für WP-2.1/2.2, die durch
  kein Gate auffielen).
- **Standard:** Frontend-Standards (Lint als Single-Source-Durchsetzung).
- **Aktion:** In `apps/web/eslint.config.js` die `files`-Globs der
  Roh-Element-Regel auf `src/components/editor/**` (idealerweise alle
  `src/components/**` außer `components/ui/**`) ausweiten. **Reihenfolge:** erst
  WP-2.1/2.2 (Code anpassen), dann Gate ziehen, sonst rote Lint.
- **DoD:** `npm run lint` grün mit erweitertem Gate; künftige rohe Form-Controls
  in der Editor-Ecke brechen den Build.

---

### Welle 3 — Housekeeping (optional, YAGNI-bewusst)

#### WP-3.1 — Deprecation-Warnings beseitigen · **Severity: Low** ✅ UMGESETZT

- **Befund:** pytest-Warnings: FastAPI `HTTP_422_UNPROCESSABLE_ENTITY`
  deprecated (→ `HTTP_422_UNPROCESSABLE_CONTENT`); OpenTelemetry
  `SelectableGroups`-DeprecationWarning (Transitiv — beobachten).
- **Aktion:** Eigene `HTTP_422_*`-Verwendungen umstellen; OTel-Warning nur
  dokumentieren (Upstream).
- **DoD:** keine selbstverursachten Deprecation-Warnings mehr in `pytest`.
- **Umsetzung:** 9 `HTTP_422_UNPROCESSABLE_ENTITY` → `…_CONTENT` (alias-gleich,
  Wert 422; 8 Dateien in `apps/api` + `packages/billing`). OTel-Warning eng per
  `filterwarnings` (nur diese Meldung) in `pyproject.toml` gefiltert + kommentiert
  — Suite jetzt warning-frei (585 passed, 174 skipped). **Zusätzlich** (Boy-Scout):
  4 vorbestehende Format-Drift-Dateien (`agent_scope`, `security`,
  `test_placeholder_renderer`, `tool_policy`) reformatiert — der Welle-0-
  Format-Gate war latent rot, weil CI seit den Startup-Failures nie lief.
  DoD grün: `ruff check`/`format --check`/`mypy` sauber, pytest warning-frei.

#### WP-3.2 — Versionierungs-Repo-Basis (DEFERRED · YAGNI)

- **Befund:** `persona/playbook/resource_repository.py` teilen sehr ähnliche
  Versionierungs-CRUD-Muster (`_select_current/_select_active`, `upsert_draft`,
  `restore_version`…). Aktuell bewusst dupliziert (locale-i18n, je
  Entity eigene Denormalisierung).
- **Entscheidung:** **Nicht jetzt extrahieren** (YAGNI). Erst wenn eine **4.**
  versionierte Entity mit identischem Muster entsteht → `VersionedEntityRepository`
  Mixin/Basis. Hier nur als bewusster, dokumentierter Verzicht festgehalten
  (Design-Prinzipien: „Pattern nur wo echtes Problem").

#### WP-3.3 — FSL-Lizenz-Header in Quelldateien (optional)

- **Befund:** Quelldateien tragen keinen FSL-Header (LICENSE.md +
  `pyproject`/`package.json` sind autoritativ).
- **Entscheidung:** Für FSL nicht zwingend; bei Bedarf nur für **neue** Module
  einführen. Standalone niedrigste Priorität — vor dem Public-Switch
  (`…2028_public-switch-github-repo`) erneut bewerten.

---

## Branch- & PR-Strategie

- **Branch:** `claude/serene-lamport-ueQxe` (vorgegeben).
- **PRs (Draft), je Welle einer** — reviewbar, unabhängig mergebar:
  - PR A: Welle 0 (Format + CI-Gate + importorskip + eslint-Warnings + uv.lock).
  - PR B: Welle 1 (Lizenz-Scan + ADR-0032).
  - PR C: Welle 2 (Radio-Primitive + Hooks + ESLint-Gate).
  - PR D (optional): Welle 3.
- Conventional Commits; jeder PR mit Session-Link.

## Gesamt-DoD

Pro Welle Stack-DoD lokal grün **vor Push**:
- Python: `ruff check .`, `ruff format --check .`, `mypy .`,
  `pytest -q` (mit & ohne `--group billing`).
- Web: `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build`.

## Aufwandseinschätzung

| Welle | Umfang | Risiko |
|---|---|---|
| 0 | klein (mech. Format + 3 CI/Code-Edits) | minimal |
| 1 | klein–mittel (CI-Steps + ADR) | gering (evtl. Allow-Liste justieren) |
| 2 | mittel (neues Primitive + 3 Hook-Refactors + Gate) | gering–mittel (Editor-Regression beachten) |
| 3 | klein (optional) | minimal |
