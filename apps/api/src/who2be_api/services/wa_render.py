"""Rendering und Entschaerfung der WorkArea-Tabellen-Ergebnisse (ADR-0049).

Reine Funktionen: kein I/O, kein DB-Zugriff, keine HTTPException und kein
`ApiGateError` (ARC-3) — was hier passiert, ist Text hinein, Text hinaus, und
genau deshalb ohne Datenbank testbar. Der Modulzweck ist die Ausgabeseite des
Tabellen-Stores: die Markdown-Tabelle, der CSV-Export mit Formel-Prefix-Guard
(OWASP CSV Injection, Security-Review L5) und die Komposition des
Result-Docs, das `wa_tables.save_query_result` als Artifact einfriert.

Die Entschaerfungen sind kein Beiwerk, sondern der Grund fuer das Modul: das
Versprechen aus Spec §10.6 lautet „der SERVER rendert, nie Modell-Text". Es
ist nur so viel wert wie die Behandlung all dessen, was NICHT aus der Engine
kommt — Titel und SQL aus dem Request, Zellinhalte aus importierten
Fremddaten. `single_line`, `sql_fence`, `neutralize_anchor`, `markdown_cell`
und `csv_cell` sind die fuenf Stellen, an denen dieser Fremdtext seine
Struktur-Wirkung verliert (Security-Review M4/L5).

Abgrenzung zu den beiden anderen Markdown-Renderern im Repo — drei
verschiedene Aufgaben, deshalb sprechende Namen statt dreimal
`render_markdown`:

- `entity_export_service._render_markdown` baut das EXPORT-Dokument einer
  versionierten Entity (YAML-Frontmatter + Body).
- `wa_blocks.render_markdown` rendert eine doc-Block-Liste zurueck zu
  Markdown und annotiert dabei die Anker (`` [#<block_id>]``, ADR-0021).
- `render_table_markdown` hier rendert ein Query-RESULT-SET als
  Markdown-Tabelle und entschaerft dabei ebendiese Anker-Sprache, weil
  Zellinhalte sie nicht sprechen duerfen.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Final


def single_line(text: str) -> str:
    """Presst Freitext auf EINE Zeile ohne Steuerzeichen (Security-Review M4).

    `title` kommt aus dem Request und landet als ``# {title}`` im
    server-komponierten Markdown. Ohne diese Normalisierung kann ein Titel
    mit ``\\n`` beliebige weitere Bloecke, Fences oder Anker-Marker in das
    Artifact schreiben — der Agent diktierte dann Struktur, die als
    Server-Ausgabe gelesen wird.
    """
    collapsed = "".join(
        " " if character < " " or character == "\x7f" else character for character in text
    )
    return " ".join(collapsed.split()) or "Ergebnis"


def sql_fence(sql: str) -> str:
    """Waehlt einen Fence, der laenger ist als jede Backtick-Folge im SQL (M4).

    Ein fixes ```` ``` ```` liesse sich mit Backticks IM SQL schliessen — der
    Rest der Query stuende danach als freier Markdown-Text im Artifact.
    """
    longest = 0
    current = 0
    for character in sql:
        current = current + 1 if character == "`" else 0
        longest = max(longest, current)
    return "`" * max(3, longest + 1)


