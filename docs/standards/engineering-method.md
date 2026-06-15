# Arbeitsmethode

Die verbindliche Mehr-Phasen-Schleife für jede Code-Aufgabe in diesem Repo —
egal ob Mensch oder LLM. Sie hält Code, Plan und Absicht konsistent und ist das
zentrale Werkzeug gegen Drift.

> **Understand → Plan → Implement → Verify → Document**

## 1. Understand (vor jeder Zeile Code)

- **Repo-Kontext lesen:** [`CLAUDE.md`](../../CLAUDE.md), relevante
  [`docs/`](../) und bestehende Muster in der Codebase — *vor* der Implementierung.
- **Projekt-Gedächtnis lesen:** die vier Dateien unter
  [`.claude/context/`](../../.claude/context/) (PROJECT / ARCHITECTURE /
  DECISIONS / STATE). Sie sagen *warum* der Code so gebaut ist, *wohin* er soll
  und *wo* er steht. Fehlen sie → aus Codebase-Analyse initial generieren.
- **Done-Condition ableiten:** eine messbare, im Transkript nachweisbare
  Abschluss-Bedingung (z. B. „Tests in `apps/api/tests/auth` grün, ruff/mypy
  clean"). Constraints und Out-of-Scope sind Leitplanken.

## 2. Plan (nicht verhandelbar bei nicht-trivialer Arbeit)

- Der Plan wird **immer** erstellt — **nie** fragen „planen oder direkt coden?".
- Ablage als living document unter
  [`.claude/plan/<YYYY-MM-DD-HHmm>_<titel>.md`](../../.claude/plan/): Ziel/Condition,
  Schritte, betroffene Dateien, Verifikations-Schritt, offene Punkte.
- **Drei-Optionen-Regel:** bei einer *inhaltlichen* Design-Weiche (Architektur-/
  Lösungsalternative) nicht raten — genau **drei** projekt- und problemspezifische
  Optionen mit Trade-offs anbieten, eine empfehlen, rückfragen. (Gilt für das
  *Wie*, nie für das *Ob* des Plans.)
- Den Plan vor der Umsetzung zur Freigabe zeigen.

### Größere Aufgaben zerlegen (nach Freigabe)

Den genehmigten Plan in **datei-disjunkte** Arbeitspakete schneiden und nach
Abhängigkeit in **Wellen** ordnen — Fundament-Pakete (gemeinsame Interfaces,
Schemas, Basis-Module) zuerst, danach maximale Breite parallel. Pakete mit
Datei-Overlap nie in dieselbe Welle.

## 3. Implement

- **In einem Branch arbeiten, nie direkt auf `main`** (`feat/<kurz>`,
  `fix/<kurz>`; Cloud-Sessions nutzen `claude/`-Präfix).
- Schritt für Schritt: pro Schritt coden, dann verifizieren (Test/Build/Lint).
  Plan als living document führen, erledigte Schritte als ✅ markieren.
- **Selbstkorrektur:** bei Testfehlschlag Ursache lesen, Hypothese korrigieren,
  fixen, erneut testen — iterieren bis grün. Ursache statt Symptom beheben.
- **Check-ins:** keine irreversiblen Aktionen ohne Freigabe (Commit/Push `main`,
  Force-Push, destruktive Befehle). Bei Bugfix **zuerst** ein reproduzierender,
  fehlschlagender Test.

## 4. Verify

- Vollständige Test-/Check-Suite gegen die Done-Condition laufen lassen und das
  Ergebnis **explizit im Output sichtbar** machen (Behauptung „grün" ohne Beleg
  zählt nicht).
- **Definition of Done** (siehe [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md)):
  ruff + mypy + pytest grün; eslint + tsc + vitest + build grün.

## 5. Document

- **Plan-Abgleich:** Plan Punkt für Punkt mit dem realen Code-Stand reconciliieren;
  bewusste Abweichungen begründen, nicht stillschweigend droppen. Abgeschlossene
  Pläne auf `_done.md` umbenennen.
- **Projekt-Gedächtnis pflegen** ([`.claude/context/`](../../.claude/context/)):
  `STATE.md` immer; `DECISIONS.md` bei jeder getroffenen Design-Entscheidung
  (append-only); `ARCHITECTURE.md` nur bei Strukturänderung; `PROJECT.md` nur bei
  Ziel-Änderung. **Lesen ohne Zurückpflegen ist schlimmer als nichts** — veraltete
  Kontext-Dateien lenken die nächste Session aktiv falsch.
- Branch pushen und **PR öffnen** (kein Direct-Merge in `main`).

## Git-Disziplin (Kurzform)

- **Atomare Commits** (eine geschlossene Einheit), häufig + früh, Conventional
  Commits im Imperativ (`feat:`, `fix:`, `docs:`).
- **Kurzlebige Branches**, `git pull` vor Push, Reviews via PR.
- **Goldene Regel:** nie öffentliche/geteilte Branches rebasen.

## Anti-Patterns

- Implementieren ohne Plan-Datei; Plan einmal schreiben und nie aktualisieren.
- Session starten ohne `.claude/context/` zu lesen → Drift am gewachsenen
  Warum/Wohin vorbei.
- Bei Unklarheit raten oder eigene Konvention erfinden (Pattern Drift) statt der
  Drei-Optionen-Rückfrage.
- Tests „grün" melden ohne Beleg im Output; in `main` mergen ohne Review.
