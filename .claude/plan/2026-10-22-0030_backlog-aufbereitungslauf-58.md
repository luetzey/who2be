# Backlog-Aufbereitungslauf 58 — 2026-10-22

**Auftrag:** jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket"
prüfen, belegbares selbst entscheiden und mit Beleg ins Issue schreiben,
Urteilsfragen als Kommentar mit drei Optionen und Empfehlung stellen, die
Warteschlange (`backlog-queue`, #442) neu ordnen und in Wellen gruppieren.

**Bezugsstand:** `main` @ `fb03322a` (2026-10-21 23:56 UTC), Vorlauf
`34056238`. Klon war shallow (50 → **1603** Commits nach `--unshallow`,
Regel 90). Alle Zahlen in diesem Lauf gemessen, keine fortgeschrieben.

## Fenster

**16 Commits, 16 PRs gemergt, 0 Issues geschlossen (vorgefunden).** Drei neue
`Accepted`-ADRs im Umlauf: ADR-0058 (seit 2026-10-20), **ADR-0061**
(Rechnungsstellung) und **ADR-0062** (Stabilität), beide seit 2026-10-20.
Dazu ADR-0060 (Tutorials, `Accepted`, Umsetzung Onboarding P1/P4).

Gemergt: #1003, #1004, #1005, #1006, #1007, #1008, #1009, #1010, #1011,
#1013, #1014, #1015, #1016, #1018, #1020, #1023.

## Zentraler Fund (→ Regel 136)

**#1009 setzt Issue #998 um, #1011 setzt Issue #999 um — und kein Träger-PR
nennt sein Issue.** #1007 trägt wörtlich `Issue: n/a (Kanban card
t_0887a9b9)`. Beide Issues standen 30 Stunden nach dem Merge noch offen,
obwohl `main` sie belegt.

Der Unterschied zu Lauf 57 ist der Punkt: dort **fehlte** das Issue
(Regel 134), hier **gab es** es und es wurde nicht gelesen. Damit ist
Weiche 23 Option C (jeder Sach-PR nennt ein Issue) keine Feinheit, sondern
die Bedingung dafür, dass die Warteschlange mehr ist als ein Schreibheft.

## Zweiter Fund (→ Regel 137)

**ADR-0062 §9 erklärt ihre eigene Pakettabelle für unverbindlich:** „Die
Pakete legt der PM als eigene Karten an; diese Liste ist ein Verweis, keine
Spezifikation." ADR-0061 §10 trägt eine Pakettabelle **mit Voraussetzung je
Paket** und keinen solchen Satz.

**Folge, bewusst asymmetrisch gehandelt (Regel 51):** aus ADR-0061 ist
**#1024** geschnitten (Paket R2), aus ADR-0062 **nichts** — A5 ist
Betreiber-Arbeit (Server auf Zeit), A6 hängt ausdrücklich an der
A5-Baseline (ein Paket darauf wäre ein Paket auf einer ungemessenen
Prämisse, Regel 24), Stufe B liegt nach dem Release. Damit hat Regel 134
zum ersten Mal einen Gegenbeleg aus dem Repo selbst. → Weiche 26.

## Selbst erledigt

1. **#998 geschlossen** (`completed`), **5 von 5 Kriterien einzeln
   nachgemessen** und als Tabelle im Issue belegt: die drei neuen Pfade
   existieren, `grep -c content_markdown main.py` → 2, der Pflichtfall aus
   ADR §9 P2 Punkt 6 steht als benannter Test
   (`test_patch_with_stale_base_rev_after_autosave_is_409_and_draft_unchanged`,
   `:156`), 24 Router-Tests mit RBAC/Tag-Scope/verwalteten Inhalten und 13×
   422, `openapi.json` 30157 → 31744 Zeilen, Fragment vorhanden, Gates grün.
   Zwei Befunde festgehalten: der PR war mit **14** statt 8 Dateien breiter
   als §Scope (kein Kriterium verletzt — Regel 132), und `edit_content` ist
   in zwölf ausgelieferten Builder-JSONs beschrieben, existiert aber erst
   mit P3.
2. **#999 geschlossen** (`completed`), **4 von 5 Kriterien belegt**; AK4 im
   Buchstaben verfehlt und **nicht umgeschrieben** (Regel 19/132). Grund ist
   ein Fehler in der Vorlage: ADR-0058 §9 P4 nennt **drei** Builder-Inhalte
   je Sprache, betroffen sind **sechs** je Sprache. Die drei zusätzlichen
   (`agent`, `external_tool`, `feedback_session`) beschrieben denselben
   BlockNote-JSON-Weg — Diff-Zitat im Issue. Der richtige Zähler war nicht
   `ls` über die genannten Pfade, sondern `grep -lic blocknote` über alle
   Builder-JSONs (Regel 42/43).
3. **#1024 geschnitten** — ADR-0061 **R2**, `enhancement` `backend`
   `needs-decision` `size/M`, vier Pflichtfelder vollständig, 5
   Akzeptanzkriterien (Norm 2–5), Scope aus den ADR-Abschnitten §3/§4/§5/§7
   plus gemessenen Repo-Stellen (`mollie.py:458`, Worker-Registry mit heute
   5 Routinen, `billing_0109` von #1022 belegt).
4. **Fünf Bodies auf Stand 58 gebracht** (Regel 38: der Body ist, was ein
   Agent lädt): #1000 (beide Blocker gefallen → Position 1), #1001,
   #989 (zwei Lockfile-Träger, Frist 11 Tage), #632 (locales zum zweiten
   Lauf in Folge bewegt), #633 (`client.ts` 1699 → 1772, `e2e/**` 2× bewegt).
5. **#442 neu geordnet und in Wellen gruppiert** (unten).
6. **Ein zweiter Kommentar in #977**, weil die Reihenfolge neu ist: #1000
   hebt die Registry auf 101, der Guard dieses PRs liest sie — **#977 vor
   #1000 mergen**, sonst wird er ein zweites Mal rot.

## Braucht eine Owner-Antwort (neu, je drei Optionen + Empfehlung in #442)

- **Weiche 24 — wer schließt ein Issue, dessen Umsetzung gemergt ist?**
  A `Closes #N` im PR-Template erzwingen · B der Lauf schließt, was `main`
  belegt · C die Kanban-Karte ist der Zustand. **Empfehlung: A, mit B als
  Netz.**
- **Weiche 25 — der Dependabot-Updater für `uv` ist rot.** „uv in /. for
  Pillow" ist **3 von 3** Versuchen gescheitert (2026-10-21, 22:21/23:36/
  23:56 UTC). `all-green` ist grün, der Updater hängt nicht am Required
  Check (Regel 64). Pillow 12.3.0 liegt transitiv über `fastembed 0.9.0`
  (`uv.lock:859`). **Ursache ungemessen:** Job-Log-Blob **403** am
  Agent-Proxy, `dependabot/alerts` **403**. A hinnehmen · B `fastembed`
  heben · C Ursache zuerst messen. **Empfehlung: C, dann A oder B** — ein
  Updater, der 3 von 3 fällt, liefert für den ganzen `uv`-Baum keine
  Einzel-Sicherheitsupdates mehr.
- **Weiche 26 — ist eine ADR-Pakettabelle Spezifikation oder Verweis?**
  A jede `Accepted`-ADR schneiden · B nur Tabellen mit Dateien/
  Voraussetzungen · C ADRs tragen keine Pakettabellen mehr.
  **Empfehlung: B** — so hat dieser Lauf gehandelt.
- **Zur Teilung von #1024** (eigener Kommentar dort): A ein Paket wie in der
  ADR · B R2a (Tabelle + Idempotenz, braucht **keine** der offenen Weichen)
  und R2b (Ausstellen + Archiv + Retry) · C erst nach W61-1 und W61-2
  starten. **Empfehlung: B**, mit dem ausdrücklichen Gegenbeleg, dass die
  ADR R2 als **ein** Paket geschnitten hat (Kriterium 2).

## Reihenfolge (Stand 58)

| Pos | Issue | Baum | Grund |
|---|---|---|---|
| 1 | **#1000** ADR-0058 P3 | Python | beide Blocker gefallen; Kriterium 2 + 3, öffnet #1001 |
| 2 | **#632** Passkey registrieren | Web | startbar, echt parallel zu 1 |
| 3 | **#1001** ADR-0058 P4b | Python | harte Abhängigkeit nach #1000 |
| 4 | **#989** `http-cache-semantics` | Web | zwei Lockfile-Träger (#674, #1017); **einziger Posten mit Datum**, Frist 2026-11-02 |
| 5 | **#633** Step-up mit Passkey | Web | nach #632 **und** einer Container-Laufzeit |

Außerhalb: **#1024** (doppelt gesperrt), #540, #535, #428, #435 (Tracking),
#454, #338, #542 (`human-only`).

## Wellen

- **S** `#1000 → #1001`, strikt seriell (Python/pytest).
- **A** `#632`, allein im Vitest-Baum. 🟢 **Parallel zu S.**
- **R** `#989` nach #674 **und** #1017. **B** `#633` nach #632 + Docker.
- **H** die Merges, billigste Reihenfolge: #1017 → #977 (nach der
  `CLAUDE.md:98`-Zeile) → #1021/#1019 → #995 → #674 → #1022 → Protokolle.
- **E** wieder gesperrt (`Caddyfile` belegt #1019). **G**, **L**, **I**,
  **J**, **M**, **Q** wie in #442. **K entfällt** — #1023 hat den
  `vitest`/`coverage-v8`-Versatz gelöst. **P** gehört in #977 selbst.

## Gates (Exit-Codes ohne Pipe, Regel 94)

| Gate | Ergebnis | Vorlauf |
|---|---|---|
| `ruff check .` | Exit 0, 0 Funde | — |
| `mypy .` | Exit 0, **630** Dateien | 613 |
| `pytest --collect-only -q` | Exit 0, **4524** Tests (135 billing) | 4320 |
| `changelog_fragments.py check` | Exit 0, **346** Fragmente | 332 |
| `npm run lint` | Exit 0, 0 errors / **90** warnings, 7 `--fix`-bar | 90 |
| `npx tsc -b` | Exit 0, 0 Byte | — |
| `npm run i18n:check` | Exit 0, **160** Waisen | 160 |
| `npm run test:coverage` | Exit 0, **276**/**2645**, **249,37 s**, **89,39 / 83,52 / 86,09 / 91,16** | 271/2562/280,04 s |

