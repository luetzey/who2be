# Backlog-Vorbereitungslauf — Norm-Audit, Korrekturen, Reihenfolge

- Status: **abgeschlossen** (Read-only-Audit plus Issue-Korrekturen; kein Produktivcode)
- Datum: 2026-09-05, 16:25 UTC (18. Lauf, Zählung nach `STATE.md`)
- Auftrag: jedes offene Issue gegen die Norm *Agent-ready Arbeitspaket* prüfen,
  repo-belegbare Lücken selbst schließen, Urteilsfragen mit drei Optionen
  vorlegen, Warteschlange (#442) neu ordnen und in Wellen gruppieren
- Vorgänger: 15. Lauf (`2026-09-05-1215_backlog-audit-parallelisierung.md`,
  **PR #443 — offen als Draft, inhaltlich überholt**)

## 1. Befund in einem Satz

Der Backlog ist in gutem Zustand — von zwölf geprüften Issues erfüllen zehn die
Norm ohne Abstriche. Der eine Fund, der zählt, steckt in **#436**: Weiche 2
plant eine Datei als Neuanlage, die es bereits gibt, und dahinter steht eine
unbeantwortete Architektur-Weiche. Alles Übrige waren vier falsche Zeiger.

## 2. Methode

Drei parallele Prüf-Agents (Sonnet — Struktur-Abgleich gegen eine feste Rubrik
plus Beleg-Verifikation im Repo, keine Design-Entscheidung; das rechtfertigt das
kleinere Modell). Je Issue geprüft: die vier Pflichtfelder einzeln am Body, die
Zusatzabschnitte gegen das Referenz-Muster #434, und jeder `datei:zeile`-Beleg
gegen den lokalen Repo-Stand.

Die Rückläufe sind **nicht** ungeprüft übernommen worden. Eine gemeldete
„offene Weiche" (#429 ↔ #430 Datei-Kollision) wurde verworfen: sie ist in #442
längst dokumentiert und die Reihenfolge dort bereits entsprechend gesetzt — der
Agent hatte die Queue nicht gelesen. Jeder übernommene Befund wurde vor dem
Schreiben selbst am Repo nachgeprüft.

## 3. Selbst erledigt

### 3.1 #436 — Startfreigabe zurückgezogen

Vorentschieden Nr. 2 nennt `packages/models/src/who2be_models/errors.py` als
„(neu)". Die Datei existiert seit WP-2/#254:

```
packages/models/src/who2be_models/errors.py:1    """Strukturierte API-Fehler-Taxonomie (RFC 7807, WP-2 / #254).
packages/models/src/who2be_models/__init__.py:29 from who2be_models.errors import ActionableBy, ApiProblem, ProblemReason
```

Ihr Feld `reason` ist laut Modul-Docstring genau das, was #436 bauen will: „ein
stabiler Enum-Schluessel […] ohne den `detail`-Freitext zu parsen". Damit ist
das keine Namenskorrektur, sondern die Frage, ob Who2Be zwei maschinenlesbare
Fehler-Vokabulare nebeneinander bekommt. Diese Frage gehört in ADR-0051 — also
in genau das Dokument, das #436 schreiben soll.

`agent-ready` abgenommen, `needs-decision` gesetzt, drei Optionen als Kommentar
am Issue. Die Eskalationsklausel des Issues hätte einen Agenten ohnehin hier
angehalten — nur eben erst nach dem Anlauf.

### 3.2 Vier falsche Zeiger korrigiert

Alle vier vor dem Schreiben selbst verifiziert:

| Issue | Stelle | Befund | Korrektur |
|---|---|---|---|
| #450 | Verifikations-Block | greppt `später`, die Datei ist durchgehend ASCII (`grep -c '[äöüÄÖÜß]' deploy/hetzner/README.md` → **0**; Zeile 274 lautet `spaeter`). Der Check lieferte schon vor der Änderung 0 Treffer und hätte auch eine unterlassene Änderung als grün gemeldet. | `später` → `spaeter` |
| #453 | Ist-Zustand-Tabelle | `playwright.config.ts:23` ist `baseURL:`; die Projekt-Deklaration steht in Zeile 27. | `:23` → `:27` |
| #429 | Problem + Einstiegspunkte | `.env.example:262-273` — 262–265 gehören noch zum `VITE_WHO2BE_EDITION`-Block, der Signup-Abschnitt beginnt bei 266. | `:262-273` → `:266-273` (zwei Vorkommen) |
| #430 | Einstiegspunkte | `LoginPage.tsx:25-50` ist `type MfaValues` + `completeMfaChallenge` (TOTP-Step-up), nicht das Login-Formular. | → `:83-128, 208-269` |

Der Fund in #450 ist der einzige mit Substanz: ein Akzeptanzkriterium, das
nichts prüft, ist schlimmer als keines — es sieht nach Prüfung aus.

### 3.3 Warteschlange und Begründung nachgezogen

- **#442:** #434 abgehakt (PR #448 gemergt), #436 als blockiert markiert, #427
  davor gezogen, Wellen neu geschnitten.
- **`.github/PROJECT.md` §Reihenfolge:** die Tabelle kannte #449 bis #454 nicht
  und führte #440/#434 noch als offen — der Punkt, den Pflege-Regel 4 in #442
  selbst als nachzuziehen markiert hat. Erledigt mit diesem PR.

## 4. Was der Owner entscheiden muss

1. **#436 — zwei Fehler-Vokabulare oder eines?** Optionen A/B/C samt Empfehlung
   (A: zwei, mit ausdrücklicher Grenze in ADR-0051) stehen als Kommentar am
   Issue. Solange offen, ist #436 nicht startbar und #402 bleibt ohne W0.
2. **PR #443 schließen?** Der Draft des 15. Laufs trägt als Kernbefund „PR #441
   mergen" — #441 ist gemergt, #440 und #434 sind erledigt, die
   Kollisions-/Sammelpunkt-Analyse ist in #442 eingeflossen. Der Plan ist
   überholt; offen bleiben nur seine zwei Vorschläge (§5.1, §5.2), siehe unten.
3. **Zwei belegte Funde ohne Issue.** Beide aus dem 15. Lauf, beide erneut
   verifiziert, beide nur im offenen Draft #443 sichtbar und damit für einen
   unbeaufsichtigten Lauf unauffindbar:
   - **Typecheck-Drift:** CI fährt `npx tsc -b` (`.github/workflows/ci.yml:162`),
     die Doku sagt `npx tsc --noEmit` an **elf** Stellen in neun Dateien
     (u. a. `CLAUDE.md:151`, `CLAUDE.md:233`, `CONTRIBUTING.md:79`,
     `docs/CLAUDE-PROFILE.md:22`). Widerspricht dem „lokal = CI"-DoD und ist als
     FE-9 in `docs/standards-review-2026-07-20.md:87` seit Juli bekannt.
   - **Kein Drift-Wächter für `docs/reference/openapi.json`:**
     `scripts/export_openapi.py` schreibt die Datei, kein Test und kein
     CI-Schritt liest sie; der Contract-Test prüft gegen
     `apps/api/tests/contract/openapi_surface.json`. `STATE.md:333` belegt, dass
     die Spec bereits einmal unbemerkt stale war.

## 5. Was dieser Lauf nicht getan hat

Kein Produktivcode, kein Branch für ein Issue, kein Issue geclaimt oder
geschlossen, keine neuen Issues angelegt (Nr. 4.3 sind Vorschläge — ob sie vor
dem Cloud-Launch Kapazität bekommen, ist eine Prioritätsfrage des Owners),
die Weiche auf #436 nicht entschieden, PR #443 nicht angefasst.
