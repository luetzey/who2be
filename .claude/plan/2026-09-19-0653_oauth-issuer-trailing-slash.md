# OAuth-Connector: "issuer mismatch" durch Trailing Slash in der PRM

_Angelegt: 2026-09-19 06:53 UTC — Branch `claude/wonderful-ptolemy-p912db`_

## Symptom

Beim Verbinden des Remote-MCP-Connectors bricht der Client ab:

```
Authorization server metadata issuer mismatch:
https://api.<DOMAIN> != https://api.<DOMAIN>/
```

## Befund (reproduziert, nicht vermutet)

Der Fehler ist **deterministisch** und **nicht** ein Konfigurationsfehler des
Betreibers. Die ENV ist korrekt slash-frei gesetzt
(`deploy/hetzner/who2be/docker-compose.yml:202`,
`deploy/dokploy/docker-compose.yml:316`:
`WHO2BE_OAUTH_ISSUER_URL: https://api.${DOMAIN}`).

Die beiden Metadaten-Dokumente widersprechen sich trotzdem:

| Dokument | Feld | Wert |
|---|---|---|
| `GET https://mcp.…/.well-known/oauth-protected-resource/mcp` (MCP, RFC 9728) | `authorization_servers[0]` | `https://api.…/` **mit** Slash |
| `GET https://api.…/.well-known/oauth-authorization-server` (API, RFC 8414) | `issuer` | `https://api.…` **ohne** Slash |

**Ursache:** `apps/mcp/src/who2be_mcp/auth.py:58` reicht den Issuer als `str`
in `RemoteAuthProvider(authorization_servers=[...])`. Das MCP-SDK-Modell
`ProtectedResourceMetadata.authorization_servers` ist
`list[AnyHttpUrl]` — und **Pydantic v2 haengt einer URL ohne Pfad beim
Validieren einen `/` an**:

```
AnyHttpUrl('https://api.<DOMAIN>') -> 'https://api.<DOMAIN>/'
```

Die API dagegen liefert den Issuer via `rstrip("/")` slash-frei
(`apps/api/src/who2be_api/routers/oauth.py:111`). Der Client nimmt den Wert
aus der PRM als Issuer-Identifier, holt damit die AS-Metadaten und vergleicht
den zurueckgegebenen `issuer` per **String-Gleichheit** (RFC 8414 §3.3) — das
schlaegt fehl.

Dieselbe Verfaelschung trifft die agent-spezifische PRM
(`apps/mcp/src/who2be_mcp/agent_path.py`, `build_agent_prm_route`), die
`provider.authorization_servers` unveraendert weiterreicht.

Der Effekt tritt auf, **sobald der Issuer eine reine Origin ohne Pfad ist** —
also in jedem Produktiv-Deployment. Lokal (`http://localhost:8000`) ebenso;
gemerkt hat es niemand, weil bisher kein Test die beiden Dokumente
gegeneinander haelt.

Reproduktion (in-process, ohne Server):
`scratchpad/repro.py` → `MISMATCH? True -> https://api.<DOMAIN> != https://api.<DOMAIN>/`

## Design-Weiche: welcher String ist der kanonische Issuer?

Beide Dokumente muessen denselben String tragen. Die Frage ist, welche Seite
nachgibt.

**A — API an die SDK-Normalform angleichen.** `oauth.py` gibt `issuer` mit
Trailing Slash aus (die Endpunkt-URLs bleiben slash-frei). Eine Zeile.
_Gegen:_ Der advertisierte Issuer-Identifier traegt dann dauerhaft einen
Slash. Ein Client, der RFC 8414 §3.1 strikt anwendet, leitet daraus die
Metadaten-URL `…/.well-known/oauth-authorization-server/` ab (mit Slash) und
haengt an FastAPIs 307-Redirect — funktioniert meist, ist aber Glueck statt
Absicht. Wir richten den Vertrag nach einem Serialisierungs-Artefakt aus.

**B — PRM an den Issuer angleichen.** Die PRM des MCP-Servers gibt
`authorization_servers` als den kanonischen, slash-freien String aus. Dazu
wird die vom SDK erzeugte JSON-Antwort an genau einem Feld korrigiert
(Modell bleibt, `model_dump` bleibt, nur `authorization_servers` wird
zurueckgesetzt) — an beiden PRM-Stellen: kanonisch und agent-spezifisch.
_Gegen:_ greift in die Serialisierung des SDK ein, also testpflichtig.

**C — B plus eine geteilte Quelle fuer die Kanonisierung.** Wie B, zusaetzlich
wandert die Normalisierung als `canonical_issuer()` nach
`packages/models/src/who2be_models/oauth.py` und wird von API **und** MCP
importiert — dasselbe Muster wie `agent_uuid.py`, das die kanonische
UUID-Form schon heute zwischen beiden Seiten teilt. Dazu Regressionstests auf
beiden Seiten mit einer Root-Origin als Eingabe.
_Gegen:_ Eine Datei und ein Import mehr als B.

