# Welle 7 / K1 — Playwright-Mobile-Profile anlegen (noch ohne CI-Gate)

**Karte:** t_e75f14b9 · **Basis:** `origin/main` @ `116bfcd2`
**Branch:** `who2be/t_e75f14b9-welle-7-k1-playwright-mobile-profile-anl`

## Ziel

`apps/web/playwright.config.ts` fuehrt vier statt einem Projekt. Die neuen drei
laufen in CI, blockieren aber keinen PR. Was sie finden, wird **gemeldet**,
nicht gefixt.

## Ist-Zustand (selbst nachgezaehlt, nicht uebernommen)

- `apps/web/playwright.config.ts@116bfcd2` fuehrte genau ein Projekt:
  `{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }`. Bestaetigt.
- Kein `webServer`-Block (Kommentar im Kopf der Datei begruendet das: Stack
  laeuft extern per Compose). Bestaetigt.
- Testmenge: `journeys.spec.ts` **6**, `public.spec.ts` **4**,
  `billing.spec.ts` **2** (Datei-Skip via `test.skip(...)` ohne
  `E2E_EDITION=cloud`). Gegen die Karte praezisiert: `--list` meldet
  **12 Tests in 3 Dateien** je Profil, nicht 10 — `billing.spec.ts` wird
  gelistet und erst zur Laufzeit uebersprungen.
- `all-green` hatte acht Eintraege in `needs:` — die Karte sagt "neun", die
  aufgezaehlte Liste enthaelt acht. Gezaehlt, nicht uebernommen.
- Die Kartenangabe "zwei der sechs Journeys ohne `page`-Fixture" ist
  **richtig** (ich hatte zunaechst falsch gezaehlt): `Agent-Read ...`
  (`{ request }`) und `Invitation-Accept ...` (`{ browser, request }`).

## Fuenf Befunde aus der Messung

### B1 — Die 320-px-Praemisse der Karte ist widerlegt

Die Karte sagt: *"kein `devices`-Preset trifft 320 px exakt"*. Ausgezaehlt ueber
`Object.keys(devices)` der installierten Playwright-Version: von **207** Presets
tragen **drei** exakt Breite 320 — `Galaxy S9+`, `iPhone SE`,
`Nokia Lumia 520`.

Der eigene Viewport bleibt trotzdem die richtige Wahl, aber aus einem anderen
Grund als dem in der Karte genannten: jedes dieser Presets bringt zusaetzlich
einen Geraete-User-Agent, einen eigenen DPR und eine feste Hoehe mit. Getestet
werden soll die **Layout-Untergrenze**, nicht ein bestimmtes Altgeraet. Die
Begruendung steht so auch im Code, damit sie nicht wieder als "es gibt kein
Preset" weitergereicht wird.

### B2 — Beide Presets verlangen WebKit, CI installiert nur Chromium

`devices['iPhone 13']` und `devices['iPad (gen 7)']` tragen beide
`defaultBrowserType: "webkit"`. Der CI-Schritt installiert genau einen Browser
(`apps/web/package.json`, Skript `e2e:install`:
`playwright install --with-deps chromium`).

Ohne Gegenmassnahme waeren **alle drei neuen Profile sofort rot** — wegen einer
fehlenden Browser-Binary, nicht wegen eines Responsive-Defekts. Genau die Sorte
Rot, die einen echten Befund unsichtbar macht. Deshalb setzen alle drei Profile
explizit `browserName: 'chromium'`; Viewport-, Touch- und DPR-Emulation kommen
unveraendert aus dem Preset.

### B3 — Die Kartenvorgabe kollidierte mit einer bestehenden Zusicherung

Die Karte schreibt vor, den neuen Job **nicht** in `all-green.needs`
aufzunehmen. `scripts/ci/test_all_green_matrix.py#check_structure` verlangte
jedoch das Gegenteil, woertlich:

> `missing = [name for name in jobs if name != "all-green" and name not in needs]`

