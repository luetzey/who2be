# Backlog-Aufbereitungslauf 50 (2026-10-14)

Auftrag: jedes offene Issue gegen die Norm **Agent-ready Arbeitspaket** prüfen,
Belegbares selbst entscheiden und mit Beleg ins Issue schreiben, Urteilsfragen
als Kommentar mit drei Optionen + Empfehlung zurückgeben, danach die
Warteschlange (#442) neu ordnen und in Wellen gruppieren.

**Basis:** `main` @ `6ef78994`, **1547** Commits, **6** Commits seit der
Lauf-49-Basis `79a8e171` (#942, #943, #944, #956, #957, #958).

🔴 **Der MCP-Server der eigenen AgentDB war zum fünften Lauf in Folge nicht
erreichbar** — `Who2Be---Coder` liefert über `ToolSearch` keine Werkzeuge.
Persona und Playbook-Katalog lagen im System-Prompt vor; `fetch_playbook`,
`fetch_resource` (die Norm selbst, `73a86231`), `record_usage` und
`search_memory` nicht. Der Lauf ist deshalb nach dem Body von #442 gefahren,
wie dort unter §Kollisionen vorgesehen. **Kein Playbook-Treffer ladbar, also
auch keine Rückmeldung über `record_usage`.**

## 1. Der Ertrag in drei Sätzen

1. **Die älteste offene Weiche des Bestands ist am Repo entschieden.** Weiche 1
   („was bricht `main`-Läufe ab, die noch keinen Job erzeugt haben?") steht seit
   Lauf 44. Dieser Lauf hat den **dritten** Fall gemessen und in allen drei
   dasselbe Muster gefunden — damit ist die Ursache belegt und die Weiche auf
   die Gegenmaßnahme neu gestellt.
2. **Ein Wächter, der einen Tag alt ist, macht drei Dependabot-PRs garantiert
   rot.** #944 hat Valkey 8 eingeführt und den Major im Test hart kodiert, ohne
   den Bot gleichzeitig zu begrenzen. → Weiche 13, Regel 116.
3. **Eine Gegenmaßnahme, die Lauf 49 als bestätigt verbucht hat, war nie
   belegt.** Regel 109 ist wieder eingetreten; die Reparatur ist jetzt in beide
   Richtungen gemessen und als #959 geschnitten. → Regel 115.

## 2. Methode

Sequenziell gemessen, ein Schreiber je Baum (Web und Python sind verschiedene
Stacks und liefen nebeneinander, Regel 31/76). Klon vorher `--unshallow`
(50 → **1547** Commits, Regel 90 — **dreizehnter Lauf in Folge** shallow).
Datei-Scope je PR über `git merge-base` mit ausdrücklicher Nicht-leer-Prüfung,
Konfliktfreiheit über `git merge-tree --write-tree`, CI-Zustand über
`get_check_runs` am Head mit namentlich herausgesuchtem `all-green`.

**Keine Sub-Agents.** Der Lauf besteht aus Messungen, die einzeln billig und in
der Reihenfolge voneinander abhängig sind (erst `main`-Basis, dann PR-Scope,
dann Zeiger); eine Aufteilung hätte Koordinationskosten ohne Zeitgewinn
erzeugt. Modell-Right-Sizing war damit kein Thema.

## 3. Selbst erledigt (Beleg → ins Issue geschrieben)

### 3.1 Weiche 1 — die Ursache der `main`-Abbrüche ist gemessen (→ #923)

Dritter Fall: Lauf `38464644002` zu `b14c213d` (#943), `conclusion: cancelled`,
**32 s**, `list_workflow_jobs` → **`total_count: 0`**.

**Das Muster, das erst mit drei Fällen sichtbar wird** — gemessen über die
Commit-Zeitstempel auf `main`, nach UTC umgerechnet:

| Fall | Commit | Push | Vorgänger | Nachfolger | Lauf lebte | Abstand zum Nachfolger |
|---|---|---|---|---|---|---|
| #863 | `e41d5d9a` | 18:16:11 | 18:14:24 | 18:18:07 | **117 s** | **116 s** |
| #933 | `de2ebcf6` | 19:18:00 | 19:17:45 | 19:19:15 | **76 s** | **75 s** |
| #943 | `b14c213d` | 20:40:03 | 20:39:33 | 20:40:33 | **32 s** | **30 s** |

**Drei von drei:** der abgebrochene Lauf ist der **mittlere** von drei
`main`-Pushes binnen rund zwei Minuten, und seine Lebensdauer deckt sich auf
eine bis zwei Sekunden mit dem Abstand zu seinem Nachfolger. Der Lauf lebt also
genau so lange, bis der nächste Push kommt.

Alle `main`-Pushes teilen die Gruppe `ci-CI-refs/heads/main` (`ci.yml:13` —
`github.event.pull_request.number` ist auf einem Push leer);
`cancel-in-progress` wertet auf `main` zu **`false`** aus (`:14`, über
`yaml.safe_load` gelesen).

⚠️ **Grenze der Messung (Regel 108):** GitHubs Scheduler-Schalter selbst ist
nicht gemessen. Die Deutung, die auf alle drei Fälle passt — pro Gruppe wird nur
**ein** Lauf vorgehalten, der dritte verdrängt den wartenden — ist die Erklärung,
die die Zahlen tragen, kein bestätigtes Feld. Das steht so im Body von #923.

**Folge für #923:** der Kommentar auf `ci.yml:11` gibt die gemeinsame Gruppe als
**Schutz** von `main` aus. Gemessen ist, dass genau diese Gruppe der Grund für
die Abbrüche ist. Das Paket korrigiert damit keine Ungenauigkeit, sondern eine
Umkehrung — Kriterium 2 im Issue ist entsprechend geschärft und erlaubt
ausdrücklich, die gemessene Ursache zu nennen.

**Folge für #849:** von den fehlenden CI-Sprüchen, die Lauf 44 dem hängenden
`e2e`-Job zugeschrieben hat, sind **drei** nachweislich Concurrency-Abbrüche.
Das Paket bleibt vollständig richtig (ein Job ohne Grenze läuft 360 Minuten),
aber es ist nicht mehr die Erklärung für die verlorenen Sprüche — Regel 104,
im Body nachgezogen.

### 3.2 Weiche 3 — durch Tatsache erledigt

#944 ist gemergt (`c2614851`), **#682, #683, #686 sind geschlossen**. Auf `main`
stehen die drei Zeilen auf `valkey/valkey:8-alpine@sha256:…`. Die Weiche fällt
aus dem Bestand; ihre Nachfolgerin ist Weiche 13.

### 3.3 #959 geschnitten — die Regel-109-Reparatur (Pflege-Regel 34)

In beide Richtungen gemessen (Regel 32): nach dem SessionStart-Hook meldet
`npm run test:coverage` **Exit 1** (`Cannot find native binding`,
`Cannot find module '@rolldown/binding-wasm32-wasi'`, **0 Tests**), während
`npm run lint` (Exit 0, 90 problems) und `npx tsc -b` (Exit 0, leer) grün sind.
Nach `rm -rf node_modules && npm ci` im selben Baum: **Exit 0**, **259 Dateien
/ 2236 Tests**.

Der Hook fährt `npm ci || npm install || true` (`scripts/install_pkgs.sh:44`) in
ein vorhandenes `node_modules`. **Welcher Mechanismus genau greift, ist nicht
gemessen** — gemessen ist nur, dass das explizite Löschen den Unterschied macht.
Das steht so im Issue.

### 3.4 Sechs verrottete Zahlen und ein falscher Pfad korrigiert

| Wert | Alt | Neu | Ursache |
|---|---|---|---|
| `core/config.py` | 256 Zeilen | **271** | #942/#943 — **Zeilennummern `:83`/`:159` halten** |
| `deploy/hetzner/RUNBOOK.md` | 2467 | **2474** | #956 |
| `who2be/docker-compose.yml` | 560 | **573** | #956 |
| Caddy-Pin darin | `:439` | **`:452`** | Folge der Zeilenverschiebung |
| `changelog.d/` | 304 Fragmente | **310** | 6 Commits |
| `mypy` | 602 Dateien | **605** | #957/#958 |
| `pytest --collect-only` | 3526 Tests | **3581** | #942/#957/#958 |
| OSV-Restlaufzeit | 20 Tage | **19** | Kalender (Regel 110 — als Datum geführt) |
| `SessionProvider.tsx` | `src/components/` | **`src/auth/`** | war implizit falsch; **267** Zeilen halten |

### 3.5 Der Body von #442 gekürzt

Von **103 527** auf **78 598** Zeichen (76 %), begründet aus Regel 114: eine
Nutzlast, die ein Modell erzeugen muss, bricht umso wahrscheinlicher ab, je
länger sie ist — und Pflege-Regel 10 verlangt ohnehin Zusammenfassung statt
Fortschreibung. Der Regel-Abschnitt ist **verbatim aus dem Altbody gespliced**,
nicht neu getippt (Regel 112). Gegenprobe: Regel 1, Regel 114 und die
Board-Sektion sind nach dem Splice vorhanden; `issue_write`-Eigenschaft „keine
angehängte Fußzeile" hält (Ende des Bodys zurückgelesen).

## 4. Braucht eine Owner-Antwort

### 4.1 Weiche 13 (NEU) — Valkey-Major gegen den eigenen Wächter

`_VALKEY_PIN` (`apps/api/tests/test_dependabot_compose_coverage.py:174`) kodiert
Major **8** hart. Gegenprobe gefahren: die Regex trifft `main`s `8-alpine`,
trifft `9-alpine` **nicht**. #951s CI ist an `python` **und** `all-green` rot,
13 × `success` sonst. `valkey/valkey` fehlt in der Major-Ignore-Liste
(`.github/dependabot.yml:160-173`); die Compose-Gruppe bündelt nur minor/patch
(`:158-159`), Majors kommen also einzeln — einer je Datei (#951/#952/#953).

**A** Ignore-Eintrag + die drei PRs schließen · **B** Wächter auf „irgendein
Major, Alpine, Digest-Pin" lockern und mergen · **C** Mindestversion.
**Empfehlung B:** die Sicherheitszusage trägt der **Digest**, und den prüft die
Regex in jeder Variante; Valkey läuft hier **ohne Persistenz**
(`valkey-server --save "" --appendonly no`), die Datenverlust-Begründung der
Ignore-Liste (`:161-165`) trägt also nicht. Kosten der Ziffer: drei rote PRs je
Bot-Tag. **Als Kommentar auf #951 gestellt** (gilt für #952/#953 gleichlautend),
Kurzfassung als Weiche 13 in #442.

### 4.2 Weiche 1 (NEU GESTELLT) — die Gegenmaßnahme

Ursache geschlossen (§3.1), Gegenmaßnahme offen. **A** nichts ändern, nur den
Kommentar richtigstellen (#923) · **B** Gruppe für `main` um `github.run_id`
erweitern — jeder `main`-Push behält seinen Lauf, Kosten: parallele Vollläufe in
Merge-Serien · **C** Merge-Queue, dann entstehen die Bursts nicht.
**Empfehlung B** — eine Zeile, stellt genau die Eigenschaft her, die der
Kommentar verspricht; **C** ist sauber, aber teuer und gehört in #338.

### 4.3 Unverändert offen

Weichen 2, 4, 5 (**Frist 2026-11-02 — 19 Tage**), 6, 7, 8, 9, 10, 11, 12 sowie
#540 und #542 — Stände einzeln nachgemessen und in #442 nachgezogen. **Weiche 11
ist entscheidungsreif:** #947 ist gate-aktuell, grün, 0 `failure`, konfliktfrei,
3 hinter `main` und **zeilenneutral** (15/15); sein Merge räumt die Adresse von
#849, #923, Welle D und Welle E frei, ohne einen Zeiger zu verschieben.

**Kein Issue hat in diesem Lauf neu `needs-decision` bekommen.** Die beiden
neuen Urteilsfragen hängen an PRs bzw. am Verfahren, nicht an einem
Arbeitspaket; #442 trägt das Label bereits.

## 5. Neue Reihenfolge

Kriterien unverändert: **1** harte Abhängigkeit · **2** Owner-Vorgabe ·
**3** Fundament vor Fläche · **4** Inventar vor Zuschnitt · **5** bei
Gleichstand das kleinere.

1. **#632** Passkey registrieren _(Kriterium 3)_ — Position gehalten. Öffnet
   #633 (harte Abhängigkeit); einzige Fläche, die weder ein PR hält noch `main`
   bewegt hat.
2. **#959** der Hook _(Kriterium 3, NEU)_ — bewusst vor die kleineren Pakete.
   Jedes Web-Paket darüber wird per `npm run test:coverage` verifiziert, und das
   ist ohne dieses Paket nicht verlässlich fahrbar. **Ausdrücklich nicht
   Kriterium 5** — nicht das kleinste, sondern das tragendste.
3. **#949** pytest-Satz im Skip-Gate _(Kriterium 5)_ — Adresse frei.
4. **#849** Timeouts _(Kriterium 5, gebremst)_ — **von 2 auf 4.** Kriterium 5
   stellt es mit #949 gleich; den Gleichstand bricht die gemessene Datei-Sperre
   (#947 hält `ci.yml`), und Regel 8 sagt, ein blockiertes Paket hält kein
   startbares auf. **Nach dem Merge von #947 rückt es wieder vor #949.**
5. **#923** Concurrency-Kommentar _(Kriterium 3, dann 5)_ — dieselbe Sperre;
   gehört in **einen** PR mit Welle D.
6. **#633** Step-up _(Kriterium 1)_ — nach #632, plus Container-Laufzeit
   (`docker info` → Exit 1, **26. Lauf**).

Dahinter, weichenabhängig: audit-Trennung + #923 (D), Caddy (E), Lint-`--fix`
(F), Coverage-Boden + `__dirname` (G), MB/MiB (J), Vitest-Augmentation (L).

## 6. Wellen

**Welle A** #632 (Web) · **Welle N** #959 (Hook, Vitest-Baum) · **Welle M**
#949 (Python) · **Welle C** #849 (`ci.yml`) · **Welle D** audit-Trennung +
#923 (`ci.yml`, ein PR) · **Welle B** #633 (nach A, braucht Docker) ·
**Welle E** Caddy · **F/G/K/L** Vitest-Baum · **Welle H** Merges ·
**Welle I** die drei Valkey-Majors (nach Weiche 13) · **Welle J** MB/MiB.

🟢 **Das echte Parallel-Paar ist A und M** — Web gegen Python, datei-disjunkt,
zwei Stacks. **Nicht parallel:** C/D/E (dieselbe `ci.yml`), F/G/K/L/N gegen
A/B (derselbe Vitest-Baum), B vor A (harte Abhängigkeit), I vor Weiche 13.

🆕 **Neue Wellen-Dimension (Regel 115):** ob die Installation des Stacks
überhaupt trägt. Jeder Web-Agent prüft vor seiner ersten Messung, dass
`npm run test:coverage` **startet**.

## 7. Messwerte

Node **v22.22.0**. `npm run lint` → Exit 0, **90** problems, 0 errors, 8 Regeln,
**7** `--fix`-bar · `npx tsc -b` → Exit 0, Ausgabe leer · `npm run test:coverage`
→ **zuerst Exit 1** (0 Tests), nach Reparatur **Exit 0**, **259 Dateien / 2236
Tests**, Coverage **88,92 / 82,94 / 85,42 / 90,65** gegen 80/79/75/80 ·
`npm run i18n:check` → Exit 0, **160** bekannte Waisen, keine neue ·
`uv run ruff check .` → Exit 0, 0 Funde · `uv run mypy .` → Exit 0, 0 Funde in
**605** Dateien · `uv run pytest --collect-only -q` → **3581** Tests, **135**
unter `packages/billing/` (`import who2be_billing` ok) ·
`changelog_fragments.py` → **310** Fragmente · `docker info` → **Exit 1** ·
`ci.yml` **1212** Zeilen, **12** Jobs, **0** mit `timeout-minutes`, `all-green`
hängt an **11**.

**`main`-CI:** HEAD `6ef78994` trägt Lauf `38488431963`, zum Messzeitpunkt
(00:16 UTC) `status: in_progress` — **13 Job-Instanzen erzeugt, 11 fertig, alle
`success`**, `web` und `python` liefen noch. Vorgänger `37d339ca`:
`conclusion: success`. **Kein roter `main`-Lauf, Regel 80 greift nicht.**

**PRs: 16 offen** (war 18), **alle 16 konfliktfrei** (`merge-tree` rc 0, einzeln
gemessen), **14 gate-aktuell**. Gemergt: #942, #943, #944. Geschlossen: #682,
#683, #686, #946, #948. Neu: #950–#955.

## 8. Neue Regeln

- **115** Ein Nicht-Eintritt belegt keine Gegenmaßnahme, wenn die auslösende
  Bedingung im Lauf fehlte — und eine Reparatur gilt erst, wenn sie in beide
  Richtungen gemessen ist.
- **116** Ein Wächter, der eine Major-Version hart kodiert, ist ein Termin mit
  dem Bot; wer ihn setzt, setzt dieselbe Grenze in der Bot-Konfiguration.
- **117** Ein abgelehnter Schreibvorgang kann aussehen wie ein geleertes Feld:
  ein `PATCH` ohne `Content-Type: application/json` wird mit einer Antwort ohne
  `body` abgelehnt. Nach jedem Schreibvorgang das Feld zurücklesen und auf
  **Inhalt** prüfen, nicht auf Länge. **In diesem Lauf einmal eingetreten**
  (an #923), ohne Schaden, weil zurückgelesen wurde.

## 9. Geschriebene Artefakte

| Ziel | Art | Inhalt |
|---|---|---|
| **#959** | neu angelegt | Hook-Reparatur, `agent-ready`, `size/S` |
| **#923** | Body | dritter Fall + Muster + Mechanismus, Kriterium 2 geschärft, Kopf auf Lauf 50 |
| **#849** | Body | Begründung präzisiert (drei Sprüche sind keine Hänger), 6 Zahlen nachgezogen |
| **#949** | Body | Basiswerte auf `6ef78994`, PR-Zahl, Adresse erneut als frei belegt |
| **#442** | Body | Reihenfolge, Wellen, Weiche 13, Weiche 1 neu gestellt, Weiche 3 gestrichen, Kollisionen/Sammelpunkte, Regeln 115–117; auf 76 % gekürzt |
| **#951** | Kommentar | Weiche 13 mit drei Optionen + Empfehlung (gilt für #952/#953) |

Jeder Schreibvorgang wurde zurückgelesen und auf erwarteten Inhalt geprüft
(Regel 117); Fußzeilen vorher gestrippt, danach je **genau eine** (Regel 111).
