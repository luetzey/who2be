# Duplicate/Copy-Routen ans Entity-Kontingent haengen (Karte t_e00aedcc)

Basis: `origin/main` @ 02dca8ad. Branch `who2be/t_e00aedcc-duplicate-copy-routen-umgehen-das-entity`.

## Outcome

`POST /personas/{id}/duplicate`, `POST /resources/{id}/duplicate` und
`POST /agents/{id}/copy` tragen `Depends(enforce_entity_quota)` wie ihre
`POST`-Create-Geschwister — eine Kopie ist eine echte neue Entity und zaehlt
entsprechend mit. Golden-File nachgezogen, Test gruen, Changelog-Fragment
vorhanden.

## Schritt 1 — Vollstaendigkeits-Pruefung (Aufgabe 1)

Frage: welche Schreibpfade legen einen in `entity_quota_service._COUNT_QUERY`
gezaehlten Typ an (`persona`, `playbook`, `resource`, `agent`, `external_tool`)
und gehoeren damit unter das Gate?

Methode, drei unabhaengige Schnitte (nicht nur das Golden):

1. **SQL-Schnitt** — `grep "INSERT INTO <typ>"` ueber `repositories/` und
   `services/`. Ergebnis:
   - `agent_repository.insert` (agent) + `agent_repository.deep_copy`
     (persona + playbook + system_prompt_template + agent)
   - `playbook_repository.insert` (playbook)
   - `versioned_repository._insert` (generisch, `{e}` = persona/resource/
     external_tool/system_prompt_template) — traegt alle vier `create`-Pfade
     **und** beide `duplicate`-Pfade
   - `workspace_repository` (Zeilen 607/636/695/741/769/921/1033): Seed und
     Builder-Nachzug beim **Workspace-Anlegen** bzw. Managed-Content-Update.
     Kein per-Request-Schreibpfad eines Nutzers; laeuft als Provisionierung,
     wo ein Entity-Gate die Einrichtung eines frischen Workspaces blockieren
     wuerde. Der Deckel dieser Ebene ist `workspace_quota` (#576).
2. **Router-Schnitt** — `grep "\.duplicate(\|\.copy(\|\.create("` ueber
   `routers/`. 17 Treffer; nach Abzug der Typen ausserhalb des
   Entity-Kontingents (tokens, invitations, organizations,
   work-areas/artifacts/tables, system-prompts) bleiben genau die fuenf
   gegateten Creates plus die drei Kopier-Routen dieser Karte.
3. **Methoden-Schnitt** — `grep "    async def "` je Service
   (persona/playbook/resource/agent/external_tool). Neben `create` legen nur
   `PersonaService.duplicate`, `ResourceService.duplicate` und
   `AgentService.copy` neue Entities an; `restore`/`update_draft`/`update`
   schreiben Versionen, keine Entity-Zeilen (`versioned_repository._restore_version`
   schreibt nur `INSERT INTO {ev}`, nie `{e}`).

Ausserdem geprueft: alle 24 `PUT`/`PATCH`-Routen — keine legt eine neue Entity
an. `system_prompt_template` bleibt out of scope (steht in keinem Kontingent,
Produktfrage).

**Ergebnis: genau die drei Routen aus der Karte, keine weitere.**
Sonderfall fuer die Notiz: `AgentService.copy` faellt bei `is_managed` auf
`deep_copy`, das Persona, N Playbooks und Template mitkopiert. Das Gate prueft
den Einstieg, nicht die N Zeilen — dieselbe Granularitaet wie beim
Workspace-Seed; im Code notiert. Eine feinere Rechnung waere eine Aenderung der
Kontingent-Definition und damit out of scope.

## Schritt 2 — Rot-Probe (vor der Aenderung)

DB-freier TestClient-Lauf mit `dependency_overrides` fuer
`get_current_workspace` + `get_pool` (FakePool liefert Org-Aufloesung und
`count = FREE_ENTITY_QUOTA`), `build_entitlement_port` auf Free gemonkeypatcht,
`edition=cloud`.

Gemessen gegen den unveraenderten Code: `3 failed, 13 passed` — rot sind exakt
`copies persona`, `copies resource`, `copies agent`; die fuenf Creates und alle
acht Gegenproben gruen. Nach der Aenderung: `22 passed` (inkl.
`test_entity_quota_service.py`).

## Schritt 3 — Gate nachziehen

Je Route `dependencies=[Depends(enforce_entity_quota)]` im Decorator, Muster
`POST /personas` woertlich. Betroffen:

- `routers/personas.py` `duplicate_persona`
- `routers/resources.py` `duplicate_resource`
- `routers/agents.py` `copy_agent` (der Import existierte in allen drei Dateien
  bereits)

## Schritt 4 — Test

Neue Datei `apps/api/tests/test_entity_quota_duplicate_routes.py`:
parametrisiert ueber die acht Routen, die eine kontingentierte Entity anlegen
(fuenf Creates als Regressionsanker, drei Kopien), je `402` mit
`reason=entity_quota_exceeded` am Limit — plus die Gegenprobe unter dem Limit,
die belegt, dass das Gate nicht pauschal blockt (sonst waere der `402` oben
wertlos). Ohne DB, damit er auch ohne Docker laeuft.

## Schritt 5 — Golden + Changelog

`REGEN=1 uv run pytest apps/api/tests/test_gate_inventory.py` — die drei Zeilen
wandern von `ungated` nach `gated`, sonst aendert sich nichts (21 Zeilen ein,
15 aus). Changelog-Fragment
`changelog.d/t-e00aedcc-duplicate-entity-quota.fixed.md` mit dem Hinweis auf die
Verhaltensaenderung (Kopieren kann jetzt `402` liefern).

## Definition of Done

`uv run ruff check .`, `ruff format --check .`, `mypy .`,
`uv run python scripts/changelog_fragments.py check`, `uv run pytest`.