Beides zugleich ging nicht. Geprueft, ob das ein CI-Gate ist: **nein** — kein
Workflow-Step ruft das Skript auf, und `pyproject.toml` sammelt unter
`testpaths` nur `scripts/tests`, nicht `scripts/ci`. Es ist ein lokales
Werkzeug.

Die Kartenvorgabe ist die wirksame und damit richtige (`all-green` urteilt nur
ueber seine `needs`-Liste). Sie haette das Werkzeug aber dauerhaft rot
hinterlassen — eine Kaputtheit, die ich selbst verursacht haette. Deshalb
nachgezogen: `UNGATED_BY_DESIGN` benennt die Ausnahme **mit Begruendung**, und
die Liste ist selbst geprueft, damit sie kein Freifahrtschein wird:

- Job muss existieren (sonst: Eintrag entfernen),
- darf nicht in `needs` stehen (sonst: scharfgestellt, Eintrag loeschen),
- muss `continue-on-error: true` fuehren.

Die dritte Bedingung ist der Kern: ohne sie waere ein **vergessener** Job von
einem **absichtlich** nicht verdrahteten nicht mehr zu unterscheiden. Belegt
durch Negativprobe (siehe Verifikation).

### B4 — `docs/branch-protection-main.md` ist ueberholt

Das Papier fuehrt sich als *"Status: Vorschlag. Nicht angewendet."* und nennt
"Required Checks: **keine**" (Stand 2026-09-22). Live gemessen am 2026-09-23
via `gh api repos/luetzey/who2be/rulesets/16707501`:

```json
{"enforcement":"active","rules":[{"type":"required_status_checks",
  "checks":[{"context":"all-green"}]}]}
```

Das Ruleset ist **scharf**, `all-green` ist der einzige Required Check. Die
Aussage der Karte stimmt also — aber die im Repo liegende Doku belegt sie nicht
mehr. Der Code-Kommentar zitiert deshalb die Live-Quelle, nicht das Papier.
**Als Befund gemeldet, nicht behoben** (Doku-Nachzug ist nicht Scope).

### B5 — Fuer K2: `browser.newContext()` erbt den Projekt-Viewport nicht

`Invitation-Accept inkl. Email-Mismatch-Guard` nimmt keine `page`-Fixture,
sondern baut seine Seiten selbst ueber `browser.newContext()` /
`context.newPage()`. Nach Playwright-Verhalten wendet die `page`-Fixture die
`use`-Optionen des Projekts an — ein selbst erzeugter Context bekommt sie nicht
automatisch.

**Nachtrag aus dem CI-Lauf — die Vermutung ist widerlegt.** Der Test faellt auf
`mobile-320` mit derselben `intercepts pointer events`-Meldung wie die
`page`-basierten Journeys (siehe B7). Ein selbst erzeugter Context uebernimmt
die Projekt-`use`-Optionen also sehr wohl — sonst haette er im Default-Viewport
gelaufen und das Banner haette nichts verdeckt. Auf `mobile-iphone-13` und
`tablet-ipad-gen-7` besteht er, weil dort mehr Platz ist. Er ist damit
viewport-**abhaengig** und zaehlt fuer K2 mit.

Die urspruengliche Vermutung steht hier bewusst stehen: sie war aus dem Code
plausibel und hat sich an der Messung als falsch erwiesen. Wer sie ungeprueft
weitergereicht haette, haette einen aussagekraeftigen Test faelschlich als
"sagt nichts ueber Responsive" abgeschrieben.

## Umsetzung

### Projektnamen (verbindlich fuer K2)

| Name | Basis | Viewport |
|---|---|---|
| `chromium` | `devices['Desktop Chrome']` | 1280x720 |
| `mobile-iphone-13` | `devices['iPhone 13']` + `browserName: chromium` | 390x664, DPR 3, Touch |
| `tablet-ipad-gen-7` | `devices['iPad (gen 7)']` + `browserName: chromium` | 810x1080, DPR 2, Touch |
| `mobile-320` | `devices['iPhone 13']`, Viewport ersetzt | 320x568, Touch |

