"""Drift-Guard: die Werkzeug-Anzahl in der Prosa gegen die Registry.

`MCP_TOOL_REQUIREMENTS` ist die durchgesetzte Quelle der registrierten
MCP-Werkzeuge — `test_tool_requirements.py` haelt die Laenge fest, der
Paritaetstest in `apps/mcp/tests/test_policy_filter.py` erzwingt Gleichheit
gegen den Server. Die nach aussen sichtbaren Zahlen in `README.md` und
`ROADMAP.md` hingen bisher an keiner Pruefung und sind genau deshalb
gedriftet (Befund 2026-09-25: Prosa nannte 81, die Registry hatte 83).

Dieser Guard schliesst die Luecke in der Richtung, in der sie aufgetreten
ist: waechst die Registry, bricht der Test und nennt die Datei, die
nachzuziehen ist. Er prueft zusaetzlich, dass das Muster ueberhaupt noch
trifft — eine Umformulierung soll den Guard nicht still abschalten.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from who2be_models import MCP_TOOL_REQUIREMENTS

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Je Eintrag: Datei + Muster mit EINER Gruppe, die die Zahl traegt.
_DOC_CLAIMS = (
    ("README.md", re.compile(r"\*\*MCP server\*\*\s+—\s+(\d+)\s+tools")),
    ("ROADMAP.md", re.compile(r"(\d+)\s+MCP tools in total")),
)


@pytest.mark.parametrize(
    ("relative_path", "pattern"),
    _DOC_CLAIMS,
    ids=[relative_path for relative_path, _ in _DOC_CLAIMS],
)
def test_documented_tool_count_matches_registry(
    relative_path: str, pattern: re.Pattern[str]
) -> None:
    document = _REPO_ROOT / relative_path
    text = document.read_text(encoding="utf-8")

    matches = pattern.findall(text)
    assert matches, (
        f"{relative_path}: Muster {pattern.pattern!r} trifft nicht mehr. Entweder "
        "die Aussage wurde umformuliert (dann das Muster hier nachziehen) oder sie "
        "ist entfallen (dann den Eintrag aus `_DOC_CLAIMS` entfernen) — ein stumm "
        "durchlaufender Guard ist schlimmer als keiner."
    )

    expected = len(MCP_TOOL_REQUIREMENTS)
    documented = {int(value) for value in matches}
    assert documented == {expected}, (
        f"{relative_path} nennt {sorted(documented)} MCP-Werkzeuge, die Registry "
        f"`MCP_TOOL_REQUIREMENTS` hat {expected}. Die Registry gilt: Zahl im "
        "Dokument nachziehen, nicht den Test."
    )
