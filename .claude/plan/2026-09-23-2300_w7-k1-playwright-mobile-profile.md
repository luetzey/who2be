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

**Bewusst als Vermutung markiert:** das ist aus dem Code gelesen, nicht durch
einen Lauf belegt (siehe "Was NICHT lokal ging"). Wenn es zutrifft, laeuft
dieser Test auf allen vier Profilen im Default-Viewport und sagt ueber
Responsive nichts — er waere also **nicht** mitgezaehlt, wenn K2 die
Mobile-Abdeckung bewertet. Der PR-Lauf kann das entscheiden. Nicht behoben:
Testanpassung gehoert zu K2, nicht hierher.

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

Die Ergebniszahlen je Profil kommen deshalb aus dem **CI-Lauf dieses PRs** —
dem einzigen Ort, an dem der Stack real existiert. Der Job ist genau dafuer als
Matrix gebaut. **Diese Zahlen liegen zum Zeitpunkt der Uebergabe noch nicht
vor**; sie sind aus dem PR-Lauf abzulesen und gehoeren hier nachgetragen, bevor
K3 das Gate scharfstellt. Das ist die ehrliche Luecke dieser Karte.

Erwartungswert, ausdruecklich als Erwartung markiert und nicht als Messung: von
den 12 gelisteten Tests je Profil sind **2** uebersprungen (billing, ohne
`E2E_EDITION=cloud`), **2** ohne `page`-Fixture (siehe B5) und damit
viewport-unabhaengig — bleiben **8** mit echter Responsive-Aussage. Die Zahl
"12 Tests je Profil" ist also groesser als der Erkenntnisgewinn; wer sie
weiterreicht, sollte diese Aufschluesselung mitreichen.

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