### CI

Neuer Job `e2e-mobile`, Klon des `e2e`-Jobs mit `strategy.matrix.project` ueber
die drei neuen Namen, `fail-fast: false` und `continue-on-error: true`. Matrix
statt Sammellauf, weil die Karte Ergebniszahl **und** Laufzeit **je Profil**
verlangt — beides ist so direkt aus der Job-Liste ablesbar. `fail-fast: false`,
damit ein rotes Profil die beiden anderen nicht abschneidet und genau die
Zahlen fehlen, die erhoben werden sollen.

Nicht-blockierend an zwei Stellen: nicht in `all-green.needs` (wirksam) und
`continue-on-error: true` (sichtbare Absicht).

## Verifikation

### Lokal ausgefuehrt

| Pruefung | Ergebnis |
|---|---|
| `playwright test --project=chromium --list` | `Total: 12 tests in 3 files` |
| `--project=mobile-iphone-13 --list` | `Total: 12 tests in 3 files` |
| `--project=tablet-ipad-gen-7 --list` | `Total: 12 tests in 3 files` |
| `--project=mobile-320 --list` | `Total: 12 tests in 3 files` |
| `playwright test --list` (alle vier) | `Total: 48 tests in 3 files` |
| `test_all_green_matrix.py` | `Alle 14 Faelle und die Struktur-Zusicherungen wie erwartet` |
| `changelog_fragments.py check` | 26 Fragmente in Ordnung |
| `ruff check` / `ruff format --check` / `mypy` (geaenderte Datei) | gruen |
| `check_code_refs.py` | 0 `error` in den geaenderten Dateien |

Damit ist "vier Projekte, jedes einzeln startbar" belegt — nicht behauptet.

### Negativprobe zur neuen Zusicherung

Eine Zusicherung, die nie rot wird, sichert nichts zu. Probeweise gebrochen und
zurueckgesetzt (`diff` gegen die Sicherungskopie bestaetigt die
Rueckgaengigmachung, danach wieder gruen):

- `continue-on-error` auf `false` gesetzt → `FAIL Struktur: 'e2e-mobile' ist
  als bewusst nicht-blockierend gelistet, fuehrt aber kein
  continue-on-error: true.`

## Was NICHT lokal ging, und warum

Der dokumentierte **Lauf** je Profil (Akzeptanzkriterium 2) braucht den
Compose-Stack. Auf dem Arbeitshost ist Docker nicht vorhanden:
`docker: command not found`, `systemctl is-active docker` = `inactive` (nur
`podman` liegt unter `/usr/sbin/podman`, ohne laufenden Dienst).

Die Ergebniszahlen je Profil kommen deshalb aus dem CI-Lauf des PRs. Sie liegen
inzwischen vor — siehe naechstes Kapitel.

## Laufprotokoll (CI-Run 35921243967, PR #615, Head `f951802f`)

### Bestaetigungslauf nach der Korrektur (Run 35923328598, Head `e486298a`)

Der zweite Lauf belegt beide Haelften der Akzeptanz zugleich:

| Job | Ergebnis | Dauer |
|---|---|---|
| `e2e` (Desktop-Gate) | **success** | 2:36 |
| `e2e-mobile (mobile-iphone-13)` | failure | 5:24 |
| `e2e-mobile (tablet-ipad-gen-7)` | failure | 5:04 |
| `e2e-mobile (mobile-320)` | failure | 6:46 |
| **`all-green`** | **success** | — |

`all-green` ist **gruen, obwohl alle drei Mobile-Jobs rot sind**. Damit ist
nicht bloss behauptet, sondern am laufenden System bewiesen, dass die neuen
Profile melden und keinen PR blockieren.

