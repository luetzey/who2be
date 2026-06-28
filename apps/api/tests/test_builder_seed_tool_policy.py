"""Regression (DB-frei): die in den Builder-Seed-Migrationen eingebetteten
`tool_policy`-JSONs muessen gegen `AgentToolPolicy` validieren.

Hintergrund: 0047 (Builder) und 0060 (Builder-Lite) schrieben `agent_read`
faelschlich als JSON-Boolean `true`; `agent_read` ist aber ein `ReadScope`
(all/assigned/none). Das liess jeden Read, der die Agent-Zeile zu `AgentRead`
validiert (`list_agents`/`get_agent`/`fetch_agent`), mit 500 scheitern. Dieser
Test parst die Policy direkt aus dem Migrations-SQL und faengt den Fehler ohne DB.
"""

from __future__ import annotations

import json
import re

import pytest
from pydantic import ValidationError

from who2be_api.core.migrations import MIGRATIONS_DIR
from who2be_models.tool_policy import AgentToolPolicy

# (Migrations-Datei, Dollar-Quote-Tag) der agent.tool_policy-Literale.
_POLICY_SOURCES = [
    ("0047_seed_builder_default_agent.sql", "w2bpol"),
    ("0060_seed_builder_lite_agent.sql", "w2bltpol"),
]


def _extract_policy(filename: str, tag: str) -> dict[str, object]:
    sql = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
    match = re.search(rf"\${tag}\$(.*?)\${tag}\$", sql, re.S)
    assert match is not None, f"tool_policy-Literal ${tag}$ in {filename} nicht gefunden."
    parsed: dict[str, object] = json.loads(match.group(1))
    return parsed


@pytest.mark.parametrize(("filename", "tag"), _POLICY_SOURCES)
def test_seed_migration_tool_policy_validates(filename: str, tag: str) -> None:
    policy = AgentToolPolicy.model_validate(_extract_policy(filename, tag))
    # Der Meta-Agent (Builder/Builder-Lite) liest den ganzen Workspace.
    assert policy.agent_read.value == "all"
    assert policy.agent_write is True


def test_agent_read_boolean_is_rejected() -> None:
    """Dokumentiert die Ursache: `agent_read` ist ein ReadScope, kein bool."""
    with pytest.raises(ValidationError):
        AgentToolPolicy.model_validate({"agent_read": True})
