# Kontoweite Routen verlangen einen menschlichen Aufrufer; agent-gebundene Tokens auf `editor` gedeckelt

Karte: `t_c119c5e6` · Vorgaenger: `t_ea83420c` (Klasse 1, Commit `e0b4ccb7`)
Basis: `origin/main` @ `a2bf65df`

## Ausgangslage (gelesen, nicht vermutet)

`get_current_user` (`core/security.py:553-562`) reduziert den Aufrufer auf die
nackte `user_id`. Die sechs Routen an dieser Dependency (`me.py`,
`organizations.py`, `gdpr.py`) koennen deshalb nicht unterscheiden, ob ein
Mensch oder eine Maschine ruft.

Route-Inventar des Pfades, per `route.dependant` ausgelesen:

| Route | Dependency heute |
|---|---|
| `GET /v1/me` | `get_current_principal` |
| `DELETE /v1/me` | `get_current_user` |
| `GET /v1/organizations` | `get_current_user` |
| `POST /v1/organizations` | `get_current_user` |
| `DELETE /v1/organizations/{id}` | `get_current_user` |
| `GET /v1/organizations/{id}/workspaces` | `get_current_user` |
| `POST /v1/organizations/{id}/workspaces` | `get_current_user` |
| `GET /v1/gdpr/export` | `get_current_user` |
| `POST /v1/invitations/{token}/accept` | `get_current_principal` |

`GET /v1/me` ist die einzige Route, die den Principal schon heute direkt nimmt
— genau die Route, die laut PM-Entscheidung erreichbar bleiben muss.

## Entscheidung: das Gate sitzt IN `get_current_user`

Statt Router-Checks wird die Dependency selbst zum Gate. Damit ist jede Route,
die `get_current_user` nutzt — heutige und kuenftige — per Vorgabe menschlich;
wer bewusst Maschinen-Zugriff will, muss explizit `get_current_principal`
nehmen und die Tenancy dort selbst behandeln. Eine neue Route erbt die
Absicherung, ohne dass jemand daran denkt.

Drei duenne Bausteine in `core/security.py`, ein gemeinsames Praedikat
(Muster `is_agent_bound` aus `e0b4ccb7`):

1. `is_machine_token(principal)` — `token_workspace_id is not None`, derselbe
   Diskriminator, den `get_consent_principal` bereits dokumentiert.
2. `deny_machine_token_account_route(principal)` — `ApiGateError` 403,
   `reason="account_route_requires_human"`, `actionable_by="human"`.
3. `get_current_user` ruft (2) vor der `user_id`-Rueckgabe;
   `get_current_human_principal` ist die Principal-Variante fuer Routen, die
   `email` brauchen (`accept_invitation`).

**Warum strikt (jedes `w2b_`-Token), nicht nur agent-gebunden:** seit Migration
`0048` (DB-CHECK) kann kein aktiver Token ungebunden sein — die Mengen sind
heute identisch, das Verhalten also genau das der Akzeptanzkriterien. Strikt
ist zugleich der sichere Default: wuerde die Bindungspflicht je gelockert,
bleibt das Gate zu statt aufzugehen.

`accept_invitation` ist im Inventar die neunte kontoweite Route und faellt
unter „uebrige kontoweite Routen"; sie wird auf `get_current_human_principal`
gezogen. Einladungen nimmt ein Mensch an.

## `GET /v1/me` — Variante A (PM-Entscheidung)

Route bleibt fuer `w2b_`-Tokens erreichbar; `MeService.fetch` schneidet die
Antwort im Token-Pfad auf den gepinnten Workspace:

- `organizations` enthaelt nur die Organisation des gepinnten Workspace, und
  darin nur diesen einen Workspace.
- `default_workspace_id` = `token_workspace_id` (sonst nennte die Antwort einen
  Workspace, der in ihrer eigenen Liste nicht mehr steht).
- `token_workspace_id` unveraendert.

Der Schnitt sitzt im Service, nicht im Repository: er ist eine Eigenschaft der
*Credential*, keine der Membership-Abfrage — dieselbe Begruendung, mit der
`token_workspace_id` dort schon durchgereicht wird.

MCP-Nachweis durch Ausfuehren (PM-Auflage 1): ein Test fahrt
`Who2BeTokenVerifier.verify_token` und `server._resolve_workspace_id` mit einem
echten Token gegen die echte App (`httpx.ASGITransport`, Muster
`test_rest_mcp_parity.py`) und prueft, dass die Introspektion gueltig bleibt und
die Workspace-Aufloesung den gepinnten Workspace liefert.

## Rollen-Deckel `editor`

Eine Definition, zwei Mint-Pfade:

- `AGENT_BOUND_MAX_ROLE = WorkspaceRole.editor` + `cap_agent_bound_role(role)`
  in `core/security.py`.
- `token_service.create`: explizit gewuenschtes `admin` ⇒ `ApiError` 403,
  `reason="agent_bound_role_capped"`, fachliche Meldung. Ohne explizite Angabe
  (Snapshot der Ersteller-Rolle) wird still gedeckelt — ein Admin soll weiter
  Tokens anlegen koennen, nur eben keine admin-Tokens.
- `oauth_service._issue`: deckelt still (die Rolle kommt dort aus der
  Membership, der Mensch waehlt sie nicht) und schreibt sie ins Audit-Detail.

Ohne den OAuth-Pfad waere der Deckel loecherig: ein Admin, der einen
Remote-Connector verbindet, erhielte weiterhin ein agent-gebundenes
admin-Token, ohne `create` zu beruehren.

Frontend: die Rollenauswahl im Token-Formular endet bei `editor` (Tokens sind
immer agent-gebunden), Hinweistext angepasst, de/en.

## Bestands-Tokens

Gesuchte Menge = aktive Tokens mit `role='admin'` (jeder aktive Token ist
agent-gebunden). Gemessen habe ich nur die lokale Entwicklungs-DB: **1**.
Produktionszugriff habe ich nicht; strukturell ist die Menge nicht leer, weil
beide Mint-Pfade sie bisher erzeugen konnten.

Migration `0088`: Herabstufung auf `editor`, jede Zeile einzeln im `audit_log`
(`token.role_capped`) — kein stiller Rechteverlust, kein stilles Weiterbestehen.
Betriebshinweis als Kommentarkopf der Migration und im Changelog-Fragment.

## Schritte

1. Tests zuerst (RED): Gate-Matrix ueber alle Routen, `/v1/me`-Schnitt,
   Deckel-Unit-Tests, MCP-Pfad-Test, Migrations-Test.
2. `core/security.py`: Praedikat, Gate, `get_current_human_principal`, Deckel.
3. `routers/invitations.py` auf die Human-Principal-Dependency.
4. `MeService.fetch`-Schnitt.
5. `token_service.create` + `oauth_service._issue`.
6. Migration `0088` + Audit.
7. `ProblemReason` + Titel; Web-Rollenauswahl + Locales.
8. OpenAPI-Referenz regenerieren, Gate-/Contract-Goldens pruefen.
9. Changelog-Fragment, DoD (ruff, format, mypy, pytest mit Coverage-Gate,
   Lizenz-Gate, Web-Gates).

## Nicht in diesem Paket

Klasse 1 (`t_ea83420c`, erledigt), Umbau des Rollenmodells, Aenderungen am
Loesch- oder Exportablauf fuer Menschen.
