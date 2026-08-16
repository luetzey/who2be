"""Drift-Guard fuer das tools/list-Payload-Budget (WP10, ADR-0047).

Hintergrund (server.py, Kommentar zu `output_schema=None`): Claude Chat
budgetiert die Connector-Payload hart — waechst die tools/list-Antwort
unbemerkt, fliegt nicht EIN Tool raus, sondern die GESAMTE Tool-Liste.
Dieser Guard macht das Wachstum messbar statt gefuehlt:

- **Gesamt-Budget:** Baseline bei Einfuehrung (2026-08-13, 71 Tools) war
  110.133 Bytes; das Budget ist Baseline x ~1,45 und laesst damit Raum fuer
  die geplanten Phase-2-Tools (WP19, 71 -> 81), aber nicht fuer schleichende
  Docstring-Inflation. Reisst der Guard, zuerst Beschreibungen kuerzen bzw.
  die Fold-Reihenfolge aus dem Plan ziehen (`list_category_rules` ->
  `set_convention`), NICHT das Budget anheben.
- **Docstring-Cap fuer neue Domain-Module:** Die `tools/`-Module (WP8+)
  halten je Tool <= 1100 Zeichen Beschreibung. Der Bestand in `server.py`
  ist grandfathered (laengste Beschreibung 2047 Zeichen, transition-Tools
  mit `TRANSITION_RULE_DOC`).
"""

import importlib
import inspect
import json
import pkgutil

import pytest

from who2be_mcp import tools as tools_pkg
from who2be_mcp.server import mcp

# Baseline 2026-08-13: 71 Tools / 110_133 Bytes (utf-8, name+description+
# inputSchema). Budget ~x1,45 — Headroom fuer WP19 (81 Tools), nicht mehr.
_PAYLOAD_BUDGET_BYTES = 160_000
_NEW_TOOL_DOC_CAP = 1_100


async def _tools_payload_bytes() -> int:
    tools = await mcp.list_tools(run_middleware=False)
    payload = [
        {"name": t.name, "description": t.description or "", "inputSchema": t.parameters}
        for t in tools
    ]
    return len(json.dumps(payload, ensure_ascii=False).encode())


def test_tools_list_payload_stays_under_budget() -> None:
    import asyncio

    size = asyncio.run(_tools_payload_bytes())
    assert size <= _PAYLOAD_BUDGET_BYTES, (
        f"tools/list-Payload {size} Bytes > Budget {_PAYLOAD_BUDGET_BYTES} — "
        "Beschreibungen kuerzen oder Tools falten (Plan-Fold-Reihenfolge), "
        "nicht das Budget anheben."
    )


@pytest.mark.parametrize(
    "module_name",
    [name for _, name, _ in pkgutil.iter_modules(tools_pkg.__path__)],
)
def test_new_domain_tool_docstrings_stay_capped(module_name: str) -> None:
    """Jedes Tool der neuen `tools/`-Module haelt den 1100-Zeichen-Cap."""
    module = importlib.import_module(f"who2be_mcp.tools.{module_name}")
    offenders = {
        name: len(inspect.getdoc(fn) or "")
        for name, fn in vars(module).items()
        if inspect.iscoroutinefunction(fn)
        and not name.startswith("_")
        and len(inspect.getdoc(fn) or "") > _NEW_TOOL_DOC_CAP
    }
    assert not offenders, f"Docstrings ueber {_NEW_TOOL_DOC_CAP} Zeichen: {offenders}"
