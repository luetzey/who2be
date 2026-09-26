- Das Gate-Inventar zeigt nicht mehr, wo sein eigener Waechter wegschaut.

  `apps/api/tests/contract/gate_inventory.json` fuehrte zwei Routen unter
  `ungated` mit dem Zusatz „GRENZE DER METHODE": `POST /tokens` und
  `POST /v1/organizations/{organization_id}/workspaces` sind gedeckelt, aber
  ihr Gate sitzt im Service statt als FastAPI-Dependency und war ueber
  `route.dependant` unsichtbar. Die beiden Begruendungen sagten oeffentlich,
  welche Aenderung dieser Test nicht bemerkt.

  Statt die Saetze zu verstecken, ist die Grenze geschlossen: das Golden hat
  eine dritte Kategorie `service_gated`, und `test_service_gates_are_wired`
  prueft per AST, dass `TokenService.create` bzw. `WorkspaceService.create`
  ihre `_enforce_*_quota`-Methode wirklich aufrufen. Vorher lief das Entfernen
  beider Aufrufe durch Suite, ruff und mypy gruen durch; jetzt bricht es.
  Geprueft wird der Quelltext, nicht das Laufzeitverhalten — letzteres decken
  `test_token_quota_service.py` und `test_workspace_quota.py` ab.

  Die drei frueher mit „OFFENE LUECKE" markierten Kopier-/Duplizier-Routen
  standen bereits seit #643 unter `gated`; dort war nichts mehr zu tun.
