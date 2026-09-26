# Gate-Inventar: Schutz behalten, Umgehungsanleitung verlieren

Karte `t_af2275f5` (Repo-Oeffentlichkeit 3/3). Stand 2026-09-26, Basis `a2bf65df`.

## 1. Ist-Stand, gezaehlt statt geschaetzt

Gemessen gegen `origin/main` (a2bf65df), nicht gegen den Befund der Messung
`t_6f554ac0`:

| Groesse | Messung `t_6f554ac0` | heute |
|---|---|---|
| `ungated`-Eintraege | 30 | **34** |
| davon `OFFENE LUECKE` | 3 | **0** |
| davon `GRENZE DER METHODE` | 1 | **2** |

Belege:

```
$ jq '{gated:(.gated|length), ungated:(.ungated|length),
       offene:([.ungated[]|select(.reason|test("OFFENE LUECKE"))]|length),
       grenze:([.ungated[]|select(.reason|test("GRENZE DER METHODE"))]|length)}' \
    apps/api/tests/contract/gate_inventory.json
{ "gated": 16, "ungated": 34, "offene": 0, "grenze": 2 }

$ git grep -l "OFFENE LUECKE"      # repo-weit, nicht nur im Golden
(keine)
```

**Der schwerere Teil der Karte ist gegenstandslos.** Die drei `OFFENE
LUECKE`-Eintraege betrafen die Duplizier-/Kopier-Routen; `t_e00aedcc` ist als
`5e8c41e0 fix: Kopier-Routen tragen das Entity-Quota-Gate (#643)` gemergt. Die
drei Routen stehen heute unter `gated`:

```
/agents/{agent_id}/copy            -> enforce_entity_quota
/personas/{persona_id}/duplicate   -> enforce_entity_quota
/resources/{resource_id}/duplicate -> enforce_entity_quota
```

Es gibt keine offene Luecke mehr zu verstecken. Uebrig bleibt genau ein
Problem — und es sind **zwei** Fundstellen, nicht eine: `POST /tokens` und
`POST /v1/organizations/{organization_id}/workspaces` geben im oeffentlichen
Golden preis, wo dieser Waechter wegschaut.

Die Karte nennt beide Zahlen anders (30 / 3 / 1). Kein Vorwurf an die Messung:
zwischen ihr und heute liegen #640 und #643.

## 2. Die Weiche: drei Wege

Die Karte schlaegt A vor und bittet ausdruecklich um Pruefung.

