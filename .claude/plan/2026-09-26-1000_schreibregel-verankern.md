# Schreibregel verankern (Karte t_23bac5e4)

**Ziel:** Die Schreibregel verankern, die verhindert, dass Umgehungswege und
Geschaeftszahlen oeffentlich landen. Der schwerste Fund der vorausgegangenen
Messung war kein Altbestand, sondern das juengste Artefakt im Repo — die Regel
muss also *ab jetzt* wirken, nicht nur rueckwaerts bereinigen.

**Grundlage:** Messbericht der Karte `t_6f554ac0` (@reviewer), Abschnitt 6
Teil B. Der Bericht selbst bleibt ausserhalb des Repos — er ist ein Verzeichnis
der Schwachstellen. Hier steht nur die Regel, keine Fundstelle.

## Owner-Entscheidungen (gesetzt, nicht neu zu verhandeln)

- Schutzwuerdig ist **(a)** Sicherheitsluecken und Umgehungswege und
  **(b)** Geschaeftliches (Preisstrategie, Marge, Kundenzahlen).
- **Planung und Roadmap sind nicht schutzwuerdig.** Sie werden hier nicht
  stillschweigend mit eingezogen.
- Die Historie wird nicht umgeschrieben.

## Schritte

1. `CLAUDE.md §Security` — die Regel gehoert neben die bestehende
   Betreiber-Host-Regel, die dieselbe Bauart hat. `CLAUDE.md` ist fuer Agenten
   schreibgesperrt: der fertige Textblock liegt als Kommentar an der Karte, der
   Owner setzt ihn ein. Kein Edit-Versuch.
2. `CONTRIBUTING.md §Commit convention` — Verweis auf die Regel plus der
   Entscheidungstest im Wortlaut.
3. Entscheidungstest **wortgleich** aus dem Bericht uebernommen: vier Fragen,
   die Reihenfolge zaehlt, die erste Ja-Antwort entscheidet. Nicht gekuerzt.
4. Die Auflage „begruende deine Entscheidung im Commit" bleibt ausdruecklich
   bestehen. 93 % der gemessenen Commit-Bodies sind ausfuehrlich und
   unbedenklich; wer daraus „weniger begruenden" ableitet, zahlt interne
   Nachvollziehbarkeit fuer ein Problem, das an vier engen Fragen haengt.
5. Der Ausweg wird benannt: Wo die Begruendung nicht oeffentlich stehen darf,
   gehoert sie in die Kartenbeschreibung auf dem Board, und im Commit steht ein
   Verweis darauf. `.claude/plan/` ist ebenfalls oeffentlich und taugt dafuer
   ausdruecklich **nicht** — dieser Satz muss dastehen, sonst wandert es genau
   dorthin.
6. Changelog-Fragment unter `changelog.d/`.

## Sprachliche Entscheidung

`CONTRIBUTING.md` ist nach aussen gerichtet und durchgaengig englisch, der
Entscheidungstest ist deutsch und darf nicht umformuliert werden (er ist
geprueft, und eine Uebersetzung waere eine zweite, abweichende Fassung). Er
steht deshalb als woertlich zitierter Block in der Originalsprache, eingefuehrt
durch einen englischen Absatz. Eine Uebersetzung daneben waere genau die zweite
Quelle, die die Regel selbst verbietet.

## Verifikation

- `uv run python scripts/changelog_fragments.py check`
- Doku-only-PR: die vier schweren CI-Jobs entfallen planmaessig, die
  Markdown-/Doku-Gates laufen.

## Nicht in dieser Karte

Dateien bereinigen, das Golden File umbauen, die Historie.
