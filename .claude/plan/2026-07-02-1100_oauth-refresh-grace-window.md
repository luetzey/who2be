# Fix: OAuth-Refresh-Grace-Window — Connector-Lockout durch strikte Rotation

Stand: 2026-07-02 · Coder · Trigger „fix" → Code-Task-Flow (kleiner Fix)

## Symptom

Who2Be-MCP-Connectoren (claude.ai) zeigen „verbunden", laden aber keine Tools.
Ursache-Kette: `tools/list` wird per `GET /v1/me` gegen die API verifiziert;
schlägt das mit einem abgelaufenen/widerrufenen Token fehl → 401 → keine Tools.

## Ursache (belegt via Live-`whoami`/`ping` aus dieser Session)

Server, `/v1/me` und Tool-Registrierung sind gesund (alle Tools statisch, keine
dynamische Filterung). Access-Tokens haben 8 h TTL; danach muss der Refresh
greifen. Der Refresh nutzt **strikte Rotation + Replay-Detection**
(`oauth_service.exchange_refresh` → `consume_refresh` → bei „nicht konsumierbar"
sofort `revoke_refresh_chain`). Ein legitimer Retry (verlorene Token-Antwort)
oder paralleler Refresh präsentiert den bereits rotierten Token erneut → die
ganze Kette wird gekillt → der Connector kann **nie wieder** refreshen und ist
nach ≤ 8 h dauerhaft leer, bis manuell neu verbunden wird.

User-Entscheidung: **8-h-TTL beibehalten (sicherer), nur Refresh härten.**

## Fix (RFC-9700-konform: Grace-Window für Rotation)

Ein kurzes Grace-Window (30 s) unterscheidet gutartigen Retry von echtem
Replay/Diebstahl:

1. `oauth_repository.refresh_within_grace(token_hash, grace)` — liefert die
   Bindung `(api_token_id, client_id)`, wenn der Token vor ≤ `grace`
   konsumiert wurde und nicht abgelaufen ist; sonst `None`.
2. `oauth_service.exchange_refresh`: liefert `consume_refresh` `None`, wird
   `refresh_within_grace` geprüft. Treffer → **gutartiger Retry**: frisch minten
   (rotated_from = token_hash, gleiche Bindung, aktuelle Rolle), **ohne** die
   Kette zu killen und **ohne** den bereits rotierten Vorgänger-Access erneut zu
   widerrufen (der erste Nachfolger bleibt gültig). Kein Treffer → wie bisher:
   `revoke_refresh_chain` + `invalid_grant`.
3. Membership-Recheck bleibt in beiden Pfaden (Deprovisioning killt die Kette).

Konstante: `_REFRESH_GRACE = timedelta(seconds=30)`. Kein Schema-Migration
(`oauth_refresh_token` hat `consumed_at`/`rotated_from`/`expires_at`).

## Trade-off (bewusst) + Single-Use-Härtung (Security-Review)

Innerhalb des 30-s-Fensters kann ein gestohlener, bereits rotierter Refresh-Token
noch **genau einmal** einlösen (max. ein zusätzlicher Ketten-Zweig). RFC 9700
erlaubt diese Grace-Periode; das Fenster ist eng, die Kette bleibt vollständig
revozierbar, das 8-h-Access-Gate unangetastet.

**Security-Review-Befund (MEDIUM, behoben):** Ein reiner `SELECT` im Grace-Pfad
wäre nicht single-use — derselbe Token ließe sich im Fenster beliebig oft
einlösen → N unabhängige, unentdeckte Zweige aus einem Race. Fix: der
Grace-Einlöse-Pfad ist jetzt **atomar genau-einmal** über die neue Spalte
`grace_consumed_at` (Migration 0062), analog zu `consumed_at`/`consume_refresh`.
Der zweite Grace-Versuch fällt durch und löst die Ketten-Revocation aus.

## Tests (Integration, echtes Postgres)

`test_oauth.py::test_oauth_full_flow_and_security` Replay-Block umbauen:
- Sofortiger Replay (in Grace) → **200** + neuer Token; die Kette lebt
  (r1-`new_access` funktioniert weiter, grace-Access funktioniert).
- Danach `consumed_at` künstlich > Grace altern (`_backdate_refresh_consumed`) →
  Replay → **400** + Kette gekillt (beide Access → 401).
- Deprovisioning-Test (`..._when_user_deprovisioned`) bleibt unverändert.

DoD: `uv run ruff check .` + `ruff format --check .`, `uv run mypy .`,
`uv run pytest apps/api/tests/test_oauth.py -q` grün. Security-Reviewer über den
Diff (Auth-Änderung, CLAUDE.md).

## Out of Scope

Access-TTL-Anhebung (verworfen zugunsten Refresh-Härtung); Client-Verhalten von
claude.ai; MCP-Server-Code.
