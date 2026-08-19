"""Rendering und Entschaerfung der WorkArea-Tabellen-Ergebnisse (ADR-0049).

Reine Funktionen: kein I/O, kein DB-Zugriff, keine HTTPException und kein
`ApiGateError` (ARC-3) — was hier passiert, ist Text hinein, Text hinaus, und
genau deshalb ohne Datenbank testbar. Der Modulzweck ist die Ausgabeseite des
Tabellen-Stores: die Markdown-Tabelle, der CSV- und der XLSX-Export mit
Formel-Prefix-Guard (OWASP CSV Injection, Security-Review L5) und die
Komposition des Result-Docs, das `wa_tables.save_query_result` als Artifact
einfriert. Dazu die Download-Formate eines doc-Artifacts
(`render_artifact_export_markdown`, `render_artifact_export_html`).

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
import html
import io
from datetime import UTC, datetime
from enum import Enum
from typing import Final

from markdown_it import MarkdownIt

# openpyxl liefert keine Typ-Stubs (kein `py.typed`) — eng begrenzte Ausnahme
# an genau dieser Import-Zeile, unser eigener Code bleibt strict.
from openpyxl import Workbook  # type: ignore[import-untyped]
from openpyxl.cell.cell import (  # type: ignore[import-untyped]
    ILLEGAL_CHARACTERS_RE,
)

from who2be_models.workarea import OccurredPrecision, Sensitivity


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
CSV_FORMULA_PREFIXES: Final = ("=", "+", "-", "@", "\t", "\r", "\n")

# Fuehrende Zeichen, hinter denen sich ein Formel-Praefix verstecken kann:
# Google Sheets TRIMMT beim CSV-Import fuehrenden Whitespace und wertet dann
# aus — ` =1+1` wuerde einen Guard umgehen, der nur auf das erste Zeichen
# schaut. Deshalb wird auf einer getrimmten Kopie geprueft, praefixiert wird
# der Originalwert (Security-Review 2026-08-19, L-2).
_FORMULA_HIDING_LEAD: Final = " \t\r\n\u00a0\ufeff"


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
    if isinstance(value, str) and value.lstrip(_FORMULA_HIDING_LEAD).startswith(
        CSV_FORMULA_PREFIXES
    ):
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


# Zeichen, die Excel im Blattnamen verbietet, plus die harte 31-Zeichen-Grenze.
# openpyxl WIRFT bei beidem (ValueError) statt still zu kuerzen — der Name
# kommt aber aus dem Tabellen-Katalog und damit aus Agenten-Hand, also
# bereinigen wir vorher, statt einen Export an einem Slash scheitern zu lassen.
_SHEET_TITLE_FORBIDDEN: Final = "[]:*?/\\"
_SHEET_TITLE_MAX_LENGTH: Final = 31


def _sheet_title(name: str) -> str:
    """Bereinigt einen Tabellennamen zu einem gueltigen Excel-Blattnamen."""
    cleaned = "".join(
        "_" if character in _SHEET_TITLE_FORBIDDEN or character < " " else character
        for character in name
    )
    return cleaned[:_SHEET_TITLE_MAX_LENGTH].strip() or "Ergebnis"


def _xlsx_cell(value: object) -> object:
    """Eine Zelle fuer die Arbeitsmappe — Strings durch den CSV-Guard.

    `csv_cell` ist die EINE Quelle der Formel-Entschaerfung (keine zweite
    Praefix-Liste). Nur `None` wird vorher abgefangen: im CSV ist die leere
    Zelle der leere String, in XLSX ist sie die LEERE Zelle — ein `""` waere
    dort ein Textwert und damit eine andere Aussage.
    """
    if value is None:
        return None
    if isinstance(value, str):
        # openpyxl wirft bei den XML-illegalen Steuerzeichen (C0 ohne
        # Tab/LF/CR) einen `IllegalCharacterError` — eine einzige Alt-Zeile
        # wuerde den XLSX-Export der Tabelle dauerhaft zum 500er machen.
        # Der Schreibpfad lehnt solche Zellen inzwischen mit 422 ab
        # (`wa_tables._validate_cell_text`); dieses Strippen ist die zweite
        # Linie fuer Bestandsdaten (Security-Review 2026-08-19, M-2).
        return csv_cell(ILLEGAL_CHARACTERS_RE.sub("", value))
    return value


def render_table_xlsx(name: str, columns: list[str], rows: list[list[object]]) -> bytes:
    """Ergebnis als XLSX-Arbeitsmappe, in memory gebaut (ADR-0049).

    Formel-Injection (Security-Review L5, analog CSV): openpyxl LEITET aus
    einem String mit ``=``-Praefix eine Formelzelle ab — die Zelle traegt dann
    Typ ``f`` und Excel fuehrt sie beim Oeffnen aus. Der Angriffspfad ist
    derselbe wie beim CSV-Export: fremde Quelldaten landen ueber den Ingest in
    einer Tabelle, der Mensch laedt den Export herunter und oeffnet ihn lokal.
    Deshalb geht jeder `str` durch `csv_cell`; Nicht-Strings (int/float/bool/
    None) werden nativ geschrieben, damit Zahlen Zahlen bleiben.
    """
    workbook = Workbook()
    sheet = workbook.worksheets[0]
    sheet.title = _sheet_title(name)
    sheet.append([_xlsx_cell(column) for column in columns])
    for row in rows:
        sheet.append([_xlsx_cell(value) for value in row])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _yaml_scalar(value: object) -> str:
    """Minimaler YAML-Scalar fuer Frontmatter (Strings doppelt gequotet).

    Bewusst eine eigene kleine Funktion nach dem Muster von
    `entity_export_service._yaml_scalar`: das dortige Symbol ist privat und
    gehoert zur Export-Achse der versionierten Entities. Ein Import ueber die
    Modulgrenze wuerde die WorkArea-Achse daran koppeln (ADR-0047: NEBEN der
    Resource-Achse, nicht daran haengend). Aenderungen am Quoting deshalb hier
    UND dort pruefen.

    Jeder Wert laeuft durch `single_line`: ein roher Zeilenumbruch in
    `source_system`/`source_url` (Fremdsystem-Felder ohne Pattern) wuerde die
    Frontmatter-Struktur genauso aufbrechen wie im Titel — Parser schneiden
    zeilenbasiert am ersten `---` (Security-Review 2026-08-19, M-3).
    """
    return '"' + single_line(str(value)).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _frontmatter_value(value: object) -> str:
    """Ein Frontmatter-Wert als Scalar: Datum ISO-formatiert, Enum als `.value`."""
    if isinstance(value, datetime):
        return _yaml_scalar(value.isoformat())
    if isinstance(value, Enum):
        return _yaml_scalar(value.value)
    return _yaml_scalar(value)


def render_artifact_export_markdown(
    *,
    title: str,
    markdown: str,
    occurred_at: datetime | None,
    occurred_precision: OccurredPrecision | None,
    sensitivity: Sensitivity | None,
    source_system: str | None,
    source_url: str | None,
    exported_at: datetime,
) -> str:
    """Ein doc-Artifact als Markdown-Download: YAML-Frontmatter + Body.

    Nicht gesetzte Felder werden AUSGELASSEN statt leer geschrieben — ein
    ``source_url: ""`` waere die Behauptung einer Quelle, die es nicht gibt.
    Der Titel laeuft durch `single_line`, weil ein Zeilenumbruch darin die
    Frontmatter-Struktur aufbrechen wuerde (Security-Review M4).
    """
    fields: list[tuple[str, object | None]] = [
        ("title", single_line(title)),
        ("occurred_at", occurred_at),
        ("occurred_precision", occurred_precision),
        ("sensitivity", sensitivity),
        ("source_system", source_system),
        ("source_url", source_url),
        ("exported_at", exported_at),
    ]
    lines = ["---"]
    lines.extend(
        f"{key}: {_frontmatter_value(value)}" for key, value in fields if value is not None
    )
    lines.append("---")
    lines.append("")
    return "\n".join(lines) + "\n" + markdown


# Schlichtes Inline-CSS: der Export ist EINE Datei ohne Netzzugriff (keine
# externe Schrift, kein Stylesheet-Link) — er soll offline lesbar sein. Die
# Meta-CSP unten erzwingt das auch fuer den INHALT: gerenderte Bild-/Link-
# Ziele aus Fremdquellen (Tracking-Pixel) laden sonst beim Oeffnen aus
# `file://`, wo die Caddy-CSP der API nicht gilt (Security-Review L-1).
_EXPORT_HTML_CSS: Final = """
body { max-width: 46rem; margin: 2rem auto; padding: 0 1rem;
       font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; }
