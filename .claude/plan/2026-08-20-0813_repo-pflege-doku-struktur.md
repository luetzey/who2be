# Repo-Pflege: Doku & Struktur (Track DOKU + STRUKTUR)

_2026-08-20 · Playbook „Repo-Pflege (Doku & Struktur)" · Weichen per
AskUserQuestion entschieden_

## Gap-Report (Kurzfassung)

Negativ-Liste: sauber (Tree-Scan heute; History-Beleg gitleaks 2026-07-22).

- **D1 CHANGELOG stale** — Unreleased endet ~Ende Juli; WorkArea/KB/Tabellen
  (ADR-0047–0049), 58→81 MCP-Tools, semantische Suche (ADR-0046),
  Tabellen-UI + Exporte, E2E-Spitze fehlen.
- **D2 README stale** — Features/Architektur ohne WorkArea-Achse,
  blobstore/tablestore.
- **D3 ROADMAP stale** — „Erledigt" endet vor der WorkArea-Achse.
- **D4 Sprachregel** — alle Public-Artefakte deutsch statt Englisch.
- **D5 API-Referenz** — keine versionierte OpenAPI-Spec im Repo.
- **S1 Description/Topics fehlen** (GitHub-API: beide leer).
- **S2 Issue-Templates + SUPPORT.md fehlen**; Stufen-Entscheidung: **Stufe 2**
  begründet (Public-Switch mit externen Issues steht bevor, #338–#341);
  Stufe 3 wäre Über-Ausbau im Solo-Repo.
- **S3 README ohne Badges/visuellen Anker** — CI seit 2026-08-16 belegbar.
- **S4 docs/-Root: 19 lose Dateien**, kein Index, keine Diataxis-Ordnung.
- **S5 .github/PROJECT.md stale** (Vorhaben „Externe Tools", fertig seit
  Juli, PR #316).

## User-Entscheidungen (2026-08-20, bindend)

1. **D4:** Jetzt komplett Englisch — Übersetzung + Inhalts-Update in einem
   Zug (statt doppelt schreiben).
2. **D5:** Export-Skript ohne CI-Gate — Spec versioniert nach
   `docs/reference/openapi.json`, Verweis in README; Drift teilgemildert
   durch bestehenden Contract-Test.
3. **S4:** Index-README (`docs/README.md`), Dateien bleiben liegen — kein
   Link-Bruch; voller Diataxis-Umbau ggf. später als eigener Lauf.
4. **S2:** Issue-Forms (Bug/Feature, YAML) + SUPPORT.md jetzt.

## Arbeitspakete (datei-disjunkt, ein PR)

| WP | Datei(en) | Zielgruppe / Diataxis / Sprache |
| --- | --- | --- |
| 1 | `README.md` | Endnutzer+Contributor / Startseite (Übersicht + Getting-Started-Tutorial) / EN; + CI-/License-Badges (belegbar), WorkArea-Achse ergänzt |
| 2 | `CHANGELOG.md` | Endnutzer / Referenz (Keep a Changelog) / EN; August-Blöcke nachgezogen |
| 3 | `CONTRIBUTING.md` | Contributor / How-To / EN |
| 4 | `SECURITY.md` | Sicherheitsforscher / How-To (Meldung) / EN |
| 5 | `ROADMAP.md` | Stakeholder / Konzept-Überblick / EN; WorkArea unter „Done" |
| 6 | `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.yml` + `config.yml`, `SUPPORT.md` | Community / Formulare / EN |
| 7 | `docs/README.md` | intern+Contributor / Index (Diataxis-Typ + Zielgruppe je Eintrag) / DE (indexierter Bestand ist deutsch, interne Doku) |
| 8 | `scripts/export_openapi.py` + `docs/reference/openapi.json` | Integratoren / Referenz / EN |
| 9 | `.github/PROJECT.md` | intern / Status / DE — Vorhaben auf „Public-Switch & erstes Release" |

Kein Sub-Agent-Spawn: Pakete sind klein, der gesamte Kontext liegt beim
Orchestrator (Modell-Effizienz — Spawns würden identischen Kontext je Paket
neu aufbauen). Keine GitHub-Issues je WP: ein kohärenter Doku-PR, kein
größeres Orchestrierungs-Vorhaben.

## Nicht machbar in dieser Session / Owner-Punkte

- **S1 Description/Topics:** kein Repo-Settings-Write-Tool im verfügbaren
  GitHub-MCP → fertige Texte im PR-/Abschlussbericht, Owner setzt sie.
- **S3 visueller Anker:** Screenshot braucht laufende App (kein
  Docker/Postgres hier) → Owner-Punkt, Platzhalter-Hinweis im Bericht,
  nicht im README.
- Discussions/Social-Preview: Owner-Settings.

## Verify (DoD dieses Laufs)

- Link-Check über alle geänderten Markdown-Dateien (relative Links
  existieren).
- Issue-Form-YAML validiert (Python `yaml.safe_load` + Pflichtfelder).
- OpenAPI-Export tatsächlich ausgeführt (Skript-Lauf = Beleg), JSON valide.
- CHANGELOG gegen die sechs Kategorien + YYYY-MM-DD geprüft.
- Keine Sprachmischung innerhalb einer Datei.
- Code-Beispiele im README gegen Repo-Stand geprüft (Befehle existieren).

## Status

- [x] Phase 1 Inventar
- [x] Phase 2 Gap-Report + Weichen
- [ ] WP1–9 schreiben
- [ ] Verify
- [ ] STATE.md-Pflege, Commit, Push, Draft-PR
