# Backlog-Aufbereitungslauf 94

**Datum:** 2026-11-28
**Messpunkt:** `main` @ `8c044ec1` (`fix(api): PUT bei offenem Review liefert 409 …`, #1160)
**Fenster seit dem letzten Messpunkt:** **0 Commits** — der Baum ist bitgleich mit dem von Lauf 93
(`git rev-list --count 8c044ec1..origin/main` = 0, `git diff --stat origin/main` leer).
**Warteschlange:** #442 (Label `backlog-queue`).

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt, selbst
entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit drei Optionen
und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit, Owner-Vorgabe,
Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — sechsundzwanzigster Lauf in Folge.**
Der Server verlangt eine Autorisierung, die diese Session nicht herstellen kann; ein erneuter
Verbindungsversuch über `ToolSearch` wurde abgewiesen. Damit fehlten `get_persona`, `list_triggers`,
`fetch_playbook`, `fetch_resource` (darunter die Norm „Agent-ready Arbeitspaket", `73a86231`),
`record_usage`, `submit_feedback` und `search_memory`/`save_memory`.
Der Lauf fährt nach dem Persona- und Playbook-Katalog im System-Prompt, nach dem Body von #442 und
nach `.github/PROJECT.md` §Constraints. **Sechsundzwanzigster Lauf ohne Kurations-Rückmeldung an die
eigene AgentDB** — die Feedback-Schleife, die das Produkt verkauft, läuft für seinen eigenen Agenten
seit sechsundzwanzig Läufen nicht.

## Messgrundlage

Node **v22.23.5**, npm **10.9.9**, uv **0.11.32**, CPython **3.11.18**. Klon war shallow (50) →
**1679** Commits nach `--unshallow` (Regel 90). `npm`-Gates in `apps/web/` mit `pwd`-Beleg,
Python-Gates im Repo-Root, jede sequenziell, **ohne vorherige Reparatur** (Regel 120).

🔴 **Selbstfund am Messweg (Regel 57):** der erste Gate-Durchgang dieses Laufs hat die Exit-Codes
hinter `| tail -3` gelesen und damit den Exit-Code von `tail` gemessen, nicht den des Gates
(Regel 36/94/172). **Alle Gates sind danach unverkettet wiederholt**; nur diese zweiten Werte stehen
unten. Der Fehler ist genau der, gegen den Regel 172 geschrieben ist — er ist in einem Lauf passiert,
der die Regel kennt.

| Gate | Ergebnis | gegen Lauf 93 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien | gleich |
| `uv run pytest --collect-only -q` | **Exit 0**, **5046** Tests | gleich |
| `changelog_fragments.py check` | **Exit 0**, **407** Fragment(e) (Eigenzahl); `ls changelog.d/*.md \| wc -l` = **408**, Differenz `README.md` (Regel 143) | gleich |
| `uv run python -m who2be_mcp.payload_report` | **Exit 0**, Builder **103 / 109.404**, Guard **103 / 109.404**, `instructions` **1.834** Bytes | gleich |
| `uv run pytest apps/mcp/tests/test_tool_payload_budget.py -q` | **Exit 0**, **64 passed** | gleich |
| `uv tool run pip-audit … -r <reqs>` | 🟢 **Exit 0**, „No known vulnerabilities found", **126** Requirements (`wc -l` = **400**) | gleich |
| Positiv-Kontrolle `soupsieve==2.10` ohne Marker | 🔴 **Exit 1, 3 CVEs** (-126190 Fix 4.0.0, -126193 / -126191 je Fix 3.0.2) | gleich |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, **7** `--fix`-bar | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, „Alle i18n-Pruefungen in Ordnung." | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, „found 0 vulnerabilities" | gleich |
| `npx playwright test --list --project=chromium` | **44** Tests in **9** Dateien | gleich |
| `docker info` | **Exit 1** — keine Container-Laufzeit, kein `podman` | gleich (**68.** Messung in Folge) |

⚪ **Mit Grund nicht gefahren** (Regel 30/160): `npm run test:coverage` und `test:a11y`. Das Fenster
ist **0 Commits** breit, der geprüfte Teilbaum ist nicht nur unberührt, sondern identisch
(`git diff --stat origin/main` leer). Bezugswerte **übernommen und als übernommen gekennzeichnet**
(Regel 42/178). 🔴 **Für die advisory-gefütterten Gates gilt das ausdrücklich nicht**
(Regel 45/181) — `pip-audit`, die Positiv-Kontrolle und `npm audit` sind heute selbst gefahren.

## PR-Bestand — **22** offene PRs, unverändert

Scope je PR über `git merge-base` + `git diff --name-only` mit Nicht-leer-Prüfung, Konfliktfreiheit
über `git merge-tree --write-tree`, Rückstand über `git rev-list --count`, Checks über die
Check-Runs am Head mit `all-green` **namentlich** und `status`/`conclusion` getrennt gelesen.
**Alle 22 heute selbst gerechnet.**

- 🟢 **Alle 22 mergen konfliktfrei** (`rc 0`), **keiner bewegt 0 Dateien** (1 … 18 Dateien).
- **Differenz 22 → 22:** −0 gemergt, −0 geschlossen, +0 neu. **Fünfzehnter Lauf, in dem der Stapel
  nicht kleiner wird.**
- **Rückstand auf `main`:** **0** → #1169, #1168, #1167, #1164, #1158, #1157, #1124 (**7**) · **1** →
  #1166, #1165, #1163, #1162, #1161, #1148 (**6**) · **2** → #1122 (**1**) · **3** → #1152, #1136,
  #1135, #1133, #1132, #1130, #1129 (**7**) · **18** → #1105 (**1**). _(7+6+1+7+1 = **22**.)_
- **Rot-Bilanz:** 🟢 **13 ohne Rot** (#1169, #1168, #1167, #1166, #1165, #1164, #1163, #1161, #1158,
  #1157, #1148, #1124, #1105) · 🔴 **9 rot** (#1162, #1152, #1136, #1135, #1133, #1132, #1130,
  #1129, #1122). _(13+9 = 22.)_
- **Draft:** #1166, #1161, #1152, #1105 — alle vier Protokoll-PRs → Weiche 71.
- ⚠️ **#1166, #1161 und #1152 tragen je 7 `skipped`**; bei #1166 und #1161 steht `all-green` trotzdem
  auf `success`. **`skipped` ist nicht `success`** (Regel 37) — pfad-gefilterte Grüns.

## Die vier Funde des Laufs

### 1. Meine eigene Partition ging nicht auf — und ein Sub-Agent hat es gemerkt (Regel 130)

Die Check-Run-Erhebung ist an einen Sub-Agenten delegiert worden, mit einer namentlichen Liste, die
ich als „19 PRs" bezeichnet habe. **Es waren 18.** Zusammen mit den drei selbst gemessenen ergab das
**21 von 22** — **#1164 fehlte vollständig**, und zwar genau der PR, dessen Zustand sich im Vorlauf
bei 0 Commits bewegt hatte. Der Sub-Agent hat die Differenz im ersten Satz seines Berichts gemeldet,
ohne danach gefragt worden zu sein; #1164 ist danach einzeln nachgemessen (**18/18 `success`**,
`all-green` 2026-11-25T17:00:28Z, `clean`, 0 hinter `main`). **Die Partition schließt erst damit:
13 + 9 = 22.**

**Die Lehre ist nicht „sorgfältiger zählen", sondern: eine Mengenangabe im Auftrag an einen
Sub-Agenten ist eine Zusicherung und wird wie ein Zeiger geprüft.** Hätte der Sub-Agent still die
18 abgearbeitet, stünde in diesem Protokoll eine Rot-Bilanz über 21 PRs, die sich zu „22" addiert
hätte, weil ich die Summe aus dem Vorlauf übernommen hätte.

### 2. Die Datums-Verteilung der geerbt-roten PRs stimmt in #442 nicht

#442 §In Review sagt: _„Acht der neun roten sind auf demselben Check rot: `audit`. Alle acht
`all-green`-Läufe datieren **vor** dem Grün von `main` — **sieben vom 2026-11-09, zwei vom
2026-11-22**."_ 🔴 **7 + 2 = 9, nicht 8** — die Satzhälfte widerspricht ihrer eigenen ersten Hälfte.
Heute je PR am `all-green`-Check-Run gemessen (`completed_at`):

| Datum | PRs | Zahl |
|---|---|---|
| 2026-11-09 | #1130, #1133, #1135, #1136 | **4** |
| 2026-11-18 | #1152 | **1** |
| 2026-11-22 | #1122, #1129, #1132 | **3** |
| **Summe** | | **8** ✅ |

🟢 **Die Aussage, auf die es ankommt, hält trotzdem:** alle acht `all-green`-Läufe liegen **vor** dem
Grün von `main` (2026-11-24T05:46:07Z), die Ursache des `audit`-Rots ist auf `main` seit #1159
behoben — **das Rot ist nach Zeitstempel UND nach Ursache geerbt.** Falsch war nur die Verteilung,
und sie stand mit einer Summe da, die ihre eigene Partition sprengt.

### 3. `uv.lock` hat 3516 Zeilen, nicht 3485 — bei bitgleichem Baum

#442 §Datei-Sperren führt `uv.lock` mit **3485** Zeilen. Gemessen sind **3516** — und zwar sowohl im
Arbeitsbaum als auch in `git show origin/main:uv.lock`. **Das Fenster hat 0 Commits, der Baum ist
bitgleich mit dem von Lauf 93**; die Zahl war also schon falsch, als sie geschrieben wurde. Eine
Datei-Länge ist ein Repo-Inhalt und verrottet nicht von allein (Gegenstück zu Regel 128) — **wenn
sie abweicht, war die Messung falsch, nicht die Welt.**

Die inhaltlichen `soupsieve`-Zeiger desselben Absatzes halten dagegen: zwei Blöcke an `:2812`
(Version **2.10**, Marker `< '3.11.5'`) und `:2825` (**4.1.3**), dazu die beiden Auflösungs-Zeilen
`:326`/`:327`.

### 4. „Jede der sieben Zeilen um +1.153 Bytes" trifft auf eine der sieben nicht zu

#442 §Startbar sagt zu #1001: _„es sind SIEBEN veraltete Zeilen … `:262`, `:263`, `:264`, `:265` …
**und** `:281`, `:282`, `:283`, **jede um genau +1.153 Bytes**."_ 🔴 **Für `:283` gilt das nicht.**
Die Zeile lautet `| Unterschied | −17 | **−15.867 (−14,4 %)** |`, und heute gemessen:

| Zeile | Doku | gemessen | Abweichung |
|---|---|---|---|
| `:262` / `:265` | 108.251 | **109.404** | +1.153 |
| `:263` | 92.384 | **93.537** | +1.153 |
| `:264` | 104.699 | **105.852** | +1.153 |
| `:281` | 110.085 | **111.238** | +1.153 |
| `:282` | 94.218 | **95.371** | +1.153 |
| **`:283`** | **−15.867 (−14,4 %)** | **−15.867 (−14,3 %)** | 🔴 **Absolutzahl hält, Prozentzahl nicht** |

Nachgerechnet: 109.404 − 93.537 = **15.867** (unverändert); 15.867 / 111.238 = **14,26 %** → −14,3 %,
während 15.867 / 110.085 = **14,41 %** → die alte −14,4 %. **Wer `:283` nach der Regel „+1.153"
anfasst, macht die einzige Zahl der Zeile falsch, die heute richtig ist.**

🟢 **Der Body von #1001 selbst sagt es korrekt** („die Absolutzahl hält, die **Prozentzahl** nicht").
Falsch ist die **Zusammenfassung in #442** — und ein Agent mit leerem Kontext liest die
Warteschlange zuerst. 🟢 **Ebenfalls bestätigt und ausdrücklich kein Fund: `:315`/`:316`** — dort
stehen 110.085 und 94.218 in einer mit „Stand 2026-10-27" datierten Vergleichsspalte.

## Norm-Prüfung „Agent-ready Arbeitspaket" — **13** offene Issues

Vier Pflichtabschnitte (`.github/PROJECT.md:151-152`): **Outcome** · **prüfbare
Akzeptanzkriterien** · **Out-of-Scope** · **exakte Verifikations-Kommandos**.

⚠️ **Was dieser Lauf wörtlich gelesen hat, und was nicht** (Regel 42/189, ehrlich ausgewiesen):
**vollständig gelesen** sind die Bodies von **#1001, #989, #633 und #632** — die vier aufgreifbaren
Pakete. **Nicht erneut vollständig gelesen** sind **#1150, #540, #454, #542, #435, #535, #428, #338,
#442**; für sie sind die Urteile aus Lauf 93 übernommen, **und das ist eine Übernahme, keine
Messung.** Lauf 93 hat diese neun bei bitgleichem Baum neu geschrieben bzw. kommentiert; neue
Gegenbelege sind heute nicht aufgetreten. **Der nächste Lauf lese diese neun wieder selbst** — die
Übernahme ist hier ausgewiesen, damit sie nicht zur stillen Gewohnheit wird.

| Issue | Labels | Outcome | AK (gesamt / mit Befehl) | Out-of-Scope | Verifikation | Urteil |
|---|---|---|---|---|---|---|
| **#1001** | `agent-ready` `size/S` | ✅ | 🟢 **5 / 5** | ✅ | ✅ | 🟢 **4/4 formal.** 🟢 **Alle Zeiger heute nachgemessen und gültig** — s. unten |
| **#632** | `agent-ready` `size/S` `needs-decision` | ✅ | ⚠️ 5 / **4** | ✅ | ✅ | **4/4 formal, inhaltlich NICHT erfüllt** (Weiche 59/74). 🟢 **Null verrottet** |
| **#633** | `agent-ready` `size/S` → **heute `needs-decision` ergänzt** | ✅ | ⚠️ 6 / **4** | ✅ | ✅ | **4/4 formal, inhaltlich NICHT erfüllt** — Vorbedingung #632 fehlt am Baum. 🟢 **Null verrottet** |
| **#989** | `agent-ready` `web` `size/S` `needs-decision` | ✅ | 🟢 **6 / 6** | ✅ | ✅ | 🟢 **4/4 formal; bestes Kriterienfeld des Backlogs.** Inhaltlich gesperrt (Weiche 48) — **benennt es selbst** |
| **#1150** | `needs-decision` `size/S` | ✅ | 🟢 5 / 5 | ✅ | ✅ | **4/4** _(aus Lauf 93 übernommen)_ |
| **#540** | `needs-decision` `size/M` | ✅ | ⚠️ 7 / **3** | ✅ | ✅ | 4/4 formal, 3/4 inhaltlich _(übernommen)_ |
| **#454** | `human-only` | ✅ | ⚠️ 5 / **0** | ✅ | ⚠️ | 4/4 formal, 3/4 inhaltlich _(übernommen)_ |
| **#542** | `needs-decision` `human-only` `size/M` | ❌ | ⚠️ 5 / **0** | ✅ | ✅ | 3/4 formal, 2/4 inhaltlich _(übernommen)_ |
| **#435** | `epic` `web` `size/M` | ✅ | ⚠️ 6 / **1** | ✅ | ✅ | 4/4 formal, 2/4 inhaltlich, Tracking _(übernommen)_ |
| **#535** | `epic` `needs-decision` `size/M` | ❌ | ⚠️ 3 / **0** | ✅ | ❌ | 2/4 formal, 1/4 inhaltlich, Tracking _(übernommen)_ |
| **#428** | `epic` `needs-decision` `size/M` | ❌ | ⚠️ 5 / **0** | ✅ | ❌ | 2/4 formal, 1/4 inhaltlich, Tracking _(übernommen)_ |
| **#338** | `human-only` | ❌ | ❌ | ❌ | ❌ | 0/4, Checkliste _(übernommen)_ |
| **#442** | `needs-decision` `backlog-queue` | — | — | — | — | diese Liste |

🔴 **Die „2–5 AK"-Norm bleibt unbelegt:** `grep -rn '2–5\|2-5\|bis 5\|zwei bis f' .github/PROJECT.md`
→ **kein Treffer, Exit 1**. **Siebenundzwanzigster Lauf ohne lesbare Quelle** → Weiche 55. Solange
sie fehlt, ist „6 AK" **kein belegter Verstoß**.

### Zeiger-Nachkontrolle — **null verrottet** in allen vier aufgreifbaren Paketen

Jeder Zeiger der vier Bodies heute am Baum nachgemessen, Pfad vor der Prüfung auf Existenz belegt
(Regel 34/66/163):

| Zeiger | Body sagt | gemessen |
|---|---|---|
| `docs/mcp-payload-budget.md` | 609 Z; `104.777` an `:233`/`:292`/`:327`/`:487`, `108.262` an `:234`/`:331`, `71.738` an `:236`/`:335` | 🟢 **alle zehn exakt** |
| `apps/web/e2e/helpers/auth.ts` | 199 Z, `createUser` `:33`, `enrollTotpAal2` `:97`, Aufruf `:55` | 🟢 **exakt** |
| `features/auth/pages/LoginPage.tsx` | 399 Z, `completeMfaChallenge` `:39`, Aufruf `:172`, Wurf `:46` | 🟢 **exakt** |
| `src/auth/SessionProvider.tsx` | 267 Z, `mfaStepUpPending` `:57`, Aufrufer `:134`/`:222` | 🟢 **exakt** |
| `features/settings/components/MfaSection.tsx` | 297 Z, Null-Fall `:77`, Entfernen-Button `:91`, `unenroll` `:255` | 🟢 **exakt** |
| `MfaSection.test.tsx` · `.a11y.test.tsx` | 284 · 45 | 🟢 **exakt** |
| `.github/workflows/ci.yml` | 1259 Z, `:463` `npm run e2e -- --project=chromium`, `:544` Billing-Zeile | 🟢 **exakt, wörtlich** |
| `apps/web/src/api/client.ts` · `types.ts` | 1849 · 2407 | 🟢 **exakt** |
| `apps/web/vite.config.ts` | 107 Z, `thresholds:` `:99`, Werte `:100-103` = 80/79/75/80 | 🟢 **exakt** |
| `src/test/a11y.test.ts` · `i18n/audit.test.ts` | 77 · 371 | 🟢 **exakt** |
| `src/i18n/orphan-baseline.json` | 156 Einträge, flache Liste | 🟢 **exakt** (`json.load`) |
| `apps/web/package.json` | 82 Z | 🟢 **exakt** |
| GoTrue-Pin | `v2.197.0` an `docker-compose.yml:63`, `supabase/…:92`, `dokploy/…:115` | 🟢 **alle drei exakt** |
| `deploy/hetzner/Caddyfile` · `RUNBOOK.md` | 208 · 3244; `rate` **0×** | 🟢 **exakt** |
| `fail2ban`-Dateien (#540) | 14 | 🟢 **14** (Kopfblock von #540 sagt 11 → Selbstwiderspruch bleibt) |

🔴 **Der Aussperr-Pfad von Weiche 59 ist heute in drei Dateien wörtlich bestätigt** — er ist der
härteste Befund der Warteschlange und der Grund, warum #632 nicht startet:
`SessionProvider.tsx:134-138` verwirft die `aal1`-Session (`setMe(null)`, `setSession(null)`);
`LoginPage.tsx:46` wirft `Error('Kein verifizierter TOTP-Faktor gefunden.')`, weil
`completeMfaChallenge` nur `factors.totp` liest; `MfaSection.tsx:255` ruft `unenroll` **ohne
Zähler- oder aal2-Prüfung**, der Button an `:91` steht an jedem verifizierten Faktor.
`grep -rniE 'webauthn|passkey' apps/web/src` → **0**. **Wer einen Passkey registriert und TOTP
entfernt, kommt nicht mehr herein.**

## Datei-Sperren — gegen alle 22 PRs, am vollen Pfad, Existenz zuerst belegt

| Pfad | Träger |
|---|---|
| 🟢 `docs/mcp-payload-budget.md` · `payload_report.py` · `test_tool_payload_budget.py` | 🟢 **FREI** — die drei Hebel von #1001 |
| 🟢 `apps/web/src/features/settings/**` · `orphan-baseline.json` | 🟢 **FREI** — die Fläche von #632 |
| 🟢 `apps/web/e2e/**` · `LoginPage.tsx` · `src/auth/SessionProvider.tsx` | 🟢 **FREI** — die Fläche von #633 |
| 🟢 `changelog.d/osv-ignore-http-cache-semantics.security.md` (615 B) | 🟢 **FREI** — die Löschung aus #989 AK3 |
| 🟢 `Caddyfile` · `RUNBOOK.md` · `.env.example` | 🟢 **FREI** — die Fläche von #540 |
| 🔴 `apps/web/package.json` · `package-lock.json` | **#1164, #1130, #1129, #1124** — **vierfach**, nach ADR-0064 streng nacheinander |
| 🔴 `apps/web/osv-scanner.toml` (26 Z) | **#1124** |
| 🔴 `uv.lock` (**3516** Z) | **#1148** — die Fläche von Weiche 67 **und** 70 |
| 🔴 `.claude/context/STATE.md` | **#1167** — steht in der DoD **jedes** Pakets |
| 🔴 `.github/PROJECT.md` | **#1167** und **#1105** |
| 🔴 `locales/de.json` · `en.json` | **#1158** — die geteilte Fläche von #632/#633 |
| 🔴 `.github/workflows/ci.yml` · `deploy.yml` | **#1163** — alleiniger Träger, ohne Zeilenverschiebung |
| 🔴 `src/api/client.ts` · `types.ts` | **#1157** |
| 🔴 `packages/models/…/blocknote_markdown.py` · `test_blocknote_markdown_ids.py` | **#1164** |
| 🔴 `apps/mcp/**` (eine Datei: `Dockerfile`) | **#1162** — ohne Draht-Wirkung |
| 🔴 `docker-compose.cloud.yml` | **#1165 UND #1132** — die einzige Kollision unter den 22 |

⚠️ **`changelog.d/` als Verzeichnis halten 6 PRs** (#1122, #1124, #1157, #1158, #1168, #1169) —
aber je ein **eigenes** Fragment. **Eine Verzeichnis-Sperre auf `changelog.d/` ist keine Sperre**;
Kollisionen entstehen nur am gleichen Dateinamen (Regel 163).

🟢 **Weiche 69 bleibt offen und der Befund hält:** `grep -rn 'defaultBlockSpecs' packages/models/src
packages/models/tests` findet **nur Kommentare** (`blocknote_markdown.py:73`,
`test_blocknote_markdown_ids.py:313`), beide auf **0.56.0** lautend. `BLOCKNOTE_VERSION` steht auf
`main` an `:58` auf **`"0.56.0"`**; #1164 hebt sie auf `0.57.0`, ohne dass irgendwo belegt ist, dass
die Typlisten gegen die installierte 0.57 geprüft wurden.

## Warteschlange

**Die Reihenfolge ist unverändert: #1001 → #632 → #633 → #989.** Siebter Lauf ohne
Positionsänderung. Kriterien in der Reihenfolge ihrer Anwendung: harte Abhängigkeit (#633 nach
#632 — im Code belegt), Owner-Vorgabe (Weichen 48/59/74 sperren #632/#633/#989), Fundament vor
Fläche, **Inventar vor Zuschnitt** (#1001 misst den Katalog und ändert ihn nicht), bei Gleichstand
das kleinere.

| Pos | Issue | Größe | Baum | Lage am 2026-11-28 |
|---|---|---|---|---|
| **1** | **#1001** Payload-Budget (ADR-0058 P4b, Rest) | `size/S` | Python/pytest | ✅ **Technisch startbar.** 🟢 Einziges Paket ohne eigene inhaltliche Owner-Weiche; alle drei Hebel über alle 22 PRs frei; Messgegenstand heute selbst gefahren; alle zehn Zeiger gültig. 🔴 DoD-Datei `STATE.md` hält #1167 |
| **2** | **#632** Passkey registrieren (#435 W2a) | `size/S` | Web/Vitest | 🔴 **Weiche 59** — Aussperr-Pfad heute in drei Dateien bestätigt. 🟢 Eigene Fläche frei; `locales/{de,en}.json` hält **#1158** → **R zuerst** |
| **3** | **#633** Step-up mit Passkey (#435 W2b) | `size/S` | Web/E2E | 🔴 **nach #632** — Abhängigkeit liegt im Code (`grep` → 0). 🟢 Eigene Fläche frei; CI-Weg für den E2E-Nachweis offen |
| **4** | **#989** `http-cache-semantics` → 4.3.0 | `size/S` | Web | 🔴 **Weiche 48**, dann **#1124**, dann die Fläche (#1164, #1130, #1129) |

🔴 **Über allen vier steht Weiche 73** (ADR-0064 Arbeitsregel B): **13 der 22 offenen PRs sind grün
und `clean`**, also fertig im Sinne der Regel; die Grenze ist 3–5. Jedes Paket endet in einem PR.
**Das ist keine Auslegung, die ein Agent allein treffen darf.**

## Wellen — was gemeinsam startbar ist

Gemeinsam startbar ist, was **datei-disjunkt** ist und sich **nicht gegenseitig blockiert**.

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🟢 **A** | **#1001 — allein** | Python/pytest; alle drei Hebel frei. Einziges Paket ohne inhaltliche Owner-Weiche |
| 🔴 **A2** | **#632** | **nach Weiche 59.** Danach echt parallel zu A (Vitest gegen pytest, code-disjunkt). ⚠️ `locales` hält #1158 → **R zuerst** |
| **B** | **#633** | nach **#632** (Code-Abhängigkeit belegt). Nachweis über eigenen CI-Lauf |
| **C** | **#989** | erst **Weiche 48**, dann **#1124**, dann die Fläche |
| 🔴 **M0** _(Owner, dringend — Frist 2026-11-30, **2 Tage**)_ | **#1124** | 🟢 **18/18 grün (2026-11-24T06:08:30Z, nach dem Grün von `main`), 0 hinter `main`, `clean`, konfliktfrei.** Entfernt **beide** `ignoreUntil`-Blöcke (`osv-scanner.toml:11` und `:19`). **Keine Vorarbeit. Ein Klick.** **Dritter Lauf in Folge in diesem Zustand** |
| 🟢 **M1** _(Owner, ein Klick)_ | **#1169** | 18/18 grün. 🔴 Solange offen, liegt ADR-0064 im PR und nicht auf `main` |
| 🟢 **M2** _(Owner, ein Klick)_ | **#1167** | 18/18 grün. 🔴 Solange offen, hält er `STATE.md` — eine Datei in der DoD jedes Pakets |
| 🟢 **R** _(Owner, Review)_ | **#1158**, **#1157** | Untereinander disjunkt, beide 18/18 grün, 0 hinter. ⚠️ **#1158 vor A2 mergen** |
| 🟢 **M3** _(Owner, nach M0)_ | **#1164** | 18/18 grün, 0 hinter, `clean`. 🔴 Kollidiert mit #1124 auf `package{,-lock}.json` → **#1124 zuerst (Frist)**. Trägt BlockNote 0.57 → Weiche 69 |
| 🟢 **M4** _(Owner, löst zwei Weichen)_ | **#1148** | 1 hinter, `clean`, 14 `success` + 1 `neutral`. 🔴 Vorbedingung für Weiche 67 **und** 70 |
| 🟢 **M5** _(Owner)_ | **#1163** · **#1165** | Beide grün, 1 hinter. ⚠️ #1165 überschneidet #1132 → nacheinander; #1165 hebt den Caddy-Pin (Regel 80) |
| **M6** _(Owner, nach dem Nachziehen)_ | **#1129, #1130, #1132, #1133, #1135, #1136, #1122, #1152** | 🟢 Alle acht geerbt-rot auf `audit` — nach Zeitstempel UND Ursache (s. Fund 2). Nachziehen sollte sie räumen; **zu messen, nicht zu glauben** |
| **M7** _(Owner, nach M4)_ | **#1162** | 🔴 Eigen-rot (7 Checks, `e2e`-Familie + `compose-smoke`), bleibt bis `httptools` ≥ 0.9.0 im Lock → Weiche 70 |
| **N** _(Owner, Aufräumen)_ | **#1166, #1161, #1152, #1105** | 🔴 Nach der Owner-Entscheidung vom 2026-11-22 dürfte es diese vier nicht geben; #1152/#1105 tragen echte Doku-Arbeit → Weiche 71 |
| **W67** _(Owner, dann 5 Zeilen)_ | #1150 / Weiche 67 | **nach M4** |

**Keine Welle:** A2/B gegen #1158 (R zuerst) · C gegen M0 · M3 vor M0 · M7 vor M4 · W67 vor M4 ·
#1165 gegen #1132 · B vor A2 · #540 gegen alles (umgebungsblockiert).

🟢 **Lückenprüfung (Regel 77):** M0 1 + M1 1 + M2 1 + R 2 + M3 1 + M4 1 + M5 2 + M6 8 + M7 1 + N 4 =
**22** von **22**; #1152 steht in M6 **und** N (gewollte Dublette, trägt beides). **Keine Lücke.**

🟢 **Empfohlene Klick-Reihenfolge:** **#1124** (Frist, 2 Tage) → **#1169** → **#1167** → **#1158** →
**#1157** → **#1164** → **#1148** → **#1163** → **#1165**. Alle neun grün, konfliktfrei, in dieser
Reihenfolge disjunkt bzw. korrekt serialisiert. Danach **13** offene PRs; mit N **9**.

## Was dieser Lauf geschrieben hat

- **#633:** Label **`needs-decision` ergänzt** (`agent-ready` bleibt). Begründung im Kommentar: die
  harte Vorbedingung #632 fehlt am Baum messbar, und #632 selbst ist `needs-decision`. Das Label
  warnt einen Agenten, der nach `agent-ready` greift; **`agent-ready` zu entziehen bleibt die
  Owner-Entscheidung (Weiche 74).**
- **#442:** Protokoll-Kommentar mit den vier Funden und den heutigen Messwerten.
- 🔴 **Der Body von #442 ist in diesem Lauf NICHT neu geschrieben** — bewusst, mit Grund:
  `issue_write` kennt keinen Teil-Schrieb, jede Änderung ist ein Voll-Schrieb des Bodys
  (**107.285** Codepunkte). **Lauf 93 hat an genau diesem Weg zwei Schriebe verloren, beide mit
  „Erfolg" gemeldet** (Weiche 75). Diese Session hält den Volltext nicht als Datei, sondern nur als
  gelesenes Werkzeug-Ergebnis — **ein abgeschnittener Schrieb wäre von hier aus nicht
  wiederherstellbar.** Was im Body heute überholt ist (Lauf-Nummer, die Datums-Verteilung aus
  Fund 2, `uv.lock` 3485, die „+1.153"-Verallgemeinerung aus Fund 4, „3 Tage" → 2), steht
  namentlich im Protokoll-Kommentar. **→ Weiche 75 braucht eine Antwort, sonst friert der
  Einstiegspunkt ein.**

## Offene Weichen, die heute etwas blockieren

Unverändert gegenüber Lauf 93, keine neue Nummer: **72** (wer liefert das Pflicht-Review),
**73** (gilt „≤ 3–5 fertige PRs" für diese Warteschlange — steht über allen vier Positionen),
**74** (`agent-ready` an einem Paket, dessen Body „nicht starten" sagt), **75** (bleibt der Body
geteilt — und wie wird er schreibbar), **48**, **55**, **59**, **67**, **69**, **70**, **71**.
Die vollständigen Optionssätze stehen im Kommentar „Offene Weichen — Optionen und Empfehlungen"
unter #442; dieser Lauf hat keine davon neu formuliert, weil keine neue Tatsache dazugekommen ist.

## Belege

Alle Zahlen dieses Protokolls sind am 2026-11-28 gegen `main` @ `8c044ec1` selbst erhoben;
Exit-Codes am unverketteten Befehl, nach dem Selbstfund in §Messgrundlage ein zweites Mal.
Übernahmen sind als Übernahmen gekennzeichnet (§Norm-Prüfung, §Messgrundlage ⚪).
