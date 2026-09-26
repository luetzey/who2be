# #538 — Obergrenze fuer Agent-Tokens je Workspace (Free 3, Pro 25)

Branch: `wt/i538-token-quota` · Karte: `t_dd6f2946` · Issue: #538
Owner-Entscheidung: **Option A — Free 3, Pro 25, je Workspace.**
Rebase-Stand: `origin/main` @ `87de64c` (enthaelt #536, PR #557 noch offen —
siehe „Abhaengigkeit" unten).

## Ziel (Completion-Condition, messbar)

Ein Token-Create ueber der fuer den Tarif geltenden Grenze antwortet `402`
mit `reason="token_quota_exceeded"` und der Grenze in `params`; bestehende
Tokens bleiben nutzbar **und rotierbar**; widerrufene und abgelaufene Tokens
zaehlen nicht mit; On-Prem/OSS ist unbegrenzt; `docs/licensing/plans.md`
traegt dieselben Zahlen wie `plans.py`. Gruen = DoD-Kommandos ohne Befund +
OpenAPI-Drift-Check Exit 0 + CI gruen.

## Abhaengigkeit zu #536 (nachgemessen)

`origin/main` @ `87de64c` traegt **noch nicht** PR #557 (#536). Die dort
angefassten Dateien (`entitlement.py`, `plans.py`, `plans.md`,
`entitlement_repository.py`, `webhook.py`, `mollie.py`, `router.py`,
`BillingPanel.tsx`, Migration 0084) fasse ich hier ebenfalls an. Konsequenz:

- Ich baue auf `origin/main`, **nicht** auf dem #536-Branch — sonst haengt
  dieser PR an einem ungemergten PR.
- Migration bekommt die naechste freie Nummer **0085**; 0084 ist von #536
  belegt (noch nicht auf main, aber vergeben). Kein Nummern-Konflikt.
- Der Textkonflikt in `entitlement.py`/`plans.py`/`plans.md` ist rein
  additiv (je ein Feld, je eine Spalte) und beim Merge trivial aufloesbar.
  Im PR-Text wird das benannt.

## Ist-Zustand (nachgemessen auf dem Worktree)

- `routers/tokens.py:35-40` — `create_token`, nur `@limiter.limit(write_limit)`
  (30/min), kein Zaehlwerk.
- `services/token_service.py:101-155` — `create()`: Rollen-Gate, MFA-Gate,
  Agent-in-Workspace, Insert. Kein Quota-Gate. Die `limit`-Parameter
  `:160/:165-167/:176/:183-185` sind **Paginierung**.
- `services/token_service.py:215-248` — `rotate()`: ersetzt in-place, legt
  **nicht** an. Bekommt deshalb bewusst **kein** Gate.
- Muster: `services/entity_quota_service.py` (`is_cloud()`-Wache `:75`,
  Org-Aufloesung `:56-68`, Zaehlung `:70-71`, 402 + `params` `:91-99`).
- `repositories/token_repository.py:172-177` — Auth filtert
  `revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now())`.

## Entscheidungen (begruendet)

1. **Eigenes Entitlement-Feld `token_quota`, keine Ableitung.**
   `entity_limit()` kann nur „Free-Zahl oder unbegrenzt" ausdruecken (es liest
   bloss, *ob* ein Paid-Feature vorliegt). Hier braucht Pro eine **eigene
   endliche Zahl** (25) — das geht nicht als Ableitung. Also dasselbe Muster
   wie `storage_quota_bytes` (#536): Feld am `Entitlement`, Plan-Metadatum,
   Spalte in `org_entitlement` + `entitlement_history`.
2. **`NULL` = unbegrenzt**, identisch zur Semantik der MCP- und
   Storage-Spalten. Bestandszeilen bleiben damit nach der Migration
   unbegrenzt (kein Backfill = keine stille Verschaerfung, vgl. ADR-0028).
3. **Zaehl-Granularitaet = Workspace**, wortgleich zur Begruendung des
   Entity-Zwillings (`entity_quota_service.py:12-15`) und der Owner-Entscheidung.
4. **Gezaehlt wird, was benutzbar ist:**
   `revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now())` —
   dieselbe Bedingung, unter der `fetch_auth_by_hash` einen Token akzeptiert.
   Widerrufene zaehlen nicht (AK), abgelaufene ebenso wenig: sie koennen sich
   nicht mehr authentifizieren, wuerden aber sonst einen Slot blockieren.
5. **Gate im Service, nicht als Router-Dependency.** Der Issue verlangt es
   im Service; ausserdem sitzt hier schon das MFA-Gate. `TokenService.create`
   ruft `TokenQuotaService.enforce(ctx)` **vor** `new_token()`. Ohne Pool
   (aeltere Test-Fakes) ist es ein No-Op — dieselbe dokumentierte Konvention
   wie `_assert_agent_in_workspace`.
6. **`rotate` bleibt ungegatet.** Rotation ersetzt, sie legt nicht an; ein
   Gate dort wuerde die Secret-Rotation (RUNBOOK §Secret-Rotation) ueber der
   Grenze aussperren. Ein Test haelt das fest.

## Arbeitsschritte

1. `licensing/entitlement.py`: `FREE_TOKEN_QUOTA = 3`, `PRO_TOKEN_QUOTA = 25`,
   Feld `token_quota: int | None = None`; `CLOUD_FREE_ENTITLEMENT` = 3,
   `OSS_ENTITLEMENT` = `None`.
2. Migration `0085_org_entitlement_token_quota.sql`: Spalte auf
   `org_entitlement` **und** `entitlement_history`, `IF NOT EXISTS`,
   `CHECK (… IS NULL OR … >= 0)`, integer reicht (25 passt in int4).
3. Persistenz + Herkunftswege: `entitlement_repository.py` (fetch/upsert/
   history), `licensing/license.py` (On-Prem-Payload), `core/license_cli.py`.
4. Billing: `plans.py` (`Plan.token_quota`, `META_TOKEN_QUOTA`, Werte),
   `mollie.py` (`metadata_to_entitlement`), `webhook.py` (`_parse_int_meta`),
   `router.py` (`override`).
5. `services/token_quota_service.py` (neu) + Aufruf in `TokenService.create`;
   `token_quota_exceeded` in `ProblemReason` (`packages/models/.../errors.py`)
   und `_PROBLEM_TITLES` (`main.py`).
6. Read-Pfad + UI: `routers/entitlement.py` (`token_quota` in `EntitlementInfo`),
   `apps/web/src/api/types.ts`, `BillingPanel.tsx` (Tarif-Zeile
   „API-Tokens je Workspace"), `features/billing/i18n.ts` (de/en),
   `i18n/locales/de.json` + `en.json` (`common.errors.token_quota_exceeded`,
   Paritaets-Gate!).
7. Doku: `docs/licensing/plans.md` (Spalte + Metadaten-Key), `CHANGELOG.md`
   (Unreleased/Added).
8. Tests: `apps/api/tests/test_token_quota_service.py` (onprem no-op,
   unbegrenzt ohne Zaehl-Roundtrip, unter Limit frei, am Limit 402 + reason +
   params, Zaehl-Query schliesst revoked/expired aus), Ergaenzungen in
   `test_token_service.py` (create gegatet, **rotate ueber der Grenze laeuft
   durch**), `test_licensing_entitlement.py`, `packages/billing/tests/test_plans.py`,
   Webhook-Metadaten, `BillingPanel.test.tsx`.
9. Verifikation: DoD-Block Python + Web, `scripts/export_openapi.py` +
   `git diff --exit-code docs/reference/openapi.json`.

## Bekannte Grenzen (im PR zu nennen)

- Das Entitlement traegt die Metadaten des **Kaufzeitpunkts**: eine spaeter
  angehobene Zahl wirkt erst beim naechsten Checkout (wie #536).
- Je Workspace, nicht je Org: die Zusage ist erst zusammen mit einem Deckel auf
  die Workspace-Zahl endlich (Folgekarte; inzwischen umgesetzt, siehe
  `docs/licensing/plans.md` §Workspace-Deckel).
- Bestandszeilen in `org_entitlement` tragen `NULL` = unbegrenzt.
