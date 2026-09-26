# STATE.md-Konflikte: Messung und Urteil (t_6324bea8)

_Stand: 2026-09-24 — Messfenster `2d957f3d..09a322a9` (letzte 60 first-parent-Commits
auf `origin/main`), offene PRs zum Messzeitpunkt: #618, #619, #620, #621, #622, #626, #420._

**Urteil in einem Satz: Ein Fragment-Verfahren für `STATE.md` lohnt sich nicht —
die Anhängsel-Kollision existiert, ist aber sichtbar und trivial auflösbar,
während die teurere Hälfte der Änderungen (Bestands-Umbauten) ein Fragment
ohnehin nicht abbilden kann; die echte Konfliktlast liegt in
`.github/workflows/ci.yml` und den Lockfiles.**

Diese Karte durfte mit „lohnt nicht, weil X" enden. Das ist der Fall. Gebaut wurde
deshalb nichts: kein `state.d/`, kein Skript, kein Guard.

Zwei Befunde stehen bewusst gegen den bequemen Erzählbogen dieses Berichts und
sind in §7.1 ausführlich belegt: `STATE.md` kollidiert **nicht** in den
aktuellen offenen PRs — aber zwei Karten, die beide einen Nachtrag unter die
`_Stand:_`-Zeile setzen, kollidieren dort **doch**, und dieser Lauf hat es an
sich selbst gemessen. Die Prämisse der Karte trägt also für die Anhängsel-Klasse;
sie rechtfertigt nur nicht den Werkzeugaufwand.

---

## 1. Was gemessen wurde, und womit

Vier unabhängige Messungen, jede mit einem eigenen Skript, alle rein lesend.
`git merge-tree --write-tree` führt den Merge im Objektspeicher aus — ohne
Arbeitsverzeichnis, ohne Ref, ohne etwas zu verändern.

| Messung | Frage | Skript |
|---|---|---|
| A | Wie oft wird welche Nabendatei geändert? | `git log --first-parent` |
| B | Anhängsel oder Bestands-Umbau? | `conflict_hotspots.py kind` |
| C | Welche Pfade kollidieren zwischen den offenen PRs **wirklich**? | `conflict_hotspots.py hotspots` |
| D | Mergt `STATE.md` **still falsch**? | Block-Vergleich, §5 |
| E | Wo wurden in der History real Konflikte aufgelöst? | `conflict_hotspots.py resolved` |

Die Messungen B, C und E sind als `scripts/conflict_hotspots.py` im Repo
abgelegt — nachprüfbar statt nur behauptet, siehe §10.

Messung D ist die wichtigste und hätte in einer reinen Konfliktzählung gefehlt.
`scripts/changelog_fragments.py` nennt im Kopf-Docstring wörtlich nicht den
Konfliktmarker als Schaden, sondern: „Genau dort merged git messbar oft still
falsch — ohne Konfliktmarker, ohne Warnung." Ein Konflikt-Zähler allein hätte
die Prämisse also auch dann verfehlt, wenn sie zuträfe.

## 2. Messung A — Änderungshäufigkeit

Letzte 60 first-parent-Commits auf `origin/main`:

| Datei | Änderungen |
|---|---|
| `CHANGELOG.md` | 15 |
| `CONTRIBUTING.md` | 8 |
| `.github/workflows/ci.yml` | 7 |
| **`.claude/context/STATE.md`** | **6** |
| `.claude/context/DECISIONS.md` | 3 |
| `.claude/context/ARCHITECTURE.md` | 0 |
| `.claude/context/PROJECT.md` | 0 |

`STATE.md` wird alle zehn Integrationsschritte angefasst. Die Karte nennt als
eigene Überbau-Schwelle „eine Datei, die zweimal im Monat angefasst wird" —
sechs Änderungen in fünf Tagen liegen darüber. Häufigkeit allein trägt die
Prämisse also. Sie ist aber nicht die Konfliktursache, wie C und D zeigen.

