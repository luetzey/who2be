# Doku-Richtigstellung: `mcp_rate_per_min` deckelt zwei Fenster (Nachtrag zu #537)

Karte: `t_918b7945` (aus dem Review zu #537 / PR #555 abgetrennt)
Branch: `p_2d6a9710/t_918b7945-doku-plans.md-beschreibt-mcp_rate_per_mi`

## Befund

`docs/licensing/plans.md:66` beschrieb den Metadaten-Schluessel als reines
"Per-Token-Rate-Ceiling (req/min)". Seit #537 (Option A) deckelt derselbe Wert
**zwei** Sliding-Windows — pro Token *und* pro Organisation, effektiv gilt das
Minimum. Die Beschreibung war damit unvollstaendig.

## Gegenprobe: wo steht dieselbe veraltete Formulierung noch?

Gesucht wurde repo-weit nach `per[- ]token`, `pro token`, `je token`,
`token-rate`, `Ceiling`, `mcp_rate_per_min`. Ergebnis:

**Korrigiert (dieselbe unvollstaendige Aussage):**

| Stelle | vorher | jetzt |
|---|---|---|
| `docs/licensing/plans.md:66` | "Per-Token-Rate-Ceiling (req/min)." | Verweis auf zwei Fenster + neuer Erlaeuterungsabsatz |
| `core/rate_limit.py:4` (Modul-Docstring) | "das Per-Token-Ceiling" | "das MCP-Rate-Ceiling" |
| `core/rate_limit.py:63` (`TokenRateLimiterPort`) | "Vertrag des Per-Token-Ceilings" | Vertrag des MCP-Rate-Ceilings + Hinweis, dass der Key das Fenster bestimmt |
| `core/rate_limit.py:73` (`TokenRateLimiter`) | "Reads pro Token (req/min) deckeln" | zwei Keys mit demselben Ceiling, Minimum gilt |
| `core/rate_limit.py:134` (`RedisTokenRateLimiter`) | "Redis-backed Per-Token-Ceiling" | "Redis-backed MCP-Rate-Ceiling" |
| `core/rate_limit.py:190` (`build_token_rate_limiter`) | "Per-Token-Backend" | "Rate-Limiter-Backend" |
| `core/config.py:86` | "(slowapi + Per-Token-Ceiling)" | "(slowapi + MCP-Rate-Ceiling)" |

**Geprueft und bewusst unveraendert:**

- `plans.md:22-25` (Tarif-Tabelle Free 30 / Pro 240) — durch #537 erst wahr,
  per Auftrag unangetastet.
- `licensing/entitlement.py:58/75` — sagt nur "`None` = unbegrenzt", trifft
  keine Aussage ueber das Fenster. Nichts zu korrigieren.
- `core/rate_limit.py:41` `rate_limit_key()` — "Per-Token-Bucket, sonst Per-IP"
  beschreibt korrekt, was **diese Funktion** berechnet (den Token-Key). Das
  Org-Fenster baut das Gate selbst (`org:{org_id}`), nicht diese Funktion.
- `mcp_limit_service.py` — in PR #537/#555 bereits mitgezogen.
- Klassennamen `TokenRateLimiter*` und `token_rate_limiter` — oeffentliche
  Symbole; Umbenennung waere eine Code-Aenderung, hier Out of Scope.
- `docs/standards/` — keine Fundstelle zum MCP-Rate-Ceiling.
- ADR-0031, GoBD-Doku, OpenAPI, Web-Locales — nennen nur Werte bzw. Feldnamen,
  keine "pro Token"-Semantik.

### Nachtrag Runde 2 (Review, 2026-09-22)

Die erste Gegenprobe hatte `docs/cloud-*-smoke.md` faelschlich als unbetroffen
abgehakt. Diese Aussage war **falsch** und wird ersetzt, nicht praezisiert.
Tatsaechlich betroffen und in derselben Aenderung mitgezogen:

- `docs/cloud-local-smoke.md:306` — "Zwei Schranken: **Per-Token-Rate/min**"
  → "MCP-Rate/min" plus Ein-Satz-Hinweis auf die zwei Fenster und `plans.md`.
- `docs/cloud-prod-smoke.md:193` — dieselbe Aussage, analog nachgezogen.
- `docs/cloud-prod-smoke.md:198` — "Ueber das Per-Token-Rate-Ceiling bursten"
  → "MCP-Rate-Ceiling"; das Burst-Verfahren bleibt gueltig (ein einzelner Token
  trifft dieselbe Zahl, weil beide Fenster denselben Wert tragen).
- `packages/models/src/who2be_models/errors.py:112` — "429 — Per-Token-MCP-Rate
  erreicht" → "MCP-Rate erreicht, Token- ODER Org-Fenster". Der `reason`
  `mcp_rate_limited` wird seit #537 von **beiden** Fenstern geworfen; PR #555
  sagt das im eigenen Helper-Docstring ausdruecklich. Dieselbe Klasse wie der
  bereits mitgezogene Kommentar in `core/config.py:86`.

Weiterhin bewusst **unveraendert**:

- `docs/cloud-hosting-owner-guide.md:250-255/278` beschreibt die von #537
  geschlossene Luecke als offen. Das Dokument ist erkennbar ein Diskussions-
  und Vorschlagspapier (es fuehrt u. a. einen Team-Tarif ein, den es nicht
  gibt) — eine Momentaufnahme der Analyse, keine Zustandsbeschreibung. Eine
  Richtigstellung dort waere eine inhaltliche Ueberarbeitung des Papiers und
  gehoert in eine eigene Karte.
- `apps/api/tests/test_token_rate_limiter.py:1` und weitere Vorkommen von
  "pro Token" in Test-/MCP-Modulen: dort geht es um Token-Caches bzw. um das
  Token-Fenster selbst — die Aussagen sind korrekt.

## CHANGELOG

Kein Eintrag: reine Richtigstellung einer Doku-Zeile, kein veraendertes
oeffentliches Verhalten. Die Verhaltensaenderung selbst ist bereits im
`Unreleased`-Eintrag von PR #555 beschrieben; ein zweiter Eintrag waere eine
Dublette und wuerde beim Merge kollidieren.

## Sequenz-Hinweis

Dieser Branch sitzt auf `main`; #537 (PR #555) ist **noch offen**. Der Text
"Seit #537" wird mit dem Merge von #555 wahr. Reihenfolge beim Mergen daher:
erst #555, dann dieser PR.

## Verifikation

```
uv run ruff check . && uv run ruff format --check .
uv run mypy apps/api
uv run pytest apps/api/tests/test_token_rate_limiter.py apps/api/tests/test_mcp_limit_service.py
```

## Out of Scope

Tarifzahlen, Entitlement-Felder, Code-Verhalten, Symbol-Umbenennungen.
