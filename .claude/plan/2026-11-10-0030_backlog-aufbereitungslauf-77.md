# Backlog-Aufbereitungslauf 77

**Datum:** 2026-11-10
**Messpunkt:** `main` @ `f89acf87` (Baum `c751ed64`, `deps(compose): bump caddy in /deploy/monitor (#1097)`)
**Fenster seit dem letzten Messpunkt:** 🔴 **0 Commits, zum dritten Mal in Folge** — `main` steht
seit dem 2026-11-06T08:05:51+01:00 still, **vier Tage**.
**Warteschlange:** #442 (Label `backlog-queue`), Mess-Abschnitte in diesem Lauf neu geschrieben,
Pflege-Regeln 1–56 wörtlich übernommen.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt, selbst
entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit drei Optionen
und Empfehlung stellen, Issue bekommt `needs-decision`. Danach die Warteschlange neu ordnen (harte
Abhängigkeit, Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das
kleinere) und in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — zwölfter Lauf in Folge.** Der Server
verlangt eine Autorisierung, die diese Session nicht selbst anstoßen kann; `get_persona`,
`list_triggers`, `fetch_playbook`, `fetch_resource` (darunter die Norm „Agent-ready Arbeitspaket"),
`record_usage`, `submit_feedback` und `search_memory`/`save_memory` standen nicht zur Verfügung.
Persona und Playbook-Katalog lagen im System-Prompt vor. Der Lauf fährt nach dem reduzierten Kern
des Bootstrap-Skills, nach dem Body von #442 und nach `.github/PROJECT.md` §Constraints.
**Zwölfter Lauf ohne Kurations-Rückmeldung an die eigene AgentDB.**

## Messgrundlage

Alle Werte am 2026-11-10 auf `main` @ `f89acf87` erhoben, sequenziell, **ohne vorherige Reparatur**
(Regel 120), **Exit-Codes am unverketteten Befehl** (Regel 94). Node **v22.23.4**, npm **10.9.9**,
uv **0.11.32**. Klon war shallow (50) → **1676** Commits nach `--unshallow` (Regel 90).

| Gate | Ergebnis |
|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien |
| `uv run pytest --collect-only -q` | **Exit 0**, **5034** Tests |
| `changelog_fragments.py check` | **Exit 0**, **406** Dateien in `changelog.d/` |
| 🔴 `uv tool run pip-audit --disable-pip --no-deps -r <reqs>` | 🔴 **Exit 1** — `oauthlib 4.0.0`, **CVE-2026-49272**, Fix 4.0.1, bei **398** Requirements |
| 🟢 `pip-audit` auf dem **Ergebnisbaum von #1120** | 🟢 **Exit 0**, „No known vulnerabilities found", `oauthlib==4.0.1` |
| `npm run lint` | **Exit 0**, 94 problems, **0 errors**, 7 `--fix`-bar |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** |
| `npm run i18n:check` | **Exit 0** |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, 0 vulnerabilities |
| `npm audit` (voll) | ⚠️ **Exit 1**, 28 moderate (`glob`/`minimatch`, dev-only) |
| 🆕 `npx playwright test --list --project=chromium` | 🟢 **44 Tests in 9 Dateien**; `scroll-guard` allein **15** |
| `npm run test:coverage` | ⚪ **nicht gefahren, mit Grund** (Regel 160: Fenster 0 Commits, `apps/web/src` 0× bewegt) |
| 🔴 `main`-CI am Kopf `f89acf87` | 🔴 Lauf **`42178623925`**, `status: completed` **und** `conclusion: failure` getrennt gelesen (Regel 91) |
| `docker info` | 🔴 **Exit 1** — keine Container-Laufzeit, kein `podman`; **53. Messung in Folge** |

**Fundstellen, einzeln nachgemessen:** `ci.yml` **1259** Zeilen, **12** Jobs, **12 von 12** mit
`timeout-minutes` (über `yaml.safe_load`), `all-green` an **11**; `e2e:` `:422`,
`e2e-billing-cloud:` `:478`, `e2e-mobile:` `:563`, `audit:` `:959`, `all-green:` `:1113`.
`Caddyfile` **208** Zeilen, `rate` **0×**. Betriebs-Pin `caddy:2.11.7-alpine` auf
`deploy/hetzner/who2be/docker-compose.yml:480`, CI-Pins `caddy:2.8-alpine` auf `ci.yml:373`/`:381`/
`:382`/`:397`/`:398`, `deploy/monitor/compose.yml:48` mit `@sha256:eb4d35b7…`.
`docs/mcp-payload-budget.md` **609**; `apps/web/vite.config.ts` **107**;
`apps/web/package.json` **82**; `package-lock.json` **11223**; `osv-scanner.toml` **26**
(`grep -c IgnoredVulns` → **2**); `uv.lock` **3485**; `STATE.md` **3195**;
`.github/PROJECT.md` **179**. `docs/licensing/plans.md:28`/`:29` „100 MB"/„10 GB" gegen
`FREE_STORAGE_QUOTA_BYTES = 100 MiB` / `PRO_STORAGE_QUOTA_BYTES = 10 GiB` ab `:37` (Weiche 9).

## PR-Bestand

🔴 **36 offene PRs** _(waren 26)._ Differenz vollständig erklärt: **+#1127 bis +#1136**, zehn
Dependabot-PRs vom 2026-11-09 (sechs Compose-Image-Bumps, drei npm-Bumps für `apps/web` — darunter
zwei Major —, einer auf `deploy.yml`). **Nichts gemergt, nichts geschlossen — vierter Tag.**

- 🟢 **Alle 36 mergen konfliktfrei** (`merge-tree --write-tree`, rc 0). **Das ist neu:** #674
  kollidierte seit dem Merge von #1114 und ist am 2026-11-09 von Dependabot rebased worden.
- **Gate-alt:** **20 von 36** (am Blob von `ci.yml` im Merge-Base gemessen, Regel 158). Delta
  unverändert **3 Zeilen, dreimal derselbe Action-SHA** (`astral-sh/setup-uv` v10.3.0 → v10.3.3).
- **Check-Lagen selbst gelesen:** **#1120** → **18/18 `success`** (auch `audit` und CodeQL, das in
  Lauf 76 noch `neutral` trug). **#1124** → **18** Checks, **16 success**, rot nur `audit` +
  `all-green`. **#674** → **15** Checks, **8 rot**, davon **7 eigene**.