Nebenbefund, der das Vorbild bestätigt: Von den 15 `CHANGELOG.md`-Änderungen
liegen **alle** vor der Einführung des Fragment-Verfahrens (`22e5f140`,
2026-09-22). In den **34** first-parent-Commits danach: **0** direkte
`CHANGELOG.md`-Änderungen. Das Verfahren wirkt dort messbar.

## 3. Messung B — Anhängsel vs. Bestands-Umbau

Ein Fragment-Verfahren beseitigt nur eine Klasse von Änderung: das *Anhängsel*,
das an einer Stelle neue Zeilen einfügt, ohne Bestand zu entfernen. Alles andere
bleibt auch mit Fragmenten konfliktfähig.

| Datei | Anhängsel | Bestands-Umbau |
|---|---|---|
| `STATE.md` | 2 von 6 | **4 von 6** |
| `DECISIONS.md` | **3 von 3** | 0 |
| `CONTRIBUTING.md` | 2 von 8 | 4 von 8 (+2 mehrstellig) |

**Das ist der inhaltliche Kern des Urteils.** Bei `STATE.md` sind zwei von drei
Änderungen *keine* Anhängsel:

- `7dd51a3e` — schreibt die `_Stand:_`-Kopfzeile um (46. → 47. Lauf), +65/-1
- `4ad976d0` — ersetzt fünf Absätze im Bestand, +27/-10
- `69bfeda6` — drei Hunks an verschiedenen Stellen, +22/-2
- `d50d6108` — korrigiert „81 Tools" → „83 Tools" an **zwei** Stellen, tief im
  Dokument (Zeilen 2234 und 2419)

Diese Klasse überlebt ein Fragment-Verfahren unverändert. Ein Fragment kann eine
vorhandene Zeile nicht korrigieren; `d50d6108` hätte auch mit `state.d/` direkt
in `STATE.md` greifen müssen. Das Verfahren würde also die 2 Anhängsel
entschärfen und die 4 echten Fälle ungelöst lassen — bei voller Werkzeuglast.

Dazu die Form: `STATE.md` ist **3013 Zeilen** und laut eigener Kopfzeile ein
„Snapshot, pro Run überschrieben". Überschreiben ist das Gegenteil dessen, was
ein Fragment-Sammelschritt tut.

## 4. Messung C — welche Pfade kollidieren wirklich

Alle 7 offenen PRs gegen `origin/main`, und alle 21 Paare gegeneinander:

```
### jeder offene PR gegen origin/main ###
  #626   konfliktfrei
  #622   .github/workflows/ci.yml
  #621   .github/workflows/ci.yml
  #620   .github/workflows/ci.yml
  #619   docs/branch-protection-main.md
  #618   .github/workflows/ci.yml
  #420   konfliktfrei

### Konflikt-Haeufigkeit je Pfad (Paar-Messung) ###
    4x  .github/workflows/ci.yml
    1x  docs/branch-protection-main.md
    0x  .claude/context/STATE.md        <- Praemisse der Karte
    0x  .claude/context/DECISIONS.md    <- Praemisse der Karte
    0x  CONTRIBUTING.md                 <- Praemisse der Karte
```

**`STATE.md`: null Konflikte.** Auch im direkten Merge der beiden PRs, die die
Karte als kollidierend nennt:

```
$ git merge-tree --write-tree --messages pr619 pr626
Auto-merging .claude/context/DECISIONS.md
Auto-merging .claude/context/STATE.md
CONFLICT (content): Merge conflict in docs/branch-protection-main.md
```

`STATE.md` und `DECISIONS.md` mergen sauber. Der Konflikt zwischen #619 und #626
liegt in `docs/branch-protection-main.md` — einer Datei, die die Karte nicht nennt.

Gegenprobe über die gesamte History (alle Merge-Commits, `git show --cc` listet
per Definition nur handverlesene Stellen): 26 Dateien mit real aufgelösten
Konflikten, angeführt von `apps/web/package-lock.json` (7x), `apps/web/package.json`
(7x), `uv.lock` (5x), `apps/web/src/api/types.ts` (5x). `STATE.md` steht bei **2x**,
zuletzt am **2026-09-06** — `DECISIONS.md`, `CONTRIBUTING.md` und `CHANGELOG.md`
bei **0x**. In den 8 Merge-Commits des Messfensters: **null** aufgelöste Konflikte
an irgendeiner Nabendatei.

