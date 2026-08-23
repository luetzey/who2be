# ADR-0050 — MCP-Principal aus der Token-Introspektion statt aus einem Lookup

- Status: **Entwurf (Vorschlag, offen zur Entscheidung)**
- Datum: 2026-08-23
- Bezug: ADR-0034 (MCP-HTTP-Transport), ADR-0036 (OAuth-2.1-Remote-Connector)
  + Addendum 2026-08-22 (Agent-Bindung ueber den Resource-Pfad), ADR-0023
  (Tenancy/RBAC), ADR-0039 (feinkoernige Agent-Schreibrechte).
  Anlass: Issue #413 / PR #414 (Stufe 1) und
  `.claude/plan/2026-08-23-1304_mcp-workspace-aus-token.md`.

## Kontext

Der MCP-Server bedient im HTTP-Transport alle Tenants aus **einem** Prozess:
jeder Request traegt seinen eigenen Bearer (ADR-0034). Wer der Aufrufer ist —
Workspace, Agent, Rolle — entscheidet damit pro Request, nicht pro Prozess.

Der heutige Weg dorthin ist ein Lookup, kein Bestandteil der Credential-Pruefung.
Gemessen am Stand von PR #414:

1. **Introspektion (jeder Request).** `apps/mcp/src/who2be_mcp/auth.py:36-49` —
   `Who2BeTokenVerifier.verify_token` ruft `GET /v1/me` und verwirft die Antwort
   bis auf den Statuscode. Es gibt **keinen** Cache auf diesem Pfad.
2. **Workspace-Aufloesung (pro kaltem Token).** `server.py:259-299` ruft
   **dasselbe** `/v1/me` ein zweites Mal, um ein einzelnes Feld zu lesen.
   Gecacht in einem prozess-lokalen `OrderedDict` (`_WS_CACHE_MAX = 512`,
   `_WS_CACHE_TTL_SECONDS = 300`, `server.py:120-122`).
3. **Kein Connection-Pooling.** `client.py:198` und beide `/v1/me`-Aufrufe
   erzeugen je einen frischen `httpx.AsyncClient`. Pro Tool-Call fallen damit
   mindestens zwei, im kalten Fall drei TCP-/TLS-Handshakes an.
4. **`/v1/me` ist der falsche Endpunkt fuer diesen Zweck.** Er joint alle
   Memberships ueber Orgs und Workspaces und traegt einen **schreibenden**
   Lazy-Seed: hat der User keinen Workspace, legt er in einer Transaktion Org,
   Membership, Workspace und Default-Templates an
   (`repositories/me_repository.py:73-85`).

Daraus folgen vier Probleme, die mit der Tenant-Zahl wachsen:

