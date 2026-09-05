# PROJECT — Aktuelles Vorhaben

_Primäre Heimat für Outcome, Why, Acceptance Criteria, Constraints und
Out of Scope des jeweils aktiven Vorhabens. Pro Vorhaben gepflegt; Historie
liegt in `.claude/plan/` und `docs/adr/`._

## Vorhaben: Cloud-Launch & Alltagstauglichkeit

Getrackt in den Issues #402, #427–#440; Stand und Belege in
`.claude/context/STATE.md`.

### Outcome

Die Cloud-Edition ist mindestens einmal real deployt und verifiziert, die
öffentliche URL ist erreichbar, ohne dass Self-Service-Registrierung offen
steht, und die Web-UI ist im Alltag benutzbar (kein 2FA-Prompt pro Tab,
Grundlage für Mobile gelegt). Der Backlog ist durchgängig so geschnitten,
dass ein Agent mit leerem Kontext das nächste Paket ohne Rückfrage findet
und abarbeiten kann.

### Why

Das Release `v0.1.0` ist draußen und das Repo public, aber die Cloud-Edition
ist nie produktiv gelaufen und der Deploy-Job hat sich seit jeher still
übersprungen. Parallel kosten zwei Alltagshürden bei jeder Nutzung Zeit: der
2FA-Prompt in jedem neuen Tab und eine UI, die auf dem Telefon nicht bedienbar
ist.

### Reihenfolge

**Diese Liste ist die Quelle der Wahrheit für „welches Issue als Nächstes“.**
Ein Agent, der den Auftrag „bearbeite ein Issue“ bekommt, nimmt den obersten
offenen Eintrag, dessen Blocker erledigt sind. Neue `agent-ready`-Issues
bekommen sofort einen Platz hier, sonst sind sie für einen unbeaufsichtigten
Lauf unsichtbar.

| # | Issue | Warum an dieser Stelle |
|---|---|---|
| 1 | #440 CI überspringt Doku-Jobs | Keine Abhängigkeit. Verkürzt jeden folgenden Lauf von 7:42 auf gut eine Minute, zahlt sich also ab dem zweiten Paket aus. |
| 2 | #429 Coming-soon-Modus | **Blockiert #428 WP-4:** die Deploy-Verifikation braucht eine erreichbare URL, hinter der noch keine Fremden Konten anlegen können. |
| 3 | #434 Cloud-Readiness-Inventar | **Blockiert den Zuschnitt von #428 WP-2 bis WP-5.** Read-only, kein Code. |
| 4 | #430 Angemeldet bleiben (12 h) | Unabhängig. Vor dem Launch gewünscht, aber nicht blockierend. Security-Review ist Pflicht. |
| 5 | #436 Fehlercodes W0 (ADR-0051) | Unabhängig. Öffnet die Router-Wellen von #402. |
| 6 | #427 Agent-Favoriten | Unabhängig. Reine Produktverbesserung ohne Kopplung. |
| 7 | #438 Responsive-Fundament W0 | Owner-Vorgabe: nach dem Cloud-Launch-Block. Öffnet #431 W1 bis W4. |

Danach oder parallel, nicht in der Nummerierung:

- **#428, #402, #431** — Tracking-Issues (`size/M`). Sie folgen ihren Kindern
  und werden erst nach deren Abschluss neu zugeschnitten. #428 trägt zusätzlich
  `needs-decision` (zwei offene Owner-Weichen, siehe dort).
- **#435 Passkeys** (`size/M`) — nach #428, #429 und #430. Vorbedingung ist ein
  GoTrue-Image ≥ v2.163.0; das Repo pinnt v2.158.1.
- **#338 Owner-Checkliste** (`human-only`) — O2 (Branch-Protection,
  Merge-Strategie, Description, Topics) und O3 (CLA-Assistant). Jederzeit
  parallel, kein Agent claimt das.

### Projects-Board

Ein Board ist eine **Sicht** auf die Reihenfolge oben, nicht ihre Quelle: die
Heimat von Outcome, Reihenfolge und Constraints bleibt dieses Repo.

Board: <https://github.com/users/luetzey/projects/3> (nutzereigen,
`project_number: 3`, angelegt 2026-09-05).

Gepflegt wird es vom Owner. Das Toolset der Agenten-Sessions trägt **keine**
Projects-Werkzeuge (geprüft 2026-09-05, auch nach der Board-Anlage: weder
`projects_*`-Tools noch Issue-Fields verfügbar, `list_issue_fields` liefert
`[]`). Ein Agent kann das Board also weder lesen noch schreiben und richtet
sich nach der Reihenfolge oben. Wer den Board-Status nachzieht, tut das von
Hand.

`.claude/project.json` trägt `github_repo` und `project_number` (Vorlage:
`.claude/project.example.json`), ist aber gitignored und existiert in einer
frischen Cloud-Session deshalb nie. Für Agenten ist diese Datei hier die
Quelle, nicht `project.json`.

### Acceptance Criteria

1. **Deploy real gelaufen (#428 WP-4):** der `deploy`-Job hat sich mindestens
   einmal nicht übersprungen, Run-ID im Issue verlinkt.
2. **Registrierung kontrolliert (#429):** bei `WHO2BE_LAUNCH_MODE=coming_soon`
   zeigt `/signup` die Hinweisseite und ein direkter GoTrue-Request antwortet
   `422`, während Login und Einladungen funktionieren.
3. **Login-Komfort (#430):** mit gesetztem Haken überlebt die Sitzung neuen Tab
   und Browser-Neustart innerhalb der Obergrenze ohne erneuten 2FA-Prompt.
4. **Backlog startbar:** jedes Issue der Reihenfolge ist geschlossen oder mit
   Begründung zurückgestellt; kein offenes `agent-ready`-Issue steht ohne Platz
   in der Liste.

### Constraints

- Keine destruktiven GitHub-Aktionen ohne Owner (Visibility, Settings,
  Branch-Löschung bleiben Owner-Schritte).
- Lizenz bleibt FSL-1.1 (Apache 2.0 Future); CLA vor externen Beiträgen.
- Lokal = CI (Coverage-Ratchet, DoD in CONTRIBUTING).
- `agent-ready` ist eine Startfreigabe, keine Beschreibung: es wird nur
  vergeben, wenn Outcome, prüfbare Akzeptanzkriterien, Out-of-Scope und exakte
  Verifikations-Kommandos tatsächlich im Issue stehen. Sonst `needs-decision`.

### Out of Scope

- Neue Tarife oder Preise, Rechnungs-PDFs und E-Rechnung (eigenes
  Compliance-Thema), Multi-Region.
- Passwortloser Passkey-Login ohne Passwort (eigenes Vorhaben).
- WP-14-Architektur-Backlog und OAuth-Phase 2 — siehe
  `docs/standards-review-2026-07-20.md` §4 und ROADMAP §Mid-term/Long-term.

---

## Abgeschlossen (zuletzt)

- **Public-Switch & erstes Release (v0.1.0)** — Repo public seit 2026-08-20,
  Release `v0.1.0` getaggt und veröffentlicht, CI-Gate grün, E2E scharf
  (#339, #340, #341). Offen bleiben nur die Owner-Klicks aus #338 (O2, O3).
- **Externe Tools (MCP-Server-Bindings) + `tool-ref`-Placeholder** —
  umgesetzt mit PR #316 (ADR-0043); Blueprint
  `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`.
- **Agent WorkArea + Knowledge Base** (ADR-0047/0048/0049) — PR #367 ff.,
  Plan `.claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md`.
