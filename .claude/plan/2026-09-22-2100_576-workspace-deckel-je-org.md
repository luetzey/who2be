# Obergrenze fuer die Zahl der Workspaces je Organisation (#576)

Karte: `t_9dd96916` · Issue: #576 (K6 von #535) · Branch:
`who2be/t_9dd96916-obergrenze-fuer-die-zahl-der-workspaces`

## Ausgangslage (nachgemessen auf `origin/main` @ `37510c1b`)

- `POST /v1/organizations/{organization_id}/workspaces` →
  `routers/organizations.py::create_organization_workspace` →
  `services/workspace_service.py::WorkspaceService.create`. Dort steht nur der
  Org-Membership-Check und der Slug-Konflikt-Fang; **kein** Zaehlwerk.
- Beide Zwillinge sind inzwischen auf `main`:
  `services/storage_quota_service.py` (#536, PR #557) und
  `services/token_quota_service.py` (#538, PR #560). Das Muster ist damit nicht
  mehr Vorschlag, sondern Bestand — inklusive des Rueckfall-Problems, das #538
  mit `Entitlement.effective_token_quota(cloud=...)` geloest hat.
- `workspace` hat kein Soft-Delete (`migrations/0006_workspace.sql`), die
  Zaehlung braucht deshalb keinen Statusfilter.
- `workspace` traegt **keine** RLS-Policy (weder 0037 noch 0068); die
  Org-Endpunkte betreten `tenant_scope` nie, `org_entitlement` ist
  permissiv-bei-unset — der Zaehl- und der Entitlement-Read laufen also im
  Org-Pfad ohne Sonderbehandlung.

## Owner-Entscheidungen (aus den Kartenkommentaren, 2026-09-22)

1. **Free 1, Pro 5** — max. Speicherzusage einer Pro-Org 5 x 10 GiB = 50 GiB.
2. **Die unbegrenzte Org-Anlage wird dokumentiert, nicht gedeckelt.** Keine
   Folgekarte. Begruendung + Gueltigkeitsbereich gehoeren in den Absatz
   „Bekannte Grenzen" von `docs/licensing/plans.md`.

## Entscheidung: Feld mit Cloud-Rueckfall, wie #538 — nicht wie #536

`storage_quota_bytes` (#536) ist ein rohes Feld; `None` heisst dort immer
„unbegrenzt". Fuer den Workspace-Deckel waere das dieselbe Luecke, die das
#538-Review gefunden hat: `webhook.map_event_to_entitlement` schreibt beim
Revoke ein `Entitlement(status="inactive", features=frozenset())` **ohne** das
neue Feld, der Upsert persistiert NULL — eine gekuendigte Cloud-Org duerfte
dann unbegrenzt Workspaces anlegen. Deshalb bekommt `workspace_quota` denselben
Rueckfall wie `token_quota`: `effective_workspace_quota(cloud=...)`, `None` gilt
nur ausserhalb der Cloud als unbegrenzt.

Der Zaehler ist **org-weit** (`count(*) FROM workspace WHERE org_id = $1`) —
anders als bei beiden Zwillingen, die je Workspace zaehlen. Das ist der Zweck
der Karte.

## Schritte

1. `licensing/entitlement.py`: `FREE_WORKSPACE_QUOTA = 1`,
   `PRO_WORKSPACE_QUOTA = 5`, Feld `workspace_quota`,
   `effective_workspace_quota(cloud=...)`, Wert in `OSS_ENTITLEMENT` (None) und
   `CLOUD_FREE_ENTITLEMENT` (Free-Wert).
2. Migration `0086_org_entitlement_workspace_quota.sql` — Spalte auf
   `org_entitlement` **und** `entitlement_history`, `integer`, CHECK `>= 0`,
   idempotent, kein Backfill.
3. `repositories/entitlement_repository.py`: Feld in `fetch`, Insert, `ON
   CONFLICT DO UPDATE SET` und Journal-Insert.
4. Neues `services/workspace_quota_service.py`: `is_cloud()`-Wache,
   org-weite Zaehlung, `402` mit `reason="workspace_quota_exceeded"` und
   `params={"limit": …}`.
5. Gate in `WorkspaceService.create` (nach dem Membership-Check, vor dem
   Repo-Create). Der Service bekommt dafuer einen optionalen `pool` — dieselbe
   Konvention wie `TokenService` (ohne Pool no-op, damit aeltere Test-Fakes
   weiterlaufen). **Nicht** am Router als Dependency, weil der Org-Kontext
   erst im Service aufgeloest ist.
6. Reason registrieren: `packages/models/.../errors.py` (`ProblemReason`),
   `main.py` (`_PROBLEM_TITLES`), `i18n/locales/{de,en}.json`.
7. Billing-Kette: `plans.py` (Feld + `META_WORKSPACE_QUOTA` + Import der
   Konstanten), `mollie.metadata_to_entitlement`,
   `webhook.map_event_to_entitlement`, `router.create_override`,
   `licensing/license.py`, `core/license_cli.py`.
8. Anzeige: `routers/entitlement.py` (`workspace_quota` ueber
   `effective_workspace_quota`), `apps/web/src/api/types.ts`, `BillingPanel`,
   `features/billing/i18n.ts`.
9. Doku: `docs/licensing/plans.md` (Spalte, Metadaten-Tabelle, Rueckfall-Absatz,
   „Bekannte Grenze 1" umschreiben — sie ist mit diesem PR geschlossen — und
   die neue Bekannte Grenze „Orgs je Nutzer" mit Owner-Begruendung und
   Gueltigkeitsbereich). Changelog-Fragment unter `changelog.d/`.
10. Uebergabe aus dem #557-Review: die Code-Kommentare, die noch faelschlich
    „je Org" sagen, korrigieren.
11. OpenAPI neu exportieren, DoD fahren, PR oeffnen.

## Nicht in diesem PR

Org-weites Zaehlen der Speicher-Bytes, die Speicher-Quota selbst (#536), die
Token-Obergrenze (#538), eine Obergrenze fuer die Zahl der Organisationen
(Owner-Entscheidung: dokumentieren, nicht deckeln).

## Verifikation

Wie im Issue §Verifikation. Der OpenAPI-Drift-Check ist Pflicht. Die
Integrationstests muessen im CI gelaufen sein — lokal ohne Docker werden sie
uebersprungen, und `skipped` ist kein Beleg.