- 🔴 **Protokoll-Rückstand: 21.** Auf `main` liegen Protokolle für Lauf **31** und **43–55**; für
  **56–76** keines. Zu Lauf **63** existiert nirgends eines (Weiche 38). Dieser Lauf legt das
  **zweiundzwanzigste** dazu.
- 🔴 `.claude/context/STATE.md` auf `main` zuletzt **2026-10-02** (`e39d05eb`) — **39 Tage**,
  dreifach gehalten (#1103/15, #1090/19, #1078/33).

## Die vier Funde des Laufs

### 1. Diese Liste hat gestern über ein Paket behauptet, was sie heute widerlegt — bei 0 Commits

Lauf 76 schrieb in #442 über #632: „🟢 **13 von 13 Zeigern am 2026-11-09 selbst nachgemessen, null
verrottet — zehnter Lauf in Folge.**" Gemessen sind **12 von 13**. §Vorentschieden 3 nennt
`@supabase/supabase-js ^2.117.3` auf `apps/web/package.json:37` mit `auth-js` 2.117.3:

```
$ grep -n "supabase" apps/web/package.json
38:    "@supabase/supabase-js": "^2.118.0",
# Lockfile: node_modules/@supabase/auth-js -> 2.118.0
```

**Drei falsche Werte in einer Zusage.** Zwischen beiden Messungen liegen **null** Commits und
derselbe Baum `c751ed64` — **die Zahl war nicht verrottet, sie war unrichtig.** 🔴 **Und Lauf 76
hat in derselben Nacht Regel 192 aufgeschrieben** („‚Alle Zeiger gültig' ist selbst eine Behauptung
und wird mitgemessen") — **an #633, und die eigene Zusage über #632 nicht gegengerechnet.**
→ **Regel 57**: eine Regel, die nur auf fremde Bodies angewandt wird, schützt den nächsten Lauf
nicht.

### 2. Ein konfliktfreier PR ist kein reparierter PR (Weiche 12, erstmals entscheidbar)

**#674** hat drei Läufe lang `rc 1` getragen, und jeder schrieb, ein Branch-Update sei
„Voraussetzung für jede weitere Aussage über ihn". Nach dem Rebase vom 2026-11-09: **konfliktfrei,
0 hinter `main`.** Die nun mögliche Aussage fällt gegen ihn aus:

| PR | Rückstand | Checks | rot | davon eigene |
|---|---:|---:|---:|---|
| **#674** | 0 | 15 | **8** | 🔴 **7** (`web`, `e2e`, `compose-smoke`, `e2e-billing-cloud`, 3× `e2e-mobile`) |
| **#1124** _(Gegenprobe, dieselbe Fläche)_ | 0 | 18 | 2 | 🟢 **0** (nur `audit` + `all-green`, geerbt) |

**Die Umgebung erklärt den Unterschied nicht, der Inhalt tut es.** → **Regel 58**; Weiche 12
wechselt von Empfehlung **C** auf **B** (schließen).

### 3. Ein Titel ist ein Zeiger, und die Norm-Tabelle sieht ihn nie

**#989s** Titel begründete das Paket mit „dem befristeten osv-scanner-Ignore" für
`http-cache-semantics`. Den hat **#1111** (`af78ad7d`) aus `main` entfernt:

```
$ grep -n "GHSA-ch52-4w7c-c8xp\|http-cache-semantics" apps/web/osv-scanner.toml
$ echo $?
1
```

Übrig sind nur `GHSA-3g3m-2fjr-6pw4` (`:10`) und `GHSA-g3hv-75wg-m249` (`:18`), beide
`ignoreUntil = 2026-11-30`. **Vier Läufe haben die Norm mit 4/4 grün gemeldet, weil sie Abschnitte
zählt — Outcome, AK, Out-of-Scope, Verifikation — und der Titel keiner ist.** 🟢 **Heute
korrigiert**, nur das Titel-Feld. → **Regel 59**.

### 4. Eine Rechnung aus `grep`-Zählungen schließt sich nicht, auch nach drei Läufen

#633 leitet die 44 E2E-Körper her als „42 `^test(`-Zeilen plus 1 `^test.skip(` = 43, davon eine in
einer Schleife über zwei Modi → 44". **Beide Glieder tragen nicht:**

- `scroll-guard.spec.ts:237` ist **eingerückt** und wird vom Anker `^test(` gerade nicht gefangen —
  demselben Anker, den der Body zwei Absätze weiter als Schutz gegen die Zähl-Falle empfiehlt.
- `test.skip(() => !isCloudRun, …)` auf `billing.spec.ts:42` ist eine **Datei-Direktive, die keinen
  Test deklariert** (`playwright --list` auf billing allein: **5 Tests bei 5 `^test(`**).

**Tragfähig ist `42 + 2 = 44`**, und `scroll-guard` hat **15** Körper statt 14 — womit die
`createUser`-Summe **38** ist statt 37. §Verifikation sagt mit `≤ 38` richtig, **Kriterium 4 und
§Startbedingung 7 widersprechen ihr im selben Body.** 🟢 **Der Ausweg ist ein Werkzeug statt eines
Ankers:** `npx playwright test --list` zählt, was zur Laufzeit entsteht, und hat die Frage in einem
Aufruf entschieden. **Wo ein Zähl-Werkzeug existiert, ist ein `grep` die schlechtere Messung.**

## Norm-Stand über alle 12 offenen Issues

Vier Pflichtabschnitte (`.github/PROJECT.md` §Constraints). **Alle vier `agent-ready`-Bodies
tragen 4 von 4.**

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Zeiger | Urteil |
|---|---|---|---|---|---|---|
| **#632** | ✅ | ✅ 5 | ✅ `**Out:**` | ✅ | 🔴 **12/13** | Zeiger-Fund kommentiert |
| **#1001** | ✅ | ✅ 5 | ✅ | ✅ | 🟢 **alle gültig** | 🟢 **defektfrei** |
| **#633** | ✅ | ✅ 6 | ✅ `**Out:**` | ✅ | 🔴 **4 Fehler** | kommentiert, zwei in zweiter Sichtung |
| **#989** | ✅ | ✅ 6 | ✅ | ✅ | 🟢 **alle gültig** | Titel korrigiert, DoD-Widerspruch kommentiert |

🔴 **Der Norm-Befund: die Norm prüft Abschnitte, und drei der vier Fehlerklassen liegen außerhalb
von Abschnitten** — ein Titel, eine Mess-Zusammenfassung im Queue-Body, eine Rechnung, und ein
Widerspruch zwischen DoD und Akzeptanzkriterium.

**Die acht übrigen Bodies** (als übernommen gekennzeichnet, Beleg `updated_at` unverändert):
Outcome fehlt in #542, #535, #428; Verifikations-Abschnitt in #535 und #428; #338 trägt 0 von 4;
Scope-„In" fehlt in #542, #540, #535, #454, #428, #338. **Bewusst nicht umgebaut** (Regel 7,
Weiche 4) — ein `size/M`-Issue wird nie durch Nachtragen von Feldern startbar.

## Was dieser Lauf selbst erledigt hat

🟢 **Kein Paket-Body neu geschrieben — der sparsamste Lauf bisher** (Regel 129/190). Begründung: in
diesem Lauf lag kein Paket-Body als Datei vor, und ein von Hand nachgebauter 25.000-Zeichen-Body
ist genau der Mechanismus, der hier zweimal Inhalt zerstört hat.

| Ziel | Aktion |
|---|---|
| **#989** | 🟢 **Titel korrigiert** (nur das Feld) — Begründung von #1111 aus dem Repo entfernt, `grep` → 0 Treffer |
| **#633** | Kommentar: vier Messfehler mit **exakten Ersetzungen**, zwei davon zweite Sichtung |
| **#632** | Kommentar: der verrottete Supabase-Pin, plus die Widerlegung von „13 von 13" |
| **#989** | Kommentar: Titel-Beleg, DoD-gegen-AK5-Widerspruch, fünffache Datei-Sperre |
| **#1001** | **kein Kommentar, mit Grund** — defektfrei; jeder Kommentar benachrichtigt |
| **#442** | Mess-Abschnitte neu, **Pflege-Regeln 1–56 wörtlich übernommen**, Regeln **57–59** ergänzt, Weichen-Block mit 15 gezielten Ersetzungen aktualisiert |

**Länge vor dem Schreiben geprüft** (Regel 10): die zusammengesetzte Fassung lag bei **66.092
Bytes** und damit über der GitHub-Grenze von 65.536. Gekürzt wurde ausschließlich an der eigenen
Redundanz dieses Laufs, **nicht am Owner-Gedächtnis** — Endstand **64.947 Bytes**.

## Reihenfolge — unverändert, und die zehn neuen PRs sind der Grund, es zu sagen

| Pos | Issue | Kriterium | Zustand |
|---|---|---|---|
| 1 | **#632** Passkey registrieren | 3 (Fundament vor Fläche) | ✅ startbar, Flächen frei |
| 2 | **#1001** Payload-Budget | 4 (Inventar vor Zuschnitt) | ✅ startbar, defektfrei |
| 3 | **#633** Step-up mit Passkey | 1 (harte Abhängigkeit) | hinter #632 **und** Container-Laufzeit |
| 4 | **#989** `http-cache-semantics` | gebremst | Weiche 48 **und** fünffache Datei-Sperre |

**Nichts hat eine Position bewegt:** kein Issue geschlossen, keines neu, keine Weiche beantwortet.
**Die zehn neuen PRs verschieben die Sperren, nicht die Reihenfolge** — `package.json` +
`package-lock.json` halten jetzt **fünf** PRs statt zwei (#989s Fläche), und Weiche 7s Dateien sind
**nicht mehr frei** (#1131), nachdem Lauf 76 sie als „mechanisch umsetzbar" gemeldet hat.

## Wellen

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🔴 **0** _(Owner)_ | **#1120** | **Der CVE-Fix. 18/18 grün, Rückstand 0, konfliktfrei, kein Draft.** Vor allem anderen |
| 🟢 **A** | **#632 + #1001** | **Das echte Parallel-Paar** — Web/Vitest gegen Python/pytest, code-disjunkt, beide Flächen über alle 36 PRs frei. ⚠️ gemeinsame DoD-Fläche `STATE.md` |
| **B** | **#633** | nach #632 (hart) und nach Container-Laufzeit **oder** einzelnen E2E-Job-Conclusions |
| **C** | **#989** | erst **Weiche 48**, dann die Fläche (fünf Schreiber) |
| **M** _(Owner)_ | #1120 → #1124 → #1123 → Compose-Bumps → Domain-Doku | #1131 überschneidet sich mit #1134/#1136 |
| **N** _(Owner)_ | **18 Protokoll-PRs**, beliebige Reihenfolge | danach seriell #1103 → #1090 → #1078 |
| **P** _(Owner)_ | #1107, #1078, #831 durch Branch-Update heilen | erst nach #1120 neu messen |
| 🆕 **Q** _(Owner)_ | **#674** | **entscheidbar; Empfehlung B (schließen)** |
| 🆕 **R** _(Owner)_ | #1128, #1129, #1130 | nach #1124, **einzeln** — #674 ist der Beleg, warum nicht als Gruppe |

🟢 **A ist das echte Parallel-Paar.** 🔴 **Mehr als zwei gleichzeitige Pakete gibt der Backlog nicht
her** — vier offen, zwei blockiert.

## Neue Regeln

- **57 — Diese Liste misst ihre eigenen Zusagen mit, nicht nur die der Paket-Bodies.**
- **58 — Konfliktfreiheit und inhaltliche Gesundheit sind zwei Messungen.**
- **59 — Ein Titel ist ein Zeiger.**

## Offen an den Owner

**32 Weichen, keine neue.** Neu bewertet: **Weiche 12** (#674) wechselt von C auf **B**. Die drei,
die diesen Lauf unmittelbar betreffen:

1. 🔴 **Weiche 11/34 — #1120 mergen.** Rückstand **0**, **18/18 grün**, konfliktfrei, kein Draft,
   Merge-Wirkung **3 Zeilen**. Fünfter Lauf als oberster Posten, `main` den vierten Tag rot.
   **Mergen ist nach Persona-Grenze ohne Freigabe verboten.**
2. 🔴 **Weiche 12 — #674 schließen** (neu: Empfehlung **B**). Konfliktfrei und aktuell, aber 7
   eigene rote Checks; die Gegenprobe #1124 auf derselben Fläche ist 16/18 grün.
3. 🔴 **Weiche 48 — Reihenfolge #1120 → #1124 → #989 und AK2-Sollwert.** Unverändert offen;
   #989s Fläche hält jetzt fünf Schreiber.

## Belege dieses Laufs

- Queue-Issue: **#442** (Mess-Abschnitte neu, Regeln 1–56 wörtlich übernommen, 57–59 ergänzt;
  Länge vor dem Schreiben auf **64.947 Bytes** geprüft, Write per Rücklese-Vergleich verifiziert)
- Titel korrigiert: **#989**
- Kommentiert: **#633**, **#632**, **#989**
- Nicht angefasst, mit Begründung: **#1001** (defektfrei), **#435**, **#428**, **#535**, **#542**,
  **#454**, **#338** (Regel 7, Weiche 4, `human-only`), alle vier Paket-**Bodies** (Regel 129/190)