**A — `reason` ins private Begleitdokument, im Golden nur eine ID.**
Loest das Symptom. Kosten: Pflege an zwei Orten, ein Golden aus
Nummern ohne Text. Der eigentliche Einwand ist aber ein anderer: dieselbe
Methodengrenze steht ausfuehrlicher im **Docstring** von
`test_gate_inventory.py` (Z. 27-40, Ueberschrift woertlich „Zwei Grenzen der
Methode, damit niemand danach sucht"). A muesste also auch den Docstring
ausraeumen — und dann ist es das Verschweigen an einer quelloffenen Codebasis,
das die Karte selbst als untauglich brandmarkt.

**B — die beiden Saetze neutral umformulieren.** Billigste Loesung, aber die
Grenze bleibt und niemand sieht sie mehr. Selbstbetrug.

**C — die Methodengrenze schliessen (gewaehlt).** Der Satz „verschwindet
dieses Gate, faengt dieser Test es nicht" ist keine Eigenschaft der Welt,
sondern eine Eigenschaft dieses Tests. Beide Gates existieren
(`TokenService._enforce_token_quota`, `WorkspaceService._enforce_workspace_quota`)
und sind gleich gebaut: eine `_enforce_*`-Methode, aufgerufen aus `create`.
Das ist per AST pruefbar. Wird der Aufruf geprueft, ist der Satz schlicht
falsch geworden und faellt ersatzlos weg — **kein privates Dokument, kein
zweiter Pflegeort.**

Gewaehlt wird C. Es ist der einzige Weg, der die Karte nicht nur erfuellt,
sondern ihren eigenen Einwand („die eigentliche Loesung liegt woanders") ernst
nimmt.

**Nicht Out of Scope.** „Weitere Gates bauen" ist ausgeschlossen — ich baue
keines. Beide Deckel existieren seit #538 / #576; ich mache einen vorhandenen
Deckel fuer den vorhandenen Waechter sichtbar.

## 3. Kosten von C, benannt

1. **Mehr Testcode statt weniger** (~50 Zeilen AST-Pruefung) gegen ~0 Zeilen
   bei A. Dafuer entfaellt die Datei unter `/home/luetzey/intern/`.
2. **Kopplung an eine Namenskonvention.** Wird `_enforce_token_quota`
   umbenannt oder der Aufruf in einen Helfer verschoben, bricht der Test,
   obwohl das Gate intakt ist. Bewusst akzeptiert, gleiche Begruendung wie die
   schon dokumentierte FastAPI-Kopplung: es bricht laut und in einer
   Testdatei, nicht still in Produktion. Die Fehlermeldung muss diesen Fall
   ausdruecklich nennen.
3. **AST statt Aufruf.** Geprueft wird, dass der Aufruf im Quelltext **steht** —
   nicht, dass er zur Laufzeit feuert. Das leisten die Verhaltenstests
   (`test_token_quota_service.py`, `test_workspace_quota.py`), die es bereits
   gibt. Diese Grenze ist real und gehoert benannt — sie ist aber harmlos,
   weil sie keinen Umgehungsweg beschreibt: sie sagt „hier greift ein anderer
   Test", nicht „hier greift keiner".
4. **Golden-Schema waechst** um `service_gated`; `REGEN=1` muss den Schluessel
   mitschreiben.

Was C **nicht** kostet: Lesbarkeit. Das Golden bleibt Prosa, nur ohne die
beiden Saetze, die den blinden Fleck beschrieben.

## 4. Schritte

1. Test: dritte Kategorie `service_gated` aus einer expliziten Registry
   (Route -> Modul/Klasse/Methode), AST-geprueft. Beide Routen raus aus
   `ungated`.
2. `_live_inventory` ordnet die zwei Routen der neuen Kategorie zu; `REGEN`
   traegt Begruendungen weiter.
3. Docstring Z. 27-40: aus „zwei Grenzen" wird die verbleibende eine.
4. Golden neu erzeugen; die beiden `GRENZE DER METHODE`-Saetze durch je einen
   Satz ersetzen, der nur noch sagt **wo** das Gate sitzt (das steht ohnehin im
   Code) — nicht mehr, dass etwas ungeprueft ist.
5. Rot-Proben, beide selbst gefahren und protokolliert (siehe §5).
6. Changelog-Fragment.

## 5. Rot-Proben — gefahren und belegt

Jede Mutation einzeln gesetzt, Test gefahren, Mutation zurueckgenommen.
`git diff -- apps/api/src` ist nach jeder Probe leer (geprueft).

| # | Mutation | Ergebnis |
|---|---|---|
| R1 | `Depends(enforce_entity_quota)` von `POST /personas` entfernt | **rot** — „Gegatete POST-Route(n) aus dem Inventar verschwunden: [('/personas', 'create_persona')]" |
| R2 | neue ungegatete Route `POST /personas/rotprobe-r2` | **rot** — „Neue POST-Route(n) ohne erkennbares Quota-Gate: [('/personas/rotprobe-r2', 'rotprobe_r2')]" |
| R3 | `await self._enforce_token_quota(ctx)` aus `TokenService.create` | **rot** — „POST /tokens hat seinen Quota-Deckel verloren" |
| R4 | `await self._enforce_workspace_quota(org_id)` aus `WorkspaceService.create` | **rot** — „POST /v1/organizations/{organization_id}/workspaces hat seinen Quota-Deckel verloren" |
| R5 | `_enforce_token_quota` → `_enforce_token_cap` umbenannt, Aufruf intakt | **rot** (gewollter Falsch-Positiv, Kosten Nr. 2) — Meldung nennt den Fall ausdruecklich |

### Der Beleg, auf den es ankommt

R3 und R4 wurden **zusaetzlich vor** der Aenderung gegen den damaligen Test
gefahren. Ergebnis damals, beide Service-Gates gleichzeitig entfernt:

```
apps/api/tests/test_gate_inventory.py   2 passed
uv run ruff check <beide Services>      All checks passed!
test_workspace_quota / test_token_quota_service / test_tokens
                                        10 passed, 14 skipped
```

Gruen auf ganzer Linie, waehrend zwei Tarif-Deckel abgeschaltet waren. Genau
das war die „GRENZE DER METHODE", und genau das ist jetzt zu. Die 14 Skips
waren die DB-Tests ohne lokale DB — sie haetten es in CI gefangen, aber eben
nicht das Verschwinden der Verdrahtung, sondern nur ihr Verhalten.

## 6. Definition of Done — Ergebnisse

Volle Suite gegen eine echte DB (Podman `pgvector/pgvector:pg16` auf :55432,
`WHO2BE_REQUIRE_DB=1`, danach entfernt):

```
uv run ruff check .                     All checks passed!
uv run ruff format --check .            903 files already formatted
uv run mypy .                           Success: no issues found in 491 source files
uv run pytest --cov --cov-fail-under=85 2157 passed, 0 skipped — coverage 91.71%
assert_skips_within_budget.py           OK (0 uebersprungen, Budget 0/0)
scripts/changelog_fragments.py check    rc=0
scripts/check_code_refs.py              0 error
```

Ohne DB liefen 1661 passed / 496 skipped bei 64% Coverage — deshalb die DB.

