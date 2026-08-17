"""Wie JSON an einen jsonb-Parameter gebunden wird (Befund 2026-08-16).

Der App-Pool registriert einen jsonb-Codec (`core/db.init_connection`,
`encoder=json.dumps`). Damit haengt die RICHTIGE Bind-Form davon ab, ob die
Connection den Codec traegt — und wer das verwechselt, bekommt keinen Fehler,
sondern einen JSON-*String* in der Spalte. Genau so ist `GET /wa-tables/{id}`
(MCP: `describe_table`) fuer jede Area gestorben, die eine Quell-Konvention
hatte: ein Leser ohne Toleranz-Zweig, und der Endpunkt war weg.

Zwei Tests, zwei Ebenen:

1. **Die Semantik selbst** — als ausfuehrbare Doku gegen die echte Datenbank.
   Aendert eine asyncpg-/PG-Version daran etwas, faellt es hier auf und nicht
   im Betrieb.
2. **Drift** — kein Repository darf einen vor-serialisierten String an einen
   nackten `$n::jsonb`-Cast binden. Ausnahmen brauchen einen Eintrag in der
   Allowlist UND eine Begruendung in der Datei.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import asyncpg
import pytest

_REPOSITORIES = Path(__file__).resolve().parents[1] / "src" / "who2be_api" / "repositories"

# Dateien, die bewusst vor-serialisiert binden — mit dem Grund, der auch in
# der Datei stehen muss. Der Start-Sync laeuft auf einer OWNER-Connection
# (Migrations-URL) ohne Pool-Codec; dort ist der String die richtige Form.
_ALLOWLIST: dict[str, str] = {
    "workspace_repository.py": "kein Pool-Codec",
}

# `$6::text::jsonb` matcht bewusst NICHT: diese Form ist auf BEIDEN
# Connection-Arten korrekt (der Parameter ist dann text, der Codec greift gar
# nicht erst) und damit die sichere Antwort, wenn der Aufrufer offen ist.
_BARE_JSONB_CAST = re.compile(r"\$\d+::jsonb")


def _code_lines(path: Path) -> str:
    """Dateiinhalt ohne reine Kommentarzeilen.

    Ohne das wuerde die Erklaerung des Fehlers als Fehler gezaehlt — die
    Kommentare zitieren die falsche Form absichtlich.
    """
    return "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


@pytest.mark.integration
def test_bind_semantik_von_jsonb_parametern() -> None:
    """Die gemessene Wahrheit, auf der der Fix steht.

    Mit Codec ist `::jsonb` + dict richtig und `::jsonb` + String der Bug;
    `::text::jsonb` + String ist auf beiden Connection-Arten richtig.
    """
    from who2be_api.core.config import get_settings

    payload = {"a": 1}

    async def _run() -> tuple[str, str, str, str]:
        codec_conn = await asyncpg.connect(get_settings().database_url)
        plain_conn = await asyncpg.connect(get_settings().database_url)
        try:
            await codec_conn.set_type_codec(
                "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
            )
            mit_dict = await codec_conn.fetchval("SELECT jsonb_typeof($1::jsonb)", payload)
            mit_string = await codec_conn.fetchval(
                "SELECT jsonb_typeof($1::jsonb)", json.dumps(payload)
            )
            text_cast = await codec_conn.fetchval(
                "SELECT jsonb_typeof($1::text::jsonb)", json.dumps(payload)
            )
            ohne_codec = await plain_conn.fetchval(
                "SELECT jsonb_typeof($1::text::jsonb)", json.dumps(payload)
            )
            return mit_dict, mit_string, text_cast, ohne_codec
        finally:
            await codec_conn.close()
            await plain_conn.close()

    mit_dict, mit_string, text_cast, ohne_codec = asyncio.run(_run())
    assert mit_dict == "object"
    # Der Bug in einer Zeile: kein Fehler, nur die falsche Form.
    assert mit_string == "string"
    assert text_cast == "object"
    assert ohne_codec == "object"


def test_kein_vorserialisiertes_json_an_nacktem_jsonb_cast() -> None:
    """Drift-Guard ueber alle Repositories.

    Bewusst grob ueber den Dateiinhalt: die Kombination „`json.dumps(` im
    Code UND `$n::jsonb`" ist der Verdacht, und ein Test, der erst Aufrufer
    und Connection-Herkunft aufloest, wuerde beim naechsten Umbau kaputtgehen
    statt zu schuetzen. Wer die Kombination braucht, traegt sie mit Grund in
    `_ALLOWLIST` ein — das ist die Stelle, an der jemand nachdenkt.
    """
    verdaechtig: list[str] = []
    for path in sorted(_REPOSITORIES.glob("*.py")):
        code = _code_lines(path)
        if "json.dumps(" not in code or not _BARE_JSONB_CAST.search(code):
            continue
        if path.name not in _ALLOWLIST:
            verdaechtig.append(path.name)
            continue
        begruendung = _ALLOWLIST[path.name]
        assert begruendung in path.read_text(encoding="utf-8"), (
            f"{path.name} steht auf der Allowlist, aber die Begruendung "
            f"'{begruendung}' steht nicht mehr in der Datei — entweder die "
            "Bindung ist inzwischen anders geloest (dann Allowlist-Eintrag "
            "entfernen) oder der Grund ist verlorengegangen."
        )

    assert verdaechtig == [], (
        "Vor-serialisiertes JSON an einem nackten `$n::jsonb`-Cast: auf einer "
        "Connection MIT jsonb-Codec encodiert das ein zweites Mal und legt "
        "einen JSON-String in der Spalte ab (Befund 2026-08-16, describe → "
        "500). Entweder das dict binden (App-Pool) oder `$n::text::jsonb` "
        "nutzen (auf beiden Connection-Arten korrekt). Betroffen: " + ", ".join(verdaechtig)
    )
