# Welle 7 / K3 — Mobile-Gate scharfstellen

Karte: `t_072f5d5a` · Issue #431 · Vorgaenger K1 (#615), K2 (#618), K2b (#620), K2c (#621)
Stand: 2026-09-24, gemessen gegen `e0f646c2` (Head von PR #621, K2c).

## Ziel

`e2e-mobile` vom Uebergangszustand (`continue-on-error: true`, nicht in
`all-green.needs`) in ein hartes Gate ueberfuehren — an **beiden** Stellen, die
in diesem Repo zusammen ein Gate ergeben.

## 1. Vorbedingung: drei gruene Vorlaeufe (vor jeder Aenderung erhoben)

Die Karte verlangt **Job-Conclusion**, nicht Run-Conclusion. `gh run list` meldet
fuer alle vier Welle-7-Laeufe `success` auf Run-Ebene — das ist wertlos, weil
`continue-on-error: true` den Run gruen faerbt, auch wenn der Job rot ist.
Gemessen wurde deshalb je Lauf ueber `gh run view <id> --json jobs`:

| Run | Head | `mobile-320` | `mobile-iphone-13` | `tablet-ipad-gen-7` |
|---|---|---|---|---|
| 35928126972 (K1) | `cef6a1f6` | failure | failure | failure |
| 35935193663 (K2) | `f13d41b4` | failure | failure | success |
| 35939748484 (K2b) | `129b7d6e` | failure | failure | success |
| 35944363069 att. 1 (K2c) | `e0f646c2` | **success** | **success** | **success** |
| 35944363069 att. 2 (rerun) | `e0f646c2` | **success** | **success** | **success** |
| 35944363069 att. 3 (rerun) | `e0f646c2` | **success** | **success** | **success** |

Die Zaehlung beginnt wie vom PM verlangt **nach K2c**: B7 (Consent-Banner) und
B8 (Popover-Hoehe) sind zwei verschiedene Defekte, und erst K2c schliesst beide.
Vor `e0f646c2` war kein einziger Lauf auf allen drei Profilen gruen.

**Ehrliche Einschraenkung, die nicht kaschiert wird:** die drei gruenen Laeufe
sind drei *Attempts desselben Commits*, keine drei verschiedenen SHAs — mehr gibt
die Historie nicht her, weil K2c der erste gruene Stand ueberhaupt ist. Was sie
belegen, ist Reproduzierbarkeit (keine Flake), nicht Stabilitaet ueber
Codeaenderungen hinweg. Der erste CI-Lauf dieses PRs ist der vierte Beleg, dann
auf einem anderen SHA.

**Gegenprobe zur PM-Warnung (Gate bewacht keinen kaschierten Defekt):**
`apps/web/e2e/consent-overlay.spec.ts` existiert, ruft `decideCookieConsent`
nicht auf (K2bs gezielter Test ohne weggeraeumtes Banner) und laeuft in allen
drei Mobile-Profilen mit. Die Profile sind also nicht allein durch K2s Helfer
gruen.

## 2. Die zwei Stellen

`all-green` (`ci.yml:736`) urteilt an zwei voneinander unabhaengigen Stellen.
Ein Job nur in `needs` faerbt den Aggregat-Job **nicht** rot — die Pruefzeile
fehlt, also wird der Wert nie gelesen.

1. `needs:` um `e2e-mobile` ergaenzen (`ci.yml:759`).
2. `env: E2E_MOBILE_RESULT` + `expect e2e-mobile … "$gated_expected"` im
   Auswertungs-Step.
3. `continue-on-error: true` am Job entfernen — ohne das meldet der Job
   `success`, selbst wenn Tests fallen, und Punkt 1+2 laufen ins Leere.

`e2e-mobile` haengt wie die fuenf anderen an `if: needs.changes.outputs.code ==
'true'`, gehoert also zur Gruppe mit `gated_expected`, nicht zu `audit` /
`changelog-guard` (die immer laufen muessen).

## 3. Das lokale Werkzeug zieht mit

`scripts/ci/test_all_green_matrix.py` fuehrt `e2e-mobile` in
`UNGATED_BY_DESIGN` — mit der ausdruecklichen Notiz "Wird der Job
scharfgestellt, muss er in `all-green.needs` UND in den Auswertungs-Step
aufgenommen und hier entfernt werden." Genau das passiert hier. `GATED_JOBS` und
`Case.gated` wachsen von fuenf auf sechs Eintraege.

## 4. Roter Beleglauf (Punkt 2 der Karte)

Nicht aus der YAML gelesen, sondern gefahren:

1. Scharfstellen committen, pushen, PR oeffnen → Lauf muss gruen sein.
2. Einen Mobile-Test gezielt brechen, pushen → `e2e-mobile` rot **und**
   `all-green` rot, mit der Zeile `e2e-mobile: 'failure', erwartet 'success'`
   im Log.
3. Bruch zuruecknehmen, pushen → wieder gruen. Der Bruch darf im Enddiff nicht
   stehen.

## 5. Laufzeit (Punkt 3 der Karte)

Baseline aus der Karte (Run 35913678865, gruen auf `main`): `python` 8 min,
`web` 7 min, `e2e` 3 min, `e2e-billing-cloud` 2 min. Kritischer Pfad ist
**Python**.

Gemessen aus Run 35944363069 Attempt 2 (Wall-Clock je Matrix-Leg, alle drei
parallel): `mobile-320` 2:15, `mobile-iphone-13` 2:28, `tablet-ipad-gen-7` 2:40.
Der Job kostet damit **rund 2,5 min** — die Matrix laeuft parallel, die
Wall-Clock-Kosten entsprechen dem langsamsten Leg, nicht der Summe.

**Empfehlung: keine Staffelung.** 2,5 min liegen weit unter den 7 min von `web`
und den 8 min von `python`; der Mobile-Job uebernimmt den kritischen Pfad nicht
einmal annaehernd. Eine Matrix-Sonderregel ("volle Matrix nur auf `main`, auf
PRs nur 320 px") wuerde null Minuten PR-Rueckmeldung sparen und dafuer eine
dauerhafte Sonderregel kosten, bei der auf PRs zwei Profile ungeprueft blieben.
Der Vorschlag wird damit ausdruecklich **nicht** zur Entscheidung vorgelegt,
sondern begruendet abgelehnt; die Zahl steht oben zum Nachmessen.

## 6. `docs/branch-protection-main.md`

Wird **nicht** angefasst. Die Required-Checks-Lage aendert sich durch diese
Karte nicht: Ruleset 16707501 fuehrt weiterhin genau einen Kontext `all-green`,
und `e2e-mobile` wird kein Required Check, sondern haengt an `all-green`. Punkt 4
der Karte ist an "falls sich die Required-Checks-Lage aendert" gebunden — sie
aendert sich nicht.

Der im Dokument stehende ueberholte Satz "Required Checks: **keine**" ist ein
bekannter, bereits laufender Nachzug: PR #619 (Befund B4) zieht genau dieses
Dokument auf den Ist-Zustand. Eine zweite, konkurrierende Aenderung derselben
Tabelle waere ein Konflikt ohne Gewinn.

## Dateibudget

1. `.github/workflows/ci.yml`
2. `scripts/ci/test_all_green_matrix.py`
3. `changelog.d/w7k3-mobile-gate-scharf.changed.md`
4. `.claude/plan/2026-09-24-0430_w7-k3-mobile-gate-scharfstellen.md`

4 von 8.
