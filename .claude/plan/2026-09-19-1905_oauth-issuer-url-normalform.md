# OAuth-Connector: der Issuer-Identifier muss die URL-Normalform sein

_Angelegt: 2026-09-19 19:05 UTC — Branch `claude/upbeat-euler-41c2cc`_
_Status: umgesetzt, lokal verifiziert; Live-Gegenprobe steht beim Betreiber aus._

## Symptom (unveraendert seit #523)

```
Authorization server metadata issuer mismatch:
https://api.luetzenburg-cloud.de != https://api.luetzenburg-cloud.de/
```

Zweiter Anlauf. #523 hat kanonisiert, #543/#544 haben dafuer gesorgt, dass der
MCP-Container ueberhaupt neu deployt wird — die Meldung ist trotzdem wortgleich
geblieben.

## Befund (gemessen, nicht geschlossen)

Der Fehler liegt **nicht** darin, dass unsere beiden Dokumente sich
widersprechen. Nach #523 tun sie das nicht mehr:

| Dokument | Feld | Wert nach #523 |
|---|---|---|
| PRM des MCP-Servers (RFC 9728) | `authorization_servers[0]` | `https://api.…` ohne Slash |
| AS-Metadaten der API (RFC 8414) | `issuer` | `https://api.…` ohne Slash |

Der Slash entsteht **im Client**. `mcp/client/auth/oauth2.py` legt den
PRM-Wert in seinem eigenen URL-Typ ab, bevor er vergleicht:

```python
self.context.auth_server_url = str(metadata.authorization_servers[0])
#                              ^^^ ProtectedResourceMetadata, Feldtyp AnyHttpUrl
```

`AnyHttpUrl("https://host")` → `"https://host/"`. Das TypeScript-SDK tut
dasselbe mit `new URL(...)`. Verglichen wird diese geparste Form dann mit dem
**rohen** `issuer` aus dem JSON — und der war slash-frei.

**Reproduktion gegen den Code nach #523**, mit den Modellen des echten Clients
(`scratchpad/repro_client.py`):

```
PRM  authorization_servers[0] (JSON) : https://api.luetzenburg-cloud.de
ASM  issuer                   (JSON) : https://api.luetzenburg-cloud.de
Client auth_server_url               : https://api.luetzenburg-cloud.de/
MISMATCH? True -> https://api.luetzenburg-cloud.de != https://api.luetzenburg-cloud.de/
```

Byte-gleich mit der Meldung des Betreibers. Eine slash-freie Kanonisierung
kann diesen Login also nie herstellen — egal auf welchem Image sie laeuft.

## Entscheidung

Advertisiert wird die **URL-Normalform**: der String, den ein URL-Parser aus
sich selbst wieder erzeugt. Fuer eine reine Origin also **mit** Trailing Slash.

Sie ist die einzige Form, die in allen vier Vergleichsvarianten haelt (Client
parst PRM / parst `issuer` / parst beides / parst nichts). Slash-frei haelt nur
in zweien.

| Funktion | Ergebnis | wofuer |
|---|---|---|
| `issuer_identifier(url)` | `https://api.example.de/` | `issuer` + `authorization_servers` |
| `issuer_base(url)` | `https://api.example.de` | `{base}/oauth/token` — kein Doppel-Slash |

Das Gegenargument aus #523 gegen genau diese Variante ("ein strikter Client
leitet `…/oauth-authorization-server/` ab") wurde an beiden SDKs nachgemessen
und traegt nicht: Python behandelt Pfad `/` wie keinen Pfad
(`if parsed.path and parsed.path != "/"`), TypeScript schneidet ihn in
`buildWellKnownPath()` ab. Beide landen auf
`https://api.<DOMAIN>/.well-known/oauth-authorization-server`.

## Aenderungen

| Datei | Aenderung |
|---|---|
| `packages/models/src/who2be_models/oauth_issuer.py` | `canonical_issuer()` → `issuer_identifier()` (URL-Normalform) + `issuer_base()`; Modul-Docstring erklaert, warum der Client die Form vorgibt |
| `apps/api/src/who2be_api/routers/oauth.py` | `issuer` aus `issuer_identifier`, Endpunkte aus `issuer_base` |
| `apps/mcp/src/who2be_mcp/{auth,prm}.py` | derselbe Identifier in beiden PRM-Wegen |
| `packages/models/tests/test_oauth_issuer.py` | Fixpunkt-Eigenschaft gegen `AnyHttpUrl` + Fail-closed-Faelle |
| `apps/mcp/tests/test_auth.py` | PRM durch `ProtectedResourceMetadata` des Clients gedreht |
| `apps/api/tests/test_oauth.py` | ausgelieferter `issuer` durch `AnyHttpUrl` gedreht |
| `scripts/oauth_smoke.py` | Live-Gegenprobe mit den Modellen + der Discovery-Logik des Clients |
| `docs/oauth-e2e-staging.md` | Troubleshooting: Client-Parser nachbauen statt unsere zwei Strings vergleichen |
| `docs/adr/0036-…md` | Addendum II — korrigiert Addendum I |

## Belege

- Repro vorher (Code nach #523): `MISMATCH? True` — s. oben.
- Repro nachher: `MISMATCH? False -> https://api.luetzenburg-cloud.de/ != https://api.luetzenburg-cloud.de/`
- `uv run pytest -q`: 1499 passed, 485 skipped (DB-Integrationstests, bekannte
  Lokal-/CI-Differenz), `ruff check`/`ruff format --check`/`mypy .` sauber.

## Offen / nicht von hier pruefbar

Der Proxy dieser Session blockt `luetzenburg-cloud.de` (403 auf CONNECT) — die
Live-Endpunkte konnten wieder nicht abgefragt werden. Nach dem Deploy gilt die
Gegenprobe aus `docs/oauth-e2e-staging.md` (Troubleshooting) als Abnahme;
davor `docker inspect --format '{{.Config.Image}}' who2be-mcp-http-1` gegen den
erwarteten SHA halten (Lehre aus #543/#544).
