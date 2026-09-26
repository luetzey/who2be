# Tests müssen Wirkung ausführen

Ein Test, der eine Datei liest und eine Zeichenkette darin zusichert, bleibt
grün, solange der Text steht — auch dann, wenn die Sache, die der Text
beschreibt, nicht funktioniert. Er prüft die Beschreibung, nicht das Verhalten.

Das ist kein theoretisches Risiko. An einem Tag trat dieser Fehlertyp dreimal
auf und kam zweimal durch alle Prüfungen; in einem Fall konnten dreizehn
bestehende Testfälle einen abgeschnittenen Datenbank-Dump prinzipbedingt nicht
fangen, weil keiner von ihnen den Sicherungslauf ausführte.

## Die Regel

**Ein Test ruft den Prüfling auf und sichert dessen Verhalten zu.**

```python
# nicht so — prüft, dass eine Zeile dasteht
def test_rotation_is_configured() -> None:
    assert "roll_size 10MiB" in Path("Caddyfile").read_text()


# so — prüft, dass die Rotation stattfindet
def test_rotation_removes_old_generations(tmp_path: Path) -> None:
    old = tmp_path / "access.log.1"
    old.write_text("x")
    os.utime(old, (0, 0))
    run_rotation(tmp_path, keep_days=14)
    assert not old.exists()
```

Die Zeile in der Konfiguration ist ein Mittel. Ob sie wirkt, entscheidet die
Software, die sie liest — und genau darüber sagt ein Zeichenketten-Test nichts.
Zwei der drei Fälle oben hatten eine korrekt gesetzte Direktive, die die
eingesetzte Programmversion still verwarf.

## Die maschinelle Prüfung

`scripts/check_effectful_tests.py` markiert **neu hinzugefügte** Python-Tests,
auf die alle drei Punkte zutreffen:

1. Sie lesen Dateiinhalte — direkt oder über einen lokalen Helfer.
2. Sie rufen nichts auf, was Verhalten ausführt: kein Symbol aus dem eigenen
   Code, kein Prozess-Start, kein HTTP-Aufruf gegen die App.
3. Alle ihre Zusicherungen sind Vergleiche oder Containment-Prüfungen.

```bash
uv run python scripts/check_effectful_tests.py --base origin/main   # wie in der CI
uv run python scripts/check_effectful_tests.py                      # Gesamtbestand
```

Der Schritt **meldet, er blockiert nicht.** Erst wird die Signalqualität
gemessen, dann wird entschieden, ob er härter wird (`--strict`). Ein Gate, das
am ersten Tag blockt und am dritten abgeschaltet wird, hat nichts geschützt.

### Warum als CI-Schritt und nicht als Regel in einem Dokument

Gemessen wurde, dass die Anweisungs-Dokumente dieses Repos in 89 % der Läufe
nicht im Kontext des arbeitenden Agenten sind. Eine Regel, die niemand liest,
wirkt nicht. Der Schritt greift auch dann, wenn dieses Dokument nicht gelesen
wurde — das ist sein ganzer Zweck.

## Der Ausnahmeweg

Manche Tests **sind** zurecht Zeichenketten-Prüfungen: ein Wächter, der die
dokumentierte Werkzeug-Anzahl gegen die Registry hält, hat keinen Prüfling. Für
sie gibt es einen Marker mit Pflicht-Begründung:

```python
# effect-exempt: hält eine Doku-Zusage gegen die Registry, hat keinen Prüfling
def test_documented_tool_count_matches_registry() -> None:
    assert f"{len(TOOLS)} Werkzeuge" in Path("README.md").read_text()
```

Er darf in der `def`-Zeile oder in den zwei Zeilen darüber stehen — dort, wo ihn
der Reviewer des Diffs sieht. **Ohne Begründung zählt er nicht:** ein leerer
Marker wäre ein stilles Abschalten, und das soll der Ausnahmeweg nicht sein.

Zulässige Ausnahmegründe, wie sie im Bestand vorkommen:

- **Doku-Konformität** — eine Zahl oder Zusage im Text gegen die Wahrheit im
  Code halten
- **Golden-File-Verträge** — eine eingecheckte Referenz gegen die erzeugte
  Fassung
- **Negativ-Nachweise** — dass ein Werkzeug etwas *nicht* angefasst hat
- **Konfigurations-Drift** — dass eine gefährliche Option nirgendwo auftaucht
  (`replicas`, `--workers`)

Kein zulässiger Grund: „der echte Test wäre aufwendiger". Dann ist der
aufwendige Test der richtige.

### Wenn die Ausnahme die halbe Wahrheit ist

Der häufigste gute Umgang mit einer Warnung ist nicht der Marker und nicht der
Umbau, sondern **beides nebeneinander**: die Zeichenketten-Prüfung bleibt als
Drift-Wächter über die Konfiguration, und daneben tritt eine Prüfung, die die
Wirkung im echten Programm messt. Genau so stehen die Security-Header dieses
Repos: ein Test hält die Werte in der Konfigurationsdatei, eine Shell-Suite
fährt sie gegen das echte Abbild.

## Grenze

Der Prüfer parst **Python**. Die Shell-Testsuiten unter `deploy/hetzner/tests/`
sieht er nicht — und einer der drei historischen Fälle liegt dort. Das ist eine
Methodengrenze, keine Einstellungsfrage: sie zu schließen bräuchte einen
zweiten Prüfer für Shell, keinen Parameter an diesem.

Ebenfalls nicht erfasst: TypeScript-Tests im Web-Frontend.

## Verworfen: der Negativ-Nachweis als CI-Mechanik

Naheliegender Vorschlag: jeden neuen Test gegen die unveränderte Vorfassung
laufen lassen und Rot verlangen. Als **Handlauf** ist er wertvoll — so wurde
einer der drei Fälle tatsächlich gefunden. Als CI-Mechanik trägt er nicht:

1. Die Vorfassung ist nicht isolierbar. Ein Änderungssatz berührt Test und
   Prüfling gemeinsam; „neuer Test, alter Produktivcode" ergibt in diesem Repo
   einen Zustand, der nicht lädt. Der Test wäre dann rot aus dem falschen
   Grund — und ein Gate, das aus dem falschen Grund rot ist, wird bald
   ignoriert.
2. Die drei Fälle wären davon **nicht** gefangen worden: sie prüfen
   Konfigurationsdateien, deren Vorfassung die geprüfte Zeichenkette nicht
   enthielt. Der Negativ-Nachweis wäre korrekt rot gewesen und hätte die Tests
   trotzdem durchgelassen.
3. Jeder Änderungssatz führe die Suite zweimal.

Die Fassung, die tatsächlich unterscheidet, ist die AST-Prüfung oben.
