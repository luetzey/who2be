# W8/P1 — Testblocker T1+T2: Billing-Override erreicht den Container, Smoke-Doku fuehrt nicht mehr in 403

Karte: `t_1467893d` · Branch: `who2be/t_1467893d-w8-p1-testblocker-t1-t2-billing-override`
Basis: `origin/main` @ `cee6478e` (Worktree vor der Arbeit darauf fast-forwarded).

## Selbst verifizierte Ausgangslage

| Befund | Beleg (gemessen, nicht uebernommen) |
|---|---|
| T1 — Variable kommt nie im Container an | `WHO2BE_BILLING_OVERRIDE_OPERATORS` taucht repoweit nur in `.env.example` (auskommentiert), Doku und `packages/billing/src/who2be_billing/router.py#_override_operator_ids` auf. In **keiner** Compose-Datei unter `api.environment`, und **nicht** in `deploy/hetzner/.env.example`. |
| T1b — S6, Dev-Stack | Root-`docker-compose.cloud.yml` hat unter `api.environment` dieselbe Luecke (Mollie-Vars stehen dort, die Operator-Allowlist nicht). Gleiche Zeile ⇒ mitgenommen. |
| T2 — Override verlangt aal2 + Web-JWT | `packages/billing/src/who2be_billing/router.py#create_override` ruft `require_aal2(ctx)` **und** `_require_override_operator(ctx)`; letzteres lehnt jeden API-Token kategorisch ab (`ctx.is_api_token or ctx.user_id not in _override_operator_ids()`). `docs/cloud-prod-smoke.md` §4A fuehrt aber mit `$TOK` (`w2b_…`) in den Aufruf ⇒ garantierter 403. Auch `deploy/hetzner/README.md` §Cloud-Edition zeigt den `$TOK`-Aufruf. |
| Zusatz — keine Quota-Schritte | `docs/cloud-prod-smoke.md` kennt nur den MCP-429-Fall (§5). Speicher (#536), Token (#538) und Workspace (#576) kommen nicht vor. |

Format der Variable (im Code nachgesehen, nicht geraten):
`packages/billing/src/who2be_billing/router.py#_override_operator_ids` splittet an `,`, trimmt und
parst jeden Eintrag als `UUID` — also **kommaseparierte User-UUIDs**, leer ⇒
fail-closed (niemand darf schreiben).

## Arbeitsschritte

1. `WHO2BE_BILLING_OVERRIDE_OPERATORS: ${WHO2BE_BILLING_OVERRIDE_OPERATORS:-}`
   unter `api.environment` in **beiden** Cloud-Overlays
   (`deploy/hetzner/who2be/docker-compose.cloud.yml` und Root-`docker-compose.cloud.yml`).
2. `deploy/hetzner/.env.example` um die Variable inkl. Erklaerung ergaenzen.
3. `docs/cloud-prod-smoke.md` §4A: Web-JWT (`$JWT`) statt `$TOK`, TOTP-Step-up
   **davor**, Operator-Allowlist als Vorbedingung; §0 und Troubleshooting nachziehen.
4. Dieselbe Korrektur in der RUNBOOK-Bring-up-Checkliste und im
   `deploy/hetzner/README.md`-Block, der den Aufruf zeigt.
5. Drei knappe Quota-Smoke-Bloecke (§5b) mit Statuscode + `reason`.
6. Regressionstest `apps/api/tests/test_cloud_compose_billing_override.py`:
   parst beide Compose-Dateien und belegt, dass die Variable bei `api` ankommt —
   der Nachweis, der ohne Docker-Daemon traegt.
7. Changelog-Fragment.

## Out of Scope

Override-Mechanismus, MFA-Pflicht, Mollie.

## Nachtrag — Review-Runde 1 (Changes requested)

Zwei Blocker, beide bestaetigt und behoben:

**B1 — Speicher-Quota-Block liefert 201, nicht 402.** Das Gate prueft
`summe(wa_blob.size_bytes) >= limit`
(`apps/api/src/who2be_api/services/storage_quota_service.py#StorageQuotaService.enforce`),
und der Workspace hat an dieser Stelle der Reise null Blobs — bei `limit=1` ist
`0 >= 1` falsch, der erste Ingest laeuft durch. Vorbereitungs-`UPDATE` in §5b
auf `storage_quota_bytes=0` (Constraint `org_entitlement_storage_quota_bytes_check`,
Migration 0084, erlaubt `>= 0`), plus Callout, das die Begruendung und die
Abgrenzung zum Free-Weg festhaelt (Free traegt nur fuer Token/Workspaces).

**B2 — Es sind drei Cloud-Overlays, nicht zwei.**
`deploy/dokploy/docker-compose.cloud.yml` setzt `WHO2BE_EDITION: cloud` und baut
`target: runtime-cloud`, sein Header bewirbt den Override-Endpoint — und ihm
fehlte dieselbe Zeile. Ergaenzt; `_CLOUD_OVERLAYS` im Test erweitert.
Damit die Drei-Dateien-Sicht nicht dieselbe Falle wird, steht das **Kriterium**
jetzt im Test statt einer Aufzaehlung: „setzt `WHO2BE_EDITION: cloud`".
Danach gegengesucht (`grep -l WHO2BE_EDITION` ueber alle Compose-Dateien) —
genau diese drei; `docker-compose.e2e-cloud.yml` ist ein Zusatz-Overlay zum
Root-Stack und setzt nur den GoTrue-Autoconfirm, keine `api`-Umgebung.

Nits mitgenommen: der Free-Weg ist in §5b jetzt sauber vom Speicher-Fall
getrennt, und `docs/cloud-local-smoke.md` nennt die Web-JWT-vs.-API-Token-
Unterscheidung selbst, statt sie nur zu verlinken.