`e2e` liegt mit 2:36 wieder auf Baseline-Niveau (3 min) — die Regression aus
B6 ist nachweislich weg, nicht nur im Diff korrigiert.

### Ergebniszahlen je Profil

| Profil | passed | failed | skipped | Dauer |
|---|---|---|---|---|
| `chromium` (Job `e2e`) | — | — | — | siehe B6 |
| `mobile-iphone-13` | 8 | 2 | 2 | 3.2 min (Job 5:09) |
| `tablet-ipad-gen-7` | 8 | 2 | 2 | 3.2 min (Job 5:21) |
| `mobile-320` | 7 | 3 | 2 | 4.6 min (Job 6:31) |

Die 2 `skipped` sind je Profil `billing.spec.ts` ohne `E2E_EDITION=cloud` —
wie erwartet. Damit ist die Erwartung aus der Vorab-Schaetzung bestaetigt: von
12 gelisteten Tests sind 10 wirklich gelaufen.

### B6 — Regression am scharfen Gate, gefunden und behoben

Der `e2e`-Job meldete **33 passed / 7 failed = 40 Tests** statt der erwarteten
12. Ursache: `npm run e2e` ruft `playwright test` **ohne** `--project` auf —
das faehrt ALLE Projekte der Config. Solange es ein Projekt gab, war das
harmlos; mit vieren zog das scharfe Desktop-Gate die noch meldenden
Mobile-Profile in eine blockierende Rolle. Der Job heisst weiterhin `e2e` und
sieht unveraendert aus — der Fehler war lautlos.

Das ist genau das, was diese Karte NICHT tun darf (das waere faktisch K3, an
`e2e-mobile` vorbei). Behoben: der `e2e`-Job ruft jetzt explizit
`--project=chromium`.

Damit es nicht wiederkommt, steht es als Zusicherung statt als Kommentar:
`check_playwright_projects` in `scripts/ci/test_all_green_matrix.py` weist
jeden Workflow-Step zurueck, der Playwright ohne `--project` (und ohne
konkreten Spec-Pfad) aufruft. Per Negativprobe belegt: Filter entfernt → `FAIL
Struktur: Job 'e2e': Playwright wird ohne --project aufgerufen`; zurueckgesetzt
→ gruen.

### B7 — Echter Responsive-Defekt: Cookie-Banner deckt Formular-Aktionen ab

Auf **allen drei** neuen Profilen scheitern dieselben Journeys mit
`Test timeout of 30000ms exceeded` beim Klick auf Submit-Buttons. Playwright
nennt den Grund woertlich:

> `<div role="region" aria-label="Cookie consent" …> from
> <div class="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center p-4">…</div>
> subtree intercepts pointer events`

Das Consent-Banner liegt fix am unteren Rand und ueberdeckt auf schmalen
Viewports die Aktionsleiste der Formulare. Auf Desktop (1280x720) ist genug
Platz, deshalb faellt es dort nie auf. Betroffen: `Persona-Lifecycle`,
`Playbook->Resource-Block-Ref`, zusaetzlich auf `mobile-320` noch
`Invitation-Accept`.

**Ist das ein Anwendungs- oder ein Testdefekt?** Beides ist vertretbar
begruendbar, und die Karte verlangt ausdruecklich, das zu unterscheiden statt
zu fixen:

- **Anwendungsseite:** Ein Consent-Banner, das auf einem 390-px-Geraet den
  primaeren Button eines Formulars unerreichbar macht, ist ein echter
  Bedienbarkeits-Defekt — ein Nutzer ohne Consent-Klick kaeme dort nicht
  weiter. Das spricht dafuer, dass hier die Anwendung falsch liegt.
- **Testseite:** Kein E2E-Test dismisst das Banner vorab. Auf Desktop war das
  folgenlos, also fiel die Luecke nie auf.

Meine Einschaetzung: **primaer Anwendung, sekundaer Test.** Beides **gemeldet,
nicht behoben** — Anwendungsdefekte sind ausdruecklich out of scope, und die
Testanpassung (Banner dismissen) gehoert zu K2.

