# Fix: MCP-Tool-Discovery-Lockout — Refresh-Reuse killt nicht mehr die Kette

Stand: 2026-07-05 · Coder · Trigger „Claude Agents finden keine Who2Be-MCP-Tools"

## Symptom

Claude-Agenten mit Who2Be-Connector zeigen dauerhaft keine Tools mehr
(`tools/list` leer bzw. 401), obwohl der Connector „verbunden" ist. Trat nach
der Umstellung auf die OAuth-Auth-Methode auf und blieb auch nach dem
Grace-Window-Fix (#293) bestehen.

## Diagnose (Repro gegen echten Stack: Wegwerf-Postgres + API + MCP-HTTP)

Server-Seite ist gesund — verifiziert in dieser Session:
- `tools/list`/Tool-Calls mit gültigem Bearer liefern alle 46 Tools (auch mit
  `?agent=<uuid>`-Query, FastMCP 3.4.2).
- PRM/AS-Metadaten, 401+`WWW-Authenticate`, voller OAuth-Flow
  (`scripts/oauth_smoke.py onprem`) grün.

Der Lockout entsteht im Refresh-Pfad (`oauth_service.exchange_refresh`),
Repro-Skript (Scratchpad `repro_lockout.py`) belegt:

1. Runtime A rotiert den Refresh-Token (normal).
2. Runtime B (Claude ist multi-runtime: mehrere Agenten/Surfaces teilen sich
   die Connector-Tokens) verwendet eine **veraltete Refresh-Kopie** > 30 s nach
   der Rotation wieder.
3. Die RFC-9700-Replay-Detection ruft `revoke_refresh_chain` → **alle aktiven
   Access-Tokens der Kette werden widerrufen**, auch die frisch rotierten der
   gesunden Runtime → MCP-Introspektion (`/v1/me`) 401 → „keine Tools".
4. Claude **retried** den toten Refresh wiederholt → jeder Retry killt die
   inzwischen wieder frisch geholten Access-Tokens erneut → **permanenter**
   Lockout (Tauziehen), bis manuell neu verbunden wird.

Zusatzbefund: Die Ketten-Revocation war gegen echten Diebstahl wirkungslos —
sie widerruft nur `api_token`-Zeilen, **nicht** die Refresh-Tokens; ein Dieb
mit gültigem Nachfolge-Refresh mintet sich einfach den nächsten Access-Token.
Die Maßnahme kostete also nur Verfügbarkeit, ohne Diebstahl zu stoppen.

## Fix

`exchange_refresh`: Reuse außerhalb der Grace (bzw. abgelaufen/unbekannt) wird
**nur abgelehnt** (`invalid_grant` + Warn-Log), **ohne** Ketten-Revocation.
Unverändert bleiben:
- Rotation + atomare Single-Use-Semantik (`consumed_at`),
- 30-s-Grace, atomar genau-einmal (`grace_consumed_at`, #293),
- Ketten-Revocation bei **echten** Sicherheits-Events: Membership-Verlust beim
  Refresh (Deprovisioning-Pfad) — dort ist das Signal eindeutig.

Der wiederverwendete Token bleibt tot (single-use + single-grace verbraucht);
ein Replay gewinnt nichts. Bewusste Abweichung von RFC 9700 §4.14.2
(Revocation-on-Reuse): Bei multi-runtime MCP-Clients ist Reuse der
Alltagsfall, kein Diebstahl-Signal — und die bisherige Umsetzung hätte einen
Dieb ohnehin nicht ausgesperrt (s. o.). Beobachtbarkeit über Warn-Log.

## Tests (Integration, echtes Postgres)

`test_oauth.py::test_oauth_full_flow_and_security`:
- Zweiter Grace-Replay → 400, **Kette lebt** (beide gesunden Access → 200).
- Neu: Stale-Reuse **außerhalb** der Grace (Backdating via
  `_backdate_refresh_consumption`) → 400; gesunde Access-Tokens → 200; nie
  benutzter Nachfolge-Refresh rotiert weiterhin (200).
- Deprovisioning-Test unverändert (Kette wird dort weiterhin gekillt).

Repro-Nachweis: vor Fix `access2`/MCP → 401 nach Stale-Reuse; nach Fix → 200.

## DoD

ruff check + format (betroffene Dateien), mypy, `pytest apps/api apps/mcp`
gegen Wegwerf-Postgres, `scripts/oauth_smoke.py` (onprem) grün,
security-reviewer über den Diff (Auth-Änderung, CLAUDE.md-Pflicht).

## Out of Scope

- Access-Token-Revocation bei Rotation (bleibt; Claude holt pro Session frische
  Tokens — kein beobachteter Schaden).
- Grace-Fenster-Breite (30 s bleibt; mit Reject-only ist die Breite unkritisch).
- TTL-Cleanup der OAuth-Tabellen (weiter offen).
