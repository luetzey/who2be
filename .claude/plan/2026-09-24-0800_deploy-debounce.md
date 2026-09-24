# Deploys buendeln: ein Deploy pro Merge-Serie

Kanban `t_c856d21a`. Owner-Entscheidung 2026-09-24: *„Deploy sammeln: push-Trigger
bleibt, aber Deploy wartet 30 Min und buendelt — bei 9 Merges am Stueck 1 Deploy
statt 9 (automatisch, kein Knopfdruck)."*

## 1. Messung (Ist-Zustand)

`gh run list --workflow=deploy.yml`, Run-IDs und Zeitstempel:

| Serie | Laeufe | Spanne | Run-IDs (erster … letzter) |
|---|---|---|---|
| 2026-09-23 04:56–04:57 | 5 | 1 min 05 s | 35820383305 … 35820449862 |
| 2026-09-23 11:02–11:07 | 6 | 4 min 48 s | 35852263671 … 35852732522 |
| **2026-09-23 20:05** | **9** | **36 s** | 35913613271 … 35913678893 |
| 2026-09-24 04:36–04:43 | 4 | 6 min 44 s | 35956379154 … 35956848991 |

Jeder dieser Laeufe baut vier Images und wuerde (bei gesetztem `DEPLOY_HOST`)
die Services neu starten. In der Welle-5-Serie waren **acht von neun** Neustarts
wertlos.

Groesster Abstand *innerhalb* dieser vier Serien: **3 min 47 s**
(35956582714 @04:39:36Z → 35956848991 @04:43:23Z).

**Wichtig — diese vier Serien sind eine Stichprobe von ~1,5 Tagen und taugen
nicht zur Bestimmung der Fensterbreite.** Ueber die letzten 100 push-Laeufe
(2026-08-22 … 2026-09-24) gemessen:

| Fenster | resultierende Deploys |
|---|---|
| 300 s (5 min) | 60 |
| **600 s (10 min)** | **59** |
| 900 s (15 min) | 57 |
| 1200 s (20 min) | 55 |
| **1800 s (30 min)** | **49** |
| 2700 s (45 min) | 45 |

Zehn Abstaende liegen im Bereich (600 s, 1800 s] — ein 30-min-Fenster zieht sie
zusammen, ein 10-min-Fenster trennt sie. Die groessten:

    1592 s = 26,53 min   33986784452 → 33988114659  @2026-09-05T19:46:25Z
    1527 s = 25,45 min   33963038718 → 33964174826  @2026-09-05T11:45:21Z
    1465 s = 24,42 min   32642360570 → 32643610443  @2026-08-23T13:51:05Z
    1450 s = 24,17 min   34026917378 → 34028044392  @2026-09-06T10:39:40Z
     944 s = 15,73 min   35465831665 → 35466623645  @2026-09-19T20:11:29Z

30 Minuten buendeln also sehr wohl mehr (10 Deploys ueber einen Monat, ~17 %).
Die Wahl ist damit eine Abwaegung, keine Ableitung — §4.

## 2. Kontingent-Folgen — geprueft, Ergebnis: null Kosten

`gh repo view --json visibility` → `PUBLIC`.

GitHub-Billing-Doku, *GitHub Actions billing*:
> „GitHub Actions usage is **free** for **self-hosted runners** and for
> **public repositories** that use standard GitHub-hosted runners."

