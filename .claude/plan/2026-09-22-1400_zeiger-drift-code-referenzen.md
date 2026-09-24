# P7 — Zeiger-Drift beenden: SHA-Permalinks und Symbolanker statt `datei:zeile`

Karte: `t_9955a9fb` · Branch: `who2be/t_9955a9fb-p7-zeiger-drift-beenden-sha-permalinks-u`
Grundlage: Recherchebericht `workflow-idee-code-review-2026-09-22.md`, Abschnitt **P7** + Quellen [18][35][29].

## Ausgangslage (aus dem Bericht, mit Stufen)

- **GEMESSEN / normativ:** GitHub garantiert Inhaltsstabilitaet nur fuer
  SHA-Permalinks — *„The version of a file at the head of branch can change as
  new commits are made […] replaces main with a specific commit ID and the file
  content will not change."* [18]
- **GEMESSEN / normativ:** Git kennt Funktionsnamen als erstklassigen Anker:
  `git log -L :<funcname>:<file>` [35].
- **Ehrlich benannte Grenze (Bericht, P7):** Der Permalink stabilisiert den
  *Inhalt*, nicht den *Ort*. Er verhindert stille Falschheit, macht den Zeiger
  aber nicht aktuell. Genau das ist die gebrauchte Haelfte.
- **Belegtes Fehlen:** *„Ich habe kein etabliertes Werkzeug gefunden, das
  `datei:zeile`-Referenzen in Tickets oder Dokumenten gegen das Repo
  validiert."* Empfehlung: kleiner Eigenbau (halbe Seite Code).
- **EIGENE ABLEITUNG (meine):** Ein Checker muss die *Altlast* melden duerfen,
  ohne rot zu werden — sonst kollidiert Akzeptanzkriterium 2 („fehlerfrei
  durchlaufen") mit dem Out-of-Scope („alte Zeiger bleiben kaputt").

## Entwurfsentscheidungen

### 1. Konvention: wo sie wohnt

Kurze, verbindliche Regel in `CONTRIBUTING.md` (englisch, nach aussen
gerichtet, Heimat der Definition of Done) + Detail-Referenz
`docs/code-references.md` (deutsch, intern — Sprachregel `docs/README.md`).
Single Source of Truth: die Regel steht *einmal* im Detaildokument, CONTRIBUTING
verweist darauf.

### 2. Referenz-Grammatik

Verbindlich fuer jeden neuen Zeiger — mindestens eine der beiden Formen:

| Form | Beispiel | Was der Checker prueft |
|---|---|---|
| SHA-Permalink | `apps/api/src/who2be_api/main.py@39dcdf4` | Datei existiert an diesem Commit |
| Symbolanker | `conftest.py#_db_reachable` | Datei existiert **und** Symbol ist dort definiert |
| kombiniert | `conftest.py@1a8f63b#_db_reachable` | beides |
| Zeile — nur **zusaetzlich** | `conftest.py@1a8f63b#_db_reachable:81` | Zeile wird nicht als Beleg gewertet |

Nackte `datei:zeile`-Zeiger sind ab jetzt Konventionsverstoss (der Checker
meldet sie als `legacy`, siehe 3).

### 3. Severity-Modell (loest den Zielkonflikt)

- `error` — eine Referenz **in Konventionsform** loest nicht auf (Datei fehlt,
  Symbol fehlt, SHA unbekannt). Exit 1.
- `legacy` — nackter `datei:zeile`-Zeiger. Wird gemeldet, faerbt aber nicht rot
  (Exit 0), weil Bestandskorrektur ausdruecklich Out of Scope ist.
  `--strict` hebt `legacy` auf `error` — fuer den Tag, an dem die Altlast weg ist.

### 4. Nicht-Ziele (aus der Karte)

Kein Umschreiben bestehender Tickets/Plaene. Keine CI-Integration. Das Skript
schreibt **nichts** — kein Index, kein Cache, keine Fixes (nur `git`-Reads).

## Arbeitsschritte

1. `scripts/check_code_refs.py` — read-only Checker.
   - Eingabe: Pfade als Argumente, Verzeichnisse rekursiv (`*.md`), `-` = stdin.
   - Symbolaufloesung: Python via `ast` (exakt), TS/JS/andere via
     Definitions-Regex (`function|class|const|export|def …`).
   - SHA-Aufloesung: `git cat-file -e <sha>:<pfad>` (read-only).
   - Ausgabe: Text (default) und `--json` (maschinenlesbar, ein Objekt mit
     `findings[]` + `summary`).
2. `docs/code-references.md` — Konvention + Skript-Doku + Belegstufen.
3. `CONTRIBUTING.md` — kurzer Abschnitt „Referencing code" + DoD-Zeile
   („ein Aufbereitungslauf nutzt das Skript statt Handarbeit").
4. `docs/README.md` — Index-Eintrag.
5. `CHANGELOG.md` — `Unreleased / Added`.
6. Tests `apps/api/tests/test_check_code_refs.py` (Praezedenz:
   `test_blobstore_bootstrap.py` testet ebenfalls ein Root-Skript).
7. DoD lokal: ruff, ruff format, mypy, pytest mit Coverage-Gate; Checker
   gegen das eigene Repo laufen lassen und die Ausgabe als Beleg festhalten.

## Verifikation (Akzeptanzkriterien → Beleg)

| AK | Beleg |
|---|---|
| 1 Konvention dokumentiert | `docs/code-references.md` + `CONTRIBUTING.md` |
| 2 Skript prueft maschinell, laeuft fehlerfrei | Ausgabe von `uv run python scripts/check_code_refs.py . --json` |
| 3 dokumentiert + in DoD genannt | `CONTRIBUTING.md` §Definition of Done |
| 4 aendert nichts | keine Schreib-Syscalls; Test `test_check_code_refs.py::test_leaves_tree_untouched` |

## Fortschritt

- [x] Plan abgelegt
- [x] Schritt 1 Checker
- [x] Schritt 2–5 Doku
- [x] Schritt 6 Tests
- [x] Schritt 7 DoD + Belegausgabe
