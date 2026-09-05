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

Die operative Warteschlange steht **nicht in dieser Datei**, sondern im offenen
Issue mit dem Label **`backlog-queue`** (derzeit #442). Ein Agent, der den
Auftrag „bearbeite ein Issue“ bekommt, holt es mit

```
list_issues(owner, repo, state=OPEN, labels=["backlog-queue"])
```

und nimmt den obersten offenen Eintrag seiner Task-Liste, dessen Blocker
erledigt sind. Das Label ist der stabile Griff, die Issue-Nummer ist
austauschbar.

**Warum dort und nicht hier:** eine Umsortierung ist im Issue ein einziger
`issue_write`-Aufruf, in dieser Datei wäre sie ein Branch, ein PR und ein
Merge. Damit können Agenten die Reihenfolge selbst pflegen. Die Arbeitsteilung:
**das Queue-Issue trägt die Reihenfolge, diese Datei die Begründung.** Bei
Widerspruch gilt für die Reihenfolge das Issue.

**Fehlt das Queue-Issue, wird es neu angelegt** — Titel „Backlog-Queue:
Reihenfolge der Arbeitspakete (Einstiegspunkt für Agenten)“, Label
`backlog-queue`, Body aus vier Teilen: die Warteschlange als Task-Liste im
Format `- [ ] #NNN — kurze Begründung`, ein Abschnitt „Nicht in der
Warteschlange“, die Pflege-Regeln und der Hinweis, dass das Projects-Board
für Agenten unlesbar ist. Reihenfolge und Begründungen stammen aus der
Tabelle unten und den offenen `agent-ready`-Issues.

#### Warum die Reihenfolge so aussieht

**Die Zeilen stehen in der Reihenfolge der Warteschlange** — wer das
Queue-Issue nach dem Muster oben neu baut, übernimmt sie von oben nach unten.

Harte Blocker gibt es nur zwei (#429, #434). Daneben erzwingen zwei
Datei-Kollisionen eine Reihenfolge, ohne echte Blocker zu sein (#430 nach
#429, #427 nach #436); der Rest ist Priorität. Die Kollisionsdetails stehen
im Queue-Issue, nicht hier.

| Issue | Rolle in der Reihenfolge |
|---|---|
| #440 CI überspringt Doku-Jobs | **Präferenz, keine Ableitung.** Blockiert nichts, öffnet nichts — nach „Fundament vor Fläche“ gehörte es hinter #434/#429/#436. Steht vorn, weil die Ersparnis mit jedem Lauf anfällt statt einmal und das folgende Paket (#434, reines `.claude/**`) sie sofort realisiert. Wer den Cloud-Launch strikt zuerst will, schiebt es auf Platz 4. |
| #434 Cloud-Readiness-Inventar | **Harte Abhängigkeit: blockiert den Zuschnitt von #428 WP-2 bis WP-5** — gibt vier Pakete frei. Inventar vor Zuschnitt; read-only, kein Code, und bei Gleichstand mit #429 das kleinere. |
| #429 Coming-soon-Modus | **Harte Abhängigkeit: blockiert #428 WP-4.** Die Deploy-Verifikation braucht eine erreichbare URL, hinter der noch keine Fremden Konten anlegen können. |
| #436 Fehlercodes W0 (ADR-0051) | Fundament vor Fläche: öffnet die Router-Wellen W1–Wn von #402. Kein Blocker, aber **vor #427** — beide regenerieren dieselben OpenAPI-Artefakte. |
| #430 Angemeldet bleiben (12 h) | Fläche, kein Blocker. **Nach #429**, weil beide `config.ts` und die Login-Seite anfassen. Vor #427 nur wegen AC 3 oben — teils Präferenz, umgekehrt vertretbar. Security-Review ist Pflicht. |
| #427 Agent-Favoriten | Fläche, öffnet nichts. **Nach #436** (Kollision in den OpenAPI-Artefakten) — nicht kopplungsfrei, anders als die Erstfassung dieser Tabelle behauptete. |
| #438 Responsive-Fundament W0 | Owner-Vorgabe: nach dem Cloud-Launch-Block — schlägt hier „Fundament vor Fläche“, obwohl es #431 W1 bis W4 öffnet. |

Danach oder parallel, außerhalb der Warteschlange:

- **#428, #402, #431** — Tracking-Issues (`size/M`). Sie folgen ihren Kindern
  und werden erst nach deren Abschluss neu zugeschnitten. #428 trägt zusätzlich
  `needs-decision` (zwei offene Owner-Weichen, siehe dort).
- **#435 Passkeys** (`size/M`) — nach #428, #429 und #430. Vorbedingung ist ein
  GoTrue-Image ≥ v2.163.0; das Repo pinnt v2.158.1.
- **#338 Owner-Checkliste** (`human-only`) — O2 (Branch-Protection,
  Merge-Strategie, Description, Topics) und O3 (CLA-Assistant). Jederzeit
  parallel, kein Agent claimt das.

### Projects-Board

Ein Board ist eine **Sicht** auf die Warteschlange, nicht ihre Quelle. Die
Reihenfolge lebt im `backlog-queue`-Issue, ihre Begründung in dieser Datei.

Board: <https://github.com/users/luetzey/projects/3> (nutzereigen,
`project_number: 3`, angelegt 2026-09-05).

Gepflegt wird es vom Owner. Das Toolset der Agenten-Sessions trägt **keine**
Projects-Werkzeuge (geprüft 2026-09-05, auch nach der Board-Anlage: weder
`projects_*`-Tools noch Issue-Fields verfügbar, `list_issue_fields` liefert
`[]`; für Issue-Dependencies gibt es kein Schreib-Werkzeug). Ein Agent kann
das Board also weder lesen noch schreiben. Es ist deshalb **nie** die Quelle
der Reihenfolge — das ist das `backlog-queue`-Issue. Wer den Board-Status
nachzieht, tut das von Hand.

Sollte in der MCP-Konfiguration später das Toolset `projects` aktiviert
werden, kann das Board die Rolle des Queue-Issues übernehmen. Bis dahin gilt
die Warteschlange im Issue.

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
4. **Backlog startbar:** jedes Issue der Warteschlange ist geschlossen oder mit
   Begründung zurückgestellt; kein offenes `agent-ready`-Issue steht ohne Platz
   im `backlog-queue`-Issue.

### Constraints

- Keine destruktiven GitHub-Aktionen ohne Owner (Visibility, Settings,
  Branch-Löschung bleiben Owner-Schritte).
- Lizenz bleibt FSL-1.1 (Apache 2.0 Future); CLA vor externen Beiträgen.
- Lokal = CI (Coverage-Ratchet, DoD in CONTRIBUTING).
- `agent-ready` ist eine Startfreigabe, keine Beschreibung: es wird nur
  vergeben, wenn Outcome, prüfbare Akzeptanzkriterien, Out-of-Scope und exakte
  Verifikations-Kommandos tatsächlich im Issue stehen. Sonst `needs-decision`.
- Ein `size/M`-Issue wird **nie** durch Nachtragen von Feldern startbar. Fehlt
  ihm nichts als die Größe, ist der nächste Schritt ein Zuschnitt, kein
  Refinement — sonst entsteht ein Paket, das vollständig aussieht und trotzdem
  nicht in einem Zug reviewbar ist. Betrifft aktuell #428, #402, #431 und #435.
- Genau **ein** offenes Issue trägt `backlog-queue`. Wer ein zweites anlegt,
  spaltet die Reihenfolge.

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
