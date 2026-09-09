# Umsetzungslauf 12 — Warteschlange abarbeiten (2026-09-09)

Betriebsmodus: **produktiv** (`.claude/project.json` fehlt → der vorsichtigere
Zustand wird nicht stillschweigend unterschritten, Code-Task-Flow Phase 1.1).

Auftrag: „Arbeite die Issues ab und setze sie der Reihe nach um." Die Reihenfolge
stammt aus dem Aufbereitungslauf 11 (#442), ergänzt um einen Blocker, der
während des Laufs aufgetreten ist.

## Reihenfolge

| # | Paket | Warum hier | Delegation |
|---|---|---|---|
| **P0** | **npm-audit-Gate wieder grün** (neu, kein Issue vorher) | **Harte Abhängigkeit:** blockiert **jeden** PR im Repo, auch die beiden anderen Pakete. `audit` hängt bewusst nicht am Doku-Skip-Gate (`ci.yml:29-31`). | Orchestrator selbst — Lockfile, keine Design-Weiche (Phase-3-Ausnahme „ein Konfigwert") |
| **P1** | **#506** — die 7 verbliebenen Fehlerstellen tragen einen `reason` | Nach P0 das einzige ohne Umgebungsabhängigkeit. Schließt #491 ab. | **Sub-Agent** — nicht-trivial (7 Stellen, 6 neue Gründe, 4 Sammelpunkte) |
| **P2** | **#499** — GoTrue ≥ v2.190.0 | Nach Kriterium 3 eigentlich Platz 1 (Fundament für #435 W2), **aber nicht abschließbar**: seine eigene Eskalationszeile nennt „kein Docker-Daemon" als Abbruchgrund. | — nicht gestartet |

**Abweichung von der Queue-Reihenfolge, begründet:** #442 setzt #499 vor #506
(Kriterium 3). Die Präferenz-Zeile derselben Liste sagt: *ohne Docker-Daemon
wird #506 zuerst gezogen*. `docker info` in dieser Session: **kein Daemon**.
Der Fall der Präferenz-Zeile ist eingetreten, die Reihenfolge bleibt unberührt.

## P0 — npm-audit-Gate

**Fertig heißt:** `npm audit --omit=dev --audit-level=high` in `apps/web` endet
mit Exit 0, und der CI-Job `audit` ist auf PR #507 grün.

**Warum:** seit dem 2026-09-09 ist der Job rot — zwei neue Advisories gegen
`@tiptap/core <=3.30.4` (GHSA-cp6q-959q-f8rh Prototype-Pollution über
`mergeAttributes()`, GHSA-j95f-988m-3j2f Quadratic ReDoS). Der letzte
main-Lauf (`597a76a`, 2026-09-08 20:05) war grün: **derselbe Code, neue
Datenbank**. Genau der Fall, den `ci.yml:29-31` beschreibt.

**Vorentschieden (Frage → Entscheidung → weil):**

- **Lockfile-Bump oder `overrides`-Block?** → **reines Lockfile-Update** →
  weil `@blocknote/core@0.54.0` (die aktuellste Version) `@tiptap/core: ^3.29.2`
  deklariert — eine offene Caret-Range. `3.31.3` liegt darin. Ein `overrides`
  wäre eine dauerhafte Sonderregel für ein Problem, das die deklarierte Range
  schon zulässt.
- **BlockNote mitheben?** → **nein** → `npm view @blocknote/core` liefert
  `latest: 0.54.0`; es gibt nichts Neueres. Der Baum trägt genau **eine**
  `@tiptap/core`-Kopie, transitiv über BlockNote.
- **In welchen PR?** → **in diesen Lauf, nicht als Anhängsel an die STATE-Zeile**
  → PR #507 ist ab hier der Sammel-PR des Laufs; Titel und Body werden
  entsprechend nachgezogen. Ein separater Branch ist nicht vorgesehen (die
  Session ist auf `claude/autonomous-code-agent-role-7ta0az` festgelegt).

**Verifikation — ausgeführt, nicht zitiert:**

| Kommando | Ergebnis |
|---|---|
| `npm audit --omit=dev --audit-level=high` | **found 0 vulnerabilities** (vorher: 1 high) |
| `npx tsc -b` | grün |
| `npm run build` | ✓ built in 2.25s |
| `npm run lint` | 0 Errors / 66 Warnungen |
| `npm run test:coverage` | **191 Dateien, 1138 Tests passed**; Branches **81,68 %** (Floor 79) |
| Diff | nur `apps/web/package-lock.json`, `package.json` unverändert |

**Out of Scope:** die neun offenen Dependabot-PRs (eigene Owner-Entscheidung,
#442); dev-Dependencies (`--omit=dev` ist das CI-Gate); ein `overrides`-Block;
ein BlockNote-Update.

## P1 — #506 (Sub-Agent)

Ask-Once-Gate **bestanden**: Outcome, 5 von außen prüfbare AK, Out-of-Scope,
4 Verifikations-Kommandos, vorentschiedene Weichen — alle vorhanden.
Nachgemessen (Regel 25, gegen `main` @ `597a76a`): AST-Zähler **13** mit exakt
der im Issue gelisteten Aufteilung, `test_error_taxonomy.py` **11 passed**,
kein openapi-Drift, `ProblemReason` **92**, `common.errors` **75** je Sprache.
Keine Korrektur nötig.

**Keine Muster-Entscheidung nötig** — die Struktur ist durch ADR-0051 und die
beiden Vorgänger-Wellen (`56abc70` W7a, `316e1e9` W7b) vorgegeben; das Paket
folgt einem bereits zweimal gebauten Muster.

**Delegation:** Sub-Agent, Modell `sonnet` — klar umrissenes Arbeitspaket mit
vollständigem Briefing und vorgegebener Struktur, keine offene Design-Weiche.
Das starke Modell bleibt beim Orchestrator für Konsolidierung und Review
(Right-Sizing, Phase 2).

**Security:** CLAUDE.md verlangt für DB-Zugriff/MCP-Tools den `security-reviewer`
— `wa_tables` und `wa_timeline` sind beides. Läuft **vor** dem Push.

## P2 — #499 (blockiert)

Nicht gestartet. Drei seiner sieben AK (`docker compose up -d --wait`,
`smoke.sh`, TOTP-E2E) brauchen einen Docker-Daemon; das Issue nennt dessen
Fehlen ausdrücklich als Abbruchgrund, nicht als Hindernis. Ein Paket
vorzubereiten, dessen Kern-Verifikation nicht fahrbar ist, hieße einen
Versions-Sprung über **23 Migrationen** ungetestet zu pushen.

## Definition of Done

Ein PR (#507) mit je einem Commit pro Paket, Testausgaben sichtbar,
`CHANGELOG.md` und `.claude/context/STATE.md` gepflegt, #506 mit `Closes`
verlinkt, #442 nachgezogen (Regel 2/17/36).