- **Falsche Semantik als Fehlerquelle.** Der Workspace ist eine Eigenschaft der
  Credential; wird er nachgeschlagen, kann das Ergebnis von der Bindung
  abweichen. Genau das war Issue #413 — jeder User mit mehr als einem Workspace
  bekam auf dem Zweit-Connector `403` bei *jedem* Tool. Stufe 1 hat das Symptom
  beseitigt, die Konstruktion („Bindung per Lookup rekonstruieren") aber nicht.
- **Ein schreibfaehiger Provisioning-Pfad als Per-Request-Check.** `/v1/me` wird
  zum heissesten Endpunkt des Systems und ist zugleich der teuerste und der
  einzige mit Schreibpfad im Auth-Weg.
- **Zustand in den Replicas.** Der Cache ist prozess-lokal: bei N Replicas hinter
  Caddy hat jede ihren eigenen Kaltstart (Verstaerkung bei Deploy/Scale-out) und
  ihr eigenes Revocation-Fenster (0-300 s, je Replica verschieden). Ueber 512
  aktiven Tokens thrasht der LRU und der Cache verpufft.
- **Latenz.** Zwei bis drei Handshakes pro Tool-Call sind bei einem
  Agenten-Client, der Dutzende Tools nacheinander ruft, spuerbar.

## Entscheidung (Vorschlag)

1. **Dedizierter, read-only Introspektions-Endpunkt.** `GET /v1/token/introspect`
   (RFC-7662-nah) liefert den Principal:
   `{active, user_id, workspace_id, agent_id, role, expires_at}`. Eine Zeile aus
   `api_token`, **kein** Membership-Join, **kein** Lazy-Seed, kein Write-Pfad.
   Damit wird der Per-Request-Check billig statt teuer.
2. **Der Principal kommt aus der Credential-Pruefung.** `Who2BeTokenVerifier`
   legt `workspace_id`/`agent_id`/`role` in die `AccessToken`-Claims; die Tools
   lesen sie ueber `build_client` aus dem Request-Kontext.
3. **`_resolve_workspace_id` und `_WS_CACHE` entfallen ersatzlos.** Kein zweiter
   Call, kein prozess-lokaler Zustand, kein TTL-Fenster. Die Replicas werden
   zustandslos.
4. **Ein geteilter `httpx.AsyncClient`** mit Connection-Pool ueber den
   Server-Lifespan statt einer Instanz pro Request.
5. **`/v1/me` bleibt, was es ist:** der Endpunkt fuer den Menschen (Workspace-
   Baum, Switcher, `/w/{id}`-Redirect). Das in Stufe 1 ergaenzte
   `token_workspace_id` bleibt gueltig — es ist die ehrliche Antwort auf „woran
   ist diese Credential gebunden" und haelt aeltere MCP-Builds lauffaehig.

## Konsequenzen

**Positiv**

- Der Fehlerklasse aus #413 ist der Boden entzogen: es gibt keinen zweiten Ort
  mehr, an dem ein Workspace „rekonstruiert" wird und abweichen kann.
- Zustandslose Replicas — horizontale Skalierung ohne Kaltstart-Effekt.
- Revocation wirkt sofort statt „irgendwo zwischen 0 und 300 s je nach Replica".
- Ein Round-Trip weniger pro kaltem Tool-Call, plus amortisierte TLS-Handshakes.
- Der Auth-Pfad enthaelt keinen Schreibvorgang mehr.

**Negativ / Kosten**

- Neue oeffentliche API-Flaeche, die versioniert und dokumentiert werden muss.
- Der Endpunkt ist sicherheitsrelevant: er darf nur den eigenen Principal
  ausgeben, braucht ein Rate-Limit und darf ueber einen ungueltigen Token nichts
  verraten (`{"active": false}`, kein Detail).
- API und MCP muessen koordiniert ausgerollt werden (s. Migration).
- Ohne Cache haengt jeder Request an einer DB-Query. Sie ist ein Index-Treffer
  auf `api_token`; ein kurzlebiger Cache (30-60 s) bleibt eine bewusste Option,
  ist aber kein Teil dieses Vorschlags — er waere wieder Zustand.

## Verworfene Alternativen

- **`/v1/me` cachen statt ersetzen.** Behebt weder den Schreibpfad im Auth-Weg
  noch die falsche Semantik, und verlaengert das Revocation-Fenster.
- **Selbst-signierte JWT-Access-Tokens mit Claims.** Der Principal steckte dann
  ohne jeden Call in der Credential. Preis: Revocation braucht wieder eine
  Sperrliste (also erneut Zustand), dazu Key-Management und -Rotation. Der
  `w2b_`-Token ist bewusst opak (ADR-0036).
- **Workspace weiterhin per `WHO2BE_WORKSPACE_ID` pinnen.** In der Cloud ein
  Isolationsfehler — ein Prozess, alle Tenants; seit PR #414 unter
  `transport=http` aktiv verboten.
- **Status quo belassen.** Traegt bis zu kleinen Tenant-Zahlen, macht aber
  `/v1/me` zum Flaschenhals der gesamten Cloud-Variante.

## Migration / Rollout

1. Endpunkt in der API ergaenzen (additiv, bricht nichts).
2. MCP-Verifier auf den neuen Endpunkt umstellen, mit Fallback auf `/v1/me`,
   solange eine aeltere API antworten koennte.
3. Nach dem Rollout beider Seiten `_resolve_workspace_id`, `_WS_CACHE` und den
   Fallback entfernen; geteilten HTTP-Client einziehen.
4. On-Prem/stdio ist unberuehrt: der statische Env-Token laeuft durch dieselbe
   Introspektion.

## Offene Fragen (Owner)

- Endpunkt-Name und -Ort: `/v1/token/introspect` vs. `/v1/principal`. Eine
  RFC-7662-Form legt eine spaetere Oeffnung fuer Dritt-Resource-Server nahe —
  ist das gewuenscht oder bewusst nicht?
- Kurzlebiger Introspektions-Cache: bewusst weglassen (maximale Sofortwirkung
  der Revocation) oder 30-60 s als Lastventil?
- Zeitpunkt: eigener Meilenstein oder gebuendelt mit OAuth-Phase 2
  (ROADMAP §Mid-term)?
