# Backlog-Aufbereitungslauf 60

**Datum:** 2026-10-24
**Messpunkt:** `main` @ `12093b46` (`fix(mcp): fetch_resource schneidet Überschriften-Anker …`, #1071)
**Fenster seit dem letzten Messpunkt (`98adac59`):** **15 Commits**
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt,
selbst entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit
drei Optionen und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit,
Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und
in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — elfter Lauf in Folge.**
Der Server steht in der Sitzung als „requires authentication"; keines seiner Werkzeuge ist
aufrufbar. Persona und Playbook-Katalog lagen im System-Prompt vor; `get_persona`,
`list_triggers`, `fetch_playbook`, `fetch_resource` (darunter die Norm „Agent-ready
Arbeitspaket", `73a86231`), `record_usage`, `submit_feedback` und `search_memory` **nicht**.
Der Lauf fährt deshalb nach dem reduzierten Kern des Bootstrap-Skills, nach dem Body von #442
und nach `.github/PROJECT.md` §Constraints. **Elfter Lauf ohne Kurations-Rückmeldung an die
eigene AgentDB** — kein `record_usage`, kein `submit_feedback`, kein Gedächtnis-Vorschlag.

## Messgrundlage

Alle Werte am 2026-10-24 auf `main` @ `12093b46` erhoben, **ohne vorherige Reparatur**
(Regel 120), **Exit-Codes ohne Pipe** (Regel 94), Python- und Web-Baum **parallel, je ein
Schreiber**. Node **v22.22.0**. Klon **shallow** (50 Commits, Voreinstellung dieser Umgebung);
nach `git fetch --unshallow`: **1643** Commits (Regel 90).

| Gate | Ergebnis | Vorlauf (Lauf 59) |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, 0 Funde | — |
| `uv run mypy .` | **Exit 0**, **649** Dateien | 637 |
| `uv run pytest --collect-only -q` | **Exit 0**, **4882** Tests, **276** unter `packages/billing/` | 4619 / 135 |
| `uv run pytest packages/billing/tests -q` | **Exit 0**, **266 passed / 10 skipped**, 20,74 s | neu |
| `scripts/changelog_fragments.py check` | **Exit 0**, **380** Fragmente | 366 |
| `npm run lint` | **Exit 0**, **0 errors / 93 warnings**, 7 `--fix`-bar | 90 |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | — |
| `npm run i18n:check` | **Exit 0**, **156** Waisen | 156 |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, 0 vulnerabilities | — |
| `npm run test:coverage` | **Exit 0**, **280** Dateien / **2780** Tests, **333 s** | 280 / 2761 / 307 s |
| Coverage Web | **89,74 / 83,78 / 86,60 / 91,56** | 89,67 / 83,79 / 86,47 / 91,50 |
| 🔴 `pip-audit` wie in CI | **rc 1**, **5 Advisories in 2 Paketen** | nicht gemessen |
| 🔴 `npm audit` (inkl. `dev`) | **rc 1**, **2 Advisories**, beide `high` | nicht gemessen |
| `docker info` | **Exit 1** — keine Container-Laufzeit, kein `podman` (**36. Messung**) | Exit 1 |
| `main`-CI | Lauf **2284**, `status: completed` **und** 🔴 `conclusion: failure` getrennt gelesen (Regel 91) | Lauf 2233, success |

**Fundstellen, einzeln wörtlich gelesen:** `MfaSection.tsx` **297**; `LoginPage.tsx` **399**;
`SessionProvider.tsx` **267**; `e2e/helpers/auth.ts` **199**; `api/client.ts` **1.823**;
`api/types.ts` **2.407**; `vite.config.ts` **107** (Schwellen `:99-102`, 80/79/75/80);
Locale-Schlüssel `de.json`/`en.json` je **3.324**; `orphan-baseline.json` **156** (flache
Liste); `Caddyfile` **208**, `grep -cE "\brate\b"` → **0**; CI-Caddy-Pin `caddy:2.8-alpine`
(`ci.yml:373`/`:381`/`:382`/`:397`/`:398`), Betriebs-Pin `caddy:2.11.7-alpine`
(`deploy/hetzner/who2be/docker-compose.yml:480`); `plans.md:28` **100 MB**, `:29` **10 GB**,
Datei **271**; `dependabot.yml:115` nur ein Valkey-**Kommentar**, kein Ignore;
`osv-scanner.toml` **ein** `[[IgnoredVulns]]`-Block, `ignoreUntil = 2026-11-02T00:00:00Z`;
`package-lock.json:6295-6297` `http-cache-semantics` **4.2.0**, `:10275-10280` `undici`
**6.29.0** (`"dev": true`), `:7937` `node-gyp -> ^6.25.0`, `:6955` `jsdom -> ^8.12.1` (eigene
Kopie **8.12.2**, nicht betroffen); `docs/mcp-payload-budget.md` **573** Zeilen;
`gobd-verfahrensdokumentation.md` **6** `<PLATZHALTER`-Marken.

## Der zentrale Fund: `main` ist rot an zwei Ursachen, und eine war unsichtbar

### 1. Was das Gate meldet

CI-Lauf **2284** auf `12093b46`: 12 von 14 Jobs grün, 🔴 **`audit`** und 🔴 **`all-green`** rot.
`audit` stirbt an Schritt **5 `pip-audit (Python)`**; **die Schritte 6–10 — `npm audit`,
License-Gate, OSV-Scan — sind alle `skipped`.**

Lokal mit dem Kommando aus `ci.yml:973-975` reproduziert, **rc 1**:

| Paket | Version | ID | Fix |
|---|---|---|---|
| fastmcp | 4.1.1 | GHSA-7xgj-8392-5q4r | 3.4.10, 4.1.2 |
| fastmcp | 4.1.1 | GHSA-vqqp-x5qm-5qp4 | 4.1.2 |
| pypdf | 6.21.1 | CVE-2026-115572 | 6.21.2 |
| pypdf | 6.21.1 | CVE-2026-115585 | 6.21.2 |
| pypdf | 6.21.1 | CVE-2026-115580 | 6.21.2 |

⚠️ **`pypdf` liegt auf einem erreichbaren Produktivpfad**, nicht nur im Gate: `extract_pdf_text`
in `apps/api/src/who2be_api/services/wa_ingest.py` parst hochgeladene oder per URL
referenzierte PDFs, und pypdf liegt im API-Produktionsimage.

**Der Fix liegt fertig vor: PR #1074**, zwei Dateien (`uv.lock` + ein Fragment), 0 hinter
`main`, manuell gebaut mit `uv lock --upgrade-package`.

### 2. Was das Gate nicht meldet

**#1074 kommt bis zum OSV-Schritt durch und stirbt dort** (Job-Log `120703702526`):

```
Scanned apps/web/package-lock.json file and found 700 packages
OSV: 2 Eintraege (rc=1)
  undici@6.29.0  GHSA-4qv8-2p9j-2685, GHSA-xjj6-f33q-929c
```

Gegenprobe lokal, `npm audit --json` in `apps/web/`, **rc 1**,
`metadata.vulnerabilities = {high: 2, total: 2}`:

| Paket | Spanne | Schwere | Fix | `fixAvailable` |
|---|---|---|---|---|
| `undici` | `>=6.5.0 <6.29.1` (EventSource-Parser, unbounded memory) | moderate | **6.29.1** | true |
| `undici` | `>=6.23.0 <6.29.1` (unhandled error on excessive content-encodings) | **high** | **6.29.1** | true |
| `http-cache-semantics` | `<=4.2.0` | **high** | **4.3.0** | true |

🟢 **Beide Web-Funde sind dev-only** (`"dev": true`; Fordernde: `node-gyp -> ^6.25.0` für
undici, der License-Gate-Pfad für http-cache-semantics). Deshalb ist
`npm audit --omit=dev --audit-level=high` — das Gate daneben — **grün mit 0 Funden**. Rot ist
allein der OSV-Scan, der das ganze Lockfile liest. **Das ist kein Ignore-Fall:** 6.29.1 liegt
innerhalb der Spanne `^6.25.0`, die `node-gyp` selbst fordert.

### 3. Warum das die Reihenfolge umstellt

**`main` wird durch den Merge von #1074 allein nicht grün.** Es braucht zwei Bumps in zwei
Dateien, und **keiner der 18 offenen PRs** fasst `undici` an — die Diffs von #1017 (5 Pakete)
und #674 einzeln gelesen, keines davon ist `undici`.

Beide Web-Bumps liegen in **derselben Datei**. Zwei PRs darauf kollidieren. → Paket **#1076**,
plus eine Weichen-Frage im Kommentar unter #989, wie sich die beiden zueinander verhalten
(Empfehlung: **ein PR**).

## Die beiden neuen Regeln

- **140 — Ein Gate, das beim ersten Fund abbricht, verdeckt den zweiten.** Der `audit`-Job
  führt vier Prüfungen als **Schritte eines Jobs**. Auf `main` stirbt Schritt 5, die Schritte
  6–10 sind `skipped`, und der undici-Fund wurde **nie gemeldet**. Er ist nicht neu — er war
  unsichtbar. Belegt am Kontrast: derselbe Job meldet ihn in #1074, wo pip-audit durchkommt.
- **141 — Eine Warnung, die im Issue steht, erreicht den PR nicht, der sie braucht.** Lauf 59
  hat in #1001 wörtlich benannt, dass #1049 die Zahl **104.777** trägt und sie vor dem Merge
  neu messen muss, mit Rechnung und Gegenvorschlag. **#1049 ist am 2026-10-23 05:47 mit genau
  dieser Zahl gemergt.** Solange ein Träger sein Issue nicht nennt, ist Issue-Text kein Kanal
  zur Arbeit. Das ist die messbare Kehrseite von Weiche 23.

## Der zweite Fund: drei Katalog-Stände in einer Datei, und der richtige fehlt

`docs/mcp-payload-budget.md` (573 Zeilen) trägt heute:

| Zahl | wo | behauptet |
|---|---|---|
| **104.777** / 101 Werkzeuge | `:254`, `:262`, `:264`, `:317`, `:451` | Katalog-Stand + Referenzprofile |
| **108.262** / 103 | `:234`, `:236`, `:299` | Katalog-Stand |
| 🟢 **108.251** / **103** | **nirgends** | **der tatsächliche Stand** |

Selbst gemessen mit dem Kommando, das die Datei an `:247` dafür nennt
(`uv run python -m who2be_mcp.payload_report`, **Exit 0**): Default-Policy **38 / 31.131**,
Default+`suggest` **42 / 34.683**, Builder **103 / 108.251**, Rolle editor **99 / 104.699**,
Guard **103 / 108.251**, `instructions` **1.732**. **Keine der fünf Zeilen der Tabelle in der
Datei stimmt noch**, in keiner Spalte.

**Die 11 Bytes Differenz sind dreifach erklärt** (Regel 130 — eine Partition, deren
Korrekturterm selbst gemessen ist):

| Zeit (UTC) | Commit | Wirkung | Doku nachgezogen? |
|---|---|---|---|
| 2026-10-22 18:42 | `1568e32e` #1045 (P3) | 114.203 → 104.777 | ja, in #1049 |
| 2026-10-22 20:38 | #1050 (`readOnlyHint`) | 104.777 → 106.415 | ja, `:291` |
| 2026-10-23 05:47 | **`3a1ee878` #1049** | — | **schreibt 104.777 als Stand** |
| 2026-10-23 16:24 | `ded708b9` #1067 | 106.415 → **108.262** | ja, `:234`/`:295` |
| 2026-10-23 22:19 | **`12093b46`** #1071 | **108.262 → 108.251** | 🔴 **nein** |

`12093b46` nennt seine Wirkung im eigenen Commit-Body: „*fetch_resource-Beschreibung kuerzer
als vorher (594 -> 583 Bytes)*" — **−11**. `git show --stat` bestätigt: angefasst wurden
`docs/adr/0021-*.md` und `docs/reference/openapi.json`, **nicht** diese Datei.
`108.262 − 11 = 108.251`. **Folgefehler:** `:236` und `:299` sagen beide „bleiben **71.738**
Bytes"; `180.000 − 108.251 =` **71.749**.

## Der dritte Fund: ADR-0061 R2 liegt auf `main`, zwei Posten sind nicht mitgereist

**R2a `dc030c62` (#1059) und R2b `1749863f` (#1064)** setzen #1024 vollständig um — ohne das
Issue zu nennen. **Die fünf Akzeptanzkriterien einzeln nachgeprüft, alle fünf erfüllt:**

| AK | Beleg |
|---|---|
| 1 Idempotenz | `billing_0111_billing_invoice.sql:34` `UNIQUE`; `test_double_webhook_creates_one_invoice_row_and_one_post:1199`, dazu `:1447`, `:662` |
| 2 vier Fehlerfälle | `:471` Erfolg · `:526` 422 · `:538` Timeout-nach-POST · AK1 Doppel-Webhook; dazu sieben weitere Fehlerpfade |
| 3 Routine | `worker/routines.py:75` `INVOICE_RETRY`, Registry `:12` (`@every 5m`), Funktion `:176`, dynamischer Import `:163` |
| 4 fail closed | `test_without_tax_mode_no_invoice_is_posted:486`, `:505`, `:1078` |
| 5 Gates | Billing-Suite **Exit 0** (266/10), ruff **0**, mypy **0** in 649, Collection 4882/276 |

🔴 **Einschränkung, ehrlich benannt:** `uv run pytest --cov --cov-fail-under=85` über den
ganzen Baum habe ich **nicht** gefahren. Den vollen Lauf belegt die CI an den Träger-Commits
(Lauf **2271** und **2259**, je `conclusion: success`) — **ein Fremdbeleg, kein eigener.**

**Die Weichen hat der Code entschieden, nicht der Owner** (Regel 119, vierter Fall):
W61-1 → **A** (`invoices/<org>/<jahr>/<nr>.pdf`, Test `:455`) · W61-2 → **weder A noch B**,
sondern ein Schalter `WHO2BE_INVOICE_PRICE_BASIS` (Default `net`) · W61-3 → **A** mit
72-h-Frist (`:810`, `:837`) · W61-4 („Wird R2 geteilt?", Empfehlung B) → **B**, geteilt in
R2a/R2b. 🔴 **ADR-0061 §11 führt W61-1 bis W61-3 weiterhin als offen** → **Weiche 30 (neu).**

**Zwei Posten sind nicht mitgereist:**

1. **Die Verfahrensdokumentation.** `grep -rn 'invoice-retry' docs/` findet **nur** die ADR.
   `gobd-verfahrensdokumentation.md` sagt an vier Stellen das Gegenteil des Codes: `:28` und
   `:101` „stellt **keine** eigenen Rechnungen aus", `:104` die EN-16931-Verneinung mit
   weggefallener Prämisse, `:129` „USt-IdNr … **nicht** in der App abgebildet" (falsch seit
   R1). Dazu `:116`: „Bis zur Umsetzung in Paket R2 gilt der Ist-Stand oben" — **die Bedingung
   ist erfüllt, der Satz steht noch.** → **#1077** geschnitten.
2. **`e2e-billing-cloud` ist nicht erweitert.** `apps/web/e2e/billing.spec.ts` trägt zwei
   Tests, beide zum R1-Formular; letzter Commit `96fde607` (R1). ADR-0061 §10 `:369` listet die
   Erweiterung als R2-Inhalt. **Braucht ein Urteil** → **Weiche 29 (neu)**, drei Optionen,
   Empfehlung **B** (Integrationstest statt Browser-Journey, plus ADR-Nachtrag).

## Weiche 27: beantwortet durch Handeln

Lauf 59 fragte, ob die Umsetzung einer ADR vor der ADR auf `main` landen darf, Empfehlung
**A** (ADR zuerst). `git log` im Fenster: **`e40af787` docs(adr): ADR-0059 (#995)** steht
**vor** **`e6eb6554` feat(models): Werkzeug-Profile Q1 (#1051)**. **Das ist A, ohne dass die
Weiche beantwortet werden musste. Weiche 27 ist geschlossen.**

## PR-Bestand

**18 offene PRs** (waren 14). Scope je PR über `git merge-base` + `git diff --name-only` mit
ausdrücklicher Nicht-leer-Prüfung (Regel 90); Abstand über `git rev-list --count`.

- **13 Code-PRs**, davon 8 neu: #1075 (1 Datei), #1074 (2), #1073 (23), #1072 (16), #1070 (11),
  #1069 (10), #1068 (9), #1062 (10), #1061 (28), #1060 (25), #1054 (15), #1017 (2), #674 (2).
- **5 Protokoll-PRs**: #1056 (15 hinter `main`), #1025 (40), #1002 (56), #990 (81),
  🔴 #831 (**204**, gate-alt, rot an `audit` ohne eine Code-Zeile).
- 🔴 **Von 13 offenen Code-PRs trägt kein einziger ein Issue.**
- 🔴 **Von 15 gemergten Commits im Fenster nennt kein einziger ein Issue.** Zehn tragen
  `Kanban t_…` oder `Issue: n/a`, **vier tragen überhaupt keinen Hinweis** (`df80b5d1`,
  `00daec90`, `f08add3d`, `acee25e1`).

**Neue Kollisionen:**

- 🔴 **Locale-Stau:** `apps/web/src/i18n/locales/de.json` wird von **sieben** offenen PRs
  angefasst (#1072, #1070, #1069, #1068, #1062, #1061, #1060). Lauf 59 nannte **einen**.
  ⚠️ **#1061 fasst `de.json` an, `en.json` nicht** — wer danach schreibt, trifft zwei Dateien
  in verschiedenem Stand.
- ⚠️ **#1075 und #1073** streiten um `apps/api/tests/test_builder_content_sync.py`.

**Gefallene Sperren:** `.github/workflows/ci.yml` (#1052 gemergt → **entsperrt Weiche 7**) ·
`apps/web/src/api/client.ts` (#1022 gemergt → entsperrt #633) · `deploy/hetzner/Caddyfile`.

## Norm-Stand über alle offenen Issues

Die vier Pflichtfelder (belegter Befund · Scope „In" **und** „Out" · 2–5 prüfbare
Akzeptanzkriterien · ausführbare Verifikations-Kommandos) stehen **vollständig in jedem
`agent-ready`-Issue** — #989, #1001, #632, #633 und den beiden neuen #1076, #1077.

Die sieben übrigen (#428, #435, #535, #540, #542, #454, #338) wurden in diesem Lauf
**unabhängig nachgemessen**, Body für Body, Kriterien gezählt:

| Lücke | betrifft |
|---|---|
| Scope-„In" fehlt | #542, #540, #535, #454, #428, #338 |
| Verifikations-Kommandos fehlen | #535, #428, #338 |
| ⚠️ **neu präzisiert:** Abschnitt „Verifikation" vorhanden, aber **ohne ein einziges Shell-Kommando** | #454 |
| Akzeptanzkriterien fehlen ganz | #338 (vier Owner-Punkte O1–O4, **keine Abschnitts-Überschriften**) |
| Kriterienzahl über der Norm 2–5 | #540 (7), #435 (6) |
| Kriterienzahl in der Norm | #542, #454, #428 (je 5), #535 (3) |
| ⚠️ **neu:** keine Fußzeile (Body endet mit „Component") | #542, #454 |

🔴 **In keinem der sieben trägt JEDES Kriterium eine Schwelle oder ein Kommando.** Ob der
Vertrag für Tracking-Issues gilt, ist **Weiche 4** — deshalb sind #435, #428, #535, #540 und
#542 bewusst **nicht** umgebaut (Regel 7).

## Was dieser Lauf selbst erledigt hat

**Zwei Pakete geschnitten:**

| Issue | Inhalt |
|---|---|
| 🆕 **#1076** | `undici` 6.29.0 → 6.29.1 — die zweite Ursache des roten `main`, `agent-ready`, `size/S`, 5 Kriterien je mit Schwelle oder Kommando |
| 🆕 **#1077** | GoBD-Verfahrensdokumentation nach R2 neu fassen, `agent-ready`, `size/S` — **ohne jede steuerliche Bewertung**, die bleibt bei #542 |

**Ein Issue mit Beleg geschlossen:** **#1024** (ADR-0061 R2), 5 von 5 Kriterien einzeln
nachgeprüft, `needs-decision` abgenommen (nichts wartet mehr auf eine Antwort — das heißt
nicht, dass die Weichen beantwortet **wurden**).

**Ein Body neu geschrieben:** **#1001** — Titel und Befund auf den tatsächlichen Rest
umgestellt (AK1 erledigt, AK2 offen), die drei Katalog-Stände einzeln mit Zeile belegt, die
11 Bytes hergeleitet, die überholte Zielzahl **101** gegen **103** ersetzt, fünf
Akzeptanzkriterien je mit Schwelle oder Kommando.

**Vier Kommentare** für das, was Urteil braucht oder einen Rewrite nicht wert ist:

- **#989** — der undici-Nachbar in derselben Datei, drei Optionen für das Verhältnis der
  beiden Pakete (ein PR / strikt hintereinander / in #1074 mitfahren), Empfehlung **A** mit
  messbarer Umschalt-Bedingung auf **B**.
- **#1024** — die Schließung mit Beleg, die vier de-facto entschiedenen Weichen, die zwei
  nicht mitgereisten Posten und **Weiche 29** vollständig mit drei Optionen.
- **#632** — der Locale-Stau von einem auf sieben Träger, alle Zeiger neu, Gates.
- **#633** — `client.ts` frei, dritter Blocker (grünes `all-green`) neu benannt, `auth.ts:33`
  als unbelastbar markiert.

**#442** komplett neu geschrieben: rotes `main` als Kopf, Reihenfolge, Wellen, Kollisionen,
20 Weichen (zwei neu, eine geschlossen), Pflege-Regeln 1–6 (Regel 6 neu), Funde ohne Issue.

## Reihenfolge — umgestellt, und zwar von oben

Lauf 59 hatte #989 auf Position 1 wegen seiner Frist. **Diese Position hält — aber nicht mehr
wegen der Frist, sondern weil in derselben Datei die Ursache eines roten `main` liegt.**

| Pos | Issue | Kriterium | Zustand |
|---|---|---|---|
| 1 | **#1076 + #989** (ein PR) | 1 (harte Abhängigkeit) | 🔴 solange offen, ist `all-green` an **jedem** PR rot |
| 2 | **#1001** Payload-Budget-Rest | 3 (Fundament vor Fläche) | startbar, Datei PR-frei, **echt parallel zu 1** |
| 3 | **#1077** GoBD-Doku | 4 (Inventar vor Zuschnitt) | startbar, Datei 0× bewegt |
| 4 | **#632** Passkey registrieren | 3 | startbar, Locale-Stau als Reihenfolge-Frage |
| 5 | **#633** Step-up mit Passkey | 1 | hinter #632, Container-Laufzeit **und** grünem CI |

**Nicht in der Reihenfolge:** die drei Tracking-Issues (#428, #435, #535), die drei
`human-only`-Issues (#338, #454, #542), #540 (Weiche 17 — **alle Datei-Sperren sind gefallen**,
es blockiert allein die Entscheidung), die 18 offenen PRs (Regel 65: kein Issue).

## Wellen

| Welle | Inhalt | Bedingung |
|---|---|---|
| **A** | **#1076 + #989** ‖ **#1001** | Web ‖ Python, datei-disjunkt — **das echte Parallel-Paar** |
| **B** | **#1077** ‖ **#632** | Python-Gegenprobe ‖ Web; Locales mit sieben PRs geteilt |
| **C** | Merge von **#1074** | kein Paket, ein Klick — wird durch #1076 grün |
| **D** | **#633** | nach #632 **und** C; braucht Laufzeit oder grünes CI |

🟢 **A ist datei- und baum-disjunkt.** **#1001 und #1077 nicht** (beide Python-Gegenproben),
**#1076/#989 und #632 nicht** (derselbe Vitest-Baum).

## Offen an den Owner

**Zwanzig Weichen**, zwei neu, eine geschlossen. Vollständig mit Optionen und Empfehlungen in
#442; die vier, die diesen Lauf unmittelbar betreffen:

1. **Nichts davon** — Position 1 braucht **keine** Antwort. **#1076 ist ohne Weiche startbar**,
   und er ist der Weg zu grünem `main`. Das ist der Unterschied zu den letzten Läufen.
2. **Weiche 30 (neu)** — wer die Antwort einer Weiche in die ADR nachträgt, wenn der Code sie
   entschieden hat. Empfehlung **A** (datierter Nachtrag-Abschnitt, je Weiche eine Zeile mit
   Commit). Dritter Fall dieser Familie nach 26 und 27.
3. **Weiche 29 (neu)** — ob der Rechnungspfad noch den E2E-Test braucht, den ADR-0061 §10
   listet. Empfehlung **B**, **C** nur mit ADR-Nachtrag. Blockiert nichts.
4. **Weiche 5** — hat ihren Ernstfall bekommen, und zwar den umgekehrten: nicht ein
   Protokoll-PR scheitert an `audit`, sondern `main`. **Hier war das Gate genau richtig.**
   Dieselbe Messung zeigt aber seine Schwäche (Regel 140): es meldet nur den ersten Fund.
   **Das sind zwei Fragen, nicht eine.**

## Belege dieses Laufs

- Queue-Issue: #442 (Body neu geschrieben, Herkunftszeile gesetzt)
- Neu geschnitten: **#1076**, **#1077**
- Geschlossen mit Beleg: **#1024** (5/5)
- Body neu geschrieben: **#1001** (Titel und Rest-Scope)
- Kommentiert: **#989**, **#1024**, **#632**, **#633**
- Nicht angefasst, mit Begründung: #435, #428, #535, #540, #542 (Regel 7, Weiche 4), #454,
  #338 (`human-only`), #989-Body (die vier Pflichtfelder stehen, der Befund ist unverändert)

⚠️ **Nicht gemessen in diesem Lauf, ausdrücklich:** der vollständige
`uv run pytest --cov --cov-fail-under=85` (ersetzt durch Collection + Billing-Suite + die CI an
den Träger-Commits); die Überlebensrate der Attributions-Fußzeilen nach dem Schreiben
(Weiche 19 — die Enden wurden **nicht** gegengelesen); die Ursache der widersprüchlichen
`unused ignores`-Meldung des OSV-Scanners.