## 5. Messung D — mergt `STATE.md` still falsch?

Die eigentliche Gefahr, die das Vorbild adressiert. Geprüft wird inhaltlich:
nach dem Merge müssen **beide** Beiträge vollständig und je **genau einmal** im
Ergebnis stehen.

```
--- die zwei Karten, die laut Karte kollidierten: pr619 x pr626 ---
  .claude/context/STATE.md auto-merged, kein Marker.
  pr619: 4 eingefuegte Bloecke -> vollstaendig, je einmal
  pr626: 1 eingefuegter Block  -> vollstaendig, je einmal
  => kein stiller Fehlmerge
```

Ebenso für #619 gegen `main` und #626 gegen `main`. **Kein stiller Fehlmerge an
`STATE.md`, in keiner der drei Kombinationen.** Damit ist auch der Schaden
widerlegt, der ein Fragment-Verfahren allein rechtfertigen würde.

Zwei eigene Messfehler, offengelegt und korrigiert, weil sie das Ergebnis
zunächst verdreht hatten:

1. `git show` liefert für einen **Merge-Commit** einen leeren Diff (combined diff
   zeigt nur Konflikt-Hunks). Die erste Fassung von `measure_hunks.py` meldete
   für fünf von sechs `STATE.md`-Änderungen „+0/-0". Behoben mit
   `-m --first-parent`.
2. Die Konflikt-Erkennung in `measure_silent.py` prüfte `STATE in out` und
   matchte damit auch die harmlose Zeile `Auto-merging <pfad>`. Behoben: nur
   `CONFLICT (...)`-Zeilen zählen. Ebenso wurde von Einzelzeilen- auf
   Block-Vergleich umgestellt — die Allerweltszeile `'reichen.'` kommt in
   `STATE.md` mehrfach vor und erzeugte einen Fehlalarm „doppelt gemergt".

## 6. Der eigentliche Befund: `.github/workflows/ci.yml`