**Muster-Entscheidung:** _Shared Kernel_ (geteilter Normalisierer in
`who2be_models`) statt zweier lokaler `rstrip`-Aufrufe. Beleg fuer die
Variabilitaet nach der Schwelle "bereits existierender zweiter Fall":
`who2be_models.agent_uuid` ist genau dieser Fall — eine Stringform, auf die
sich API und MCP einigen muessen, weil ein Dritter (der LLM-Client) beide
Seiten per String-Vergleich gegeneinander haelt. Die kompaktere Alternative
(B: `rstrip` an zwei Stellen) wurde verworfen, weil sie die Uebereinstimmung
nicht erzwingt, sondern nur wiederherstellt.

**Empfehlung: C.** A behebt den Fall, C behebt die Klasse: solange die beiden
Dokumente aus derselben Funktion kommen und ein Test sie gegeneinander haelt,
kann der Mismatch nicht zurueckkommen — auch nicht, wenn jemand die ENV mit
Slash setzt.

## Arbeitspaket (bei Zustimmung zu C)

1. `packages/models/src/who2be_models/oauth_issuer.py`: `canonical_issuer(url) -> str`
   + Export in `__init__`; Test in `packages/models/tests/`.
2. `apps/api/src/who2be_api/routers/oauth.py`: `rstrip("/")` → `canonical_issuer(...)`.
3. `apps/mcp/src/who2be_mcp/auth.py`: kanonische PRM-Route liefert
   `authorization_servers` slash-frei.
4. `apps/mcp/src/who2be_mcp/agent_path.py`: dieselbe Korrektur fuer die
   agent-spezifische PRM.
5. Regressionstests (test-first, erst rot):
   `apps/api/tests/test_oauth.py`, `apps/mcp/tests/test_auth.py`,
   `apps/mcp/tests/test_agent_path.py` — jeweils mit Root-Origin als Issuer.
6. Doku: CHANGELOG `[Unreleased] → Fixed`, Troubleshooting-Eintrag in
   `docs/oauth-e2e-staging.md`, Notiz in ADR-0036.

Out of Scope: Web-UI, Caddy, Token-/Consent-Flow, GoTrue (#499).

## DoD

`uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`,
`uv run pytest --cov --cov-fail-under=85` — lokal gruen vor dem Push.
Web-Stack nicht betroffen.

---

## Ergebnis (2026-09-19, umgesetzt)

Gewaehlt wurde **C**. Eine Abweichung vom Plan: der Helfer liegt in einem
eigenen Modul `who2be_models/oauth_issuer.py` statt in `oauth.py` — letzteres
haelt ausschliesslich Pydantic-Modelle, und `agent_uuid.py` (dasselbe Muster)
liegt aus demselben Grund neben `agent.py` statt darin.

**Geaendert**

| Datei | Was |
|---|---|
| `packages/models/src/who2be_models/oauth_issuer.py` | neu — `canonical_issuer()` + die Begruendung, warum die Kanonisierung geteilt wird |
| `packages/models/src/who2be_models/__init__.py` | Export |
| `apps/api/src/who2be_api/routers/oauth.py` | `rstrip("/")` → `canonical_issuer(...)` |
| `apps/mcp/src/who2be_mcp/prm.py` | neu — gemeinsamer PRM-Renderer fuer beide Wege |
| `apps/mcp/src/who2be_mcp/auth.py` | `Who2BeRemoteAuthProvider` ersetzt die PRM-Routen des SDK |
| `apps/mcp/src/who2be_mcp/agent_path.py` | agent-PRM nutzt denselben Renderer |
| Tests | 5 neue Faelle in 4 Dateien |
| Doku | CHANGELOG (Unreleased/Fixed), ADR-0036-Addendum, Troubleshooting in `docs/oauth-e2e-staging.md` |

**Nebenbefund, der in den ADR gewandert ist:** Es gab Tests fuer beide
PRM-Wege — sie haben den Bug nicht gefangen, weil der eine das
Provider-*Attribut* prueft (die Verfaelschung entsteht erst beim
Serialisieren) und der andere die agent-spezifische PRM gegen die kanonische
haelt (beide gleich falsch ⇒ gruen). Die neuen Tests prufen deshalb das
**ausgelieferte JSON** gegen einen erwarteten String.

**Verifikation (lokal, transkript-belegt)**

- Repro vorher: `MISMATCH? True -> https://api.<DOMAIN> != https://api.<DOMAIN>/`
- Repro nachher: `MISMATCH? False`
- `uv run ruff check .` → All checks passed
- `uv run ruff format --check .` → 744 files already formatted
- `uv run mypy .` → Success: no issues found in 462 source files
- `uv run pytest --cov --cov-fail-under=85` → **1426 passed, 485 skipped**, keine Fehlschlaege

**Coverage-Gate lokal rot — und zwar unveraendert rot.** 64,08 % gegen die
geforderten 85 %. Gegenprobe auf dem gestashten, unveraenderten Baum:
**64,00 %**. Ursache sind die 485 uebersprungenen Tests — dieser Container hat
keine erreichbare Datenbank, und die DB-gebundenen Integrationstests
ueberspringen sich selbst. Die Aenderung senkt die Abdeckung nicht, sie hebt
sie leicht; die geaenderten Dateien liegen bei 100 % (`prm.py`,
`oauth_issuer.py`), 99 % (`agent_path.py`) und 95 % (`auth.py`, offen nur der
defensive `resource_url is None`-Zweig). In CI mit Datenbank laeuft das Gate
wie gewohnt.