### Laufzeit gegen die Baseline

Baseline (Run `35913678865`): `e2e` 3 min, `python` 8 min, `web` 7 min,
Wall-Clock ~9 min.

Gemessen: die drei `e2e-mobile`-Jobs starten gleichzeitig (alle 21:15:09/10) und
enden nach 5:09 / 5:21 / 6:31. Die **Wall-Clock-Kosten des neuen Jobs betragen
also 6:31**, nicht die Summe von 17 min — die Parallelitaets-Erwartung ist
bestaetigt. Sie liegen damit unter der von der Karte gesetzten Obergrenze von
etwa 7 min und ueber der `e2e`-Baseline von 3 min; der Aufschlag kommt aus dem
zusaetzlichen Compose-Build je Matrix-Job, nicht aus der Testdauer selbst
(3.2–4.6 min).

Der kritische Pfad bleibt `python`/`web`. **Eine Staffelung ist nach dieser
Messung nicht noetig** — die Vorschlaege unten bleiben als Reserve stehen,
falls die Runner-Minuten (3x Compose-Build) stoeren. Entscheidung liegt beim
Owner.

## Laufzeit

**Baseline** (Run `35913678865`, gruen auf `main`): `e2e` 3 min,
`e2e-billing-cloud` 2 min, `python` 8 min, `web` 7 min, Wall-Clock ~9 min.
Kritischer Pfad ist `python`, nicht `e2e`.

**Erwartung fuer `e2e-mobile`:** Die drei Matrix-Jobs laufen parallel, jeder
gegen einen eigenen Compose-Stack. Die Wall-Clock-Kosten entsprechen damit dem
**langsamsten Profil**, nicht der Summe — grob der `e2e`-Dauer von 3 min, nicht
9 min. Die Summe der Runner-**Minuten** verdreifacht sich hingegen (3x
Compose-Build, 3x `npm ci`, 3x Browser-Install). Der kritische Pfad bleibt
`python` mit 8 min; die PR-Rueckmeldung wird dadurch voraussichtlich **nicht**
langsamer. Zu pruefen am PR-Lauf.

**Zur Entscheidung durch den Owner, von mir NICHT entschieden:** Sollte sich im
PR-Lauf zeigen, dass die Runner-Minuten stoeren, sind das die Staffelungen — in
der Reihenfolge, wie ich sie empfehlen wuerde:

1. **Volle Matrix nur auf `main`**, auf PRs nur `mobile-320` — der schmalste
   Viewport bricht am ehesten zuerst.
2. **Ein Stack fuer alle drei Profile** statt Matrix
   (`--project=a --project=b --project=c`). Spart zwei Compose-Builds, kostet
   aber die getrennte Laufzeitmessung je Profil — also genau das, was diese
   Karte erheben soll. Erst nach K3 sinnvoll.
3. **Nur `public.spec.ts` auf den Mobile-Profilen.** Billigste Variante,
   kleinster Erkenntnisgewinn.

Keine davon ist umgesetzt. Die Messung im PR-Lauf entscheidet, ob sie
ueberhaupt gebraucht werden.

## Out of Scope (eingehalten)

Gate scharfstellen (K3). Anwendungsdefekte beheben. BlockNote (K4).
Doku-Nachzug an `docs/branch-protection-main.md` (B4 — gemeldet, nicht behoben).
Testanpassung fuer B5 (gehoert zu K2).

## Geaenderte Dateien (4 von max. 8, plus diese Plan-Datei)

1. `apps/web/playwright.config.ts` — drei Projekte
2. `.github/workflows/ci.yml` — Job `e2e-mobile`
3. `scripts/ci/test_all_green_matrix.py` — `UNGATED_BY_DESIGN` + Selbstpruefung
4. `changelog.d/w7k1-playwright-mobile-profile.added.md`