Vier der fünf konfliktbehafteten PRs kollidieren an derselben Datei, und zwar
aus **demselben** Grund: #618, #620, #621 und #622 fügen jeweils den Job
`e2e-mobile` hinzu (+115/-2 bis +119/-2). Auf `main` steht dieser Job seit
`c4999d3f` („feat(e2e): Playwright-Mobile-Profile anlegen — meldend, noch ohne
Gate (#615)") bereits — in `ci.yml` Zeile 447.

Das ist kein Sammeldatei-Problem und **kein Fall für ein Fragment-Verfahren**:
Ein Workflow ist ausführbares YAML mit einem Job-Namensraum, kein additiver
Textstapel. Vier Zweige haben unabhängig denselben Job angelegt, der inzwischen
gemergt ist. Die Auflösung ist inhaltlich (den eigenen Block verwerfen, gegen
den auf `main` ersetzen) und liegt ohnehin bei `t_5e97c04f`.

`ci.yml` hat mit 857 Zeilen und 7 Änderungen im Fenster **mehr** Änderungslast
als `STATE.md` — und im Unterschied dazu auch die Konflikte.

## 7. Empfehlungen

### 7.1 `STATE.md` — kein Fragment-Verfahren, aber die Anhängsel-Kollision ist real

Gegen die verbleibende Anhängsel-Hälfte liegt die naheliegende Konvention nahe:
**Statusnachträge gehören als neuer `##`-Abschnitt direkt unter die
`_Stand:_`-Zeile, bestehende Abschnitte werden nicht umgeschrieben.**

**Diese Karte hat dabei den Gegenbeweis gegen sich selbst geliefert, und er
gehört hierher.** Der erste Entwurf dieses Laufs trug einen solchen Nachtrag
genau dort ein — ein Hunk, 0 gelöschte Zeilen, das Musterbeispiel eines
Anhängsels. Gemessen mit dem eigenen Werkzeug:

```
=== mein Branch gegen origin/main ===
keine Meldung = konfliktfrei
=== und gegen die beiden STATE.md-PRs ===
-- gegen pr626 --
CONFLICT (content): Merge conflict in .claude/context/STATE.md
```

Zwei Karten, die beide brav „unter die `_Stand:_`-Zeile" schreiben, teilen
denselben Einfügeanker und kollidieren dort. Die Konvention verschiebt den
Konflikt, sie beseitigt ihn nicht — und genau das ist die Lücke, die ein
Fragment-Verzeichnis schließt. Insofern trägt die Prämisse der Karte **für die
Anhängsel-Klasse**, und das ist gegen den ersten Eindruck dieses Berichts
festzuhalten.

Das Urteil bleibt dennoch „lohnt nicht", aber aus einem präziseren Grund als
„es gibt keine Konflikte":

1. Der Konflikt ist **sichtbar und trivial** — zwei benachbarte Einfügungen,
   die Auflösung ist „beide behalten", ohne inhaltliche Entscheidung. Das ist
   Welten entfernt vom Schaden, der das Verfahren bei `CHANGELOG.md`
   gerechtfertigt hat: dem *stillen* Fehlmerge, der laut §5 an `STATE.md`
   nachweislich nicht auftritt.
2. Die **teure Hälfte bleibt** ungelöst: 4 von 6 Änderungen sind
   Bestands-Umbauten, die ein Fragment strukturell nicht abbilden kann.

Ein Verzeichnis, ein Skript und ein CI-Job für eine Konfliktklasse, die man in
zehn Sekunden mit „beide behalten" auflöst, während die schwierige Klasse
unberührt bleibt — das ist der Überbau, den die Karte selbst ausschließen
wollte.

**Praktische Folge für diesen PR:** Der Nachtrag wurde wieder entfernt. Er hätte
#626 von `MERGEABLE` auf `CONFLICTING` gebracht, und die konfliktbehafteten PRs
sind laut Karte ausdrücklich out of scope (`t_5e97c04f`). Der Befund steht
stattdessen hier und im Changelog-Fragment — das ist ohnehin der bessere Ort,
weil `changelog.d/` das Problem für die eigene Datei bereits gelöst hat.

Bewusst **nicht** empfohlen wird die Kopfzeile `_Stand: …_` als Pflichtfeld je
Karte: sie ist mit `7dd51a3e` genau der Fall, der sich nicht additiv lösen lässt,
weil zwei Karten dieselbe Zeile ersetzen wollen. Wer sie entschärfen will,
streicht sie besser, statt sie zu automatisieren.

### 7.2 `DECISIONS.md` — getrennt beurteilt: nichts tun

Die Karte fragt danach ausdrücklich. Die Antwort ist am klarsten von allen:
**3 von 3** Änderungen im Fenster sind Anhängsel, alle mit **einem** Hunk, alle
mit **0** gelöschten Zeilen, alle am Dateiende (`@@ -1738,0 +1739,31 @@`,
`@@ -1554,0 +1555,30 @@`, `@@ -1646,0 +1647,62 @@`). Konflikte in der gesamten
History: **0**.

Die von der Karte vermutete „schwächere Regel (immer anhängen, nie bestehende
Absätze umschreiben)" **existiert bereits und wird eingehalten** — wörtlich in
Zeile 1 und 7–8 der Datei: „# DECISIONS — Warum so (append-only)" und
„Append-only: nie umschreiben; eine Revision bekommt einen neuen Eintrag mit
Verweis."

Hier ist nichts zu tun. Eine Norm, die nachweislich zu 3/3 befolgt wird und
null Konflikte erzeugt, braucht kein Gate.

### 7.3 Was stattdessen lohnt

Nach der Konflikt-Messung, nicht nach der Vermutung, in dieser Reihenfolge:

1. **`apps/web/package.json` + `package-lock.json`** (7x + 7x aufgelöst) und
   **`uv.lock`** (5x) — die tatsächlichen Spitzenreiter. Lockfiles sind der
   klassische Fall für `merge=binary` plus Neugenerierung; hier trägt ein
   Verfahren nachweisbar.
2. **`.github/workflows/ci.yml`** (4x offen, 857 Zeilen) — nicht per Fragment,
   sondern durch Aufteilen in mehrere Workflow-Dateien oder `uses:`-Composite-
   Actions, damit zwei Karten verschiedene Dateien anfassen. Das ist derselbe
   *Gedanke* wie bei `changelog.d/`, aber mit dem Werkzeug, das zu ausführbarem
   YAML passt.
3. **`apps/web/src/api/types.ts`** (5x) — generiert? Dann aus dem Diff nehmen.

Ob daraus Karten werden, entscheidet der PM; diese Karte hat dafür kein Mandat.

## 8. Grenzen dieser Messung

- Fenster sind 60 first-parent-Commits (5 Tage) und 7 offene PRs. Die
  History-Gegenprobe in §4 reicht weiter zurück und stützt dasselbe Bild.
- Gemessen wird der Zustand vom 2026-09-24. Wächst `STATE.md` weiter und kippt
  das Verhältnis Anhängsel/Umbau, ändert das die Rechnung — dann ist §7.1 der
  Ort, an dem nachzuschärfen wäre.
- Konflikte, die der Owner vor dem Push lokal auflöste, hinterlassen keine Spur
  und sind so nicht messbar. Die offenen PRs in §4 sind davon unberührt.

## 9. Offen für den PM

Die Sammel-Weiche aus Aufgabe 3 der Karte (wann wird gesammelt: Wellenende von
Hand / CI-Job auf `main` / gar nicht) **entfällt gegenstandslos** — es gibt kein
Verfahren, für das sie zu entscheiden wäre. Sie wird nicht vorgelegt, weil sie
nur unter „lohnt sich" existiert.

Vorzulegen ist stattdessen eine andere Frage: **ob aus §7.3 Karten werden.**
Das ist Priorisierung und gehört nicht in diese Karte.

## 10. Das Messwerkzeug bleibt im Repo

Statt die Zahlen nur zu behaupten, liegt die Messung als
`scripts/conflict_hotspots.py` im Repo — mit 19 Tests unter
`scripts/tests/test_conflict_hotspots.py`. Es ändert nichts:
`git merge-tree --write-tree` merged im Objektspeicher, ohne Arbeitsverzeichnis
und ohne Ref.

```bash
uv run --no-project python scripts/conflict_hotspots.py hotspots          # offene PRs paarweise (braucht gh)
uv run --no-project python scripts/conflict_hotspots.py resolved --window 400   # History
uv run --no-project python scripts/conflict_hotspots.py kind              # Anhaengsel vs. Umbau
```

Struktur und Konventionen sind von `scripts/changelog_fragments.py` übernommen,
nicht neu erfunden: reine Entscheidungslogik (`conflicting_paths`,
`classify_diff`) getrennt von den git-Aufrufen, damit sie unter pytest steht;
ein `MeasureError` mit nennbarem Grund statt einer Ausnahme aus der Tiefe;
Unterkommandos über `argparse` mit sprechender Hilfe.

Zwei Tests sind Regressionstests für die Messfehler aus §5 — ein Messwerkzeug,
das still falsch misst, ist schlimmer als keines:

- `test_auto_merging_ist_kein_konflikt` — `STATE.md` darf nicht als
  konfliktbehaftet zählen, nur weil git seine erfolgreiche Zusammenführung
  meldet. Das war der Fehler, der zunächst das genaue Gegenteil der Wahrheit
  ausgab.
- `test_leerer_diff_zaehlt_nichts` plus der dokumentierte Grund an
  `change_for`: ohne `-m --first-parent` liefert `git show` für einen
  Merge-Commit einen leeren Diff, und dieses Repo mergt ohne Squash.

**Der Gebrauch ist die eigentliche Lehre dieser Karte.** Die Prämisse „`STATE.md`
ist unsere Konfliktnabe" war plausibel, breit geteilt und falsch. Ein
`hotspots`-Lauf hätte das in zwei Minuten gezeigt, bevor ein Verfahren für die
falsche Datei entworfen wird. Wer künftig eine Konfliktquelle beseitigen will,
misst sie zuerst.
