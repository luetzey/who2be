# Backlog-Aufbereitungslauf 89

**Datum:** 2026-11-22
**Messpunkt:** `main` @ `f89acf87` (Baum `c751ed64`, `deps(compose): bump caddy in /deploy/monitor`, #1097)
**Fenster seit dem letzten Messpunkt (Lauf 88):** 🔴 **0 Commits, zum vierzehnten Mal in Folge** —
`main` steht seit dem 2026-11-06T08:05:51+01:00 still, **16 Tage**.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf gepflegt.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt, selbst
entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit drei Optionen
und Empfehlung, das Issue bekommt `needs-decision`. Danach die Warteschlange neu ordnen (harte
Abhängigkeit → Owner-Vorgabe → Fundament vor Fläche → Inventar vor Zuschnitt → bei Gleichstand das
kleinere) und in Wellen gruppieren. Bericht in drei Blöcken.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — die Sitzung hält die Anmeldung, der
Server weist sie ab.** Der erneute Verbindungsversuch über eine `ToolSearch`-Abfrage mit dem
Servernamen wurde abgelehnt. Nicht verfügbar: `get_persona`, `list_triggers`, `fetch_playbook`,
`fetch_resource` (darunter die Norm selbst), `record_usage`, `submit_feedback`,
`search_memory`/`save_memory`.

Persona und Playbook-Katalog lagen im System-Prompt vor; der Lauf fährt deshalb nach dem Body von
#442 (§Pflege-Regeln) und nach `.github/PROJECT.md` §Constraints — dort stehen die vier
Pflichtabschnitte der Norm. **Kein Playbook-Trigger traf.** **Keine Kurations-Rückmeldung an die
eigene AgentDB, zum wiederholten Mal.**

🔴 **Nummerierungs-Fund beim Boot:** der Body von #442 trug „Stand 2026-11-20, Aufbereitungslauf
87", während **PR #1155 „Protokoll Backlog-Aufbereitungslauf 88"** bereits seit dem 2026-11-21
offen ist. Lauf 88 hat #442 kommentiert, aber den Body nicht geschrieben — die Stand-Zeile war
damit eine Nummer zu niedrig. **Dieser Lauf ist 89**, nicht 88.

## Messgrundlage

Alles am 2026-11-22 auf `main` @ `f89acf87` erhoben, **ohne vorherige Reparatur**, Exit-Codes am
**unverketteten** Befehl, sequenziell. Node **v22.23.5**, npm **10.9.9**, uv **0.11.32**,
CPython **3.11.18**. Klon war shallow (50) → **1676** Commits nach `--unshallow`.
`git status --porcelain` leer, `git rev-list --count f89acf87..origin/main` → **0**,
`origin/main^{tree}` = **`c751ed64`** — **bitgleich zu Lauf 87 und 88**.

| Gate | Ergebnis |
|---|---|
| 🔴 `uv tool run pip-audit --disable-pip --no-deps -r <reqs>` | 🔴 **Exit 1 — 7 CVEs in 4 Paketen** bei **125** Requirements / **124** Namen (`wc -l` = **398**) — selbst gefahren |
| 🔴 **`main`-CI am Kopf `f89acf87`** | 🔴 Lauf **`42178623925`**, `status: completed` **und** `conclusion: failure` getrennt gelesen — **unverändert rot, 16 Tage** |
| `docker info` | 🔴 **Exit 1** — keine Container-Laufzeit, kein `podman` (**65. Messung in Folge**) |
| `uv run python -m who2be_mcp.payload_report` | **Exit 0**, Builder **103 / 108.251**, `instructions` **1.834** B — 🟢 **23. identische Messung** |
| `uv run pytest apps/mcp/tests/test_tool_payload_budget.py -q` | **Exit 0**, **64 passed** |
| `uv run ruff check .` / `uv run mypy .` / `pytest --collect-only -q` | Exit 0 · Exit 0, **659** Dateien · **5034** Tests |
| `npm run lint` / `npx tsc -b` / `npm run i18n:check` | **94** problems, **0 errors**, 7 fixable · 0 Byte · **156** Waisen |
| `npm run test:coverage` | **282** Testdateien, **2849** Tests, grün |
| `npx playwright test --list --project=chromium` | **44** Tests in **9** Dateien |
| `ls changelog.d/*.md \| wc -l` | **406** (Skript-Eigenzahl **405**, Differenz ist `README.md`) |

🟢 **Baum-Gates an einem bitgleichen Baum sind die Erwartung, kein Befund.** 🔴 **Die
advisory-gefütterten Gates sind trotzdem selbst gefahren** — `pip-audit` ist unabhängig von Baum
und Vorlauf, weil seine Datenquelle wandert (Regel 79).

## PR-Bestand

🔴 **51 offene PRs** _(waren 50)_, zusammen **56** bewegte Dateipfade in **75** Vorkommen. Scope
je PR über `git merge-base` + `git diff --name-only`, Konfliktfreiheit über
`git merge-tree --write-tree`, Rückstand über `git rev-list --count` — **alle 51 selbst gerechnet.**

- 🟢 **Die Differenz 50 → 51 ist vollständig erklärt: +#1155** (Protokoll Lauf 88, der Vorlauf),
  genau eine Datei. **Keine Abgänge.**
- 🟢 **Alle 51 mergen konfliktfrei** (`rc 0`), **keiner bewegt 0 Dateien.**
- 🔴 **Seit dem 2026-11-06 ist kein PR gemergt — 16 Tage, vierzehntes leeres Fenster.**
- 🟢 **Wellen-Bilanz nach Regel 77:** 0 (3) + M (11) + N (**32**) + Q (1) + R (3) + S (1) =
  **51 von 51**, keine Dublette, keine Lücke.

### Mehrfach gehaltene Pfade (selbst gezählt)

| Pfad | Halter |
|---|---|
| 🔴 `apps/web/package.json` · `apps/web/package-lock.json` | **5** — #1147, #1130, #1129, #1124, #674 |
| 🔴 `uv.lock` | **4** — #1148, #1142, #1141, #1120 |
| 🔴 `.claude/context/STATE.md` | **3** — #1103, #1090, #1078 |
| ⚠️ Domain-Doku (4 Pfade je 2×) | #1106 / #1122 — **das Duplikat-Paar, Weiche 49** |
| 🟢 `apps/web/src/**` · `apps/web/e2e/**` | 🟢 **keiner der 51** |
| 🟢 `docs/mcp-payload-budget.md`, `payload_report.py`, `test_tool_payload_budget.py` | 🟢 **frei** — die drei Hebel von #1001 |
| 🟢 `.github/workflows/ci.yml`, `deploy/hetzner/Caddyfile`, fail2ban-Dateien | 🟢 **frei** |

---

## Die vier Funde des Laufs

### 1. 🔴 Der oberste Posten der Warteschlange liefert einen Aussperr-Pfad

**#632 stand seit Lauf 31 auf Position 1 und trägt `agent-ready`.** Die Reihenfolge wurde bisher
damit begründet, #633 hänge hart an #632, weil ohne registrierbaren Faktor der Step-up nicht
testbar sei. 🔴 **Das ist am Code nicht belegbar — und die Abhängigkeit, die existiert, läuft in
die andere Richtung.**

| # | Stelle | Inhalt |
|---|---|---|
| 1 | `MfaSection.tsx:255` | `await supabase.auth.mfa.unenroll({ factorId: factor.id })` — **kein Letzt-Faktor-Schutz**; `verified` (`:66`) filtert nur auf `status === 'verified'`, nicht auf Anzahl |
| 2 | `SessionProvider.tsx:57-63` | `mfaStepUpPending()` ist `true`, sobald GoTrue `nextLevel === 'aal2' && currentLevel !== 'aal2'` meldet — **bei JEDEM verifizierten Faktor, auch `webauthn`** |
| 3 | `SessionProvider.tsx:134-138` | `if (nextSession !== null && (await mfaStepUpPending())) { setMe(null); setSession(null); return }` |
| 4 | `LoginPage.tsx:44-47` | `if (factors.totp.length === 0) { throw new Error('Kein verifizierter TOTP-Faktor gefunden.') }` — `grep -n webauthn LoginPage.tsx` → **0 Treffer** |

**Ablauf mit genau dem Funktionsumfang, den #632 herstellt:** Passkey registrieren → verifizierter
`webauthn`-Faktor → TOTP entfernen (die UI erlaubt es) → nächster Login: `nextLevel: aal2`,
`currentLevel: aal1` → Session verworfen → `completeMfaChallenge` wirft. 🔴 **Kein Weg zurück über
die Oberfläche.** Für Konten unter `require_aal2` (`security.py:202`) trifft es Admins zuerst.

⚠️ **Grenze, ausdrücklich benannt:** die Kette ist **am Code gelesen, nicht ausgeführt** — ohne
Container-Laufzeit gibt es keinen GoTrue. Die einzige Annahme ist GoTrues `nextLevel`-Verhalten bei
einem WebAuthn-Faktor, und die steht faktor-unspezifisch schon im Kommentar von
`SessionProvider.tsx:50-56`.

🟢 **Kein Widerspruch im Body von #632:** §Out schließt `LoginPage.tsx`, `SessionProvider.tsx` und
`e2e/helpers/auth.ts` aus, „TOTP bleibt unverändert nutzbar" hält, und **keines der fünf Kriterien
verlangt oder verbietet einen Letzt-Faktor-Schutz.** 🔴 **Es ist eine Scope-Lücke, kein Body-Fehler
— und genau deshalb gefährlich: ein Agent erfüllt jedes Kriterium und baut den Pfad.**

→ **`needs-decision` gesetzt** (`agent-ready` bleibt, wie bei #989), **Weiche 59** mit drei Optionen,
Empfehlung **A** (Letzt-Faktor-Schutz in #632 aufnehmen: +2 Dateien, +1 Kriterium, bleibt `size/S`).
**A ist die einzige Option, die den Pfad unabhängig von #633 und von der Container-Laufzeit
schließt — und der Schutz bleibt auch nach #633 nötig.**

### 2. 🔴 #542 verlangt eine Entscheidung, die gefallen und gebaut ist — für eine Option, die es nicht anbietet

#542 fragt A (Merchant of Record) / B (selbst) / C (Buchhaltungstool) und begründet das mit:
„**Es gibt kein Rechnungs-Artefakt im Repo — kein Template, keine Nummernvergabe, keinen Endpunkt,
keinen Versand.**"

| Messung | Ergebnis |
|---|---|
| `docs/adr/0061-...md` Kopf | **„Status: Accepted (Owner, 2026-10-20)"** — Rechnungsstellung über **Mollie Invoicing** |
| Code | `invoice.py` **1230** · `billing_profile.py` **325** · `tax.py` **175** = **1730** Zeilen |
| Migration | `billing_0111_billing_invoice.sql` |
| Endpunkte | `router.py:468` `GET /profile` · `:476` `PUT /profile` · `:561` `GET /invoices` · `:574` `GET /invoices/{id}/pdf` |
| Tests | `test_invoice.py`, `test_invoice_endpoint.py`, `test_cloud_compose_invoice_switches.py` |
| Träger | **#1059, #1064, #1088 — alle gemergt** (2026-10-23/24) |

🔴 **Der gewählte Weg ist keine der drei Optionen.** Das ist die Steigerung von Regel 76: nicht nur
ein verrotteter Blocker-Grund, sondern **eine Frage, deren Antwortmenge die Antwort nicht enthält.**
Wer den Body gewissenhaft beantwortet, entscheidet gegen die eigene, umgesetzte Entscheidung.
**#542 nennt ADR-0061 an keiner Stelle** (`updated_at` 2026-10-12 — acht Tage vor der Entscheidung).

🟢 **Wirklich offen sind:** ADR-0061 §11 **W61-1** (PDF-Archiv), **W61-2** (Preisbasis brutto),
**W61-3** (EU-B2B mit ungeprüfter USt-IdNr.) plus **10 `<PLATZHALTER>`** in
`docs/compliance/gobd-verfahrensdokumentation.md`. → **Weiche 63**, Empfehlung **B** (neu
zuschneiden), ausdrücklich **nicht A** (schließen), weil die drei ADR-Weichen sonst ihren Träger
verlieren. → **Regel 82**.

### 3. 🔴 Von zehn `main`-Commits des 2026-11-06 trägt höchstens einer einen CI-Spruch

| Messung | Ergebnis |
|---|---|
| `main`-Commits am 2026-11-06 | **10** (`c64c58db` 07:54:17 … `f89acf87` 08:05:51) |
| gelistete `main`-Push-Läufe (`2390`–`2399`) | **8** |
| davon 🔴 `cancelled` | **7** (2390, 2391, 2392, 2393, 2396, 2397, 2398) |
| davon `failure` | **1** — `42178623925`, Kopf `f89acf87` |
| davon `success` | **0** |

🔴 **Lauf 47 hat über 40 `main`-Läufe „`created_at == run_started_at` bei jedem, 40× success, 0×
cancelled" gemessen** — für sein Fenster korrekt — **und daraus „kein `main`-Lauf hat JEMALS
gewartet" geschlossen und die Weiche geschlossen.** Die Verallgemeinerung ist widerlegt.

🟢 **Der Mechanismus ist dokumentiert, nicht neu:** `ci.yml:11-15` sagt selbst, auf `main` werte
`cancel-in-progress` zu `false` aus, **aber alle `main`-Pushes teilen dieselbe Gruppe** — „ein
Spruch je `main`-Commit ist damit NICHT garantiert", mit drei gemessenen Lauf-IDs und Issue #923.
🔴 **Neu ist das Ausmaß:** die Kopfnotiz nennt „bei drei `main`-Pushes binnen ~2 min endete der
mittlere ohne einen Job"; gemessen sind **sieben von acht in einem Burst von zwölf Minuten.**

**Folge für die Lesart „`main`-CI ist rot":** sie ist zu freundlich. `main` hat seit dem 2026-11-06
**genau einen** abgeschlossenen Spruch, und der ist rot; **neun Commits tragen gar keinen.**
⚠️ **Zu zwei Commits (`7cb412cf`, `d3983e94`) führt die API-Seite keinen Lauf** — ich sage „höchstens
einer von zehn", nicht „genau einer", weil ich nicht belegt habe, dass es für diese beiden nirgends
einen gibt. → **Regel 83**.

### 4. 🟢 #540 ist erstmals kriterienweise geprüft — vier von sieben sind belegt erfüllt

Lauf 87 hat festgestellt, dass die Umsetzung auf `main` liegt. **Dieser Lauf liest die sieben
Kriterien einzeln gegen das Repo**, statt vom Commit-Titel auf Fertigkeit zu schließen.

| # | Urteil | Beleg |
|---|---|---|
| 1 | 🔴 **nicht belegt** | braucht Host mit `iptables` + fail2ban + Docker; CI belegt Regex, nicht Sperrwirkung |
| 2 | ⚠️ teilweise | `bantime` 1h / 15m gesetzt; Wirkung ungefahren |
| 3 | 🟢 **erfüllt** | Filter nimmt `mcp.` und `/v1/health` aus; in CI gefahren (`ci.yml:399`/`:407`) |
| 4 | ⚠️ **Substanz ja, Ort nein** | `grep` in `.env.example` → **0**; Schwellen nur in `jail.d/`, dort aber ausdrücklich per `fail2ban-client reload` änderbar |
| 5 | 🟢 **erfüllt** | `RUNBOOK.md:1002` §Rate-Limit, `:1124` §Entsperren, TOC `:15` |
| 6 | 🟢 **erfüllt** | `test_headers.sh` in `39407da6` nicht enthalten |
| 7 | 🟢 **erfüllt** | `(access_log)` auf `Caddyfile:115`, Jail-`logpath` auf dieselbe Datei, Diff nur Kommentar |

🟢 **Die gebaute Option ist am Konfigurationsinhalt eindeutig A** (`logpath` auf Caddys JSON-Log,
`banaction = iptables-allports`, `chain = DOCKER-USER`; `grep -cE "\brate\b" Caddyfile` → **0**).
🔴 **Alle sieben Kästchen stehen als `[ ]`** — der teuerste Einzelfehler des Bodys. 🔴 **§Eskalation
behauptet „`fail2ban` existiert im Repo nicht"**: `git grep -il fail2ban` → **13** Dateien (9 ohne
Planprotokolle). 🔴 **Der Verifikations-Block ist für Option B geschrieben** (verlangt `caddy
validate` mit „Adapter-Warnung zur neuen Direktive" — es gibt keine neue Direktive).
→ **Weiche 60**, Empfehlung **A** (schließen mit Verzicht) **+ C als Folge-Issue**.

### 🟢 Nebenbefund: für #1150 sind alle drei Optionen erstmals AUSGEFÜHRT

In einer Wegwerf-Kopie (`git archive` ins Scratchpad, `uv lock` darin; Repo unberührt,
`git status --porcelain` → 0 Zeilen):

| Option | Blöcke | Export-Zeile | Requirements | `pip-audit` danach |
|---|---|---|---|---|
| **A** (`>=3.11.5` in 5 Dateien) | 🟢 **1** | 🟢 `soupsieve==4.1.3` **markerfrei** | **123** | 🟢 **3 CVEs in 3 Paketen** |
| **B** (`[tool.uv] environments`) | 🟢 **1** | ⚠️ Marker bleibt | **123** | ⚪ nicht gefahren |
| **C** (nur `uv lock --upgrade-package`) | 🔴 **2** | — | — | 🔴 **widerlegt** |

`uv` wörtlich zu C: `Updated soupsieve v2.9.2 -> v2.10, v4.1.3`. 🟢 **Die Kosten von A sind viermal
mit 0 gemessen** (`python-version` in allen drei Workflows **0×**, kein `.python-version`,
Dockerfiles `python:3.14-slim`, ruff/mypy ohne Patch-Ebene). **Damit ist die Weiche auf ihren Kern
eingeschmolzen: darf die öffentlich erklärte Mindestversion von `>=3.11` auf `>=3.11.5`?**
🔴 **Neuer Fund:** A und B entfernen zusätzlich `async-timeout` und `tomli` — das erklärt 125 → 123,
widerspricht aber §Out of Scope („jede andere Zeile von `uv.lock`"). 🟢 **Zielversion 4.1.3, diesmal
ohne Drift** (zwei Wege: PyPI und der Lock selbst) — die Serie aus drei Werten in drei Läufen bricht.

---

## Norm-Prüfung „Agent-ready Arbeitspaket" — alle 13 offenen Issues

Vier Pflichtabschnitte nach `.github/PROJECT.md` §Constraints: **Outcome** · **prüfbare
Akzeptanzkriterien** · **Out-of-Scope** · **exakte Verifikations-Kommandos**; Scope-„In" separat.

**Lesestand ehrlich getrennt:** die zwölf Paket-Bodies sind von **vier** Sub-Agenten wörtlich
gelesen und gegen die Felder geprüft (Modellwahl **Sonnet** für alle vier: mechanisches Lesen,
Zeiger- und Zahlenvergleich — das kleinste Modell, das die Aufgabe trägt; die Urteilsbildung und
jede Weiche sind von mir selbst formuliert, die vier tragenden Befunde selbst nachgemessen).
**#442 ist die Liste selbst.**

| Issue | Labels | Outcome | AK (mit Schwelle) | Out-of-Scope | „In" | Verifikation | Urteil |
|---|---|---|---|---|---|---|---|
| **#1001** | `agent-ready` `size/S` | ✅ | **5** (4) | ✅ | ✅ | ✅ | 🟢 **4/4** |
| **#989** | `agent-ready` `size/S` `needs-decision` | ✅ | **6** (6) | ✅ | ✅ | ✅ | 🟢 **4/4** |
| **#632** | `agent-ready` `size/S` 🆕 `needs-decision` | ✅ | **5** (2) | ✅ | ✅ | ✅ | 🟢 **4/4** — 🔴 **Scope-Lücke, Fund 1** |
| **#633** | `agent-ready` `size/S` | ✅ | **6** (3) | ✅ | ✅ | ⚠️ E2E hier nicht fahrbar | **3/4** |
| **#1150** | `needs-decision` `size/S` | ✅ | **5** (5) | ✅ | ⚠️ optionsabhängig | ✅ | 🟢 **4/4**, bewusst ohne `agent-ready` |
| **#540** | `needs-decision` `size/M` | ✅ | **7** (2) | ✅ | 🔴 | ✅ veraltet | **3/4** — 🔴 falsche Aussagen, Fund 4 |
| **#435** | `epic` `size/M` | ✅ | **6** (1) | ✅ | ✅ | ✅ | **4/4 formal**, Tracking |
| **#454** | `human-only` | ✅ | **5** (1) | ✅ 🔴 überholt | 🔴 | ⚠️ ohne Befehl | **2/4** |
| **#542** | `needs-decision` `human-only` `size/M` | 🔴 | **5** (0) | ✅ | 🔴 | ✅ | **2/4** — 🔴 **Fund 2** |
| **#535** | `epic` `needs-decision` `size/M` | 🔴 | **3** (0) | ✅ | 🔴 | 🔴 | **1/4**, Tracking |
| **#428** | `epic` `needs-decision` `size/M` | 🔴 | **5** (0) | ✅ | 🔴 | 🔴 | **1/4**, Tracking |
| **#338** | `human-only` | 🔴 | 🔴 (O1–O4) | 🔴 | 🔴 | 🔴 | **0/4**, Checkliste |
| **#442** | `needs-decision` `backlog-queue` | — | — | — | — | — | diese Liste |

🔴 **Eine Label-Änderung: #632 bekommt `needs-decision`** (Fund 1). Sonst keines vergeben, keines
entzogen. 🔴 **`size/M` → Zuschnitt, nicht Refinement:** #428, #435, #535, #540, #542.
⚠️ **Die „6/7-AK"-Markierungen bleiben kein belegter Verstoß:** `grep -rn '2–5\|2-5\|bis 5'
.github/PROJECT.md` → **kein Treffer**, **fünfundzwanzigster Lauf ohne lesbare Quelle für die
Obergrenze** (die Norm liegt in der AgentDB und war nicht erreichbar).

### Zeiger und Zahlen — der Befund nach Startbarkeit getrennt

🟢 **In den vier norm-vollständigen, aufgreifbaren Paketen: null verrottete Zeiger.** #632 (alle 14),
#633, #989, #1001, #1150 — jeder Zeiger selbst nachgemessen, alle gültig. **Das ist die wichtigste
Zahl der Tabelle**, denn nur diese Bodies werden von einem Agenten gelesen.

🔴 **In den nicht-aufgreifbaren Bodies: durchgehend verrottet** — und das ist genau die Lage, die
**Weiche 57** zur Entscheidung stellt. Belege, je selbst gemessen:

- **#540:** sechs Dateilängen (`Caddyfile` 208 statt 203 · `docker-compose.yml` 605/581 ·
  `RUNBOOK.md` 3244/2700 · `ci.yml` 1259/1237 · `core/config.py` 300/271 ·
  `test_compose_hardening.py` 603/539), elf verschobene Zeiger, drei verschiedene Zahlen für
  dieselbe `fail2ban`-Trefferzahl (11 / 10 / **13**).
- **#454:** **sechs** Zeiger ins Leere, darunter `RUNBOOK.md:1819-1829` → `:1819` ist eine **leere
  Zeile**; der Inhalt liegt auf `:2200-2209`, „betreiberseitig" auf `:2207`. Dazu vier
  `router.py`-Zeiger um ~280 Zeilen verschoben (Ursache: die neuen Rechnungs-Endpunkte).
- **#435:** 🔴 `deploy/dokploy/docker-compose.yml:82` ist falsch (Pin auf **`:115`**) — ein Zeiger,
  den der Body mehrfach als „gemessen" ausweist; sieben `ci.yml`-Zeiger in einem Zug verschoben;
  sieben Zahlen zu niedrig (Lint 94/90, Tests 2849/2236, Collection 5034/3614, Fragmente 405/322,
  Waisen 156/160). 🔴 **#824 und #946 als gemergt geführt — beide geschlossen ohne Merge.**
- **#338:** 🔴 `.claude/plans/` im **ersten Satz** existiert nicht (richtig: `.claude/plan/`);
  `CONTRIBUTING.md` 499 statt 469. 🟢 Der `uses:`-Zähler hält exakt (**33**, 0 ohne SHA, 9 Actions).
- **#542:** `router.py` 732 statt 453, gobd-Doku 231 statt 137, alle fünf Zeiger verschoben.
- **#535:** `BillingPanel.tsx:40-42` → `TIERS` heute `:48`/`:49`; „10 Dateien verweisen" → **11**.
- **#428:** `ci.yml`-Zeiger `:438`→`:478`, `:503`→`:544`, `:1091`→`:1113`; OSV-Frist „2026-11-02,
  18 Tage" → **2026-11-30**; „`ROADMAP.md` 0× bewegt" → `git log` zeigt Commits.

🔴 **Eine verrottete Zahl in einer eingecheckten Datei:** `.github/PROJECT.md:90` behauptet
`supabase/gotrue:v2.196.0`; gemessen steht an allen drei Stellen **`v2.197.0`**
(`docker-compose.yml:63`, `deploy/hetzner/supabase/docker-compose.yml:92`,
`deploy/dokploy/docker-compose.yml:115`). ⚠️ **Nicht korrigiert, mit Grund:** die Datei ist von
**#1105** gehalten, und ein zweiter Schreiber ist genau das, was diese Liste jedem Paket verbietet.
🟢 Die tragende Aussage hält — die Version ist neuer als behauptet.

---

## Reihenfolge — **geändert**, zum ersten Mal seit Lauf 76

Kriterien in dieser Ordnung: **harte Abhängigkeit → Owner-Vorgabe → Fundament vor Fläche →
Inventar vor Zuschnitt → bei Gleichstand das kleinere.**

**#1001 → #632 → #633 → #989.**

| Pos | Issue | Größe | Baum | Lage |
|---|---|---|---|---|
| **1** | **#1001** Payload-Budget (ADR-0058 P4b, Rest) | `size/S` | Python/pytest | ✅ **startbar** — 🟢 **das einzige Paket, das heute ohne Owner-Antwort startet.** Alle drei Hebel über alle 51 PRs frei |
| **2** | **#632** Passkey registrieren/entfernen | `size/S` | Web/Vitest | 🔴 **Weiche 59** (Fund 1). 🟢 keine Datei-Sperre, alle Zeiger gültig — **nach der Antwort ohne Refinement startbar** |
| **3** | **#633** Step-up mit Passkey | `size/S` | Web/E2E | 🔴 nach #632 — **jetzt wegen Weiche 59 und der geteilten `de.json`/`en.json`, nicht wegen Code** (belegt: `LoginPage.tsx:46` liest kein `webauthn`) — **und** Container-Laufzeit **oder** ein CI-Lauf mit einzeln gelesenen E2E-Conclusions |
| **4** | **#989** `http-cache-semantics` → 4.3.0 | `size/S` | Web | 🔴 erst **Weiche 48**, dann die Fläche (`package-lock.json` fünffach). 🔴 **Neu: #1124 trägt den Hunk `@@ -5,22 +5,9 @@` über genau die Zeilen `:5-7`, die #989 umschreiben will** — Textkonflikt vorhersehbar |

**Was sich verschoben hat und warum:** #632 ist von Position 1 herausgefallen — **nicht wegen einer
Datei-Sperre und nicht wegen der Umgebung**, sondern weil sein Zuschnitt einen Aussperr-Pfad
erzeugt. #1001 rückt auf. **Die Begründung von #633s Abhängigkeit hat sich geändert, die Position
nicht.**

## Wellen — was gemeinsam startbar ist

Gemeinsam startbar ist, was **datei-disjunkt** ist und sich **nicht gegenseitig blockiert**.

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🔴 **0** _(Owner, dringend)_ | **#1120 + #1141 + #1142 + #1150** | Die vier Schritte zu `pip-audit` Exit 0, reihenfolge-frei. 🔴 **#1150 braucht A/B/C** — alle drei in diesem Lauf ausgeführt, A belegt. 🔴 **Liegt auf dem kritischen Pfad zweier Fristen** |
| 🟢 **A** | **#1001 — allein** | 🔴 **Das Parallel-Paar ist zerfallen.** Python/pytest, alle Hebel frei. ⚠️ DoD-Fläche `STATE.md` → **Weiche 66** |
| 🔴 **A2** | **#632** | nach **Weiche 59**. Danach wieder echt parallel zu #1001 |
| **B** | **#633** | nach #632 **und** Container-Laufzeit **oder** CI mit einzeln gelesenen E2E-Conclusions |
| **C** | **#989** | erst **Weiche 48**, und **nach #1124** (Hunk-Überschneidung belegt) |
| 🔴 **M** _(Owner)_ | 0 → **#1124** → **#1148** → **#1132–#1136 / #1149** → **#1146** → #1106 **oder** #1122 | 🔴 **#1124 ist terminiert: 8 Tage.** #1149 überschneidet #1134/#1132. **#1106/#1122 nicht beide** (Weiche 49), **und einer muss kommen** |
| **N** _(Owner)_ | **32 Protokoll-PRs**, beliebige Reihenfolge | je genau eine Datei außer #1105 (zwei) und #1152 (drei). Danach **seriell** #1103 → #1090 → #1078 (`STATE.md`) |
| **P** _(Owner)_ | **#1107, #1078, #831** per Branch-Update heilen | Rückstand 15 / 33 / 237 |
| **Q** _(Owner)_ | **#674** | konfliktfrei, 0 hinter `main`, eigene Checks rot. **Empfehlung: schließen** |
| **R** _(Owner)_ | **#1129, #1130, #1147** | nach #1124, einzeln |
| **S** _(Owner)_ | **#1127** | Fläche genau `.github/workflows/deploy.yml` — sperrt kein Paket |

🟢 **Bilanz: 3 + 11 + 32 + 1 + 3 + 1 = 51 von 51**, keine Dublette, keine Lücke.

🔴 **Der Backlog gibt heute GENAU EIN gleichzeitiges Paket her** — vier Arbeitspakete, **drei**
blockiert. Das ist eine Verschlechterung gegenüber den letzten dreizehn Läufen (zwei) und geht
ausschließlich auf Weiche 59 zurück. **Eine Antwort auf Weiche 59 stellt das Paar wieder her.**

### 🔴 Zwei Fristen, und die erste ist in drei Tagen

| Termin | Abstand ab 2026-11-22 |
|---|---|
| Rückfall auf Weiche 58 Option B (`audit` aus `all-green` lösen), von Lauf 88 datiert | 🔴 **3 Tage** |
| `ignoreUntil` beider `[[IgnoredVulns]]` in `apps/web/osv-scanner.toml` (`:11`, `:19`) | 🔴 **8 Tage** |

**#1150 ist der einzige Welle-0-Schritt, der auf eine Antwort wartet** — #1120, #1141 und #1142 sind
fertige Dependabot-PRs. 🟢 **Der Beleg, der bisher fehlte, liegt vor** (Nebenbefund oben). Es fehlt
genau ein Satz: „A", „B" oder „C".

### 🔴 Ein Posten, der keiner Welle gehört: die Protokoll-Halde

**32 der 51 offenen PRs sind Protokolle dieser Läufe** — vorhanden sind 42, 56–62, 64–75, 77–88;
zu **63** und **76** existiert nirgends eines. Sie mergen alle konfliktfrei und bewegen je genau eine
Datei. **Dieser Lauf legt das dreiunddreißigste dazu.** 🔴 **Solange niemand sie mergt, erzeugt die
Routine pro Nacht einen PR, der nie landet, und `.claude/plan/` endet auf `main` bei Lauf 55** —
die Arbeit der Läufe 56–89 ist auf `main` unsichtbar. **Das ist kein Fund gegen das Repo, sondern
gegen die eigene Mechanik.**

---

## Was dieser Lauf geschrieben hat

**Als Kommentar, mit drei Optionen und Empfehlung** (das Urteil liegt beim Owner):
**#632** (Weiche 59, Fund 1) · **#540** (Weiche 60, Fund 4) · **#542** (Weiche 63, Fund 2) ·
**#535** (Weiche 61) · **#428** (Weiche 62) · **#454** (Weiche 64) · **#338** (Weiche 65) ·
**#1001** (Weiche 66).

**Als Kommentar, mit Beleg, ohne offene Frage:** **#1150** (alle drei Optionen ausgeführt, Scope-Lücke
`async-timeout`/`tomli`, Fristen) · **#989** (Hunk-Überschneidung mit #1124, Befunde gegengeprüft) ·
**#435** (falscher „gemessener" Zeiger, zwei PRs fälschlich als gemergt, sieben Zahlen).

**Als Kommentar, Blocker neu begründet:** **#633** (die harte Abhängigkeit auf #632 ist am Code
widerlegt und auf ihren wirklichen Grund umgestellt).

🟢 **Alle zwölf Paket-Issues sind kommentiert** — jedes mit seinen eigenen Messungen.

**Als Label:** **#632** → `needs-decision` ergänzt (`agent-ready` bleibt).

**In den Body von #442:** die neue Reihenfolge, die Wellen mit Bilanz 51/51, die vier Funde, **acht
neue Weichen (59–66)** und **fünf neue Regeln (79–83** — davon **79–81 aus Lauf 88 nachgetragen**,
weil jener Lauf nur kommentiert und den Body nicht geschrieben hat). 🟢 **Abschnittsweise gebaut**
(Anker statt Zeilennummern, jede Ersetzung mit `assert count == 1`), **vorher auf Integrität
geprüft** (83 Regeln lückenlos, **keine** Weichen-Nummer verloren) und **nach dem Schrieb maschinell
zurückgelesen und zeichenweise verglichen** (Regel 78), nicht per Sichtvergleich.

🔴 **Kein Paket-Body ist vollgeschrieben — mit Grund.** Die inhaltlich scharfen Korrekturen dieses
Laufs sind **Weichen**, keine Zahlen: sie gehören dorthin, wo sie als jüngster Eintrag zuerst
gelesen werden, und das Label `needs-decision` hält das Paket ohnehin an. Was sich an den vier
`agent-ready`-Bodies überholt hat, sind der PR-Bestand (49 → 51) und Tagesabstände — also genau die
strukturell wandernden Zahlen, für die Regel 78 den zweiten Vollschrieb verbietet. **#540, #535,
#435 und #428 tragen zusätzlich ihre Attributions-Fußzeile**, die ein MCP-Vollschrieb nachweislich
zerstört (Weichen 44/45/53).

## Neue Regeln

**82.** 🆕 **Ein überholter Entscheidungsträger ist gefährlicher als ein verrotteter Zeiger: er
fordert eine Handlung, die falsch ist.** Regel 76 sagte, ein Blocker-Grund verrottet; dies ist die
Steigerung — **die Antwortmenge einer Frage kann die Antwort nicht mehr enthalten** (#542 gegen
ADR-0061). **Messweg: zu jedem `needs-decision` prüfen, ob eine ADR mit `Status: Accepted` seinen
Gegenstand trägt — nicht nur, ob Code dazu existiert.**

**83.** 🆕 **Eine Messung gilt für ihr Fenster, ihre Verallgemeinerung gilt nie.** Lauf 47 hat
korrekt „40× success, 0× cancelled" gemessen und daraus „kein `main`-Lauf hat jemals gewartet"
geschlossen; am 2026-11-06 waren sieben von acht `cancelled`. **Folge: ein Satz mit „jemals",
„immer" oder „nie" wird nur geschrieben, wenn er aus der Definition folgt, nicht aus einer
Stichprobe** — sonst trägt er sein Fenster im Wortlaut.

---

## Belege dieses Laufs

- Messpunkt `f89acf87`, Baum `c751ed64` (bitgleich zu Lauf 87/88), Fenster **0 Commits**,
  **1676** Commits nach `--unshallow`
- **51** offene PRs, **56** Pfade, **75** Vorkommen — alle selbst gerechnet (`merge-base`,
  `diff --name-only`, `merge-tree --write-tree`, `rev-list --count`); Wellen-Bilanz **51/51**
- `pip-audit` selbst gefahren: **Exit 1**, 7 CVEs / 4 Pakete, 125 Requirements
- `main`-Push-Läufe `2390`–`2399` gelesen: **7× `cancelled`**, **1× `failure`**, **0× `success`**
- `ci.yml:11-15` wörtlich gelesen (Concurrency-Kopfnotiz, Issue #923)
- Aussperr-Kette an vier Fundstellen in drei Dateien wörtlich gelesen
- ADR-0061 Kopf, 1730 Zeilen Rechnungs-Code, Migration, vier Endpunkte, 10 `<PLATZHALTER>`
- #1150 Optionen A/B/C in einer `git archive`-Kopie mit `uv lock` ausgeführt; Repo unberührt
- GoTrue-Pins dreifach `v2.197.0` gegen `.github/PROJECT.md:90` (`v2.196.0`)
- Norm: zwölf Bodies über vier Sonnet-Sub-Agenten wörtlich gelesen; die vier tragenden Funde
  selbst nachgemessen
- Geschrieben: **#442** (Body, **76.588 Zeichen, maschinell zurückgelesen: zeichengleich**, Labels
  `needs-decision` + `backlog-queue` unverändert, 83 Regeln lückenlos, alle acht neuen Weichen
  vorhanden) · Kommentare in **#632, #633, #540, #542, #535, #428, #454, #338, #435, #989, #1001,
  #1150** · Label an **#632**
