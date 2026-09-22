# Code-Referenzen: wie Codestellen zitiert werden

**Typ:** Referenz · **Zielgruppe:** alle, die Issues, Kanban-Karten, Plaene,
Reviews oder ADRs schreiben — Menschen wie Agenten.

## Das Problem

Ein Zeiger der Form `webhook.py:441` ist nur so lange richtig, wie die Datei
sich nicht aendert. Sie aendert sich. Der Zeiger wandert und zeigt auf
Nachbarcode — ohne dass irgendetwas kaputtgeht, das jemand bemerken wuerde.
Genau das ist die teure Variante: eine Angabe, die falsch ist und gueltig
aussieht.

GitHub beschreibt die Ursache fuer seine eigenen Links so:

> „The version of a file at the head of branch can change as new commits are
> made, so if you were to copy the normal URL, the file contents might not be
> the same when someone looks at it later."
> — [GitHub Docs, Getting permanent links to files](https://docs.github.com/en/repositories/working-with-files/using-files/getting-permanent-links-to-files)

Und die Garantie der Gegenmassnahme, ebenso woertlich: ein Link mit Commit-SHA
statt Branchnamen „replaces main with a specific commit ID and the file content
will not change."

**Die Grenze davon ehrlich benannt:** Ein SHA-Permalink stabilisiert den
*Inhalt*, nicht den *Ort*. Er zeigt weiterhin auf die alte Fassung, auch wenn
die Stelle inzwischen woanders steht. Er verhindert, dass ein Zeiger
stillschweigend auf **falschen** Code zeigt — er macht ihn nicht automatisch
aktuell. Deshalb steht neben dem SHA der Symbolname: der SHA sagt, was gemeint
war, der Symbolname findet, wo es heute steht.

## Die Konvention

**Jede Code-Referenz nennt mindestens einen stabilen Anker: einen Commit-SHA,
einen Symbolnamen, oder beides. Eine Zeilennummer ist erlaubt, gilt aber nie
als Beleg.**

Referenzen stehen in Backticks — nur dort sucht der Pruefer (siehe unten), und
nur so bleibt Prosa von Zeigern unterscheidbar.

| Form | Beispiel | Wann |
|---|---|---|
| Symbolanker | `` `conftest.py#_db_reachable` `` | Standardfall. Die Stelle hat einen Namen. |
| SHA-Permalink | `` `apps/api/src/who2be_api/main.py@39dcdf4` `` | Die Stelle hat keinen Namen (Konfigzeile, Datenblock), oder der Zustand *zu diesem Zeitpunkt* ist der Punkt. |
| kombiniert | `` `conftest.py@1a8f63b#_db_reachable` `` | Beleg und Auffindbarkeit zugleich — die beste Form. |
| Zeile zusaetzlich | `` `conftest.py@1a8f63b#_db_reachable:81` `` | Zeile als Lesehilfe, nie allein. |
| GitHub-Permalink | `https://github.com/luetzey/who2be/blob/39dcdf4/apps/api/src/who2be_api/main.py#L20-L28` | Fuer Leser ausserhalb eines Checkouts. Im Dateiview mit `y` erzeugt. |

**Verboten als alleinige Angabe:** `` `webhook.py:441` `` — nackte
`datei:zeile`-Zeiger. Bestehende Vorkommen bleiben stehen (siehe „Altlast").

### So findet man die Angaben

```bash
# SHA, gegen den die Stelle gemessen wurde (letzter Commit der Datei):
git log -1 --format=%h -- pfad/zur/datei.py

# Wo steht das Symbol heute, und wie hat es sich entwickelt:
git log -L :_db_reachable:conftest.py
git grep -n "def _db_reachable"
```

`git log -L :<funcname>:<file>` ist dabei kein Behelf, sondern Gits eigener
Adressierungsmechanismus: „Trace the evolution of the line range given by
`<start>`, `<end>`, or by the function name regex `<funcname>`, within the
`<file>`." ([git-log(1)](https://git-scm.com/docs/git-log))

## Der Pruefer: `scripts/check_code_refs.py`

Ein Werkzeug, das `datei:zeile`-Referenzen in Tickets gegen ein Repo validiert,
existiert nicht — Link-Checker pruefen HTTP-Erreichbarkeit, und ein Permalink
bleibt erreichbar, auch wenn der Zeiger inhaltlich sinnlos geworden ist. Dieses
Skript schliesst die Luecke fuer unseren Fall.

```bash
# Ganzes Repo (alle *.md rekursiv):
uv run python scripts/check_code_refs.py .

# Gezielt, maschinenlesbar:
uv run python scripts/check_code_refs.py docs/ .claude/plan/ --json

# Einen Kartentext ohne Datei pruefen:
pbpaste | uv run python scripts/check_code_refs.py -
```

Geprueft wird: **gibt es die genannte Datei** (im Arbeitsbaum bzw. an dem
genannten Commit) und **gibt es das genannte Symbol dort** (Python exakt via
`ast`, TypeScript/JavaScript/Shell/SQL/YAML ueber Definitions-Muster).
Symbolnamen duerfen Bindestriche tragen — CI-Jobs und npm-Skripte heissen
`compose-smoke` oder `e2e-billing-cloud`, und ein Anker darauf loest auf.

### Befund-Stufen

| Stufe | Bedeutung | Faerbt rot? |
|---|---|---|
| `ok` | Referenz loest auf. | — |
| `legacy` | Nackter `datei:zeile`-Zeiger, kein Anker. | nein (mit `--strict` ja) |
| `unsupported` | Symbolanker in einer Dateiart ohne Aufloesung, oder ein SHA, den ein shallow clone nicht enthaelt. | nein |
| `error` | Referenz **in Konventionsform** loest nicht auf: Datei fehlt, Symbol fehlt, SHA unbekannt. | **ja** (Exit 1) |

Exit-Codes: `0` sauber, `1` mindestens ein `error`, `2` Aufrufsfehler.

**Warum ein nicht pruefbarer SHA kein Fehler ist:** `actions/checkout` klont
per Default mit `fetch-depth: 1`. In so einem shallow clone ist ein aelterer
Commit schlicht *nicht vorhanden*, und `git cat-file -e` kann „kenne ich
nicht" nicht von „gibt es nicht" unterscheiden. Ein Pruefer, der dort auf
`error` geht, verurteilt ausgerechnet die Referenzform, zu der diese
Konvention raet. Deshalb meldet er `unsupported` und sagt in der Meldung, dass
der SHA ungeprueft blieb — falsche Sicherheit waere schlimmer als eine
ehrliche Luecke. Wer SHAs wirklich verifizieren will, klont mit
`fetch-depth: 0`.

### Das Skript aendert nichts

Es liest Dateien und ruft `git` ausschliesslich lesend auf (`cat-file -e`,
`show`). Es gibt keinen Fix-Modus, keinen Cache, keine Schreiboperation — mit
Absicht: ein Pruefer, der repariert, verwischt genau die Information, die ein
Mensch sehen soll. Ein Regressionstest haelt das fest
(`apps/api/tests/test_check_code_refs.py#test_leaves_tree_untouched`).

## Altlast

Der Bestand an alten `datei:zeile`-Zeigern in Issues, Reviews und
Plandokumenten wird **nicht** nachtraeglich korrigiert. Diese Zeiger bleiben
kaputt; das ist eine bewusste Entscheidung, keine Nachlaessigkeit — der Aufwand
traegt den Nutzen nicht, und das Risiko besteht in *neuen* Zeigern.

Deshalb ist `legacy` im Default nicht rot. Erst wenn der Bestand abgebaut ist,
schaltet `--strict` die Stufe auf `error` und haelt sie geschlossen.

## Was hier ausdruecklich *nicht* hilft

`.git-blame-ignore-revs` (`git blame --ignore-revs-file`) wird in diesem
Zusammenhang regelmaessig als Loesung angeboten. Es ist keine: es entfernt
Blame-Rauschen durch Reformatierungs-Commits und beruehrt Zeiger-Drift in
Dokumenten ueberhaupt nicht.