h1, h2, h3 { line-height: 1.25; }
code, pre { font-family: ui-monospace, monospace; }
pre { padding: 0.75rem; overflow-x: auto; background: #f4f4f5; }
table { border-collapse: collapse; }
th, td { padding: 0.35rem 0.6rem; border: 1px solid #a1a1aa; text-align: left; }
img { max-width: 100%; }
"""


def render_artifact_export_html(*, title: str, markdown: str) -> str:
    """Ein doc-Artifact als eigenstaendiges HTML-Dokument.

    Die Renderer-Optionen sind WOERTLICH dieselben wie in
    `agent_render_service` (``MarkdownIt("commonmark", {"html": False,
    "breaks": True})``) — zwei Stellen, EIN Verhalten; bei einer Abweichung
    zuerst dort lesen. ``html: False`` escapet rohes HTML im Markdown, statt
    es durchzureichen: Artifact-Inhalte stammen aus Ingest und Agenten-Text,
    ein durchgereichtes ``<script>`` liefe im Browser des Menschen. Titel und
    Ueberschrift gehen zusaetzlich durch `html.escape`, weil sie NICHT durch
    den Markdown-Renderer laufen.
    """
    safe_title = html.escape(single_line(title))
    body = MarkdownIt("commonmark", {"html": False, "breaks": True}).render(markdown)
    return (
        "<!doctype html>\n"
        '<html lang="de">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:\">\n"
        '<meta name="referrer" content="no-referrer">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{safe_title}</title>\n"
        f"<style>{_EXPORT_HTML_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        f"<h1>{safe_title}</h1>\n"
        f"{body}"
        "</body>\n"
        "</html>\n"
    )