`main` @ `fb03322a`: **26** Check-Runs, `all-green` namentlich
`completed`/`success` (getrennt gelesen, Regel 91), **1** roter Check-Run —
und das ist der Dependabot-Updater, **kein CI-Job dieses Repos**. Regel 80
greift nicht. Umgebung: `docker info` → Exit 1, kein `podman`, Node
v22.22.0, npm 10.9.4.

## Nebenbefunde

- 🟢 **Der `vitest`/`coverage-v8`-Versatz ist erledigt** (#1023, installiert
  alle drei 4.1.12, kein Mismatch-Hinweis mehr).
- 🔴 **#1022 beantwortet W61-3 mit A im PR-Body; ADR-0061 §11 führt die
  Weiche weiter als offen.** Der Nachtrag fehlt (Regel 119/126).
- 🔴 **Die Onboarding-Serie springt von P1 (#1014) auf P4 (#1020)** — P2 und
  P3 gibt es im Repo nicht.
- ⚠️ **Elfter Stillstand der Lint-Verteilung, diesmal mit Gegenprobe:**
  #1020 brachte 976 + 316 neue Zeilen, `npx eslint src/features/help` findet
  **0** Befunde. Der Stillstand liegt im Altbestand (Regel 48/79).
- 🔴 **Dreizehnter Lauf ohne die eigene AgentDB.** `Who2Be---Coder` braucht
  eine Freigabe, die aus dieser Session nicht erteilbar ist — die Norm
  „Agent-ready Arbeitspaket" (`73a86231`) ist aus den Pflichtfeldern der
  bestehenden Issues rekonstruiert, nicht aus der Quelle gelesen.

## Fußzeile (Weiche 19)

**6 von 6 in diesem Lauf, je genau +58 Zeichen.** Fünf `PATCH`-Rewrites
(#1000, #1001, #989, #632, #633) behalten sie, der `POST`-Create #1024
bekommt sie angehängt. Das Verfahren, das hält: **die vorhandene Fußzeile
aus der Nutzlast entfernen und nichts erwähnen.** 🔴 **Die Ausnahme bleibt
#442 selbst** — nach dem Schreiben gegengelesen: **0** Vorkommen.

## Länge von #442 (Regel 10, hinterher gemessen)

Vorgefunden **67.794** Zeichen, nach dem Schreibvorgang gegengelesen
**71.840** — **+4.046**. **Das Ziel aus Regel 10 ist verfehlt**, und der
Grund ist benennbar: drei neue Weichen mit je drei Optionen (~5,5k), zwei
neue Regeln (~3,5k) und fünf neue PR-Zeilen stehen gegen die Kürzungen
(fünf beantwortete Weichen entfernt, zehn stabile Befunde zu einer Zeile
zusammengefasst, §Nicht in der Warteschlange gebündelt). **Gekürzt wurde
dort, wo Dopplung war — nicht dort, wo der nächste Lauf etwas braucht.**
