"""Regression (DB-frei): die in den Builder-Seed-Migrationen eingebetteten
`tool_policy`-JSONs muessen gegen `AgentToolPolicy` validieren.

Hintergrund: 0047 (Builder) und 0060 (Builder-Lite) schrieben `agent_read`
faelschlich als JSON-Boolean `true`; `agent_read` ist aber ein `ReadScope`
(all/assigned/none). Das liess jeden Read, der die Agent-Zeile zu `AgentRead`
validiert (`list_agents`/`get_agent`/`fetch_agent`), mit 500 scheitern. Dieser
Test parst die Policy direkt aus dem Migrations-SQL und faengt den Fehler ohne DB.

Dazu (Content-Stand 15, ADR-0047) die DB-freien Zusicherungen zur *heutigen*
kanonischen Policy aus `_builder_tool_policy()`: sie traegt die drei
Arbeitsbereichs-Capabilities, ist an Fach-Agenten weitergebbar (`is_within`),
die Sichtbarkeits-SSoT laesst den Builder die Schreib-Tools aufrufen, und der
`tools-overview`-Resolver markiert die zugehoerigen Gruppen als Schreibzugriff.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_api.core.migrations import MIGRATIONS_DIR
from who2be_api.repositories.workspace_repository import _builder_tool_policy
from who2be_api.services.placeholders._core import RenderContext
from who2be_api.services.placeholders.resolvers.tools import _TOOLS, ToolsOverviewResolver
from who2be_models import is_tool_visible
from who2be_models.tool_policy import AgentToolPolicy

# Die kuratierten Gruppen, die die neuen Capabilities tragen — ueber die
# Tool-Namen gesucht, damit ein Umbau der Gruppierung hier auffaellt statt
# still durchzurutschen.
_WORKAREA_GROUPS = [
    doc for doc in _TOOLS if {"create_artifact", "create_node", "create_edge"} & set(doc.tool_names)
]

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


def test_builder_policy_carries_workarea_and_kb_capabilities() -> None:
    """Content-Stand 15 (ADR-0047): die kanonische Builder-Policy traegt die
    drei Arbeitsbereichs-Capabilities.

    Ohne sie koennte der Builder sie wegen der `is_within`-Anti-Eskalation
    auch keinem Fach-Agenten vergeben — die Weitergabe ist der Zweck.
    """
    policy = AgentToolPolicy.model_validate(_builder_tool_policy())
    assert policy.workarea_write is True
    assert policy.kb_write is True
    assert policy.kb_edge_write is True
    # Anti-Eskalation: was der Builder selbst hat, darf er weitergeben.
    delegated = AgentToolPolicy(workarea_write=True, kb_write=True, kb_edge_write=True)
    assert delegated.is_within(policy) is True


_WORKAREA_WRITE_TOOLS = ("create_artifact", "create_node", "create_edge")


def test_builder_may_call_workarea_and_kb_write_tools() -> None:
    """Die Sichtbarkeits-SSoT (ADR-0042) laesst den Builder die neuen
    Schreib-Tools aufrufen — und einen Agenten ohne die Capabilities nicht.

    `is_tool_visible` ist dieselbe Funktion, die `PolicyFilterMiddleware`
    fuer `tools/list` und der Resolver fuer den System-Prompt nutzen; sie ist
    damit der aussagekraeftige Pruefpunkt fuer „der Builder darf das jetzt".
    """
    builder = AgentToolPolicy.model_validate(_builder_tool_policy())
    lean = AgentToolPolicy()
    for name in _WORKAREA_WRITE_TOOLS:
        assert is_tool_visible(name, builder) is True, name
        assert is_tool_visible(name, lean) is False, name


def test_builder_tools_overview_announces_workarea_write_access() -> None:
    """Der gerenderte System-Prompt des Builders fuehrt die WorkArea-/KB-Gruppen
    und markiert sie als Schreibzugriff — ohne Sidecar-Aenderung.

    Belegt die Annahme hinter dem reinen Policy-Bump (Content-Stand 15): die
    Tools stehen bereits in der kuratierten `_TOOLS`-Liste des Resolvers.
    Geprueft wird der `has_visible_write`-Pfad, denn nur der haengt an der
    Capability — die Signatur-Zeile einer gemischten Gruppe nennt ihre
    Schreib-Tools auch dann, wenn der Agent sie nicht halten darf.
    """
    ctx = RenderContext(
        workspace_id=uuid4(),
        persona_id=None,
        now=datetime(2026, 8, 16, tzinfo=UTC),
        tool_policy=AgentToolPolicy.model_validate(_builder_tool_policy()),
    )
    # Der Resolver liest die DB nicht (`db` ist mit ARG002 markiert).
    text = asyncio.run(ToolsOverviewResolver().resolve("", ctx, cast("Any", None))).text

    assert "search_workarea" in text
    assert "search_kb" in text
    for group in _WORKAREA_GROUPS:
        assert group.has_visible_write(ctx.tool_policy) is True, group.signature
        # Gegenprobe: ohne die Capabilities faellt der Schreib-Hinweis weg.
        assert group.has_visible_write(AgentToolPolicy()) is False, group.signature
