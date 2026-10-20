# Backlog-Aufbereitungslauf 51 (2026-10-15)

**Gegen `main` @ `5f251c2f` gemessen** (13 Commits / 85 Dateien seit der Lauf-50-Basis
`6ef78994`, ADR-0053 Phase E5b–E5k). Warteschlange und Begründungen stehen in
**#442**; dieses Protokoll hält fest, was gemessen wurde und was daraus folgte.

## Was dieser Lauf ergeben hat

### 1. Der zentrale Fund: 43 axe-Tests an einer 5-s-Grenze → #975

Der `main`-Lauf **38610320689** (`b450e17e`, #973) ist rot geworden — Job `web`,
Schritt „Test (coverage ratchet)", **zwei Tests mit „Test timed out in 5000ms"**:
`ReviewDetailPage.test.tsx:572` und `ReviewPreparePage.test.tsx:546`.

Ursache vollständig gemessen: `apps/web/vite.config.ts:14` hebt das Vitest-Timeout
auf 15 s, aber nur für das Projekt `a11y`, dessen `include` genau ein Glob ist
(`:15` = `src/**/*.a11y.test.tsx`). Der Kommentar `:8-13` begründet das mit einer
eigenen Messung („unter fremder Last gemessen bis ~7 s") und setzt voraus, dass
axe-Läufe nur in diesem Glob stehen.

| Messung auf `5f251c2f` | Wert |
|---|---|
| Dateien mit `await axe(` unter `apps/web/src` | 76 |
| davon im Glob (15 s) | 51 |
| davon außerhalb (Projekt `unit`, 5 s) | 25 |
| axe-Tests in diesen 25 Dateien | 69 |
| davon mit eigenem `}, 15_000)` | 26 |
| **ohne eigenes Timeout** | **43** |

Gegenprobe in beide Richtungen (Regel 32): der nächste Commit `5f251c2f` ist grün
**ohne** eine der beiden Dateien anzufassen, und lokal laufen beide grün — Suite
**289,64 s** gegen **764,55 s** im roten CI-Lauf. Älteste Nicht-Glob-Datei:
**2026-06-05** — die Entscheidung (Review PR #814) war beim Schreiben schon
unterlaufen.

**Als #975 geschnitten**, `needs-decision`, mit drei Optionen (globale Grenze /
Tests verschieben / Konvention zu Ende führen plus Wächter) und Empfehlung **C**.
Verallgemeinerung: **Pflege-Regel 118** in #442.

### 2. Weiche 13 ist beantwortet — außerhalb des Repos

Der Owner hat am **2026-10-14 05:16 UTC** auf #951 das Dependabot-Kommando
*ignore this major version* gesetzt; #951/#952/#953 sind geschlossen, die drei
`docker-compose.cloud.yml` sind frei. **Gemessener Rest:** `.github/dependabot.yml`
trägt weiterhin **keinen** `valkey/valkey`-Eintrag in der Ignore-Liste (`:160-173`),
und `_VALKEY_PIN` (`apps/api/tests/test_dependabot_compose_coverage.py:174`) kodiert
Major **8** hart. Die Bot-Bestätigung deckt wörtlich nur Major 9 — **Valkey 10
erzeugt dieselben drei roten PRs.** → **Weiche 15**, Pflege-Regel **119**.

### 3. Zwei rote `main`-Läufe, zwei verschiedene Fälle

| Lauf | Commit | rot an | Klasse |
|---|---|---|---|
| 38498136667 | `91ec8371` | `e2e-mobile (mobile-iphone-13)` | bekanntes Rauschen (einer der sieben Jobs) |
| 38610320689 | `b450e17e` | `web` / „Test (coverage ratchet)" | **neu → #975** |

Ein Lauf, der nur „zwei rote Läufe" gezählt hätte, hätte #975 nicht gefunden →
**Pflege-Regel 121**.

### 4. Keine Abbrüche — und das ist kein Beleg

**0 von 14** `main`-Läufen `cancelled`, alle 14 mit Spruch. Die Bedingung der drei
bekannten Abbrüche (drei `main`-Pushes binnen rund zwei Minuten) lag nicht vor: die
Abstände betragen **35 bis 77 Minuten**. Nach Regel 115 ist der Nicht-Eintritt
deshalb kein Argument für oder gegen eine Option der Weiche 1. Laufzeiten des
Fensters: **11,7 bis 15,2 min** (frisches Maximum für Kriterium 3 von #849).

### 5. Ein Fehler gegen den eigenen Lauf → Pflege-Regel 120

Dieser Lauf hat `rm -rf node_modules && npm ci` als **erste** Handlung im Web-Stack
gefahren — die Reparatur aus #959 — und damit **nicht gemessen**, ob der
Hook-Zustand nach 13 `main`-Commits erneut eintritt. Die Bedingung lag vor, der
Lauf hat sie selbst beseitigt. #959 bleibt begründet, aber aus Lauf 50. Im Body von
#959 ausdrücklich so vermerkt.

### 6. Der Schreibweg verändert den Text → Pflege-Regel 122

#442 wurde mit 84 853 Zeichen gesendet und mit 84 873 zurückgelesen. Diff: genau
vier Zeilen. Gemessen: in jedes Vorkommen des Bot-Kommandos — **in Backticks** —
hat die Gegenstelle **fünfmal U+00B7 MIDDLE DOT** eingefügt. Der Zweck (keine
Erwähnung auslösen) ist nachvollziehbar, die Folge nicht: wer die Zeichenkette
herauskopiert, postet eine wirkungslose. Im Body steht deshalb jetzt eine
Beschreibung statt eines Literals. Die Regel ist beim Aufschreiben noch einmal
eingetreten (das Zitat wurde ebenfalls umgeschrieben).

### 7. Ein offener Posten geschlossen

Der `npm audit`-Fund des SessionStart-Hooks ist **`http-cache-semantics` ≤4.2.0,
high, dev-only**. `npm audit --omit=dev --audit-level=high` → **0 vulnerabilities**.
Der prod-only-`audit`-Job ist also zu Recht grün; die Hook-Meldung ist für ihn kein
Fund.

## Reihenfolge — eine Position getauscht

**#959 ist von Position 2 auf 1 gerückt, #632 von 1 auf 2.** Begründung aus
Kriterium 3 gegen einen weggefallenen Gleichstandsbrecher: Lauf 50 hatte #632 vorne,
weil seine Schreibfläche die einzige war, die **weder** ein PR hält **noch** `main`
bewegt — und `i18n/locales/{de,en}.json` ist in diesem Fenster **9×** von `main`
bewegt worden. #959 trägt die Verifikation von #632, #633 und #975.

1. **#959** — der SessionStart-Hook (Fundament vor Fläche)
2. **#632** — Passkey registrieren (öffnet #633)
3. **#949** — der irreführende pytest-Satz (keine Sperre)
4. **#849** — `timeout-minutes` (Adresse von #947 belegt)
5. **#923** — der `concurrency`-Kommentar (dieselbe Datei, gehört in Welle D)
6. **#633** — Step-up mit Passkey (nach #632 + Docker)

**#975 steht nicht in der Reihenfolge** (Regel 8, wartet auf Weiche 14); nach einer
Antwort gehört es zwischen Position 1 und 2 — und in denselben PR wie der
Coverage-Boden und der `__dirname`-Posten, weil alle drei `apps/web/vite.config.ts`
schreiben.

## PR-Bestand: 16 → 15, vier merge-fertig

Alle 15 mergen konfliktfrei (`git merge-tree --write-tree` → rc 0, einzeln), alle 15
merge-bases rechnen (nach `--unshallow`: 50 → **1560** Commits, Regel 90, vierzehnter
Lauf in Folge).

**Merge-fertig (gate-aktuell, `all-green` success, 0 `failure`, konfliktfrei):**
**#968** (E-MCP-2, der erste Sach-PR seit Läufen, 7 hinter `main`), **#947**
(`ci.yml`, zeilenneutral — räumt die Adresse von #849/#923/D/E frei), **#954**,
**#955**. **Eigen-rot ist nur noch #674** (Vitest 5, an **acht** Jobs rot).
Protokoll-Rückstand: **10** offene Draft-PRs, dieser legt den elften dazu.

## Messwerte

Sequenziell erhoben, ein Schreiber je Baum, Node **v22.22.0**, nach
`rm -rf node_modules && npm ci`:

| Kommando | Ergebnis | Vorlauf |
|---|---|---|
| `npm run lint` | Exit 0, **90** Probleme, 0 Fehler, 7 `--fix`-bar | 90 (4. Stillstand) |
| `npx tsc -b` | Exit 0, leer | Exit 0 |
| `npm run test:coverage` | Exit 0, **267 Dateien / 2517 Tests**, 289,64 s | 259 / 2236 |
| → Coverage | **89,47 / 83,67 / 86,13 / 91,20** | 88,92 / 82,94 / 85,42 / 90,65 |
| `npm run i18n:check` | Exit 0, **160** bekannte Waisen | 160 |
| `uv run ruff check .` | Exit 0, 0 Funde | 0 |
| `uv run mypy .` | Exit 0, 0 Funde in **608** Dateien | 605 |
| `uv run pytest --collect-only -q` | **3614** Tests, **135** unter `packages/billing/` | 3581 / 135 |
| `changelog_fragments.py` | **322** Fragmente | 310 |
| `npm audit --omit=dev --audit-level=high` | **0** vulnerabilities | nicht gemessen |
| `docker info` | Exit 1 (**27.** Lauf) | 26. Lauf |
| `ci.yml` | **1212** Zeilen, **12** Jobs, **0** mit `timeout-minutes` | gleich |

Engster Coverage-Abstand: Branches **4,67** Punkte über der Schwelle (war 3,94).

## Norm-Prüfung „Agent-ready Arbeitspaket"

Gegen alle offenen Issues einzeln gemessen (Abschnitts-Überschriften gelesen, nicht
nach Muster geraten — Regel 18/29):

- **Vollständig** (Akzeptanzkriterien, Scope/Out, Verifikation, Belege): #632, #633,
  #849, #923, #949, #959 — alle `agent-ready` — sowie das neue **#975**.
- **Teilweise** (Tracking, `size/M`): **#428** und **#535** tragen
  „Acceptance criteria (Tracking)" und „Out of scope", **aber keinen
  Verifikations-Abschnitt**; **#435** hat einen. Genau diese Lücke ist Weiche 4.
  Nach Pflege-Regel 7 ist der nächste Schritt ein Zuschnitt, kein Refinement.
- **`human-only`:** #454 und #542 tragen Kriterien und Verifikation ohne DoD; **#338**
  ist eine Owner-Checkliste ohne Arbeitspaket-Form — beides so beabsichtigt.

## Zeiger-Pflege

Nachgezogen, weil gemessen verrottet: `RUNBOOK.md` **2474 → 2502** (#962, in #540,
#535, #849), `toHaveNoViolations`-Leser **71 → 77**, Fragmente **310 → 322**, mypy
**605 → 608**, Collection **3581 → 3614**, OSV-Frist **20 → 18 Tage** (als Datum
geführt: `2026-11-02`, Regel 110), `docker info` **25./26. → 27. Lauf**.

Alle `path:NNN`-Zeiger der neun geprüften Bodies liegen innerhalb ihrer Dateien
(programmatisch gegen den Arbeitsbaum geprüft) — **verrottet sind weiter nur die
Zahlen ohne Dateibezug**, die kein Gate sieht (`check_code_refs.py` läuft in keinem
Workflow und liest keine Issue-Bodies).

## Geschrieben

- **#975** neu angelegt (`enhancement`, `web`, `size/S`, `needs-decision`).
- **#442** umsortiert und neu gefasst (86 888 Zeichen, byte-identisch zurückgelesen;
  Pflege-Regeln **118–122** ergänzt).
- **#632, #633, #849, #923, #949, #540, #959, #435, #428, #535** mit dem gemessenen
  Stand versehen; jeder Body nach dem Schreiben zurückgelesen und auf Inhalt geprüft
  (Regel 114b/117), jeder trägt genau eine Attributions-Fußzeile.

## Offen für den Owner

**Dreizehn Weichen**, davon zwei neu: **14** (#975, Empfehlung C) und **15** (der
Valkey-Rest, Empfehlung B). **Erledigt: 13** (Valkey, vom Owner beantwortet).
Billigster Einzelposten bleibt die MB/MiB-Zeile (`docs/licensing/plans.md:28-29`,
ein Ja/Nein). Dringlichster Termin: die OSV-Ausnahme läuft am **2026-11-02** ab.

Vier Klicks räumen am meisten frei: **#968**, **#947**, **#954**, **#955**.
