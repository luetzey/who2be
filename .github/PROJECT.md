# PROJECT — Aktuelles Vorhaben

_Primäre Heimat für Outcome, Why, Acceptance Criteria, Constraints und
Out of Scope des jeweils aktiven Vorhabens. Pro Vorhaben gepflegt; Historie
liegt in `.claude/plan/` und `docs/adr/`._

## Vorhaben: Cloud-Launch & Alltagstauglichkeit

Getrackt in #428 (Cloud-Launch) und #535 (Cloud-Härtung); Stand und Belege in
`.claude/context/STATE.md`. Der Responsive-Block #431 ist am 2026-09-25
geschlossen.

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
**Stand 2026-09-25 nach Aufbereitungslauf 31, gegen `main` @ `cee6478`
gemessen.**

Der Cloud-Launch-Block und der Responsive-Block sind **durch**: alle Pakete aus
#428 außer dem `human-only`-Rest (#454) liegen auf `main`, und #431 ist am
2026-09-25 mit 6 von 6 Akzeptanzkriterien geschlossen worden. Was bleibt, ist
schmal — die Reihenfolge folgt deshalb fast nur noch Kriterium 1 (harte
Abhängigkeit).

| Issue | Rolle in der Reihenfolge |
|---|---|
| **#632** Passkey registrieren (#435 W2a) | **Fundament vor Fläche:** öffnet #633. Einziges Paket, das heute ohne Owner-Antwort und ohne Docker startbar ist. Fasst `e2e/helpers/auth.ts` bewusst **nicht** an. |
| **#633** Step-up mit Passkey (#435 W2b) | **Harte Abhängigkeit: nach #632** — ohne registrierbaren Faktor ist der Step-up nicht testbar. Zusätzlich nach PR #631 (beide ändern `LoginPage.tsx`). |
| **#624** Statusaktionen auf dem Phone | **`needs-decision` — nicht starten.** Alle Felder stehen, die Design-Weiche (Bottom-Bar / Sticky / `DetailHeader`) ist Produktverhalten und nicht aus dem Repo belegbar. Drei Optionen mit Empfehlung stehen als Kommentar; nach der Antwort ohne weiteres Refinement startbar. |
| **#540** Rate-Limit an der Kante | **`needs-decision` und umgebungsblockiert.** Letztes offenes Kind von #535. Braucht die Mechanismus-Entscheidung (A/B/C im Issue) **und** einen Docker-Daemon — in Cloud-Sessions seit neunzehn Läufen nicht vorhanden. Steht hinten wegen der Umgebung, nicht wegen geringer Bedeutung. |

Erledigt und deshalb aus der Tabelle genommen: der gesamte Cloud-Launch-Block
(#429, #449–#453), der Responsive-Block (#438, #500, #513, #561–#573 sowie die
Welle-7-Pakete #615–#623) und die fünf Härtungs-Kinder von #535
(#536–#539, #576).

Danach oder parallel, außerhalb der Warteschlange:

- **#428, #535** — Tracking-Issues (`size/M`, beide `needs-decision`). Sie
  folgen ihren Kindern. #428: sieben von acht Kindern erledigt, offen nur #454.
  #535: fünf von sechs, offen nur #540. Beide warten auf je eine Owner-Antwort,
  die nichts blockiert.
- **#435 Passkeys** (`size/M`) — Tracking. W1 (#499) ist gemergt: alle drei
  Stacks pinnen `supabase/gotrue:v2.196.0` (`docker-compose.yml:63`,
  `deploy/hetzner/supabase/docker-compose.yml:63`,
  `deploy/dokploy/docker-compose.yml:81`), der WebAuthn-Faktor ist serverseitig
  verfügbar. W2 ist am 2026-09-25 in **#632** und **#633** geschnitten.
- **#454 Cloud-Deploy und Testkauf** (`human-only`) — Owner-Schritte
  (Repo-Variablen, Host-Secrets, Mollie-Konto, DNS, ein Kauf im Browser).
  **Alle Code-Voraussetzungen sind erfüllt.**
- **#542 Rechnungsstellung und Umsatzsteuer** (`human-only`) — braucht
  steuerliche Beratung, kein Agent claimt das.
- **#338 Owner-Checkliste** (`human-only`) — O2 (Merge-Strategie, Description,
  Topics) und O3 (CLA-Assistant). Jederzeit parallel, kein Agent claimt das.
  Die **Branch-Protection** aus O2 ist seit 2026-09-22 erledigt (Ruleset
  `16707501`, `all-green` als einziger Required Check —
  [`docs/branch-protection-main.md`](../docs/branch-protection-main.md)).

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
