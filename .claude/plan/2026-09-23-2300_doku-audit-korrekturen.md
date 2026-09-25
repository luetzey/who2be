# Doku-Korrekturen aus dem Audit (Aufraeumen 3/4)

Karte: `t_b6dd72e0` · Eltern-Audit: `t_330533c4` · Basis: `main @ 116bfcd2`
Branch: `wt/t_b6dd72e0` · Reine Doku-Aenderung, kein Code.

## Nachgemessene Belege (vor der ersten Aenderung, selbst ausgefuehrt)

| Behauptung der Karte | Eigene Messung | Ergebnis |
|---|---|---|
| Code hat 83 MCP-Tools, Doku sagt 81 | `assert len(MCP_TOOL_REQUIREMENTS) == 83` in `packages/models/tests/test_tool_requirements.py#test_mapping_covers_all_registered_server_tools`; 83 eindeutige `with_tool_log`-Registrierungen in `apps/mcp/src/` gegengezaehlt | bestaetigt |
| 52 ADRs, Doku sagt 49 | `ls docs/adr/*.md \| wc -l` = 52 | bestaetigt |
| `PRO_WORKSPACE_QUOTA` = 5 | `apps/api/src/who2be_api/licensing/entitlement.py#PRO_WORKSPACE_QUOTA` | bestaetigt |
| Ruleset `16707501` aktiv | `gh api repos/luetzey/who2be/rulesets/16707501`: `enforcement: active`, Regeln `deletion,non_fast_forward,pull_request,required_status_checks` | bestaetigt |
| Toter Link `.claude/plans/...shiny-lollipop.md` | Verzeichnis heisst `.claude/plan/` (Singular); Datei nie angelegt | bestaetigt |

## Schritte

1. **A1** — Tool-Zahl 81 → 83 an vier Stellen: `CLAUDE.md`, `ROADMAP.md`,
   `.claude/context/STATE.md` (zweimal; bei Z.2235 wandern die Summanden
   58 + 23 → 58 + 25 mit).
2. **A2** — `docs/licensing/plans.md`: `workspace_quota` in Metadaten-Tabelle,
   Beispiel-JSON und Rueckfall-Absatz nachtragen (A2.1/A2.2/A2.3).
3. **A3** — `docs/branch-protection-main.md`: Status-Kopf auf „umgesetzt",
   Ausgangslage-Ueberschrift als Vor-Zustand kennzeichnen.
4. **A4** — `docs/frontend/design-language.md`: toten Link zweimal streichen.
5. **B1** — `docs/README.md`: 49 → 52 ADRs.
6. **B2** — `docs/README.md`: `auto-merge-agenten.md` in den Index, vor
   `branch-protection-main.md`. Dessen Eintrag traegt „nicht angewendet" —
   muss mit A3 mitwandern, sonst behauptet der Index das Gegenteil des Dokuments.
7. **B3** — `docs/architecture.md`: zweite DoD-Kette durch Verweis auf
   `CONTRIBUTING.md` §Definition of Done ersetzen (einzige DoD-Liste,
   `AGENTS.md` §Nicht verhandelbar).
8. **B4** — `docs/frontend/component-map.md`: Vollstaendigkeitsanspruch
   zuruecknehmen (kein Nachtragen der 16 Zeilen).
9. Changelog-Fragment `changelog.d/doku-audit-korrekturen.fixed.md`.
10. DoD: `check_code_refs` (Basis 116bfcd2: 364 Dateien, 1043 Referenzen,
    42 ok, 1001 legacy, 0 unsupported, 0 error, Exit 0),
    `changelog_fragments check` + `guard --base origin/main`, eigener
    Linkcheck ueber `docs/`, `.claude/context/`, Wurzel.

## Nicht umgesetzt: A1 Punkt 1 (`CLAUDE.md@116bfcd2`, Abschnitt MCP-Tool-Familien)

`CLAUDE.md` ist in dieser Laufzeit eine geschuetzte Agent-Instruktionsdatei.
Der Schreibversuch wurde abgelehnt (Approval-Prompt ohne anwesenden Nutzer,
Schweigen ist keine Freigabe), auch der Weg ueber Terminal ist damit gesperrt.
Die Aenderung ist trivial und steht woertlich fest:

    Ist:  WorkArea-/KB-Familien (**81 Tools gesamt**, ADR-0047): `tools/workarea.py`
    Soll: WorkArea-/KB-Familien (**83 Tools gesamt**, ADR-0047): `tools/workarea.py`

Sie muss vom Owner oder in einer Session mit Freigabe nachgezogen werden. Die
drei uebrigen A1-Stellen (`ROADMAP.md`, `.claude/context/STATE.md` zweimal) sind
korrigiert.

## Abweichung vom Karten-Wortlaut

B2 nennt nur das Einfuegen des `auto-merge-agenten.md`-Eintrags. Der direkt
folgende `branch-protection-main.md`-Eintrag in `docs/README.md` sagt aber
„**Vorschlag** … (Owner; nicht angewendet)" — genau die Aussage, die A3 im
Dokument selbst als falsch korrigiert. Den Index dabei stehenzulassen haette
den Fund nur verschoben; der Eintrag wird darum mitgezogen. Begruendung hier,
weil es ueber den woertlichen Auftrag hinausgeht.

## Out of scope (aus der Karte)

ADRs, `CHANGELOG.md`, `.claude/plan/**` inhaltlich; `THIRD-PARTY-LICENSES.md`;
die 16 fehlenden Komponenten-Zeilen; Merge und Remote-Branch-Loeschen.
