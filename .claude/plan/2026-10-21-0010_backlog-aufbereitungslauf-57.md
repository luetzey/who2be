# Backlog-Aufbereitungslauf 57

**Datum:** 2026-10-21
**Messpunkt:** `main` @ `34056238` (`feat(web): BlockNote-Oberfläche in der UI-Sprache, Slash-Menü nach Gruppen (Editor P1)`, #997)
**Fenster seit dem letzten Messpunkt (`a6027b88`):** **25 Commits** — das größte Fenster seit Läufen.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt,
selbst entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit
drei Optionen und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit,
Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und
in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — zwölfter Lauf in Folge.**
`ToolSearch` liefert keine seiner Werkzeuge. Persona und Playbook-Katalog lagen im
System-Prompt vor; `get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource` (darunter
die Norm „Agent-ready Arbeitspaket", `73a86231`), `record_usage` und `search_memory` nicht.
Der Lauf fährt nach dem reduzierten Kern des Bootstrap-Skills, nach dem Body von #442 und nach
`.github/PROJECT.md`. **Zwölfter Lauf ohne Kurations-Rückmeldung an die eigene AgentDB.**

## Was im Fenster passiert ist

Der Owner hat am **2026-10-20 um 05:06–05:08 UTC** die Merge-Welle **genau in der von Lauf 56
empfohlenen Reihenfolge** gefahren — #987, #980, #988, #947, #984, #985, #986 — und danach
**dreizehn Protokoll-PRs**. Abends kam ein **neuer Arbeitsstrom**: #992, #994, #993 (ADR-0058
`Accepted`), #996 (P1), #997 (Editor P1).

| Bestand | Lauf 56 | **Lauf 57** |
|---|---|---|
| offene PRs | 24 | **5** |
| offene Issues | 16 | 11 vorgefunden → **15** nach diesem Lauf |
| Protokoll-Rückstand | 14 | **2** (#831, #990) |
| Datei-Sperren des Repos | 11 Flächen | **1** (`apps/web/package.json` + Lock → #674) |

**Geschlossen im Fenster:** #849, #923, #949, #959, #975 (alle 05:06). **Geschlossen ohne
Merge:** #823, #954, #955. → **Weichen 10, 11, 20 und 21 sind damit beantwortet**, 20/21 mit
Option A, genau wie empfohlen.

## Messgrundlage

Alle Werte am 2026-10-21 auf `main` @ `34056238` erhoben, sequenziell (ein Schreiber je Baum),
Node **v22.22.0**, npm **10.9.4**, **ohne vorherige Reparatur** (Regel 120), **Exit-Codes ohne
Pipe** (Regel 94). Der Klon war **shallow** (50 Commits, Voreinstellung dieser Umgebung); nach
`git fetch --unshallow`: **1587** Commits (Regel 90).

| Gate | Ergebnis |
|---|---|
| `npm run test:coverage` | **Exit 0**, **271** Dateien / **2562** Tests, **280,04 s** |
| Coverage | **89,51 / 83,70 / 86,16 / 91,24** — Statements 11479/12823, Branches **8050/9617**, Functions 3333/3868, Lines 10563/11577 |
| `npm run lint` | **Exit 0**, 90 problems, **0 errors**, 8 Regeln, 7 `--fix`-bar |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** |
| `npm run i18n:check` | **Exit 0**, **160** bekannte Waisen |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, 0 vulnerabilities |
| `uv run ruff check .` | **Exit 0**, 0 Funde |
| `uv run mypy .` | **Exit 0**, 0 Funde in **613** Dateien _(waren 608)_ |
| `uv run pytest --collect-only -q` | **4320** Tests _(waren 3648, **+672** durch P1)_, **135** unter `packages/billing/` |
| `changelog_fragments.py check` | **Exit 0**, **332** Fragmente (333 Dateien − `README.md`, `IGNORED_NAMES` auf `:84`) |
| `docker info` | **Exit 1** — keine Container-Laufzeit, kein `podman` |
| `main`-CI | **24** Check-Runs, `all-green` **namentlich**, `status`/`conclusion` getrennt (Regel 91), **0** rot |

**Coverage-Gegenprobe:** 271 Dateien / 2562 Tests sind **deckungsgleich mit #997s eigener
Messung** im PR-Body — zwei unabhängige Messwege, gleiches Ergebnis.

**Fundstellen, einzeln gelesen:** `ci.yml` **1237** Zeilen _(war 1212; #988 +16, #980 +9)_,
`ruff format --check` auf **`:128`** _(war `:122`)_, Caddy-Pins **`:359`/`:360`/`:375`/`:376`**
_(waren `:351`/`:352`/`:367`/`:368`)_, fail2ban-Filtertest auf **`:385`**; `Caddyfile` **203**
Zeilen _(war 195)_, `grep -cE "\brate\b"` → **0**, `max_size` **`:160`**; `RUNBOOK.md` **2700**
_(war 2502)_, fail2ban-Abschnitt **`:830`**, TOC **`:15`**;
`deploy/hetzner/who2be/docker-compose.yml` **581** _(war 573)_, Caddy-Pin **`:460`** _(war
`:452`)_, Service **`:454`**; `vite.config.ts` **94** _(war 89)_, Schwellen **`:86-90`** _(waren
`:82-85`)_, `__dirname` **`:34`** _(war `:29`)_; `LoginPage.tsx` **399** _(war 394)_;
`MfaSection.tsx` **297**, `e2e/helpers/auth.ts` **180**/`:33`, `SessionProvider.tsx` **267**,
`api/types.ts` **2402**, `client.ts` **1699**, `audit.test.ts` **371**, `package.json` **80**
(alle unverändert); `vitest-axe.d.ts` **699** Bytes, **82** Leser _(waren 77)_;
`orphan-baseline.json` **160** Einträge; `osv-scanner.toml:11` `ignoreUntil =
2026-11-02T00:00:00Z`; `package-lock.json:6283` → `http-cache-semantics` **4.2.0**;
`workspace_repository.py` **1173** Zeilen, `BUILDER_CONTENT_VERSION = 18` auf **`:509`**;
`server.py` **1590**, `client.py` **974**, `tool_requirements.py` **423**,
`test_tool_payload_budget.py` **1511**, `test_server.py` **514**; Registry **100** Einträge;
`blocknote_markdown.py` **1873** Zeilen; `main.py` **617**, **41** `include_router`;
`openapi.json` **30157** Zeilen / **852.323** Bytes; `CLAUDE.md:98` „**100 Tools gesamt**",
`README.md:70` „100 tools", `ROADMAP.md:24` „100 MCP tools in total";
`STATE.md` seit `e39d05eb` über **189** Commits 0× bewegt, Inhalt vom **2026-10-02**.

## Die vier Funde des Laufs

### 1. Eine beschlossene Zerlegung lag vollständig außerhalb der Warteschlange (Regel 134)

**ADR-0058** ist seit dem **2026-10-20** `Accepted` (Owner, Weichen W58-1…4 im Wortlaut „1D,
2B, 3A, 4 ja") und schneidet ihre Umsetzung in **§9 selbst** in Pakete — mit Dateilisten,
Domänen, einer Reihenfolge-Bedingung und einer Teilungsregel. **P1 ist gemergt (#996).**

🔴 **P2, P3 und P4 hatten kein Issue.** Gleichzeitig schloss Lauf 56 aus dem Bestand der
offenen Issues: „nach #632 ist der Vorrat an `agent-ready`-Arbeit praktisch leer" (Weiche 22).
**Beide Aussagen waren über ihre jeweilige Quelle richtig und zusammen falsch.**

Der Trägerweg erklärt es: **#996 und #997 tragen im Body wörtlich `Issue: n/a (Kanban card
t_e41ad85a / t_8b7b45d3)`.** ADR-0058 nennt als Grundlage „Kanban-Karte t_5aa518a0" und eine
Entscheidungsvorlage „**außerhalb des Repos**". Der Paketschnitt der Editor-Serie steht in
**keiner** Repo-Datei (`grep -rn "Editor P[1-9]" docs/ changelog.d/ .claude/` → **0**).

**Die Warteschlange war nicht falsch gepflegt — sie war nicht die Quelle.** → **Regel 134**,
und **Weiche 23** (neu) stellt die Frage, ob der Strom gespiegelt wird.

### 2. Die Teilungsregel der ADR greift, und niemand hatte nachgezählt

ADR §9 schreibt: „Zählt man DE und EN einzeln, sind es **mehr als acht** Dateien. Dann teilt
sich P4 in P4a (Inhalte DE+EN, Version) und P4b (Doku). **P4a muss vor oder mit P3 auf `main`
sein.**"

**Einzeln gezählt und jede Datei im Baum nachgeschlagen: 10.** Sechs Builder-Inhalte (DE+EN,
alle vorhanden), `workspace_repository.py`, zwei Doku-Dateien, ein Fragment. **Die Bedingung
greift** → P4 ist **zwei** Pakete, und die harte Reihenfolge P4a-vor-P3 ist Teil der
Entscheidung, nicht Präferenz.

🔴 **Dazu, vor dem PR erkannt: P3 braucht zwei Zeilen über seine acht hinaus.** Es hebt die
Registry **100 → 101**; der Wächter `test_doc_tool_count.py` vergleicht sie gegen `README.md:70`
und `ROADMAP.md:24` (heute beide „100", Test auf `main` **3 passed**). Ohne die beiden
Prosa-Zeilen wird er rot. **Regel 132 beim nächsten Paket schon wieder einschlägig** — diesmal
im Scope benannt statt im PR entdeckt.

### 3. Weiche 16 ist beantwortet — zweimal, und beide Belege lagen im Repo

| Quelle | Wortlaut |
|---|---|
| **ADR-0058 §9** (`Accepted`, Owner, 2026-10-20) | „Die Werkzeugzahl (100 → 101) zieht P4 nicht in `CLAUDE.md` nach. Sie steht künftig nur in `README.md` und `ROADMAP.md`; das regelt Kanban-Karte t_bf8ed54c." |
| **PR #977**, eigener Docstring | „`CLAUDE.md` nennt die Zahl bewusst nicht mehr (Owner-Entscheidung **2026-10-14**)." |

**Regel 119 erneut eingetreten** — die Antwort lebte außerhalb der Weiche, seit sieben Tagen.
#977 ist **korrekt rot**: sein neuer Test `test_claude_md_names_no_tool_count` verlangt, dass
`CLAUDE.md` keine Zahl nennt, der Diff ändert aber nur den Test. `CLAUDE.md:98` trägt weiter
„**100 Tools gesamt**", das Muster `\d+\s+Tools\s+gesamt` trifft genau sie.
**Es fehlt eine Zeile, und `CLAUDE.md` ist PR-frei.** Kommentar in #977 gesetzt.

### 4. Eine gemergte Umsetzung schließt ihr Issue nicht — und der Body verrottet weiter

**#980 ist am 2026-10-20 gemergt; #540 stand am 2026-10-21 offen**, und sein Kopfblock
beschrieb den PR als „merge-fertig", nannte ein RUNBOOK-Kapitel als „auf `main` fehlend", das
da ist, und **zwei Datei-Träger (#823, #943), die nicht offen sind**.

🟢 **Erstmals gegen `main` statt gegen einen PR gemessen (Regel 16), je Kriterium:**

| # | Kriterium | auf `main` | Beleg |
|---|---|---|---|
| 1 | Flut vor dem `api`-Container, Fehlen im API-Log | 🔴 **nicht belegt** | braucht Host mit `iptables` + fail2ban; `docker info` → Exit 1 |
| 2 | Verkehr nach der Sperrfrist | ⚪ Parameter gesetzt, Wirkung ungefahren | `bantime` 1h / 15m, `findtime` 10m / 2m |
| 3 | `mcp.` ausgenommen, Health erreichbar | 🟢 **belegt** | Filter `:26`/`:29`, `mdre-edge:68` (Negative-Lookahead); Test in `ci.yml:385`, `compose-smoke` **success** |
| 4 | Schwellen in `.env.example` oder Caddyfile | ⚠️ **Substanz ja, Buchstabe nein** | nur in `jail.d/who2be-caddy.conf`; `.env.example` → **0** Treffer |
| 5 | RUNBOOK-Entsperr-Abschnitt | 🟢 **jetzt erfüllt** | `RUNBOOK.md:830`, TOC `:15` |
| 6 | `test_headers.sh` unverändert | 🟢 erfüllt | im grünen `compose-smoke` |
| 7 | kein zweites Logging | 🟢 erfüllt | ein Writer, `Caddyfile:115-135` |

**4 von 7 belegt, 1 teilweise, 1 ungefahren, 1 umgebungsblockiert.** 🟢 `fail2ban` liegt jetzt
in **11** Repo-Dateien _(vorher: eine Plan-Datei)_ — das Argument gegen Option A ist erledigt.
🟢 Alle Datei-Sperren dieses Pakets sind weg. Kopfblock **repariert**, Kommentar mit drei
Optionen gesetzt (Empfehlung **A**, mit dem Wirkungsnachweis als eigenem Paket statt als
Abschlussbedingung).

⚠️ **Nebenbefund:** `deploy/hetzner/tests/test_fail2ban_filter.sh` lädt `fail2ban-regex` 1.1.0
aus dem Netz, wenn es nicht im PATH ist — in dieser Umgebung **`curl: (22) … 403`**
(Agent-Proxy). Der Test ist hier nicht fahrbar; sein Beleg kommt aus `compose-smoke`.

## Die Fußzeile: 12 von 13 — und der dreizehnte ist dieser Lauf selbst (Regel 135)

| Schreibweg | n | Fußzeile danach |
|---|---|---|
| `POST` Create (#998–#1001) | 4 | 🟢 **4× angehängt** |
| `PATCH` auf dieselben (Quervernetzung) | 4 | 🟢 **4× behalten** |
| `PATCH` an Bestandsbodies (#989, #632, #633, #540) | 4 | 🟢 **4× vorhanden** — #989/#632/#633 trugen vorher **keine** |
| `PATCH` an **#442** | 1 (3 Schreibvorgänge) | 🔴 **0×**, bei 69.685 Bytes |

**Keine der Nutzlasten erwähnte die Fußzeile.** Damit ist **Regel 129s Kernsatz widerlegt**
(„durch Sorgfalt nicht zu retten" — Sorgfalt war nie das Problem) und **Regel 38s Abwägung
aufgehoben: ein Body-Rewrite kostet die Fußzeile nicht.** Genau darauf beruht die Reparatur von
#540 in diesem Lauf.

🔴 **Die saubere Fassung ist im selben Lauf gestorben, der sie aufgestellt hat.** Erst stand
„nicht erwähnen, dann kommt sie" im #442-Body — der dreizehnte Schreibvorgang, dieser Body,
bekam keine. **Regel 133 ein zweites Mal, diesmal an der eigenen Regel.** Die
Längen-Hypothese scheidet aus: **Lauf 56 bekam an genau diesem Body bei ~65.000 Bytes eine
angehängt.** Richtiggestellt, statt die Behauptung stehen zu lassen.

**Was steht, ist die Richtung und nur sie:** ausdrücklich mitgeschrieben → **6 von 6** entfernt
(Lauf 55: 5, Lauf 56: 1); nicht erwähnt → **12 von 13** angehängt oder behalten.

## Norm-Stand über alle 15 offenen Issues

Die vier Pflichtfelder (belegter Befund · Scope „In" **und** „Out" · 2–5 prüfbare
Akzeptanzkriterien · ausführbare Verifikations-Kommandos) stehen **vollständig in jedem
`agent-ready`-Issue**, einschließlich der vier neuen.

| Lücke | betrifft |
|---|---|
| Scope-„In" fehlt | #542, #540, #535, #454, #428, #338 |
| Verifikations-Kommandos fehlen | #535, #428, #338 |
| Akzeptanzkriterien fehlen ganz | #338 (keine Abschnitts-Überschriften) |
| Kriterienzahl über der Norm 2–5 | #540 (7), #633/#435 (je 6) |
| Kriterienzahl in der Norm | #989/#632/#542/#454/#428/**#998**/**#999**/**#1000** (je 5), **#1001** (4), #535 (3) |

🔴 Ob der Vertrag für Tracking-Issues gilt, ist **Weiche 4** — deshalb sind #435, #428, #535,
#540 und #542 bewusst **nicht** umgebaut (Regel 7).

## Was dieser Lauf selbst erledigt hat

**Vier Issues geschnitten** — die fehlende Zerlegung aus ADR-0058 §9 (Regel 34):

| Issue | Paket | Dateien | Startbedingung |
|---|---|---|---|
| **#998** | P2 — Markdown-Schreibweg an der API | 8 (§9 P2) | 🟢 **startbar**, P1 liegt auf `main` |
| **#999** | P4a — Builder-Inhalte DE+EN, Version +1 | 8 | nach #998, **vor oder mit #1000** |
| **#1000** | P3 — MCP auf Markdown, `edit_content` | 8 + 2 Prosa-Zeilen | nach #998 **und** #999 |
| **#1001** | P4b — Payload-Budget und Referenz | 3 | nach #1000 |

Jedes mit belegtem Befund, Scope „In"/„Out", 4–5 prüfbaren Kriterien, ausführbaren Kommandos,
Vorentschieden-Block aus den ADR-Weichen und einer Paketketten-Tabelle, die alle vier
quervernetzt.

**Vier Bodies entrottet:**

| Issue | behoben |
|---|---|
| **#989** | Prämisse **nach dem Merge von #984 nachgemessen und bestätigt** (Lock weiter 4.2.0) · Sperre von zwei Trägern auf **einen** (#674) · Frist 13 → **12 Tage** · PR-Zahl 24 → **5** · `audit` auf `main` grün ergänzt |
| **#632** | Position 1 → **2** mit Begründung · 🔴 **`locales` im Fenster bewegt** (#992, #997) — vorher stand „0× bewegt" · Träger `package.json` #954+#674 → **nur #674** · Zeiger einzeln nachgemessen · #959-Vorsichtsmaßnahme als **erledigt** markiert |
| **#633** | 🔴 **`LoginPage.tsx` 394 → 399** (#992 hat den Login-Pfad angefasst, den das Paket erweitert) · `locales` bewegt · PR-Zahl · `main`-Zeiger · #959 erledigt |
| **#540** | **Kopfblock neu** mit der Messung gegen `main` je Kriterium · „merge-fertig" → **gemergt** · K5 „fehlt auf `main`" → **erfüllt** · 🔴 **#823 und #943 als Datei-Träger entfernt (beide nicht offen)** · alle Caddy-Zeiger gewandert und korrigiert |

**Zwei Kommentare** für das, was Urteil braucht:

- **#540** — Weiche 17, neu gemessen und enger: drei Optionen mit Trade-offs, Empfehlung **A**
  (schließen mit ausdrücklichem Verzicht auf K1/K2, K4 als Substanz-erfüllt), **plus** der
  Wirkungsnachweis als eigenes Issue statt als Abschlussbedingung. Mit dem Präzedenzfall vom
  2026-10-20 (Weichen 20/21) belegt.
- **#977** — Weiche 16 ist beantwortet, zweimal im Repo belegt; es fehlt eine Zeile in
  `CLAUDE.md:98`, die Datei ist PR-frei, danach wird der PR von allein grün. Dazu der Hinweis,
  dass #1000 die Registry auf 101 hebt und dann `README.md:70`/`ROADMAP.md:24` mit müssen.

**#442** komplett neu geschrieben: Reihenfolge, Wellen, Kollisionen, Weichen 1–23,
Pflege-Regeln 1–39 und 40–135, Funde ohne Issue. **70.635 → 69.685 Bytes.**

## Reihenfolge

| Pos | Issue | Baum | Kriterium | Zustand |
|---|---|---|---|---|
| **1** | 🆕 **#998** ADR-0058 P2 | Python | **2 (Owner-Vorgabe) + 3 (Fundament vor Fläche)** | 🟢 startbar, öffnet drei Pakete |
| **2** | **#632** Passkey registrieren | **Web** | 3, bei Gleichstand 5 | 🟢 startbar, **echt parallel zu 1** |
| **3** | 🆕 **#999** P4a | Python | **1 (harte Abhängigkeit)** | nach #998, vor oder mit #1000 |
| **4** | 🆕 **#1000** P3 | Python | **1** | nach #998 und #999 |
| **5** | 🆕 **#1001** P4b | Python | **1** | nach #1000 |
| **6** | **#989** `audit`-Sprung | Web | 1, Präferenz gegen die Frist | Sperre **#674**; **Frist 12 Tage** |
| **7** | **#633** Step-up | Web | **1** + Umgebung | nach #632 **und** Docker |

**Position 1 folgt aus Kriterium 2 und 3, nicht aus 5.** #998 ist das größere Paket; nach
Kriterium 5 allein stünde #632 vorne. Entscheidend ist, dass #998 **drei** Pakete öffnet (#632
öffnet eines) und einen Strom fortsetzt, den der Owner vorgestern per `Accepted`-ADR beschlossen
hat und sichtbar fährt, mit W58-3 = A „vor dem Cloud-Release" — und der Cloud-Launch ist das
Outcome in `.github/PROJECT.md`. **Der Tausch von 1 und 2 kostet nichts: sie laufen ohnehin
parallel.**

**Nicht in der Reihenfolge:** #540 (Weiche 17, Umsetzung liegt auf `main`), die drei
Tracking-Issues (#428, #435, #535), die drei `human-only` (#338, #454, #542), dieses Issue, die
fünf offenen PRs (Regel 65: kein Issue).

## Wellen

🟢 **Zum ersten Mal seit Läufen sind zwei Pakete gleichzeitig startbar.**

| Welle | Inhalt | Baum | Bedingung |
|---|---|---|---|
| **S** | `#998 → #999 → #1000 → #1001` | Python | **strikt seriell** — harte Abhängigkeiten **und** ein Verifikations-Baum |
| **A** | #632 | Web | 🟢 **parallel zu S** — das echte Parallel-Paar |
| **R** | #989 | Web | nach Merge **oder** Schließen von #674 |
| **B** | #633 | Web | nach #632, braucht Docker |
| **H** | die Merges | — | #995 · #977 nach der `CLAUDE.md`-Zeile · #674 reparieren oder schließen · #831 nach #989 + Branch-Update · #990 |
| **E** | Caddy-Widerspruch | Python/Shell | 🟢 **entsperrt** (`Caddyfile` **und** `ci.yml` PR-frei), braucht Weiche 7 |
| **G** | Coverage-Boden + `__dirname` | Web | 🟢 **entsperrt** (`vite.config.ts` PR-frei), **ein** PR |
| **L** | Typ-Augmentation Vitest 5 | Web | 🟢 **entsperrt** (`src/test/**` PR-frei), nach Weiche 12 C |
| **M** | `STATE.md` + `.github/PROJECT.md` | — | 🟢 **entsperrt durch das Schließen von #823** — Weiche 10 ist beantwortet |
| **P** | die Zeile in `CLAUDE.md:98` | Python | 🟢 **gehört in #977 selbst**, Weiche 16 ✅ beantwortet |
| **I, J, K, Q, F** | Valkey · MB/MiB · Versatz · Wirkungsnachweis · Lint-Fixes | — | s. #442 |

🔴 **Kollisionsregel:** S ist nach dem **Verifikations-Baum** geschnitten, nicht nach der
Schreibfläche — auch die datei-disjunkten Pakete der Kette laufen **nicht** gleichzeitig. Welle
E, I und P liegen ebenfalls im Python-Baum und kollidieren mit S. A, R, B, G und L teilen den
Vitest-Baum und kollidieren untereinander.

## Neue Regeln

- **134 — Eine beschlossene Zerlegung kann vollständig außerhalb der Warteschlange liegen.**
  Dann ist die Warteschlange nicht falsch gepflegt, sondern nicht gefragt worden. **Folge: der
  Lauf liest die ADRs mit Status `Accepted` gegen die Warteschlange, nicht nur die Issues und
  `git log`.**
- **135 — Die Attributions-Fußzeile geht nicht am Rewrite verloren, sondern am Erwähnen.**
  12 von 13, und die eine Ausnahme ist dieser Body. Regel 129s Kernsatz widerlegt, ihre
  Gegenmaßnahme bestätigt, **Regel 38s Abwägung aufgehoben.**

**Ergänzt:** Regel 10 (dritter Anlauf an der eigenen Länge — eine Zahl, die sich selbst
mitzählt, ist im eigenen Body nicht stabil zu halten), Regel 16 (am Übergang #540 von „gegen
PR" zu „gegen `main`"), Regel 24 (Welle Q bewusst **nicht** geschnitten: die `NET_ADMIN`-Frage
ist ungemessen), Regel 34 (vier Issues), Regel 98 (sechs Zeiger-Wanderungen im Fenster
belegt), Regel 119 (Weiche 16, Antwort außerhalb der Weiche), Regel 132 (vor dem PR erkannt
statt im PR), Regel 133 (zweites Mal, an der eigenen Regel).

## Offen an den Owner

**23 Weichen, 16 offen** — eine neu, vier in diesem Fenster beantwortet (10, 11, 20, 21), eine
durch Beleg erledigt (16), eine fast (19). Vollständig mit Optionen und Empfehlungen in #442;
die vier, die diesen Lauf unmittelbar betreffen:

1. **Weiche 23 (neu)** — wird der Kanban-Strom in die Warteschlange gespiegelt? Empfehlung
   **A** (jede beschlossene Zerlegung wird beim Beschluss als Issue geschnitten), **plus C** als
   Gate (`Issue: n/a` im PR-Template unzulässig). Ohne C wiederholt sich Regel 134 beim nächsten
   ADR — und **ADR-0059 liegt als #995 schon `Proposed` vor.**
2. **Weiche 16** — ✅ beantwortet, es fehlt **eine Zeile** in `CLAUDE.md:98`. Danach ist #977
   von allein grün. **Der billigste offene Posten des Backlogs.**
3. **Weiche 12 / 5** — **#674 ist jetzt der Flaschenhals:** die einzige verbliebene
   Datei-Sperre des Repos, und sie hält #989 auf, dessen Frist in **12 Tagen** abläuft.
   Reparieren **oder** schließen — beides macht Welle R frei.
4. **Weiche 17** — enger geworden, siehe Fund 4. Empfehlung **A** mit dem Präzedenzfall vom
   2026-10-20.

## Belege dieses Laufs

- Queue-Issue: **#442** (Body neu geschrieben, **69.685** Bytes, nach dem Schreiben gegengelesen)
- Geschnitten: **#998**, **#999**, **#1000**, **#1001**
- Entrottet: **#989**, **#632**, **#633**, **#540**
- Kommentiert: **#540** (Weiche 17, drei Optionen), **#977** (Weiche 16 beantwortet)
- Nicht angefasst, mit Begründung: #435, #428, #535, #542 (Regel 7, Weiche 4), #454, #338
  (`human-only`)
- Bewusst **nicht** geschnitten: Welle Q (ungemessene `NET_ADMIN`-Prämisse, Regel 24) und der
  Editor-Paketschnitt (steht in keiner Repo-Datei, Weiche 23)
