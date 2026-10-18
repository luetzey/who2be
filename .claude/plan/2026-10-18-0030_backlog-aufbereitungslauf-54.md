# Backlog-Aufbereitungslauf 54 (2026-10-18)

Auftrag: jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen,
Belegbares selbst entscheiden und mit Beleg ins Issue schreiben, Urteilsfragen
als Kommentar mit drei Optionen und Empfehlung zurückgeben (`needs-decision`),
danach die Warteschlange (#442) neu ordnen und in Wellen gruppieren.

**Messgrundlage:** `main` @ `a6027b88`, gemessen am 2026-10-18.
**Das Fenster seit Lauf 53 enthält 0 Commits.** `main` steht auf exakt dem
Commit, gegen den Lauf 53 gemessen hat. Keines der 15 offenen Issues wurde seit
Lauf 53 berührt (alle `updated_at` ≤ 2026-10-17T00:45:54Z), kein neuer Sach-PR,
keine Owner-Antwort.

**MCP-Server der eigenen AgentDB erneut nicht erreichbar** (neunter Lauf):
`Who2Be---Coder` liefert über `ToolSearch` keine Werkzeuge. Persona und
Playbook-Katalog lagen im System-Prompt vor; `fetch_playbook`, `fetch_resource`
(die Norm „Agent-ready Arbeitspaket", `73a86231`), `record_usage` und
`search_memory` nicht. Geprüft wurde deshalb gegen die Norm-Fassung in
`.github/PROJECT.md` §Constraints und die Pflege-Regeln in #442. Neunter Lauf
ohne Kurations-Rückmeldung an die eigene AgentDB.

## Warum ein stilles Fenster ein guter Messplatz ist

Ein Fenster ohne Commit ist die saubere Kontrollbedingung für zwei Regeln, die
Vorläufe aus Einzelbeobachtungen gebildet haben. Beide wurden in diesem Lauf
gegengemessen — mit entgegengesetztem Ergebnis.

### Regel 125 hält als Gegenmaßnahme, nicht als Diagnose

Lauf 53 hat aus einer Abweichung geschlossen, die Coverage-Zahl ändere sich
ohne Commit („ein Messwerkzeug ist keine Funktion seines Eingangs"). Dieser Lauf
hat dasselbe Kommando auf dem **bitgleichen** Baum gefahren:

| Wert | Lauf 53 (2026-10-17) | Lauf 54 (2026-10-18) |
|---|---|---|
| Statements | 89,47 % (11419/12762) | **89,47 % (11419/12762)** |
| Branches | 83,67 % (**7993**/9553) | **83,67 % (7993/9553)** |
| Functions | 86,13 % (3325/3860) | **86,13 % (3325/3860)** |
| Lines | 91,20 % (10507/11520) | **91,2 % (10507/11520)** |
| Dateien / Tests | 267 / 2517 | **267 / 2517** |
| Dauer | 342 s | 328 s |

**Alle vier Werte und die Branch-Rohzahlen reproduzieren exakt.** Damit steht
der Branch-Wert bei **drei** Beobachtungen auf `7993` (Lauf 51, 53, 54) und bei
**einer** auf `7994` (Lauf 52). Lauf 52 ist der Ausreißer — nicht der
Korrekturstand, als der er geschrieben wurde.

Die *Gegenmaßnahme* aus Regel 125 bleibt damit richtig und bewährt sich an
sich selbst: eine Zahl auf der letzten Dezimale nie aus **einer** Messung
„korrigieren". Die *Diagnose* ist zu weit gefasst — die Messung war in 3 von 4
Beobachtungen eine Funktion ihres Eingangs. Der Abstand zur Branch-Schwelle 79
ist **4,67** Punkte, Stand 2026-10-18, jetzt mit n = 3 statt n = 1.

### Regel 124 a hat nicht gegriffen — und der Grund ist die zweite Sonde

Das ist der zentrale Fund dieses Laufs.

**#975 trägt im Titel die Zahl 43.** Lauf 52 hat sie auf **44** „korrigiert"
und daraus Regel 124 a gebildet. Lauf 53 hat 44 „mit einer zweiten, unabhängig
geschriebenen Sonde gegengemessen" und Regel 124 a für erfüllt erklärt.

Dieser Lauf misst **43** — und kann zeigen, warum beide Vorläufe danebenlagen.

Die Sonde dieses Laufs geht nicht vorwärts über `it()`-Aufrufe, sondern
**rückwärts von jedem `await axe(` zum umgebenden Test**, auf einer Quelle, in
der Strings, Template-Literale und Kommentare vorher durch Leerzeichen ersetzt
sind. Sie ist gegen eine **Positiv-Kontrolle** belegt (Regel 32), die die Falle
enthält: ein Apostroph in einem Testnamen (`it('don\'t b', …)`).

Ohne diese Bereinigung öffnet genau so ein Apostroph einen Schein-String, die
Klammer-Suche läuft über das Ende des `it()`-Aufrufs hinaus und schluckt den
folgenden Test — derselbe Test wird zweimal gezählt. Nachgewiesen in zwei
Dateien: `FeedbackInbox.test.tsx` (1 `await axe(`, naiv **2** Treffer) und
`MemoryPage.test.tsx` (4 Vorkommen, naiv **5** Treffer).

**Drei Struktur-Gegenproben stimmen überein:**

| Größe | Wert |
|---|---|
| Dateien mit `await axe(` | **76** |
| davon im Glob `src/**/*.a11y.test.tsx` | **51** |
| davon außerhalb | **25** |
| `await axe(`-**Vorkommen** außerhalb | **70** |
| axe-**Tests** außerhalb (zwei Tests enthalten je zwei Zusicherungen) | **68** |
| davon mit eigenem Test-Timeout (3. Argument numerisch) | **25** |
| davon **ohne** → laufen auf dem 5-s-Default | **43** |
| verteilt über | **20** Dateien |

`25 + 43 = 68` und `70 − 2 = 68` — die Partition schließt in beide Richtungen.
Lauf 53 hat **69** berichtet, also einen Wert *zwischen* Vorkommen (70) und
Tests (68): seine Sonde hat die beiden Größen vermischt.

**Mechanik dazu, wörtlich gelesen:** die Grenze ist nicht per Test gesetzt,
sondern über zwei Vitest-Projekte. `apps/web/vite.config.ts:14-15` definiert
`A11Y_TEST_TIMEOUT_MS = 15_000` und `A11Y_TEST_GLOB =
'src/**/*.a11y.test.tsx'`; das Projekt `a11y` (`:57-59`) bekommt den Timeout,
das Projekt `unit` (`:50-51`) schließt den Glob aus und bleibt beim 5-s-Default
(`src/test/setup.ts:16`). Ein axe-Test in einer Datei **ohne** die Namensform
fällt deshalb auf 5 s zurück. Das ist Regel 118 in Reinform: die Grenze hängt
an einem Glob, und der Glob fängt 51 von 76 Dateien.

Die 11 `{ timeout: … }`-Vorkommen in Testdateien sind **`waitFor`-Optionen**,
keine Test-Timeouts — ein `waitFor` mit `timeout: 8000` in einem 5-s-Test
reißt die Testgrenze zuerst. Sie dürfen in keiner Zählung als Timeout gelten.

### Die Bezugswerte, die der Lauf selbst bewegt

Lauf 53 hat in #949 sechs verrottete Bezugswerte korrigiert. Nach einem Fenster
**ohne einen einzigen Commit** sind drei davon wieder falsch — und zwar genau
die drei, die nicht vom Repo abhängen:

| Bezugswert | Lauf 53 | heute (2026-10-18) | Ursache der Verrottung |
|---|---|---|---|
| changelog-Fragmente | 324 | **324** ✅ | Repo-Inhalt — hält |
| Commits nach `--unshallow` | 1562 | **1562** ✅ | Repo-Inhalt — hält |
| `pytest --collect-only` | 3648 | **3648** ✅ | Repo-Inhalt — hält |
| offene PRs | 18 | **19** 🔴 | **der Lauf selbst**: Lauf 53 hat #981 eröffnet |
| `docker info`-Lauf | 29. | **30.** 🔴 | Lauf-Zähler, tickt pro Lauf |
| shallow-Klon-Lauf | 16. | **17.** 🔴 | Lauf-Zähler, tickt pro Lauf |

Der Zähler offener PRs steigt, **weil** der Aufbereitungslauf sein Protokoll als
PR ablegt. Er misst eine Größe, die er durch das Messen verändert.

## Zwei neue Regeln (Vorschlag, Owner entscheidet)

> **127. Eine zweite Sonde, die dieselbe Annahme trifft wie die erste, ist
> keine unabhängige Gegenmessung.** Lauf 52 und Lauf 53 haben beide „Timeout am
> letzten Argument des Testaufrufs" gezählt und beide die Testgrenze per naiver
> Klammer-Zählung gesucht. Lauf 53 hat damit die Off-by-one des Vorlaufs
> **reproduziert** statt sie zu fangen — und Regel 124 a für erfüllt erklärt.
> Unabhängigkeit heißt ein **anderer Messweg**, nicht ein zweites Skript.
> **Gegenmaßnahme:** (a) eine Sonde über Quellcode ersetzt Strings,
> Template-Literale und Kommentare vor dem Mustervergleich durch Leerzeichen;
> (b) sie wird gegen eine Positiv-Kontrolle belegt, die die Falle enthält
> (Regel 32); (c) die billigste echte Unabhängigkeit ist eine
> **Struktur-Gegenprobe** — Vorkommen, Einheiten und die Partition müssen
> aufgehen (`70 − 2 = 68 = 25 + 43`). _124 a sagt: eine Zahl aus einer
> Differenz einmal direkt gegenmessen. **127 sagt: und die Gegenmessung darf
> nicht dieselbe Annahme treffen.**_

> **128. Ein Bezugswert, den der Lauf selbst bewegt, verrottet durch den Lauf
> — nicht durch das Repo.** In einem Fenster mit **0** Commits sind von sechs in
> Lauf 53 korrigierten Bezugswerten genau die drei wieder falsch, die nicht am
> Repo hängen: der Zähler offener PRs (er steigt, weil der Lauf sein Protokoll
> als PR ablegt) und die zwei Lauf-Zähler. **Gegenmaßnahme:** ein solcher Wert
> gehört nicht als blanke Zahl in einen Issue-Body. Lauf-Zähler bekommen die
> Form aus Regel 110 (**Datum der ersten Beobachtung**, Zählstand höchstens als
> Zusatz mit Messdatum); der Bestand offener PRs gehört gar nicht in ein
> Akzeptanzkriterium, weil er keine Eigenschaft des Pakets ist, sondern eine der
> Warteschlange. _110 sagt: eine Frist wird als Datum geschrieben. **128 sagt:
> dasselbe gilt für jeden Zähler, den der Messende selbst weiterdreht.**_

## Zustand von `main` und der PRs

**`main` ist grün.** HEAD `a6027b88`, Lauf **38953392933**, `status: completed`
und `conclusion: success` **getrennt** gelesen (Regel 91). Regel 80 greift
nicht: kein Paket ist durch ein rotes `main` gesperrt.

⚠️ **Weiche 1 bekommt zum vierten Mal in Folge keinen Beleg — und diesmal im
stärksten Sinn: im Fenster liegt NULL `main`-Push** (0 Commits). Unter den
zehn jüngsten `main`-Läufen sind **0** `cancelled`. Die Bedingung der drei
bekannten Abbrüche (drei Pushes binnen rund zwei Minuten) kann nicht vorliegen,
wenn gar nicht gepusht wurde. **Das ist eine Aussage über das Fenster, nicht
über die Maßnahme** (Regel 115).

**19 offene PRs** _(waren 18)_. Neu ist **#981**, das Protokoll von Lauf 53.
Datei-Scope je PR über `BASE=$(git merge-base origin/main <head>)` mit
ausdrücklicher Nicht-leer-Prüfung, dann `git diff --name-only`, **nach
`git fetch --unshallow`** (50 → **1562** Commits, Regel 90; **17. Lauf in
Folge** ein shallow Klon). Konfliktfreiheit je PR über
`git merge-tree --write-tree` (Regel 95). CI über die Check-Runs am Head,
`all-green` **namentlich** herausgesucht, Conclusions **positiv** auf
`failure`/`timed_out` gefiltert (Regel 101). Gate-Alter über die Anwesenheit
des Checks `secrets`.

| PR | Inhalt | Schreibt nach | `all-green` | Gate | hinter `main` | Klasse |
|---|---|---|---|---|---|---|
| **#980** | Rate-Limit an der Kante per fail2ban (#540) | `ci.yml`, `Caddyfile`, `RUNBOOK.md` + 3 × `fail2ban/**` + Fragment (**7**, +573/−0) | 🟢 **success**, 18 Checks, 0 rot | ✅ aktuell | **0** | 🟢 **merge-fertig, einziger Sach-PR, braucht kein Branch-Update** |
| **#977** | Werkzeugzahl aus `CLAUDE.md` nehmen, Wächter dafür | `changelog.d/`, `packages/models/tests/test_doc_tool_count.py` (2) | 🔴 **failure** (`python` + `all-green`; 16 grün) | ✅ aktuell | **1** | 🔴 **EIGEN, Weiche 16** |
| **#947** | `actions-all`, 3 Updates | `.github/workflows/ci.yml` (**zeilenneutral** 15/15) | 🟢 **success**, 15 Checks | ✅ aktuell | **18** | 🟢 **grün, frei** |
| **#954** | web-minor-patch, 4 Updates | `apps/web/package.json` + Lock | 🟢 **success**, 15 Checks | ✅ aktuell | **18** | 🟢 **grün** · stellt die Bedingung von #959 her |
| **#955** | python-minor-patch, 5 Updates | `uv.lock` | 🟢 **success**, 15 Checks | ✅ aktuell | **18** | 🟢 **grün, frei** |
| 🆕 **#981** | Protokoll Lauf 53 | eine Plan-Datei | 🟢 **success**, 16 Checks | ✅ aktuell | **0** | ⚪ Protokoll (Draft) |
| **#978 #976 #961 #950 #945 #924 #896 #870 #851 #841** | Protokolle 52–43 | je **eine** eigene Plan-Datei | 🟢 **alle success**, je 16 Checks | ✅ **alle aktuell** | 1 … 115 | ⚪ Protokoll, untereinander disjunkt |
| **#831** | Protokoll 42 | eine Plan-Datei | 🔴 **failure** (`all-green` + `audit`), 15 Checks | **alt** | **123** | 🔴 **Weiche 5** |
| **#823** | verrottete Zeiger nachziehen | `STATE.md`, `.github/PROJECT.md`, `RUNBOOK.md` + Plan (4) | 🟢 **success**, 17 Checks | **alt** | **126** | 🔴 **Weiche 10** (Draft) |
| **#674** | Vitest 4 → **5** (Major) | `apps/web/package.json` + Lock | 🔴 **failure**, **8** rote Jobs von 15 | ✅ aktuell | **18** | 🔴 **EIGEN, Weiche 12** |

🟢 **Alle 19 mergen konfliktfrei** (`git merge-tree --write-tree` → rc 0,
einzeln gemessen), **alle 19 merge-bases rechnen** (nicht-leer geprüft).
🟢 **Vier PRs sind gate-aktuell, grün und konfliktfrei: #980, #947, #954,
#955** — #980 braucht kein Branch-Update (0 hinter `main`).
🔴 **Zwei sind eigen-rot** (#977, #674).
🟢 **Elf der zwölf Protokoll-PRs sind grün UND gate-aktuell** _(Lauf 53: zehn
von elf)_ — nur #831 ist rot, nur #831 und #823 sind gate-alt. **Ein
Sammel-Merge-Fenster ist damit noch billiger als im Vorlauf.**

⚠️ **Nebenbefund zu Regel 101:** `CodeQL` trägt in #947, #954, #955 und #674
die Conclusion **`neutral`**. Der positive Filter auf `failure`/`timed_out`
zählt sie korrekt nicht als rot — ein Filter auf „nicht `success`" hätte in
vier PRs einen roten Check erfunden.

## Norm-Prüfung der 15 offenen Issues

Die Bodies sind seit Lauf 53 **unverändert** (alle `updated_at` ≤
2026-10-17T00:45:54Z), und im Fenster liegt kein Commit. Damit kann **keine**
Zeilennummer und **kein** Pfad in einem Body durch eine Repo-Änderung verrottet
sein — die Zeiger-Prüfung von Lauf 53 trägt konstruktiv weiter. Nachgemessen
wurde deshalb gezielt, was **ohne** Commit verrottet: die Bestands- und
Lauf-Zähler (Regel 128) und die Zahl aus #975 (Regel 127).

Die vier Pflichtfelder (Scope In/Out, prüfbare Akzeptanzkriterien,
Verifikations-Kommandos, Belege) stehen vollständig in **jedem**
`agent-ready`-Issue und in #975. **#428, #435, #535** tragen sie als
Tracking-Issues weiter nur teilweise (→ Weiche 4). **#540** fehlt ein
expliziter Scope-„In" und es führt **7** Kriterien, wo die Norm 2–5 vorsieht
(→ Weiche 4, Nebenbefund nach Regel 19).

### Selbst entschieden und geschrieben

| Issue | Befund | Entscheidung | Beleg |
|---|---|---|---|
| **#975** | Titel und Body nennen seit Lauf 52 **44** axe-Stellen | **43** — der Wert des ursprünglichen Titels ist richtig | Sonde mit Positiv-Kontrolle, drei Struktur-Gegenproben (`70 − 2 = 68 = 25 + 43`), Verteilung über 20 Dateien einzeln aufgeführt |
| **#949** | drei Bezugswerte nach 0-Commit-Fenster wieder verrottet | auf den heutigen Stand gesetzt **und in die dauerhafte Form gebracht** (Regel 110/128): Lauf-Zähler als Datum der ersten Beobachtung, Bestand offener PRs aus den Grenzen entfernt | heute gemessen; die drei Repo-Werte (324/1562/3648) halten unverändert |
| **#959, #632, #633, #849, #923** | dieselben Lauf-Zähler in Kopf- und Grenz-Blöcken | gleiche Form-Korrektur, Positionen unverändert | Fenster 0 Commits, Flächen 0× bewegt |

Keine Weiche ist durch Beleg geschlossen oder neu aufgegangen (Regel 13).

### Gegenprobe nach Regel 126 — in beide Richtungen

Nicht nur „welches Issue hat einen PR?", sondern „welche offene Weiche berührt
ein offener PR?". **Ergebnis: keine neue Antwort.** Im Fenster ist kein
Sach-PR entstanden; der einzige neue PR (#981) ist das Protokoll des Vorlaufs.
#980 beantwortet weiter nur die Mechanismus-Frage von #540, wie in Lauf 53
eingetragen. Kein offener PR-Body nennt eine Owner-Entscheidung, die nicht schon
im zugehörigen Issue steht.

## Reihenfolge

Kriterien unverändert: **1** harte Abhängigkeit · **2** Owner-Vorgabe ·
**3** Fundament vor Fläche · **4** Inventar vor Zuschnitt · **5** bei
Gleichstand das kleinere.

**Die Reihenfolge ist unverändert.** Das ist kein Versäumnis, sondern das
Ergebnis: im Fenster ist kein Issue geschlossen, keines neu, keine Weiche
beantwortet, keine Fläche bewegt. Es gibt nichts, was eine Position verschieben
könnte.

1. **#959** — SessionStart-Hook _(Kriterium 3)_. Trägt die Verifikation von
   #632, #633 und #975. ⚠️ **Vierter Lauf ohne Eintritt, und erneut mit
   fehlender Bedingung** (Regel 115/124 b): `apps/web/package.json` im Fenster
   **0×** bewegt. `npm run test:coverage` lief als **erste** Handlung im
   Web-Stack, ohne Reparatur (Regel 120) → **Exit 0**, und es hat wirklich etwas
   geprüft (**2517** Tests gefahren, Regel 49). ✅ Adresse frei:
   `scripts/install_pkgs.sh` über alle 19 PRs unberührt, auf `main` 0× bewegt,
   Datei **49** Zeilen, Befund weiter auf **`:44`** (`npm install || true`),
   **kein `rm -rf` im Hook**. 🔴 Die Bedingung steht weiter unmittelbar bevor:
   #954 **und** #674 warten beide darauf, `apps/web/package.json` zu bewegen.
2. **#632** — Passkey registrieren _(Kriterium 3)_. Öffnet #633. ✅ **Startbar
   ohne Vorbehalt, neunter Lauf in Folge.** Alle drei Schreibflächen PR-frei
   und im Fenster 0× bewegt (`features/settings/**`, `locales/{de,en}.json`,
   `orphan-baseline.json` — **160** Einträge als Liste gezählt). ⚠️ Momentwert
   (Regel 113). Zeiger einzeln nachgemessen: `MfaSection.tsx` **297**,
   `e2e/helpers/auth.ts` **180**, `package.json` **80**, `vite.config.ts`
   **89**, `SessionProvider.tsx` **267**. 🔴 Datei-Sperre an
   `apps/web/package.json` hält: **#954 UND #674**; #632 fasst sie nicht an.
3. **#949** — der irreführende pytest-Satz _(Kriterium 5)_. ✅ **Weiter das
   einzige Paket der Warteschlange ohne jede Datei-Sperre, sechster Lauf.**
   Befund wörtlich: `assert_skips_within_budget.py:128`, zwei Aufrufe in
   `ci.yml` (**`:210`** pytest, **`:268`** vitest), Datei **183** Zeilen,
   Adresse auf `main` 0× bewegt.
4. **#849** — Timeouts in `ci.yml` _(Kriterium 5, gebremst)_. Befund über
   `yaml.safe_load` gezählt: **12** Jobs, **0** mit `timeout-minutes`;
   `grep -c` → **0**; `all-green` hängt an **11**; Datei **1212** Zeilen, auf
   `main` 0× bewegt. 🔴 Adresse **doppelt** belegt (#947 **und** #980), und
   #980 ist nicht zeilenneutral (`ci.yml` 1212 → **1221**, +9 bei `:366`).
   ⚠️ Kriterium 3 bleibt bei n = 1 — belastbar ist 11,7–15,2 min aus Lauf 51.
5. **#923** — der `concurrency`-Kommentar _(Kriterium 3, dann 5)_. Befund
   wörtlich gehalten: `grep -c "run_id" ci.yml` → **1**, nur `:11`; Gruppe auf
   `:13`, `cancel-in-progress` auf `:14` = `${{ github.ref !=
   'refs/heads/main' }}`, auf `main` also **false**. 🟢 `:8-14` liegt **vor**
   beiden Einfügepunkten und überlebt die Merges von #980 und #947.
   🟢 Fährt am besten mit Welle D in **einem** PR.
6. **#633** — Step-up mit Passkey _(Kriterium 1)_. Genau zwei Blocker: **#632**
   (hart) + **Container-Laufzeit** (`docker info` → Exit 1, erstmals beobachtet
   2026-09-19, seither durchgehend). ✅ Keine Datei-Sperre über die 19 PRs; die
   zweite Achse im Fenster vollständig ruhig. Zeiger: `helpers/auth.ts`
   **180**/`:33`, `LoginPage.tsx` **394**, `SessionProvider.tsx` **267**,
   `api/types.ts` **2402**.

**#975 steht bewusst NICHT in der Reihenfolge** (Regel 8, Weiche 14). **Nach
einer Antwort gehört es zwischen Position 1 und 2** — und in **denselben** PR
wie der Coverage-Boden und der `__dirname`-Posten: alle drei schreiben
`apps/web/vite.config.ts`.

## Wellen

Geschnitten nach dem **Verifikations**-Baum, nicht nach der Schreibfläche
(Regel 76). Unverändert gegenüber Lauf 53, weil keine Fläche bewegt wurde;
die Freigaben sind **Momentwerte vom 2026-10-18** (Regel 113).

| Welle | Paket | Schreibt | Gemeinsam startbar mit |
|---|---|---|---|
| **N** | #959 _(Pos. 1)_ | `scripts/install_pkgs.sh` + Fragment | **M** — und nur M. Verifiziert im **Vitest**-Baum, also nicht mit A, B, F, G, K, L, O |
| **M** | #949 _(Pos. 3)_ | `scripts/ci/assert_skips_within_budget.py` + Test + Fragment | **N**. Nicht gegen einen zweiten Python-Schreiber (P, I) |
| **A** | #632 _(Pos. 2)_ | `MfaSection.tsx` + 2 Tests, `locales/{de,en}.json`, `orphan-baseline.json` | allein im Web-Stack; nicht mit N |
| **C** | #849 _(Pos. 4)_ | `ci.yml` + Fragment | nicht mit D, E, Q; **nach dem Merge von #980 alle Zeiger neu messen** |
| **D** | `audit`-Trennung **+ #923** | `ci.yml` | **beide in EINEN PR**; nicht mit C; hinter Weiche 11 |
| **B** | #633 _(Pos. 6)_ | `LoginPage.tsx`, `SessionProvider.tsx`, `e2e/**`, `locales/*` | **allein**; nach #632; braucht Docker |
| **O** | #975 _(nur nach Weiche 14)_ | `vite.config.ts` (+ bis zu **20** `*.test.tsx` bei Option C) | **mit G in einem PR**; nicht mit A, B, F, K, L, N |
| **G** | Coverage-Boden + `__dirname` _(nach Weiche 6)_ | `vite.config.ts` `:82-85` und `:29` | **mit O in einem PR** |
| **P** | Weiche 16 / #977 | eine Zeile `CLAUDE.md:98` | Python-Stack; nicht mit M oder I |
| **Q** | Wirkungsnachweis #540 _(nach Weiche 17 C)_ | `deploy/hetzner/tests/` + `ci.yml` | hinter dem Merge von #980 **und** hinter der `NET_ADMIN`-Messung |
| **E** | Caddy-Versions-Widerspruch | `Caddyfile`, zwei `*_ci.sh`, `ci.yml` | 🔴 blockiert: `Caddyfile` → #980, `ci.yml` → #947 **und** #980 |
| **F** | die 7 `--fix`-baren Lint-Warnungen | vier Dateien | nicht gegen A, B, G, K, L, N, O |
| **I** | Valkey-Rest _(Weiche 15)_ | `.github/dependabot.yml`, `test_dependabot_compose_coverage.py:174` | Python-Stack; nicht mit M oder P |
| **J** | MB/MiB-Zeile | `docs/licensing/plans.md:28-29` | **parallel zu jeder Welle**, ein Satz |
| **L** | Typ-Augmentation auf Vitest 5 _(Weiche 12 C)_ | `src/test/vitest-axe.d.ts` | eine Datei, 77 Leser |
| **H** | Branch-Updates und Merges | kein Repo-Paket | **#980** zuerst (0 hinter), dann #947 (Konfliktfreiheit danach **neu** messen), #954, #955 |

**Keine Welle:** C gegen D gegen E gegen Q (dieselbe `ci.yml`) · O gegen G
(dieselbe `vite.config.ts`) · F, G, K, L, N, O gegen A oder B (derselbe
Vitest-Baum) · B vor A (harte Abhängigkeit) · M gegen P gegen I (ein
pytest-Baum) · #823 gegen die Protokoll-Merges (Weiche 10 zuerst) · ein Merge
gegen alles im selben Baum.

**Bedingungen für jede Welle:** jeder Agent fährt **nur** die Gates seines
Stacks; **kein Beteiligter — Sub-Agent wie Orchestrator — setzt einen
git-Schreibbefehl ab**; **keiner startet einen zweiten Testlauf im selben
Baum**, solange ein anderer läuft (Regel 30/31). Jeder Web-Agent prüft vor
seiner ersten Messung, dass `npm run test:coverage` **startet** (Regel 115) —
und gibt einem neuen axe-Test entweder die Namensform `*.a11y.test.tsx` oder
ein explizites Timeout (#975). Wer einen Wächter einführt, bringt den Baum im
selben PR in den geforderten Zustand (Regel 123) und begründet eine bewusste
Lücke nicht mit einer ungemessenen Behauptung (Regel 39). Wer eine Zahl
gegenmisst, nimmt einen **anderen Messweg**, nicht ein zweites Skript mit
derselben Annahme (**Regel 127**).

## Messwerte des Laufs

Sequenziell erhoben, ein Schreiber je Baum, Node **v22.22.0**, ohne vorherige
Reparatur (Regel 120), Exit-Codes **ohne Pipe** gelesen (Regel 94 — ein erster
Versuch mit `| tail` las den Exit-Code von `tail` und wurde verworfen).

`npm run test:coverage` → **Exit 0**, **267** Dateien / **2517** Tests,
Coverage **89,47 / 83,67 / 86,13 / 91,2** (Branches **7993/9553**), Dauer
**328 s** · `npm run lint` → **Exit 0**, **90 problems, 0 errors**, 8 Regeln,
**7** `--fix`-bar · `npx tsc -b` → **Exit 0**, Ausgabe **leer (0 Byte)** ·
`npm run i18n:check` → **Exit 0**, **160** bekannte Waisen ·
`npm audit --omit=dev --audit-level=high` → **Exit 0**, **0 vulnerabilities** ·
`uv run ruff check .` → **Exit 0**, 0 Funde · `uv run mypy .` → **Exit 0**,
0 Funde in **608** Dateien · `uv run pytest --collect-only -q` → **3648**
Tests, **135** Zeilen unter `packages/billing/` ·
`uv run python -c "import who2be_billing"` → ok _(ein blankes `python3 -c`
ist die falsche Sonde, Regel 49)_ · `changelog_fragments.py check` →
**Exit 0**, **324** Fragmente · `docker info` → **Exit 1** ·
`ci.yml` **1212** Zeilen, **12** Jobs, **0** mit `timeout-minutes` ·
`Caddyfile` **195** Zeilen, `grep -cE "\brate\b"` → **0** · Betriebs-Pin
`deploy/hetzner/who2be/docker-compose.yml:452` = `caddy:2.11.7-alpine` (Datei
**573** Zeilen, Service-Schlüssel `:446`), CI validiert weiter gegen
`caddy:2.8-alpine` (`ci.yml:351`/`:352`/`:367`/`:368`) · Registry **100**
Werkzeuge (`tool_requirements.py`, Mapping-Einträge gezählt), alle vier
Doku-Stellen **100** (`CLAUDE.md:98`, `README.md:70`, `ROADMAP.md:24`,
`docs/mcp-payload-budget.md:267`) · `osv-scanner.toml:11`
`ignoreUntil = 2026-11-02T00:00:00Z` → **15 Tage** ·
Lint-Verteilung unverändert: `set-state-in-effect` **48** ·
`classnames-order` **18** · `only-export-components` **12** ·
`incompatible-library` **5** · `preserve-manual-memoization` **4** ·
`use-memo`/`refs`/`exhaustive-deps` je **1**; die 18 `classnames-order`
liegen unverändert in `ui/sheet.tsx` **10**, `ui/checkbox.tsx` **4**,
`LinkedBlocksList.tsx` **2**, `ResourceBlockLinkPicker.tsx` **2**.

**Siebter Stillstand auf 90** Lint-Warnungen.

## Was offen zurückgeht

**Siebzehn Weichen stehen unverändert** — keine wurde beantwortet, keine neu
belegt. Sie werden nicht erneut gestellt (Regel 9); Volltexte stehen in #442
und in den jeweiligen Issue-Bodies (Regel 38). Fristgebunden: **Weiche 5**,
`ignoreUntil = 2026-11-02` → **15 Tage**.

**Weiche 18 ist neu** und betrifft das Verfahren selbst, nicht den Backlog:
dieser Lauf hat ein bitgleiches Repo gemessen. Sein Beitrag zum Repo-Zustand
ist **ein weiterer unverschmolzener PR**, und dieser PR hat in sechs
Issue-Bodies drei Bezugswerte verrottet (Regel 128). Zwölf der neunzehn offenen
PRs sind Protokolle dieses Verfahrens. Drei Optionen mit Empfehlung stehen als
Kommentar an #442.

## Was der Lauf nicht tut

Kein Code an den Issues, kein Branch für ein Issue, kein Issue-Claim, keine
neuen Issues, kein Merge, kein Branch-Update, keine Label-Änderung an einem
`human-only`-Issue. #454, #338 und #542 tragen `human-only` — der Lauf endet
dort nach Schritt 1. Die Reihenfolge wurde **nicht** verändert, weil kein
Kriterium sich geändert hat.
