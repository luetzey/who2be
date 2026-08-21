# Standup-Folgearbeiten: Karteileiche #388, STATE-Drift, CLA-Vorbereitung

**Status:** aktiv · **Branch:** `claude/reload-skills-s8bxpb` · **Datum:** 2026-08-21 16:30 UTC

Ergebnis des Playbook-Laufs „Projekt-Standup" (read-only) vom selben Tag.
Der Standup fand drei offene Issues und zwei Drift-Stellen; der User hat
alle drei Empfehlungen freigegeben („alles go").

## Ausgangslage (belegt, nicht geraten)

| Fakt | Beleg |
|---|---|
| Repo public, `v0.1.0` live, CI grün | Run `32483875971` (2026-08-21), conclusion `success` |
| 0 offene PRs | `list_pull_requests(state=open)` → `[]` |
| Remote hat **einen** Branch (`main`) | `list_branches` → `[{"name":"main","protected":false}]` |
| Branch-Protection auf `main` **nicht** aktiv | ebenda, `"protected": false` |
| Repo hat **keine** Description und **keine** Topics | `search_repositories` — beide Felder fehlen in der Antwort |
| Discussions sind an | ebenda, `"has_discussions": true` |

## Zielsetzung (Completion-Condition)

1. Issue #388 ist geschlossen, mit dem Beleg im Kommentar, warum es
   gegenstandslos ist.
2. `.claude/context/STATE.md` §Bekannte Probleme und §Nächste Schritte
   widersprechen dem eigenen Dokumentkopf nicht mehr.
3. `CONTRIBUTING.md` §CLA beschreibt den Ist-Zustand (Repo ist public),
   sodass beim CLA-Klick nur noch der Link einzusetzen ist.
4. #338 und #341 tragen die Owner-Zuarbeit, die sie brauchen, als Kommentar
   — inklusive fertigem Description-/Topics-Text.
5. Ein PR gegen `main` ist offen, CI grün.

## Arbeitspakete

Alle WPs sind Doku-/Metadaten-Ebene, kein Produktivcode, keine
Design-Weiche. Deshalb **ohne Sub-Agents** (Persona-Ausnahme „triviale
Änderungen") — Orchestrierung wäre hier reiner Overhead.

### WP-1 — Issue #388 schließen

Das Issue verlangt das Löschen von 70 toten Remote-Branches. Die Löschung
ist am 2026-08-20 vor dem Public-Flip passiert (STATE.md: „72+2 tote
Branches weg"), die API listet heute nur noch `main`. Auch die im Issue
empfohlene Ursachen-Behebung („Automatically delete head branches") ist
laut #338 aktiv und am Auto-Delete des #390-Head-Branch verifiziert.

Kommentar mit Beleg, dann `state_reason: completed`.

### WP-2 — STATE.md entdriften

Zwei Stellen widersprechen dem Kopf desselben Dokuments:

- Zeilen 857–861 (§Bekannte Probleme): „E2E-Gate bleibt Soft" und „eine
  überhaupt laufende CI ist seit 2026-08-19 ~16:37 wieder **nicht**
  gegeben". Beides ist am 2026-08-20 erledigt worden (SHA-Pinning-Fix;
  `continue-on-error` entfernt, #341 WP-9).
- §Nächste Schritte Punkt 2 fordert „Tag `v0.1.0` pushen + Release
  anlegen" — ist seit 2026-08-20 14:45 UTC live. Punkt 3 führt
  „Auto-delete head branches" als offen, ist aktiv.

Kein Rückwirkend-Umschreiben der Historie: die Abschnitte oben bleiben, nur
die als *offen* geführten Punkte werden auf den Ist-Stand gezogen.

### WP-3 — CONTRIBUTING §CLA auf den Ist-Zustand

Der Abschnitt sagt „Placeholder — becomes active with the public switch"
und „will be added here as soon as the repository is public" — das Repo ist
seit einem Tag public. Der Text wird auf den echten Zustand gezogen
(Repo public, CLA-Assistant noch nicht aktiv, externe Beiträge warten
darauf), mit einer klar markierten Stelle für den Link. Sprachregel:
CONTRIBUTING ist nach außen gerichtet → bleibt Englisch.

Die Aktivierung auf cla-assistant.io selbst bleibt Owner-Schritt (#338 O3).

### WP-4 — Owner-Zuarbeit an #338 und #341

- **#338:** Description- und Topics-Text aus PR #389 als
  Copy-Paste-Block; Hinweis, dass Auto-delete bereits erledigt ist und
  Branch-Protection per API als `protected: false` verifiziert wurde.
  Offenlegen, dass diese Session kein Repo-Edit-Tool hat.
- **#341:** WP-10 ist der einzige offene Punkt; benennen, was der Owner
  setzen muss (`DEPLOY_HOST` als Variable, `DEPLOY_USER`/`DEPLOY_SSH_KEY`
  als Secrets) und dass `deploy.yml:80` sich bis dahin still überspringt —
  das ist der Grund, warum die Pipeline nie „rot" war, obwohl sie
  unverifiziert ist.

### WP-5 — Verifikation + PR

Kein Quellcode berührt → keine Test-Suite betroffen. Verifiziert wird:
- JSON/YAML unangetastet, nur Markdown geändert (`git diff --stat`),
- Markdown-Links der geänderten Dateien auflösbar,
- CI-Lauf am PR grün (das ist hier das echte Gate).

## Nicht in Scope

- Branch-Protection, Merge-Strategie, CLA-Aktivierung, Description/Topics
  setzen — Repo-Settings, Owner-Schritte (Persona: verboten bzw. technisch
  nicht erreichbar).
- `.claude/project.json` anlegen — **bewusst** gitignored
  (Public-Switch-Entscheidung, Notion-IDs); Template liegt als
  `.claude/project.example.json`. Nebenbefund fürs Backlog: das Template
  kennt kein `github_repo`/`project_number`, obwohl die Coder-Persona die
  Projekt-Zuordnung darüber auflöst.
- #341 WP-10 tatsächlich ausführen — braucht einen realen Host.
- Tiefes Standards-Audit → eigenes Playbook.

## Fortschritt

- [x] WP-1 Issue #388 geschlossen
- [x] WP-2 STATE.md entdriftet
- [x] WP-3 CONTRIBUTING §CLA
- [x] WP-4 Owner-Zuarbeit an #338/#341
- [x] WP-5 Verifikation + PR
