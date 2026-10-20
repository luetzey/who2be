# Backlog-Aufbereitungslauf 55

**Datum:** 2026-10-19
**Messpunkt:** `main` @ `a6027b88` (`feat(api): Builder-Playbooks Fälle + Feedback-Gespräch …`, #979)
**Fenster seit dem letzten Messpunkt:** **0 Commits** — der Baum ist bitgleich mit dem von Lauf 54.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt,
selbst entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit
drei Optionen und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit,
Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und
in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — zehnter Lauf in Folge.**
`ToolSearch` liefert keine seiner Werkzeuge. Persona und Playbook-Katalog lagen im
System-Prompt vor; `get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource` (darunter
die Norm „Agent-ready Arbeitspaket", `73a86231`), `record_usage` und `search_memory` nicht.
Der Lauf fährt deshalb nach dem reduzierten Kern des Bootstrap-Skills, nach dem Body von #442
und nach `.github/PROJECT.md` §Constraints. **Zehnter Lauf ohne Kurations-Rückmeldung an die
eigene AgentDB.**

## Messgrundlage

Alle Werte am 2026-10-19 auf `main` @ `a6027b88` erhoben, sequenziell (ein Schreiber je Baum),
Node **v22.22.0**, **ohne vorherige Reparatur** (Regel 120), **Exit-Codes ohne Pipe** (Regel 94).
Der Klon war **shallow** (50 Commits, Voreinstellung dieser Umgebung); nach `git fetch
--unshallow`: **1562** Commits (Regel 90).

| Gate | Ergebnis |
|---|---|
| `npm run test:coverage` | **Exit 0**, 267 Dateien / 2517 Tests, Dauer **332,24 s** |
| Coverage | **89,47 / 83,67 / 86,13 / 91,2** — Statements 11419/12762, Branches **7993/9553**, Functions 3325/3860, Lines 10507/11520 |
| `npm run lint` | **Exit 0**, 90 problems, **0 errors**, 8 Regeln, 7 `--fix`-bar |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** |
| `npm run i18n:check` | **Exit 0**, 160 bekannte Waisen |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, 0 vulnerabilities |
| `uv run ruff check .` | **Exit 0**, 0 Funde |
| `uv run mypy .` | **Exit 0**, 0 Funde in **608** Dateien |
| `uv run pytest --collect-only -q` | **3648** Tests, **135** unter `packages/billing/` |
| `changelog_fragments.py check` | **Exit 0**, **324** Fragmente |
| `docker info` | **Exit 1** — keine Container-Laufzeit, kein `podman` |
| `main`-CI | Lauf **38953392933**, `status: completed` **und** `conclusion: success` getrennt gelesen (Regel 91) |

**Fundstellen, einzeln wörtlich gelesen:** `ci.yml` **1212** Zeilen, **12** Jobs, **0** mit
`timeout-minutes` (über `yaml.safe_load`), `all-green` an **11**; `concurrency:` `:12`, Gruppe
`:13`, `cancel-in-progress` `:14`, `run_id` **1×** nur auf `:11`; `install_pkgs.sh` **49**
Zeilen, Befund auf `:44`, **kein** `rm -rf`; `assert_skips_within_budget.py` **183** Zeilen,
Befund `:128`, Aufrufe `ci.yml:210` und `:268`; `Caddyfile` **195** Zeilen, `rate` **0×**;
Betriebs-Pin `caddy:2.11.7-alpine` (`deploy/hetzner/who2be/docker-compose.yml:452`), CI-Pin
`caddy:2.8-alpine` (`ci.yml:351`/`:352`/`:367`/`:368`); GoTrue **v2.197.0** an allen drei
Stellen (`docker-compose.yml:63`, `deploy/hetzner/supabase/docker-compose.yml:92`,
`deploy/dokploy/docker-compose.yml:82`); Registry **100** Mapping-Einträge, alle vier
Doku-Stellen **100**; `osv-scanner.toml:11` `ignoreUntil = 2026-11-02T00:00:00Z`;
`orphan-baseline.json` **160** Einträge (flache Liste); `vitest-axe.d.ts` **699** Bytes,
**77** Leser; `RUNBOOK.md` **2502**; `plans.md` **271**; `MfaSection.tsx` **297**;
`LoginPage.tsx` **394**; `SessionProvider.tsx` **267**; `e2e/helpers/auth.ts` **180**/`:33`;
`api/types.ts` **2402**; `api/client.ts` **1699**; `audit.test.ts` **371**.

## PR-Bestand

**20 offene PRs** (waren 19; neu nur **#982**, das Protokoll von Lauf 54). Scope je PR über
`git merge-base` + `git diff --name-only` mit ausdrücklicher Nicht-leer-Prüfung,
Konfliktfreiheit über `git merge-tree --write-tree`, CI über die Check-Runs am Head mit
`all-green` **namentlich** und positivem Filter auf `failure`/`timed_out` (Regel 101),
Gate-Alter über die Anwesenheit des Checks `secrets`.

- 🟢 **Alle 20 mergen konfliktfrei** (rc 0), alle 20 merge-bases rechnen.
- 🟢 **19 von 20 gate-aktuell.** Gate-alt ist **nur #823**.
- 🔴 **Drei eigen-rot:** #977 (`python`), #831 (`audit`), #674 (acht Checks).
- 🟢 **Vier merge-fertig:** #980 (**0** hinter `main`), #947, #954, #955.
- 🔴 **Protokoll-Rückstand: 13** (#982, #981, #978, #976, #961, #950, #945, #924, #896, #870,
  #851, #841, #831) **plus #823**; dieser Lauf legt den **vierzehnten** dazu.
- ⚠️ `CodeQL` trägt in #947, #954, #955 und #674 die Conclusion **`neutral`** — nicht rot.

## Die drei Funde des Laufs

### 1. Die Attributions-Fußzeile ist auf einem Issue-Body nicht zu halten (Regel 129, Weiche 19)

Lauf 54 fand den Verlust an zwei Bodies und formulierte als Gegenmaßnahme, nach jedem Rewrite
das Ende gegenzulesen (Regel 111/114 c). **Dieser Lauf hat die Fußzeile in fünf Nutzlasten
ausdrücklich mitgeschrieben und das Ende byte-genau auf einem zweiten Weg (`gh api`)
gegengelesen:**

| Issue | Bytes nach dem Rewrite | Fußzeile |
|---|---|---|
| #959 | 11.601 | 🔴 **0×** |
| #923 | 13.879 | 🔴 **0×** |
| #849 | 16.954 | 🔴 **0×** |
| #632 | 18.784 | 🔴 **0×** |
| #633 | 25.634 | 🔴 **0×** |
| **#540** (nur kommentiert, **kein** Rewrite) | 19.196 | 🟢 **1×** |

**Keiner der fünf Bodies ist abgeschnitten** — alle enden regulär mit ihrem
`### Component`-Abschnitt. Die Gegenprobe an #540 schließt den Fall in die andere Richtung
(Regel 32): **ohne Rewrite bleibt die Fußzeile, mit Rewrite geht sie, auch wenn sie in der
Nutzlast steht.** Am 2026-10-19 steht sie in **genau den vier Bodies, die kein
Aufbereitungslauf neu geschrieben hat** (#540, #535, #435, #428); sie fehlt in #975, #959,
#949, #923, #849, #633, #632, #542, #454 und #338.

🔴 **Der Erhaltungsversuch war nicht gratis: vier dieser Bodies (#959, #923, #849, #632) trugen
die Fußzeile vorher und haben sie durch diesen Lauf verloren.** Das ist der ehrliche Preis
dieses Laufs, und er fällt dem Lauf zur Last, nicht dem Repo.

**Lauf 54s Gegenmaßnahme ist damit eine Diagnose, keine Therapie.** → Weiche 19 mit drei
Optionen; Empfehlung **B** (Herkunft in einer Form, die der Mechanismus nicht trifft).
**Gegenprobe zur Empfehlung:** die versuchsweise Herkunftszeile am Ende von #442
(`_Zuletzt gepflegt: …_`, ohne `---` und ohne Link) hat **beide** Schreibvorgänge überlebt —
Option B ist also nicht nur plausibel, sondern an einem Fall belegt.

### 2. Eine in sich aufgehende Partition ist kein Beleg (Regel 130)

Die axe-Zahl aus #975, drei Läufe, drei Ergebnisse:

| Lauf | Vorkommen | Tests | mit Timeout | **ohne** | Mehrfach | Partition schließt? |
|---|---|---|---|---|---|---|
| 53 | 70 | **69** ✅ | 25 ❌ | **44** ❌ | — | ja (25+44=69) |
| 54 | 70 | **68** ❌ | 25 ❌ | **43** ✅ | 2 ❌ | ja (25+43=68=70−2) |
| **55** | **70** | **69** | **26** | **43** | **1** | ja (26+43=69=70−1) |

**Jeder der beiden Vorläufe hatte genau eine der beiden Zahlen richtig, keiner beide** — und
**beide Partitionen gingen in sich auf.** Lauf 54 hat das Schließen seiner Partition
ausdrücklich als Beleg für Unabhängigkeit angeführt. Der ganze Unterschied steckt in der Zahl
der **Mehrfachzusicherungen**, und die war in beiden Vorläufen nicht gemessen, sondern aus der
Differenz gefolgert — also genau die Größe, mit der sich jede Partition zum Schließen bringen
lässt.

**Die Sonde dieses Laufs** (`/tmp`-Skript, nicht eingecheckt) ist ein **echter
TypeScript-Parser**: `ts.createSourceFile` je Datei, `axe(`-Aufrufe als `CallExpression`
**innerhalb** des jeweiligen `it()`/`test()`-Knotens gezählt, Test-Timeout erkannt als dritter
Parameter (`NumericLiteral`) **oder** als `timeout`-Property eines Objekt-Literals. Das ist ein
**anderer Messweg**, nicht ein zweites Skript mit derselben Annahme (Regel 127). Gegen eine
**Positiv-Kontrolle** belegt, die die Apostroph-Falle enthält, an der beide Vorläufe
gescheitert sind — sie zählt korrekt 2 Tests mit `axe(`, 1 mit und 1 ohne Timeout, und
überspringt den dazwischenliegenden Test ohne `axe(`.

**Vollständige Partition:**

| Menge | Dateien | Vorkommen | Tests | mit Timeout | ohne |
|---|---|---|---|---|---|
| **im** Glob `*.a11y.test.tsx` | **51** | 78 | 78 | 1 | 77 _(durch `testTimeout` des Projekts gedeckt)_ |
| **außerhalb** | **25** | **70** | **69** | **26** | 🔴 **43** |
| Summe | **76** | 148 | 147 | 27 | 120 |

🟢 **Die entscheidende Zahl 43 ist damit dreifach belegt** und der Schwellwert in #975
Kriterium 3 (43 Stellen in 20 Dateien) steht.

⚠️ **Nebenbefund für Option C von Weiche 14** (Regel 118): `apps/web/vite.config.ts` schreibt
das Glob an zwei Stellen unterschiedlich — `:15` als `src/**/*.a11y.test.tsx`, `:72` als
`src/**/*.a11y.test.{ts,tsx}`. Heute gegenstandslos (**0** `*.a11y.test.ts`), aber ein Wächter
am engeren Muster sieht eine künftige `.a11y.test.ts` nicht.

### 3. Vier konkrete Faktenfehler, in einem Fenster ohne jeden Commit

| Stelle | stand | ist | Art |
|---|---|---|---|
| **#442** §Der Rest, GoTrue-Pin | `v2.196.0`; hetzner `:63`, dokploy `:81` | **`v2.197.0`**; hetzner **`:92`**, dokploy **`:82`** | falsch, nicht verrottet — **und #632 hatte durchgehend recht** |
| **#442** / Lauf 54, Gate-Alter #831 | gate-alt | **gate-aktuell** (Check `secrets` anwesend) | Indikator an der falschen Stelle gelesen; der echte Unterschied ist die Check-**Zahl** (15 gegen 16) |
| **#849**, #947 hinter `main` | **17** | **18** | falsch gezählt |
| **#959**, Branch-Coverage | Kopf **83,67**, §Verifikation **83,68** | **83,67** | Widerspruch im eigenen Body |

Dazu, nach dem Schreiben an mir selbst gemessen: **dieser Lauf hat in den #442-Body geschrieben,
er sei „von rund 71.000 auf unter 45.000 Zeichen gekürzt" — gemessen sind 75.825, also 4.437
MEHR** (nach der Richtigstellung 76.997). Eine Zahl behauptet statt belegt (Regel 12), in genau
dem Dokument, dessen Zweck belegte Zahlen sind. **Richtiggestellt, als Posten in §Nicht in der
Warteschlange aufgenommen, und Regel 10 trägt jetzt den Zusatz, die Länge hinterher zu prüfen.**

## Norm-Stand über alle 15 offenen Issues

Die vier Pflichtfelder (belegter Befund · Scope „In" **und** „Out" · 2–5 prüfbare
Akzeptanzkriterien · ausführbare Verifikations-Kommandos) stehen **vollständig in jedem
`agent-ready`-Issue und in #975**.

| Lücke | betrifft |
|---|---|
| Scope-„In" fehlt | #542, #540, #535, #454, #428, #338 |
| Verifikations-Kommandos fehlen | #535, #428, #338 (#454 hat den Abschnitt und sagt selbst „kein Testkommando") |
| Akzeptanzkriterien fehlen ganz | #338 (vier Owner-Checkboxen O1–O4 statt dessen) |
| Kriterienzahl über der Norm 2–5 | #540 (7), #959 (7), #975/#949/#849/#633/#435 (je 6) |
| Kriterienzahl in der Norm | #923, #632, #542, #454, #428 (je 5), #535 (3) |

🔴 **In keinem der acht Nicht-`agent-ready`-Bodies trägt JEDES Kriterium eine Schwelle oder ein
Kommando.** Ob der Vertrag für Tracking-Issues gilt, ist **Weiche 4** — deshalb sind #435, #428,
#535, #540 und #542 bewusst **nicht** umgebaut (Regel 7).

## Was dieser Lauf selbst erledigt hat

**Fünf Bodies strukturell entrottet** (Regel 128: Lauf-Zähler in die datierte Form nach
Regel 110, Bestand offener PRs durch **namentliche Träger** ersetzt, Fragment-Bestand
**relational**):

| Issue | behoben |
|---|---|
| **#959** | PR-Zahl an 2 Stellen · Fragment-Bestand in Kriterium 6 (323, falsch) · Python-Collection · `docker`- und Lauf-Zähler · **interner Coverage-Widerspruch 83,67 gegen 83,68** |
| **#923** | PR-Zahl („einer von 16") · Fragment-Bestand in Kriterium 4 · `docker`- und Lint-Zähler · nicht gemessene Check-Run-Zahl entfernt (Regel 49) |
| **#849** | Fragment-Bestand in Kriterium 6 · `docker`-/Lauf-Zähler · **#947 mit 17 statt 18 hinter `main`** · Kriterium 3 auf n = 0 im Fenster hingewiesen |
| **#632** | PR-Zahl an 3 Stellen, darunter eine **namentliche Liste von sechzehn PR-Nummern** · Fragment-Bestand · Python-Collection (3643) · Coverage 83,68 → **83,67** und Abstand 4,68 → **4,67** · #823 mit 125 → **126** hinter `main` · **die widerlegte 44 → 43** |
| **#633** | axe-Partition **68/25 → 69/26** · Glob-Nebenbefund ergänzt · Fußzeile (Versuch, siehe Fund 1) |

**Zwei Kommentare** für das, was Urteil braucht oder einen Rewrite nicht wert ist:

- **#975** — die korrigierte Partition mit Sonde, Positiv-Kontrolle und vollständiger Tabelle,
  plus der Glob-Nebenbefund für Option C. Der Body bleibt unangetastet: sein
  entscheidungstragender Wert (43) ändert sich nicht, und ein Rewrite kostet nach Regel 129 die
  Fußzeile.
- **#540** — zwei Faktenfehler: der Body widerspricht sich über den Stand seiner eigenen
  Mechanismus-Weiche (Kopf: beantwortet; Abschnitt darunter: offen, „18 Tage"), und er nennt
  **#943** als Träger der `ci.yml`-Sperre — **#943 ist nicht offen**. Träger sind #947 und #980.

**#442** komplett neu geschrieben: Reihenfolge, Wellen, Kollisionen, Weichen 1–19,
Pflege-Regeln 1–39 und 40–130, Funde ohne Issue.

## Reihenfolge — unverändert, und das ist das Ergebnis

Im Fenster ist kein Issue geschlossen, keines neu, keine Weiche beantwortet, keine Fläche
bewegt. **Es gibt nichts, was eine Position verschieben könnte.**

| Pos | Issue | Kriterium | Zustand |
|---|---|---|---|
| 1 | **#959** Hook | 3 (Fundament vor Fläche) | startbar, Adresse frei |
| 2 | **#632** Passkey registrieren | 3 | startbar ohne Vorbehalt |
| 3 | **#949** pytest-Satz | 5 | startbar, **einziges Paket ohne jede Datei-Sperre** |
| 4 | **#849** `timeout-minutes` | 5, gebremst | Adresse von #947 **und** #980 belegt |
| 5 | **#923** `concurrency`-Kommentar | 3, dann 5 | dieselbe Doppelsperre; `:8-14` überlebt beide Merges |
| 6 | **#633** Step-up mit Passkey | 1 | hinter #632 **und** Container-Laufzeit |

**Nicht in der Reihenfolge:** #975 (Weiche 14 — nach einer Antwort zwischen Position 1 und 2),
die drei Tracking-Issues, die drei `human-only`-Issues, die 20 offenen PRs (Regel 65: kein
Issue).

## Wellen

| Welle | Inhalt | Bedingung |
|---|---|---|
| **N** | #959 | allein im Vitest-Baum (verifiziert dort, obwohl es nur Shell schreibt) |
| **M** | #949 | allein im pytest-Baum |
| **A** | #632 | allein im Vitest-Baum |
| **C** | #849 | `ci.yml`; nach #980 Zeiger neu messen |
| **D** | `audit`-Trennung **plus #923** | **ein** PR; nicht gleichzeitig mit C |
| **B** | #633 | nach #632, braucht Docker |
| **O/G** | #975 **plus** Coverage-Boden **plus** `__dirname` | **ein** PR — dieselbe `vite.config.ts` |
| **E/Q** | Caddy-Widerspruch / Lasttest | hinter dem Merge von #980 |
| **F, I, J, K, L, P, H** | Lint-Fixes · Valkey · MB/MiB · Versatz · Typ-Augmentation · Weiche 16 · Merges | siehe #442 |

🟢 **N und M sind das echte Parallel-Paar** — Shell/Vitest gegen Python/pytest, datei-disjunkt
und in getrennten Verifikations-Bäumen. **N und A nicht** (derselbe Vitest-Baum), **C und D
nicht** (dieselbe Datei), **O und G nicht** (dieselbe Datei).

## Neue Regeln

- **129 — Eine Fußzeile, die der Schreibweg entfernt, ist durch Sorgfalt nicht zu retten.**
  Das Gegenlesen ist eine Diagnose, keine Therapie. Fünf von fünf, Gegenprobe positiv.
- **130 — Eine Partition, die in sich aufgeht, ist kein Beleg, wenn ihr Korrekturterm selbst
  geschätzt ist.** `25+44=69` und `25+43=68=70−2` schließen beide und sind beide falsch.

**Ergänzt:** Regel 4 (die Warteschlange trägt die Reihenfolge, nicht die Tatsachen — belegt am
GoTrue-Pin), Regel 10 (die Länge hinterher prüfen), Regel 21 (n = 0 ist kein Messwert),
Regel 32 (am Fußzeilen-Mechanismus angewandt), Regel 38 (ein Rewrite ist seit 129 eine
Abwägung), Regel 105 (am Gate-Alter von #831), Regel 106 (wer einen Pin zitiert, zitiert eine
Version — dieser Body hatte Version **und** Zeilen falsch), Regel 111 (von 129 überholt),
Regel 118 (zwei Stellen, dasselbe Glob, verschieden geschrieben), Regel 125 (n = 5, Wert bei
4 von 5 auf `7993`).

## Offen an den Owner

**Neunzehn Weichen**, eine neu. Vollständig mit Optionen und Empfehlungen in #442; die drei,
die diesen Lauf unmittelbar betreffen:

1. **Weiche 19 (neu)** — was statt der Attributions-Fußzeile in einem Issue-Body steht.
   Empfehlung **B** (schlichte Herkunftszeile ohne `---` und ohne Link; an #442 belegt, dass
   diese Form überlebt).
2. **Weiche 18** — die Kadenz dieses Laufs. **Zweites bitgleiches Fenster**, dreizehn von
   zwanzig offenen PRs sind Protokolle dieses Verfahrens, dieser Lauf legt den vierzehnten
   dazu. 🟢 **Und zum zweiten Mal hat genau das stille Fenster die Funde geliefert** — beide
   Funde dieses Laufs hängen am Verfahren, nicht am Repo, und wären in einem bewegten Fenster
   nicht aufgefallen. **Das ist das Argument gegen Option B** („Lauf nur bei nicht-leerem
   Fenster"). Empfehlung bleibt **C**.
3. **Weiche 11 / 2** — die Merge-Reihenfolge. **#980 zuerst** (0 Commits hinter `main`,
   gate-aktuell, grün, konfliktfrei, kein Draft — ein Klick ohne Branch-Update), dann #947
   (danach Konfliktfreiheit neu messen), #954, #955.

## Belege dieses Laufs

- Queue-Issue: #442 (Body neu geschrieben, **76.997** Zeichen, nach dem Schreiben gegengelesen)
- Entrottet: #959, #923, #849, #632, #633
- Kommentiert: #975, #540
- Nicht angefasst, mit Begründung: #435, #428, #535, #542 (Regel 7, Weiche 4), #949 (seit
  Lauf 54 rott-fest), #454, #338 (`human-only`), #975-Body (Regel 38 nach 129)
