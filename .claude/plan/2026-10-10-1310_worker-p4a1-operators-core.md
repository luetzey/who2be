# Worker P4a-1 — Betreiber-Prüfung in core, Billing auf den Kern-Parser

- Karte: t_5eb2e5ba (ADR-0057 Worker-Welle), Basis `origin/main` @ `be706b1a`
- Grundlage: ADR-0057 §7 + Nachtrag 2026-10-10 (Owner E2a: On-Prem nutzt
  dieselbe Allowlist `WHO2BE_OPERATORS` wie die Cloud)
- Abgespalten: Health-Feld `worker` (eigene Karte, bereits PR #893)
- Out of Scope: `/v1/system/routines` (P4b/P4c), Metriken (PM-W2),
  Login-Zuordnung zur Bootstrap-Org (eigene Karte)

## Schritte

1. [x] `core/operators.py`: `parse_uuid_allowlist(env)`, `operator_ids()`,
       `is_operator(principal|ctx)`, Dependency `require_operator` (403,
       `HTTPException.detail` wie Billing).
2. [x] Billing: `_override_operator_ids` ruft den Kern-Parser für die
       unveränderte Variable; eigener Parser und `os`-Import entfallen.
3. [x] Compose: `WHO2BE_OPERATORS: ${WHO2BE_OPERATORS:-}` in den drei
       **Basis**-Stacks (gilt in beiden Editionen; Overlays erben über den
       Mapping-Merge). `deploy/hetzner/.env.example` bietet sie an,
       `.env.example` kommentiert.
4. [x] Tests `apps/api/tests/test_operators.py`: Parser (leer, gültig, Müll,
       ungecacht), Billing nutzt den Kern-Parser, is_operator in Cloud und
       On-Prem, API-Token nie Betreiber, require_operator 200/403, Compose-
       Durchreichung mit leerem Default.
5. [x] ADR-0057 §7 Nachtrag, Changelog-Fragment.
6. [ ] DoD lokal (ruff, mypy, pytest mit `WHO2BE_REQUIRE_DB=1` + Coverage,
       Skip-Budget, Lizenz-Gate), PR, CI.

## Entscheidungen

- Compose-Zeile im Basis-Stack statt in den Cloud-Overlays: die Regel gilt
  laut E2a auch On-Prem; nur im Overlay wäre On-Prem immer 403.
- `is_operator` akzeptiert `CurrentPrincipal` und `WorkspaceContext`: die
  Betreiber-Route ist kontoweit (kein Workspace), `require_operator` hängt
  deshalb an `get_current_principal`.
- Die beiden Listen bleiben getrennt: Betreiber zu sein gibt kein
  Override-Recht (ADR-0028 unverändert).