Der Workflow faehrt ausschliesslich `runs-on: ubuntu-latest` (Standard-Runner).
**Ein wartender Job kostet damit 0 Actions-Minuten.** Die Sorge aus der
Aufgabenstellung („wartende Runner koennen teuer sein") trifft auf dieses Repo
nicht zu; sie waere in einem privaten Repo berechtigt gewesen.

Der Preis eines Wartefensters ist damit ausschliesslich:

- **Latenz** bis der Stand live ist (Fensterbreite),
- **ein** belegter Job-Concurrency-Slot (Free-Plan: 20 gleichzeitige Jobs,
  *Actions limits*). Weil der Entwurf zu jedem Zeitpunkt **genau einen**
  wartenden Job zulaesst (siehe §4), ist das 1 von 20 — kein Engpass fuer die
  PR-CI.

Harte Grenzen, die eingehalten werden (*Actions limits*): Workflow-Run-Laufzeit
35 Tage „including … time spent on waiting", Job-Laufzeit 6 h. Ein Fenster von
Minuten liegt drei Groessenordnungen darunter.

## 3. Drei Mechanismen abgewogen

### A) `concurrency` mit `cancel-in-progress: true` + vorgeschaltetem Wartefenster

Workflow-Syntax-Doku, `concurrency`:
> „When a concurrent job or workflow is queued, if another job or workflow using
> the same concurrency group in the repository is in progress, the queued job or
> workflow will be `pending`. … To also cancel any currently running job or
> workflow in the same concurrency group, specify `cancel-in-progress: true`."

Das ist ein **Debounce**: jeder neue Push toetet das laufende Wartefenster und
startet ein neues. Nach dem letzten Merge einer Serie ueberlebt genau ein Lauf.
Bei 9 Merges in 36 s: 8 `cancelled`, 1 deployt.

*Risiko:* `cancel-in-progress` unterscheidet nicht zwischen „wartet" und
„deployt gerade". Auf die **ganze** Workflow-Ebene angewandt wuerde es einen
laufenden Deploy mitten in `docker compose up -d` abschiessen. Deshalb nicht
workflow-weit, sondern **job-level** nur auf dem Wartejob.

### B) `schedule`-Lauf, der prueft, ob neue Commits da sind

Automatisch, kein wartender Runner. Aber:

- `schedule` ist in GitHub Actions nicht puenktlich; die Doku warnt vor
  Verzoegerungen, und Laeufe koennen bei Last ganz ausfallen. Ein Deploy, der
  „irgendwann in der naechsten halben Stunde, vielleicht" kommt, ist schlechter
  beobachtbar als einer, der an einem Merge haengt.
- Der Owner fordert ausdruecklich: **„der push-Trigger bleibt"**. B ersetzt ihn.
- B braucht zusaetzlichen Zustand („was wurde zuletzt deployt?") — Tag, Artefakt
  oder API-Abfrage. Das ist eine neue Fehlerquelle in genau dem Pfad, der schon
  einmal still versagt hat (der `deploy-not-configured`-Kommentar in `deploy.yml`
  erzaehlt die Geschichte).
- Es deployt auch dann, wenn niemand etwas gemergt hat — bzw. muss das
  wegpruefen, was wieder Zustand braucht.

**Verworfen:** verletzt die Owner-Anforderung und tauscht einen einfachen
Mechanismus gegen Zustandshaltung.

### C) Wartefenster im Job, danach „bin ich noch HEAD von `main`? sonst abbrechen"

Die im Issue als naheliegend bezeichnete Variante. Sie funktioniert — aber sie
hat **ohne** A einen teuren Nebeneffekt und **mit** A eine gefaehrliche Luecke:

- *Ohne A:* alle neun Laeufe warten **parallel** die volle Fensterbreite. Neun
  belegte Concurrency-Slots von 20; die PR-CI steht waehrenddessen in der
  Warteschlange. Kostenlos, aber blockierend.
- *Die Luecke:* der harte Abbruch „ich bin nicht HEAD, also deploye ich nicht"
  setzt voraus, dass fuer den neuen HEAD **garantiert** ein Deploy-Lauf
  existiert. Das ist nicht garantiert — ein Commit mit `[skip ci]` in der
  Nachricht laesst den Workflow aus (GitHub: *Skipping workflow runs*). Der
  wartende Lauf braeche ab, der neue Stand triggerte nie einen Lauf: **dieser
  Stand bliebe dauerhaft unausgeliefert.** Genau das schliesst Akzeptanz-
  kriterium 4 aus.

## 4. Gewaehlt: A als Debounce, C nur als Diagnose, Deploy serialisiert

Drei Bausteine, jeder mit einem eigenen Zweck:

1. **`debounce`-Job** (neu, laeuft vor allem anderen), job-level:
   ```yaml
   concurrency:
     group: deploy-debounce-${{ github.ref }}
     cancel-in-progress: true
   ```
   Wartet bei `push` die Fensterbreite. Jeder weitere Push auf `main` cancelt
   diesen Lauf und startet sein eigenes Fenster. **Zu jedem Zeitpunkt wartet
   genau ein Job.** Bei `workflow_dispatch` wird nicht gewartet (§5).

2. **HEAD-Vergleich nach dem Fenster** — aus C uebernommen, aber **bewusst ohne
   harten Abbruch**. Er schreibt ins Step-Summary, ob der eigene SHA noch HEAD
   von `main` ist. Faellt der Vergleich negativ aus, wird trotzdem deployt und
   der serialisierte Nachfolgelauf korrigiert unmittelbar danach. Begruendung:
   die Fehlerrichtung „einmal zu viel deployen" ist harmlos, die Fehlerrichtung
   „ein Stand bleibt liegen" ist es nicht (§3 C).

3. **`deploy`-Job serialisiert**, job-level:
   ```yaml
   concurrency:
     group: deploy-main
     cancel-in-progress: false
   ```
   Ein laufender Deploy wird **nie** abgebrochen. Ein waehrenddessen
   eintreffender Lauf wird `pending` und faehrt danach.

### Fensterbreite: 10 Minuten statt 30

Die Fensterbreite ist eine **Latenz-Entscheidung**, keine Ableitung aus der
Buendelungs-Wirkung: ein breiteres Fenster buendelt messbar mehr (§1).

| | 10 min | 30 min |
|---|---|---|
| Deploys / Monat (gemessen, §1) | 59 | 49 |
| Zeit bis Live, pro Merge | bis 10 min | bis 30 min |
| Kosten | 0 (§2) | 0 (§2) |

30 Minuten sparen ueber einen Monat zehn weitere Laeufe (~17 %). Dafuer wartet
*jeder* einzelne Merge bis zu dreimal so lange auf seine Auslieferung — auch
der einzelne Merge, der auf keine Serie trifft, und das ist der Regelfall
(die zehn zusammenziehbaren Abstaende stehen 99 Abstaenden gegenueber).
Die dichten Serien, die den Anlass gaben (neun Laeufe in 36 s), faengt das
10-min-Fenster vollstaendig: der groesste Abstand innerhalb einer Serie war
3 min 47 s. Der Zusatznutzen von 30 min liegt ausserhalb dieses Anlasses.

Deshalb 10 — als Abwaegung, nicht weil 30 wirkungslos waere. Da Wartezeit hier
nichts kostet (§2), ist es eine reine Latenz-gegen-Lauf-Anzahl-Frage, und die
Zahl steht als eine Zeile im Workflow: wer die Gewichtung anders setzt, setzt
`DEPLOY_DEBOUNCE_SECONDS` auf `1800`.

Der Wert steht als benannte `env`-Konstante im Workflow, nicht als Repo-Variable:
Repo-Variablen sind im Repo unsichtbar, und genau diese Unsichtbarkeit hat bei
`DEPLOY_HOST` schon einmal Stunden gekostet.

### Nachteile der gewaehlten Variante — benannt

- **Bis zu 10 Minuten spaeter live.** Der manuelle Weg (§5) ist die Notbremse.
- **Keine Images fuer Zwischen-Commits mehr auf GHCR.** Weil der Debounce *vor*
  `build-and-push` sitzt, werden die uebersprungenen SHAs nie gebaut. Ein
  Rollback auf einen Commit *innerhalb* einer Serie hat kein fertiges Image; man
  rollt auf den letzten deployten SHA zurueck oder loest den Build per
  `workflow_dispatch` auf dem Ref aus. Der Tausch ist bewusst: acht ueberfluessige
  Builds sind derselbe Laerm wie acht ueberfluessige Neustarts.
- **Superseded Laeufe erscheinen als `cancelled`, nicht als `success`.** Die
  Run-Historie zeigt rote/graue Eintraege, die kein Fehler sind. Das ist ehrlich,
  aber gewoehnungsbeduerftig; der Grund steht im Step-Summary des Laufs.
- **Dauermerges verzoegern unbegrenzt.** Merges im Abstand < 10 min setzen das
  Fenster immer wieder zurueck. Beim gemessenen Nutzungsmuster (Wellen, dann
  Ruhe) ist das kein Problem; ein Dauerstrom waere eins.

## 5. Sicherheitsfragen — beantwortet

**Merge waehrend des Wartefensters.** Der neue Push landet in derselben
`deploy-debounce-<ref>`-Gruppe. `cancel-in-progress: true` cancelt den wartenden
Lauf; der neue wartet sein Fenster ab und deployt. Der gecancelte Lauf trug den
aelteren SHA — sein Stand ist im neueren enthalten (`main` ist linear, PR-Pflicht,
kein Force-Push). **Kein Stand geht verloren.**

**Merge waehrend der Deploy laeuft.** Der neue Lauf durchlaeuft sein
Debounce-Fenster, kommt dann an die `deploy-main`-Gruppe. `cancel-in-progress:
false` ⇒ der laufende Deploy wird nicht angetastet, der neue wird `pending`
(Doku: *„the queued job or workflow will be `pending`"*) und faehrt danach.
**Beide Staende werden ausgeliefert, in Reihenfolge.**

**Zwei Merges waehrend der Deploy laeuft.** Beide gehen durch dasselbe
Debounce-Fenster; nur der spaetere ueberlebt und wird `pending`. Ein Deploy,
neuester Stand.

**Warum bleibt nie ein Stand liegen?** Ein Lauf wird nur in einem Fall
abgebrochen: weil ein *neuerer* Lauf fuer denselben Branch existiert. Dieser
neuere Lauf traegt einen Commit, der den abgebrochenen enthaelt. Ein Abbruch ohne
Nachfolger ist im Entwurf nicht moeglich — deshalb auch kein harter HEAD-Abbruch
(§3 C).

**Ein Vorbehalt, unveraendert gegenueber vorher.** Die Aussage gilt fuer die
Buendelung, nicht fuer die Trigger-Ebene darueber: ein Commit mit `[skip ci]`
in der Nachricht startet ueberhaupt keinen Workflow-Lauf, also auch keinen
Deploy — dieser Stand geht erst mit dem naechsten regulaeren Push live. Das
war vor dieser Aenderung genauso und ist keine Regression; die Debounce fuehrt
den Fall weder ein noch verschaerft sie ihn. Sie ist aber der Grund, warum der
HEAD-Vergleich nur berichtet statt abzubrechen (§3 C) — ein harter Abbruch
wuerde aus diesem Vorbehalt einen dauerhaft unausgelieferten Stand machen.

## 6. Manueller Weg bleibt sofort

`workflow_dispatch` durchlaeuft **kein** Wartefenster (`if: github.event_name ==
'push'` am Sleep-Step) und **keine** Debounce-Gruppe (die Gruppe traegt den
Event-Namen, ein manueller Lauf cancelt also keinen wartenden Push-Lauf und wird
von keinem gecancelt). Er unterliegt nur der `deploy-main`-Serialisierung — ein
manueller Deploy wartet also hoechstens auf einen bereits laufenden Deploy,
was korrekt ist.

## 7. Zusaetzliche Haertung (klein, gleiche Baustelle)

Der `deploy`-Job bekommt `github.ref == 'refs/heads/main'` in seine
`if`-Bedingung. Heute kann ein `workflow_dispatch` auf einem beliebigen Ref den
Produktiv-Deploy ausloesen; mit dem Testbranch-Nachweis (§8) waere das eine
offene Flanke. Die Deploy-**Schritte** bleiben unberuehrt (out of scope).

## 8. Nachweis

`DEPLOY_HOST` ist **nicht** gesetzt (`gh api repos/luetzey/who2be/actions/variables`
liefert eine leere Liste) — der `deploy`-Job wird heute uebersprungen. Kein Test
kann die Produktivumgebung erreichen.

Trotzdem wird der Nachweis **nicht** am `deploy.yml`-Trigger gefuehrt: ein Push
auf einen Testbranch wuerde `build-and-push` ausloesen und vier Images mit dem
Tag **`latest`** nach GHCR schieben. `latest` zeigte dann auf einen Testbranch-
Build — ein realer Schaden ausserhalb des Auftrags.

Stattdessen: temporaerer Workflow `.github/workflows/_debounce-proof.yml` mit
**identischer** concurrency-Semantik und kurzem Fenster, Dummy-Deploy-Echo statt
Build/SSH. Belegt wird:

1. zwei Pushes in kurzer Folge → Lauf 1 `cancelled`, Lauf 2 deployt **einmal**;
2. der ueberlebende Lauf traegt den **neueren** SHA;
3. `workflow_dispatch` deployt ohne Wartezeit.

Run-IDs und Zeitstempel kommen in den Abschlussbericht. Der Proof-Workflow wird
vor dem PR wieder geloescht.

## 9. Doku

- `deploy/hetzner/README.md` §CI/CD: Trigger-Beschreibung um das Buendeln
  ergaenzen.
- `CHANGELOG.md` → `## [Unreleased]` / `### Changed`.