def compose_result_doc(
    *,
    title: str,
    table_name: str,
    sql: str,
    columns: list[str],
    rows: list[list[object]],
    truncated: bool,
) -> str:
    """Komponiert das doc-Artifact eines eingefrorenen Query-Ergebnisses (WP16).

    Spec §10.6: die Zahlen im Artifact stammen aus dem Result-Set der Engine
    — der SERVER rendert (via `render_table_markdown`), nie Modell-Text. Der
    Zeitstempel ist der Ausfuehrungszeitpunkt (UTC); `occurred_at` des
    Artifacts traegt davon getrennt den FACHLICHEN Zeitpunkt aus dem Request.

    Alles, was NICHT aus der Engine kommt (`title`, `sql`), wird vorher
    entschaerft (`single_line`, `sql_fence`, `neutralize_anchor`) — sonst
    waere „der Server rendert" nur nominell wahr (Security-Review M4).
    """
    stamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    cut = ", gekuerzt" if truncated else ""
    safe_title = neutralize_anchor(single_line(title))
    fence = sql_fence(sql)
    return (
        f"# {safe_title}\n\n"
        f"Eingefrorenes Query-Ergebnis vom {stamp} "
        f"(Tabelle '{table_name}', {len(rows)} Zeilen{cut}).\n\n"
        f"{fence}sql\n{sql}\n{fence}\n\n"
        f"{render_table_markdown(columns, rows)}\n"
    )


def neutralize_anchor(text: str) -> str:
    """Entschaerft ``[#...]``-Anker-Marker in Freitext (Security-Review M4).

    ``[#xxxxxxxx]`` ist die ANKER-Sprache der Artifacts (ADR-0021): der
    Lesepfad rendert damit Block-Adressen. Steht die Sequenz in Zellinhalten
    oder im Titel, faelscht sie Anker, die es nicht gibt. Ein eingefuegtes
    Leerzeichen bricht das Muster, ohne den Text unlesbar zu machen (bewusst
    kein Zero-Width-Zeichen: unsichtbare Fixes sind nicht pruefbar).
    """
    return text.replace("[#", "[ #")


def markdown_cell(value: object) -> str:
    """Eine Zelle als Markdown-Tabellenzelle — strukturneutral (M4).

    Drei Angriffe, drei Antworten: ``|`` bricht die Spaltenstruktur
    (escaped), ``\\r``/``\\n`` brechen die ZEILE (zu Leerzeichen — sonst
    schreibt eine Zelle beliebige neue Tabellenzeilen oder Bloecke), und
    ``[#`` faelscht Anker (`neutralize_anchor`). Zellinhalte stammen aus
    importierten Fremddaten und sind damit ebenso untrusted wie Agenten-Text.
    """
    if value is None:
        return ""
    flattened = "".join(" " if character in "\r\n\t" else character for character in str(value))
    return neutralize_anchor(flattened.replace("|", "\\|"))


def render_table_markdown(columns: list[str], rows: list[list[object]]) -> str:
    """Ergebnis als Markdown-Tabelle (agentengerecht, Entscheidung 7)."""
    lines = [
        "| " + " | ".join(markdown_cell(column) for column in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines.extend("| " + " | ".join(markdown_cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


# Zeichen, die Tabellenkalkulationen als Formel-Start lesen (OWASP CSV
# Injection). Ein importierter Zellwert `=cmd|'/c calc'!A1` wird in Excel/
# Sheets beim Oeffnen des Exports AUSGEFUEHRT — der Export ist damit ein
# Angriffspfad aus fremden Quelldaten in das Geraet des Menschen.
CSV_FORMULA_PREFIXES: Final = ("=", "+", "-", "@", "\t", "\r")


def csv_cell(value: object) -> object:
    """Entschaerft Formel-Zellen im CSV-Export (Security-Review L5).

    Nur `str`-Werte werden praefixiert: SQLite liefert Zahlen als int/float,
    und ein numerisches ``-3.2`` ist in jeder Tabellenkalkulation eine ZAHL,
    keine Formel. So bleibt der haeufigste legitime Fall (negative Betraege
    aus NUMERIC-Spalten) unveraendert, waehrend jeder Textwert mit
    Formel-Praefix ein fuehrendes ``'`` bekommt.
    """
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def render_table_csv(columns: list[str], rows: list[list[object]]) -> str:
    """Ergebnis als CSV (stdlib `csv`, QUOTE_MINIMAL); None → leere Zelle."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow([csv_cell(column) for column in columns])
    for row in rows:
        writer.writerow([csv_cell(value) for value in row])
    return buffer.getvalue()
