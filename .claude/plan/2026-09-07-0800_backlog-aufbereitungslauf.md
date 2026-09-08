# Backlog-Aufbereitungslauf (2026-09-07)

Playbook: **Issue-Refinement** (`290b0c4f`), Prüfnorm: Resource
**Agent-ready Arbeitspaket** (`73a86231`). Auftrag: jedes offene Issue gegen die
Norm prüfen, Belegbares selbst entscheiden und mit Beleg ins Issue schreiben,
Urteilsfragen als Kommentar mit drei Optionen + Empfehlung zurückgeben, danach
die Warteschlange (#442) neu ordnen und in Wellen gruppieren.

Alle Messungen dieses Laufs gegen `main` @ `9316e20`.

## Ausgangslage

Der Lauf vom 2026-09-06 hat die Warteschlange sauber hinterlassen; seither ist
**nichts gemergt**. Die Lage hat sich trotzdem verschoben, und zwar an einer
Stelle, die die Liste nicht abbildete:

- **PR #478** ist offen, `mergeable_state: clean`, alle sieben CI-Jobs grün auf
  `a846753`, und wartet seit 2026-09-06 20:09 auf Owner-Review. Er schließt
  **sechs** Issues (#470, #469, #471, #462, #453, #479). Das ist der einzige
  Engpass im Backlog, der nicht an Kapazität hängt.
- Aus diesem PR sind drei Nebenfunde entstanden (#477, #480, #481), die die
  Vorgänger-Liste pauschal als „blockiert, keiner dringend" führte — **ohne
  sie je gegen die Norm geprüft zu haben**. Genau das war die Lücke dieses
  Laufs.

## Triage der offenen Issues

22 offene Issues. Legende: **E** = im Repo belegt, vom Refiner entschieden ·
**U** = braucht Urteil, bleibt `needs-decision` · **—** = kein Refinement-Fall.

| Issue | Norm-Stand vorher | Befund | Ergebnis |
|---|---|---|---|
| #480 Test-Helper ohne Transaktion | Befund, 0 von 4 Pflichtfeldern | **E** | veredelt → `agent-ready`, `size/S`, **entblockt** |
| #477 dokploy-Stack | Befund, 0 von 4 | **E** (A gegen B) + **U** (Support-Frage) | Body korrigiert + Zuschnitt vorbereitet; bleibt `needs-decision` |
| #481 Workspace-Anlage ohne Rolle | Befund, 0 von 4 | **U** | Fundstellen nachgeprüft; bleibt `needs-decision` |
| #479 RLS-Blocker | 4 von 4 + Empfehlung | — | Fix liegt implementiert und security-reviewed in PR #478 |
| #482–#487 (#402-Wellen) | vollständig | — | `agent-ready`, unverändert; #482 nachgemessen |
| #402 #428 #431 #435 | `size/M` | — | Zuschnitt, kein Refinement (Regel 7) |
| #454 #338 | `human-only` | — | Lauf endet dort (Playbook Schritt 1) |
| #442 | Warteschlange | — | neu geordnet |

## Die selbst entschiedene Weiche

**#480 — Transaktion ergänzen (A), weil die Konvention im Repo steht.**

Die Originalfassung stellte A/B/C als Angemessenheits-Frage dar. Sie ist im
Repo beantwortet, und zwar unabhängig von RLS:

- `me_repository.py:81-84` — der **einzige** Produktiv-Aufrufer wrappt
  `ensure_personal_workspace` in `async with self._pool.acquire() as conn,
  conn.transaction():`.
- `me_repository.py:76-80` — und begründet es schriftlich: „der Seed besteht
  aus mehreren Inserts (Org, Member, Workspace, Default-Templates). Atomar,
  damit zwei parallele Erstaufrufe desselben Users keinen Teilzustand
  hinterlassen — die ON-CONFLICT-Klauseln […] machen den Re-Lauf idempotent
  (analog `WorkspaceRepository.create`)."
- `workspace_setup.py:50-65` — der Test-Helper tut es als einziger nicht.

Damit ist B („nur dokumentieren") das Festschreiben einer Abweichung von einer
belegten, begründeten Konvention, und C (Rollen-Assert) hat im Repo keinen
zweiten Fall. Nach Playbook Schritt 4 keine offene Weiche, sondern unerledigte
Recherche.

## Die drei widerlegten Belege in #477

Der Befund selbst stimmt — die Belege, auf denen seine Optionen standen, nicht.
Nachgemessen wurde der `environment`-Block des `web`-Service in allen drei
Stacks:

| | root | hetzner | dokploy |
|---|:--:|:--:|:--:|
| fünf Basis-Variablen | ✅ | ✅ | ✅ |
| `WHO2BE_LAUNCH_MODE` / `_CONTACT` | ✅ | ✅ | ❌ |
| `WHO2BE_SESSION_MAX_AGE_HOURS` | ❌ | ❌ | ❌ |

1. **„Es fehlen drei Variablen"** → heute **zwei**. Die dritte fehlt in allen
   drei Stacks.
2. **„Die beiden anderen reichen alle drei durch (letztere seit #470)"** →
   #470 ist nicht gemergt, es steckt in PR #478. Auch die
   Root-`.env.example:299-301` beschreibt das Durchreichen bereits als
   gegeben — eine Vorwegnahme desselben PRs.
3. **„der GoTrue-Pin aus #435 ist bereits ein zweiter Fall"** → **widerlegt**.
   Alle drei Stacks pinnen identisch `supabase/gotrue:v2.158.1`
   (`docker-compose.yml:50`, `deploy/hetzner/supabase/docker-compose.yml:63`,
   `deploy/dokploy/docker-compose.yml:81`). #435 beschreibt einen Pin, der
   *überall* zu alt ist — keine dokploy-Divergenz.

Punkt 3 trug die Option B („vollständig diffen, findet vermutlich mehr").
Zusätzlich zeigt der Struktur-Vergleich, dass die beiden Stacks absichtlich
verschieden sind: hetzner ist geteilt (App + eigener Supabase-Stack + Caddy)
und zieht GHCR-Images, dokploy ist all-in-one (eigene `db`, `auth`,
`auth-gateway`, `db-roles`) und baut aus dem Kontext. Ein „vollständiger Diff"
fände überwiegend gewollte Topologie.

**Damit ist A gegen B entschieden.** Offen bleibt allein die Produktfrage
„bleibt dokploy ein unterstützter Pfad?" — Außenwirkung auf Betreiber, steht
dem Refinement nicht zu. Die Ja/Nein-Antwort ersetzt die alte A/B/C-Frage; der
Zuschnitt für „ja" liegt fertig im Body.

## Nachgeprüft, nicht geändert

- **#481** — alle vier Fundstellen unabhängig bestätigt: `organizations.py:94-103`
  (keine Rollenprüfung im Router), `workspace_service.py:45-48` (einzige Prüfung
  ist `fetch(...) is None` → 404), `organization_repository.py:45-54` (`fetch`
  joint `org_member`, **ohne** `m.role` in der Query),
  `0005_organization.sql:17-19` (drei Rollen). Produktentscheidung, bleibt beim
  Owner; kein Duplikat-Kommentar mit denselben Optionen.
- **#482** — Bestandszahl nachgemessen (Regel 12): 3/2/1/1 = **7 Stellen**,
  deckungsgleich mit der Tabelle im Issue.
- **#435** — GoTrue-Pin an genau **drei** Stellen `v2.158.1`, wie im Issue
  angegeben.

## Neue Reihenfolge

Kriterien unverändert: harte Abhängigkeit → Owner-Vorgabe → Fundament vor
Fläche → Inventar vor Zuschnitt → bei Gleichstand das kleinere.

1. **#480** — kleinste Änderungsfläche der Liste (eine Funktion, eine Klammer,
   ein Test) und datei-disjunkt zu **allem**, auch zu PR #478.
2. **#482** — W1 Agents, 7 Stellen; die migrierte Vorlage aus #436 steht
   daneben.
3. **#484** — W4, 10 Stellen; einzige Welle mit Router-Stellen + MCP-Test.
4. **#485** — W5, 10 Stellen.
5. **#483** — W2, 18 Stellen.

Nach dem Merge von #478: **#486** (W3, kollidiert an
`workspace_repository.py`) und **#487** (W6, kollidiert an
`token_service.py`).

**Präferenz-Anteil bei Platz 1/2:** nach *Laufzeit* gemessen wäre die
Reihenfolge umgekehrt — #480 verlangt die volle Integrationssuite mit
erreichbarer DB (498 Aufrufstellen des Helpers), #482 kommt mit zwei gezielten
Testdateien weit. Entschieden hat die Änderungsfläche, weil sie das ist, was
Review kostet. Praktisch ist die Frage klein: beide liegen in Welle A.

**Blockiert, nicht einplanbar:** #477 (Support-Frage), #481 (Produktfrage),
Punkte 1+3 aus #463.

## Wellen

| Welle | Pakete | Warum gemeinsam |
|---|---|---|
| A | #480 · #482 · #484 | Drei disjunkte Flächen: `testing/workspace_setup.py` · `services/agent_*` + `core/agent_scope` · `services/memory_service` + `core/workarea_scope` + drei Router |
| B | #485 · #483 | fünf Service-Dateien gegen sieben Service-Dateien |

Welle A hat drei Pakete im Python-Stack — **drei getrennte Worktrees**, sonst
sieht der Testlauf des einen den halbfertigen Stand des anderen (Lehre aus dem
Fünf-Pakete-Lauf). #480 berührt keinen der vier #402-Sammelpunkte
(`errors.py`, `main.py`, beide Locale-JSONs).

Zwei Kollisionszeilen sind neu:

- **#480 ↔ jedes Paket mit Integrationstests** _(latent)_: kein Datei-Konflikt,
  aber wer nach #480 mergt, fährt seine Suite erstmals gegen den geänderten
  Helper (498 Importstellen). CI fängt das.
- **#477 ↔ PR #478** _(aktiv)_: `WHO2BE_SESSION_MAX_AGE_HOURS` gehört erst nach
  dem Merge in den dokploy-Block — vorher wäre sie eine Variable, die in keinem
  anderen Stack existiert.

## Regel 16 (neu)

**Ein Beleg gilt gegen `main`, nicht gegen einen offenen PR.** #480 begründete
seine Dringlichkeit mit `_scope_to_new_workspace` und einem Docstring bei
`workspace_repository.py:116-119` — beides existiert auf `main` nicht, es kommt
erst mit #478. #477 nannte einen Stack-Zustand, der ebenfalls erst nach diesem
Merge eintritt. Beide Befunde blieben richtig, aber ihre Belege zeigten ins
Leere, und ein Beleg, den der ausführende Agent nicht findet, kostet ihn die
Zeit, die er beim Suchen verliert. Wer ein Issue aus einem laufenden PR heraus
schreibt, notiert dazu, welcher Teil erst nach dem Merge zutrifft.

## Was der Lauf nicht tut

Kein Code, kein Branch für die Issues, kein Issue-Claim, keine neuen Issues,
kein Zuschnitt von #431 W1–W4 (das wäre Projekt-Blueprint). #454 und #338
tragen `human-only` — der Lauf endet dort nach Schritt 1 des Playbooks.

## Ergebnis

Ausgeführt am 2026-09-07. Gegen-Read über `issue_read` (#480) und
`list_issues(labels=["needs-decision"])` bestätigt Titel, Body und Labels.

| Issue | Vorher | Nachher | Belege im Body |
|---|---|---|---|
| #480 | `backend`, `needs-decision` | `backend`, `agent-ready`, `size/S` | Produktiv-Aufrufer als Konventions-Beleg; PR-Dateiliste geprüft |
| #477 | `bug`, `needs-decision`, `deploy` | unverändert (Frage geschrumpft) | drei Stacks vermessen, drei Belege widerlegt |
| #481 | `bug`-frei, `needs-decision`, `security`, `api` | unverändert | vier Fundstellen einzeln bestätigt |
| #442 | Queue von 2026-09-06 | neu geordnet, 5 startbar + 2 nach #478 | — |

`needs-decision` trägt danach noch: #477, #479 (Fix in PR #478), #481.

### Was offen zurückgeht

- **#477** — eine Ja/Nein-Frage statt A/B/C: bleibt dokploy unterstützt?
  Kommentar mit drei Wegen und Empfehlung A steht.
- **#481** — Produktentscheidung zur Org-Rollenabstufung; Optionen standen
  bereits im Body, kein Duplikat geschrieben.
- **#463 Punkte 1 + 3** — Kommentar vom 2026-09-06 steht.
- **PR #478** — wartet auf Review. Sechs Issues und die Wellen W3/W6 hängen
  daran.
