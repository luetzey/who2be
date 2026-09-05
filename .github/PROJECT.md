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
Stand 2026-09-05 nach dem Backlog-Aufbereitungslauf; #440 und #434 sind
erledigt und stehen im Queue-Issue abgehakt.

Harte Blocker sind die drei Vorbedingungen des Cloud-Deploys (#429, #450,
#451 → alle blockieren #454). Daneben erzwingen Datei-Kollisionen eine
Reihenfolge, ohne echte Blocker zu sein (#453 nach #449, #452 nach #451, #430
nach #429, #427 vor dem blockierten #436); der Rest ist Owner-Vorgabe und
Priorität. Die Kollisionsdetails stehen im Queue-Issue, nicht hier.

| Issue | Rolle in der Reihenfolge |
|---|---|
| #429 Coming-soon-Modus | **Harte Abhängigkeit: blockiert #454.** Die Deploy-Verifikation braucht eine erreichbare URL, hinter der noch keine Fremden Konten anlegen können. |
| #450 Registry-Pull als Regelweg | **Harte Abhängigkeit: blockiert #454.** Ohne den Umbau baut die Prod-Box ein anderes Artefakt, als die CI geprüft hat. Datei-disjunkt zu allem außer den Sammelpunkten. |
| #451 Kettentest + Billing-Check im Smoke | **Harte Abhängigkeit: blockiert #454** — der Prod-Smoke braucht den Check. Reine Testarbeit, kein Produktivcode. |
| #449 Tarife bewerben das Kontingent | Owner-Vorgabe (Cloud-Block). Vor #453 wegen der Datei-Kollision im Billing-Panel; stellt ein Produktversprechen richtig, das heute nicht zutrifft. |
| #452 Webhook-Härtung | Owner-Vorgabe (Cloud-Block). Nach #451 — beide fassen `packages/billing/tests/` an. Geprüft und heute nicht ausnutzbar: Härtung, kein Notfall. |
| #453 E2E-Journey „Upgrade auf Pro“ | Owner-Vorgabe (Cloud-Block), letztes Paket darin. Nach #449, sonst testet die Journey eine Oberfläche im Umbau. |
| #438 Responsive-Fundament W0 | **Fundament vor Fläche:** öffnet #431 W1–W4. Die Owner-Vorgabe „nach dem Cloud-Launch-Block“ bindet es an den Block, nicht ans Listenende — innerhalb des Restes schlägt Fundament die Fläche. **Teils Präferenz:** wer „nach dem Block“ als „ganz hinten“ liest, schiebt es hinter #427. |
| #430 Angemeldet bleiben (12 h) | Fläche, kein Blocker. Nach #429 (Datei-Kollision) und nach #453 (weiche Kollision an `LoginPage.tsx`). Vor #427 nur wegen AC 3 unten — teils Präferenz, umgekehrt vertretbar. Security-Review ist Pflicht; revidiert ADR-0035, braucht also eine ablösende ADR-0052. |
| #427 Agent-Favoriten | Fläche, öffnet nichts. Stand ursprünglich nach #436; seit #436 blockiert ist, rückt es davor — ein blockiertes Paket hält kein startbares auf. |
| #436 Fehlercodes W0 (ADR-0051) | **`needs-decision` — nicht starten.** Wäre nach „Fundament vor Fläche“ das stärkste Paket dieser Hälfte (öffnet die Router-Wellen W1–Wn von #402) und stünde vor #438. Es steht allein deshalb hinten, weil eine Architektur-Weiche offen ist: `packages/models/.../errors.py` trägt mit `ApiProblem`/`ProblemReason` bereits einen maschinenlesbaren Fehlerschlüssel, das Issue plant die Datei als Neuanlage. Offen ist damit, ob Who2Be zwei Fehler-Vokabulare nebeneinander bekommt. Drei Optionen stehen als Kommentar am Issue; nach der Entscheidung rückt #436 vor #438. |

Erledigt und deshalb aus der Tabelle genommen: **#440** (CI überspringt
Doku-Jobs, PR #445) und **#434** (Cloud-Readiness-Inventar, PR #448) — beide
am 2026-09-05 gemergt. #434 hat den Zuschnitt von #449 bis #454 freigegeben.

Danach oder parallel, außerhalb der Warteschlange:

- **#428, #402, #431** — Tracking-Issues (`size/M`). Sie folgen ihren Kindern
  und werden erst nach deren Abschluss neu zugeschnitten. #428 ist am
  2026-09-05 in sechs Kinder zerlegt (#449–#454), seine beiden
  `needs-decision`-Weichen sind beantwortet. #402 → #436 und #431 → #438
  haben je ihre nächste Welle herausgelöst.
- **#435 Passkeys** (`size/M`) — nach #428, #429 und #430. Vorbedingung ist ein
  GoTrue-Image ≥ v2.163.0; das Repo pinnt v2.158.1 an **drei** Stellen
  (`docker-compose.yml:50`, `deploy/hetzner/supabase/docker-compose.yml:63`,
  `deploy/dokploy/docker-compose.yml:81`). Einziges der drei `size/M`-Issues
  ohne herausgelöstes Kind.
- **#454 Cloud-Deploy und Testkauf** (`human-only`) — Owner-Schritte
  (Repo-Variablen, Host-Secrets, Mollie-Konto, DNS, ein Kauf im Browser).
  Voraussetzungen: #429, #450, #451.
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

1. **Deploy real gelaufen (#454, WP-7 von #428):** der `deploy`-Job hat sich
   mindestens einmal nicht übersprungen, Run-ID im Issue verlinkt. Setzt #429,
   #450 und #451 voraus; die Schritte selbst sind `human-only`.
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
