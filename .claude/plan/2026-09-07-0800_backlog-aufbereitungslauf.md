# Backlog-Aufbereitungslauf (2026-09-07)

Playbook: **Issue-Refinement** (`290b0c4f`), Prüfnorm: Resource
**Agent-ready Arbeitspaket** (`73a86231`). Auftrag: jedes offene Issue gegen die
Norm prüfen, Belegbares selbst entscheiden und mit Beleg ins Issue schreiben,
Urteilsfragen als Kommentar mit drei Optionen + Empfehlung zurückgeben, danach
die Warteschlange (#442) neu ordnen und in Wellen gruppieren.

Alle Messungen dieses Laufs gegen `main` @ `9316e20`.

> **Dieser Lauf ist überholt — nachgetragen als Beleg, nicht als Anleitung.**
> Er ist der in #442 als „2026-09-07 (Backlog-Aufbereitungslauf)" geführte
> Lauf, aus dem **Regel 16** entstand. Seine Ergebnisse sind inzwischen
> eingelöst oder fortgeschrieben; die beiden Stellen, an denen er heute
> **falsch** wäre, stehen unten unter §Was seither überholt ist. Der aktuelle
> Stand steht in #442 und `STATE.md`, nicht hier.

## Ausgangslage

Die drei Nebenfunde aus PR #478 (#477, #480, #481) führte die Warteschlange
pauschal als „blockiert, keiner dringend" — **ohne sie je gegen die Norm
geprüft zu haben**. Genau das war die Lücke dieses Laufs. PR #478 war zu
diesem Zeitpunkt offen, `mergeable_state: clean`, alle sieben CI-Jobs grün.

## Triage

22 offene Issues. **E** = im Repo belegt, vom Refiner entschieden · **U** =
braucht Urteil, bleibt `needs-decision` · **—** = kein Refinement-Fall.

| Issue | Norm-Stand vorher | Befund | Ergebnis |
|---|---|---|---|
| #480 Test-Helper ohne Transaktion | Befund, 0 von 4 Pflichtfeldern | **E** | veredelt → `agent-ready`, `size/S` |
| #477 dokploy-Stack | Befund, 0 von 4 | **E** (A gegen B) + **U** (Support-Frage) | Body korrigiert + Zuschnitt vorbereitet; bleibt `needs-decision` |
| #481 Workspace-Anlage ohne Rolle | Befund, 0 von 4 | **U** | Fundstellen nachgeprüft; bleibt `needs-decision` |
| #482–#487 (#402-Wellen) | vollständig | — | `agent-ready`, unverändert; #482 nachgemessen |
| #402 #428 #431 #435 | `size/M` | — | Zuschnitt, kein Refinement (Regel 7) |
| #454 #338 | `human-only` | — | Lauf endet dort (Playbook Schritt 1) |

## Die selbst entschiedene Weiche — #480

Die Originalfassung stellte A/B/C als Angemessenheits-Frage dar. Sie war im
Repo beantwortet, und zwar unabhängig von RLS:

- `me_repository.py:81-84` — der **einzige** Produktiv-Aufrufer wrappt
  `ensure_personal_workspace` in `async with self._pool.acquire() as conn,
  conn.transaction():`.
- `me_repository.py:76-80` — und begründet es schriftlich: „der Seed besteht
  aus mehreren Inserts (Org, Member, Workspace, Default-Templates). Atomar,
  damit zwei parallele Erstaufrufe desselben Users keinen Teilzustand
  hinterlassen — die ON-CONFLICT-Klauseln […] machen den Re-Lauf idempotent
  (analog `WorkspaceRepository.create`)."
- `workspace_setup.py:50-65` — der Test-Helper tat es als einziger nicht.

Damit war B („nur dokumentieren") das Festschreiben einer Abweichung von einer
belegten, begründeten Konvention, und C (Rollen-Assert) hatte im Repo keinen
zweiten Fall. Nach Playbook Schritt 4 keine offene Weiche, sondern unerledigte
Recherche.

Die Umsetzung (`d1fde05`, in PR #490) ist dieser Fassung gefolgt — inklusive
des Akzeptanzkriteriums, dass der Docstring die Klammer als Seed-Klammer
benennt und **nicht** als RLS-Workaround.

## Die drei widerlegten Belege in #477

Der Befund stimmte — die Belege, auf denen seine Optionen standen, nicht.
Nachgemessen wurde der `environment`-Block des `web`-Service in allen drei
Stacks:

1. **„Es fehlen drei Variablen"** → damals **zwei**. Die dritte
   (`WHO2BE_SESSION_MAX_AGE_HOURS`) fehlte in allen drei Stacks.
2. **„Die beiden anderen reichen alle drei durch (letztere seit #470)"** →
   #470 war nicht gemergt, es steckte in PR #478. Auch die
   Root-`.env.example:299-301` beschrieb das Durchreichen bereits als
   gegeben — eine Vorwegnahme desselben PRs.
3. **„der GoTrue-Pin aus #435 ist bereits ein zweiter Fall"** → **widerlegt**.
   Alle drei Stacks pinnen identisch `supabase/gotrue:v2.158.1`
   (`docker-compose.yml:50`, `deploy/hetzner/supabase/docker-compose.yml:63`,
   `deploy/dokploy/docker-compose.yml:81`).

Punkt 3 trug Option B („vollständig diffen, findet vermutlich mehr").
Zusätzlich zeigt der Struktur-Vergleich, dass die beiden Stacks absichtlich
verschieden sind: hetzner geteilt (App + eigener Supabase-Stack + Caddy) und
mit GHCR-Pull, dokploy all-in-one (eigene `db`, `auth`, `auth-gateway`,
`db-roles`) und aus dem Kontext gebaut. Ein „vollständiger Diff" fände
überwiegend gewollte Topologie. **A gegen B war damit entschieden**; offen
blieb allein die Produktfrage „bleibt dokploy ein unterstützter Pfad?".

## Nachgeprüft, nicht geändert

- **#481** — alle vier Fundstellen bestätigt: `organizations.py:94-103`
  (keine Rollenprüfung im Router), `workspace_service.py:45-48` (einzige
  Prüfung ist `fetch(...) is None` → 404), `organization_repository.py:45-54`
  (`fetch` joint `org_member`, **ohne** `m.role` in der Query),
  `0005_organization.sql:17-19` (drei Rollen). Produktentscheidung.
- **#482** — Bestandszahl nachgemessen (Regel 12): 3/2/1/1 = **7 Stellen**.
- **#435** — GoTrue-Pin an genau **drei** Stellen `v2.158.1`.

## Regel 16

**Ein Beleg gilt gegen `main`, nicht gegen einen offenen PR.** #480 begründete
seine Dringlichkeit mit `_scope_to_new_workspace` und einem Docstring bei
`workspace_repository.py:116-119` — beides existierte auf `main` nicht, es kam
erst mit #478. #477 nannte einen Stack-Zustand, der ebenfalls erst nach diesem
Merge eintrat. Beide Befunde blieben richtig, aber ihre Belege zeigten ins
Leere, und ein Beleg, den der ausführende Agent nicht findet, kostet ihn die
Zeit, die er beim Suchen verliert.

## Was der Lauf nicht tut

Kein Code, kein Branch für die Issues, kein Issue-Claim, keine neuen Issues,
kein Zuschnitt von #431 W1–W4. #454 und #338 tragen `human-only` — der Lauf
endet dort nach Schritt 1 des Playbooks.

## Was seither überholt ist

Zwei Aussagen dieses Laufs sind heute falsch; wer die Datei als Beleg zieht,
liest hier weiter:

1. **„#480 steht auf Platz 1 der Warteschlange."** #480 ist am 2026-09-07
   gemergt (`d1fde05`, PR #490) und geschlossen. Die Veredelung war die
   Vorlage der Umsetzung, keine Wartemarke.
2. **„Dem dokploy-Stack fehlen zwei Variablen."** Seit dem Merge von #470
   (`543a9d2`, in PR #478) sind es wieder **drei** — genau der Fall, den
   Regel 16 vorhergesagt hat. Der Body von #477 ist am 2026-09-08
   entsprechend nachgezogen; die dortige Fassung gilt.

Ebenso überholt ist die Reihenfolge dieses Laufs (#480 → #482 → #484 → #485 →
#483) samt ihrer Wellen: alle sieben Pakete sind gemergt. Die gültige
Warteschlange steht in #442, nachgemessen auf `a39df09`.
