"""Werkzeug-Profile (ADR-0059, Paket Q1): Gruppen, Profile, Formel.

Prueft die Single Source of Truth in `who2be_models/tool_profiles.py`:
jedes Werkzeug in genau einer Gruppe, Kern nicht abwaehlbar, die Formel aus
§3.1, Rechte gehen vor, die mitgelieferten Profile aus §5.2 und dass das
Profil „Builder" alle Werkzeuge abdeckt, die die verwalteten Builder-Inhalte
(DE und EN) nennen. Die Rot-Probe am Ende stellt sicher, dass der
Paritaetstest ein Werkzeug ohne Gruppe tatsaechlich bemerkt.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import (
    BUILTIN_PROFILES,
    CORE_TOOLS,
    MCP_TOOL_REQUIREMENTS,
    TOOL_GROUP_OF,
    TOOL_GROUPS,
    AgentCapability,
    AgentToolPolicy,
    AgentToolProfileUpdate,
    BuiltinProfileKey,
    MemoryMode,
    ReadScope,
    SystemFeedbackCategory,
    ToolGroup,
    ToolProfileCreate,
    ToolProfileGrant,
    WhoAmIRead,
    WorkspaceRole,
    builtin_profile_tools,
    core_tools_in,
    effective_tool_set,
    expand_groups,
    is_tool_in_profile,
    is_tool_visible,
    is_tool_visible_for,
    is_tool_visible_for_with_profile,
    is_tool_visible_with_profile,
    tool_catalog,
    unknown_groups,
    unknown_tools,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BUILDER_CONTENT_DIR = _REPO_ROOT / "apps/api/src/who2be_api/repositories"

_FULL_POLICY = AgentToolPolicy(
    playbook_read=ReadScope.all,
    resource_read=ReadScope.all,
    agent_read=ReadScope.all,
    external_tool_read=ReadScope.all,
    persona_read=True,
    persona_write=True,
    playbook_write=True,
    resource_write=True,
    agent_write=True,
    system_prompt_write=True,
    feedback_write=True,
    feedback_resolve=True,
    promote_retire=True,
    external_tool_write=True,
    workarea_write=True,
    kb_write=True,
    kb_edge_write=True,
    test_report=True,
    case_triage=True,
    memory_mode=MemoryMode.auto,
)

_ALL_CAPS = list(AgentCapability)
_ALL_SCOPES = {
    "persona": ReadScope.all,
    "playbook": ReadScope.all,
    "resource": ReadScope.all,
    "agent": ReadScope.all,
    "external_tool": ReadScope.all,
}


def _grant_for(key: BuiltinProfileKey, **extra: list[str]) -> ToolProfileGrant:
    profile = BUILTIN_PROFILES[key]
    return ToolProfileGrant(
        id=uuid4(),
        name=profile.names["de"],
        groups=[g.value for g in profile.groups],
        tools=list(profile.tools),
        **extra,
    )


def _group_parity_errors(groups: Mapping[ToolGroup, tuple[str, ...]]) -> list[str]:
    """Abweichungen zwischen Gruppen und `MCP_TOOL_REQUIREMENTS`."""
    counts = Counter(tool for tools in groups.values() for tool in tools)
    errors = [f"{tool}: in {n} Gruppen" for tool, n in counts.items() if n > 1]
    errors += [f"{tool}: ohne Gruppe" for tool in MCP_TOOL_REQUIREMENTS if tool not in counts]
    errors += [f"{tool}: kein MCP-Werkzeug" for tool in counts if tool not in MCP_TOOL_REQUIREMENTS]
    return sorted(errors)


# --- Gruppen (§5.1) --------------------------------------------------------


def test_every_tool_is_in_exactly_one_group() -> None:
    assert _group_parity_errors(TOOL_GROUPS) == []
    assert set(TOOL_GROUP_OF) == set(MCP_TOOL_REQUIREMENTS)


def test_every_group_has_tools_and_enum_matches_mapping() -> None:
    assert list(TOOL_GROUPS) == list(ToolGroup)
    for group, tools in TOOL_GROUPS.items():
        assert tools, group


def test_edit_content_is_in_content_write() -> None:
    # ADR-0059 §5.1: `edit_content` (ADR-0058 W1-P3) kommt in `content_write`.
    assert TOOL_GROUP_OF["edit_content"] is ToolGroup.content_write


def test_core_tools_are_the_core_group() -> None:
    assert CORE_TOOLS == {"ping", "whoami", "report_problem"}
    assert set(TOOL_GROUPS[ToolGroup.core]) == CORE_TOOLS


def test_catalog_lists_groups_in_order_with_core() -> None:
    catalog = tool_catalog()
    assert [g.key for g in catalog.groups] == list(ToolGroup)
    assert set(catalog.core_tools) == CORE_TOOLS
    assert sum(len(g.tools) for g in catalog.groups) == len(MCP_TOOL_REQUIREMENTS)


# --- Mitgelieferte Profile (§5.2) -------------------------------------------


def test_builtin_profile_groups_match_adr() -> None:
    read = {ToolGroup.core, ToolGroup.read, ToolGroup.feedback_memory, ToolGroup.workarea_read}
    expected = {
        BuiltinProfileKey.read: read,
        BuiltinProfileKey.author: read
        | {ToolGroup.content_write, ToolGroup.transition, ToolGroup.workarea_write},
        BuiltinProfileKey.curator: read | {ToolGroup.transition, ToolGroup.curation},
        BuiltinProfileKey.builder: read
        | {
            ToolGroup.content_write,
            ToolGroup.transition,
            ToolGroup.agent_admin,
            ToolGroup.system_prompt,
            ToolGroup.curation,
        },
    }
    assert set(BUILTIN_PROFILES) == set(BuiltinProfileKey)
    for key, groups in expected.items():
        assert set(BUILTIN_PROFILES[key].groups) == groups, key
        assert BUILTIN_PROFILES[key].tools == (), key


def test_builder_profile_contains_workarea_read_w59_4() -> None:
    # Owner 2026-10-21: „Alle wie empfohlen, aber W59-4 ja".
    assert ToolGroup.workarea_read in BUILTIN_PROFILES[BuiltinProfileKey.builder].groups
    builder = builtin_profile_tools(BuiltinProfileKey.builder)
    assert set(TOOL_GROUPS[ToolGroup.workarea_read]) <= builder
    assert not set(TOOL_GROUPS[ToolGroup.workarea_write]) & builder


def test_builtin_profile_sizes() -> None:
    # ADR-0059 §5.2, gemessen bei 100 Werkzeugen. `edit_content` (ADR-0058)
    # kam danach in `content_write` und zaehlt bei Autor und Builder mit;
    # `update_rows`/`delete_rows` (ADR-0049-Nachtrag) kamen in `workarea_write`
    # und zaehlen nur beim Autor (Builder schreibt keine WorkArea).
    sizes = {key: len(builtin_profile_tools(key)) for key in BuiltinProfileKey}
    assert sizes == {
        BuiltinProfileKey.read: 42,
        BuiltinProfileKey.author: 77 + 1 + 2,
        BuiltinProfileKey.curator: 59,
        BuiltinProfileKey.builder: 85 + 1,
    }


def test_builtin_profiles_have_de_and_en_names() -> None:
    expected = {
        BuiltinProfileKey.read: ("Lesen", "Read"),
        BuiltinProfileKey.author: ("Autor", "Author"),
        BuiltinProfileKey.curator: ("Kurator", "Curator"),
        BuiltinProfileKey.builder: ("Builder", "Builder"),
    }
    for key, (de, en) in expected.items():
        assert BUILTIN_PROFILES[key].names == {"de": de, "en": en}


def _builder_content_files() -> list[Path]:
    files = [
        path
        for directory in (_BUILDER_CONTENT_DIR, _BUILDER_CONTENT_DIR / "en")
        for path in sorted(directory.glob("*.json"))
        if path.name.startswith(("builder_", "agent_builder"))
    ]
    return files


def test_builder_profile_covers_managed_builder_content_de_and_en() -> None:
    # §5.2: „Der Builder verliert keinen Arbeitsschritt." Jedes Werkzeug, das
    # Persona, Modi, Playbooks, Resource oder System-Prompt-Templates des
    # verwalteten Builders nennen (DE und EN), liegt im Profil „Builder".
    files = _builder_content_files()
    assert {p.parent.name for p in files} == {"repositories", "en"}
    assert len(files) >= 20, files
    names = sorted(MCP_TOOL_REQUIREMENTS, key=len, reverse=True)
    pattern = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(names) + r")(?![A-Za-z0-9_])")
    mentioned: set[str] = set()
    for path in files:
        mentioned |= set(pattern.findall(path.read_text(encoding="utf-8")))
    # Untergrenze gegen einen leer laufenden Scan. Seit Content-Stand 22
    # (Builder schlank B3, K2) zaehlen die Playbooks keine Werkzeuge mehr auf,
    # die tools/list schon beschreibt — 69 statt 70 genannte Werkzeuge.
    assert len(mentioned) >= 65, sorted(mentioned)
    missing = mentioned - builtin_profile_tools(BuiltinProfileKey.builder)
    assert missing == set()


# --- Formel (§3.1) ----------------------------------------------------------


def test_no_profile_and_alle_mean_all_tools() -> None:
    every = set(MCP_TOOL_REQUIREMENTS)
    assert effective_tool_set(None) == every
    assert effective_tool_set(ToolProfileGrant(name="Alle")) == every


def test_alle_with_removed_tool() -> None:
    grant = ToolProfileGrant(name="Alle", tools_removed=["create_agent"])
    assert effective_tool_set(grant) == set(MCP_TOOL_REQUIREMENTS) - {"create_agent"}
    assert is_tool_in_profile("create_agent", grant) is False
    assert is_tool_in_profile("update_agent", grant) is True


def test_profile_is_groups_union_tools_plus_added_minus_removed() -> None:
    grant = ToolProfileGrant(
        id=uuid4(),
        name="Eigen",
        groups=["read"],
        tools=["create_persona"],
        tools_added=["create_table"],
        tools_removed=["search", "create_persona"],
    )
    expected = (
        set(TOOL_GROUPS[ToolGroup.read]) | {"create_persona", "create_table"} | CORE_TOOLS
    ) - {"search", "create_persona"}
    assert effective_tool_set(grant) == expected
    for tool in MCP_TOOL_REQUIREMENTS:
        assert is_tool_in_profile(tool, grant) is (tool in expected), tool


def test_core_tools_survive_any_profile() -> None:
    grant = ToolProfileGrant(id=uuid4(), name="Leer", tools_removed=sorted(CORE_TOOLS))
    assert effective_tool_set(grant) == CORE_TOOLS
    for tool in CORE_TOOLS:
        assert is_tool_in_profile(tool, grant) is True


def test_unknown_names_are_skipped_on_evaluation() -> None:
    grant = ToolProfileGrant(
        id=uuid4(),
        name="Alt",
        groups=["read", "abgebaut"],
        tools=["entfallen"],
        tools_added=["auch_weg"],
    )
    assert effective_tool_set(grant) == set(TOOL_GROUPS[ToolGroup.read]) | CORE_TOOLS
    assert expand_groups(["abgebaut"]) == frozenset()


def test_effective_set_matches_is_tool_in_profile_for_builtins() -> None:
    for key in BuiltinProfileKey:
        grant = _grant_for(key)
        assert effective_tool_set(grant) == builtin_profile_tools(key), key
        for tool in MCP_TOOL_REQUIREMENTS:
            assert is_tool_in_profile(tool, grant) is (tool in builtin_profile_tools(key))


# --- Rechte gehen vor (§3.1 c) ----------------------------------------------


def test_profile_never_extends_rights_policy_path() -> None:
    policy = AgentToolPolicy()  # Standard-Rechte: keine Writes
    grant = ToolProfileGrant(name="Alle", tools_added=["create_agent", "create_table"])
    for tool in MCP_TOOL_REQUIREMENTS:
        by_rights = is_tool_visible(tool, policy)
        combined = is_tool_visible_with_profile(tool, policy, grant)
        if not by_rights:
            assert combined is by_rights, tool
    assert is_tool_visible_with_profile("create_agent", policy, grant) is False


def test_profile_never_extends_rights_whoami_path() -> None:
    grant = ToolProfileGrant(name="Alle", tools_added=["report_problem", "create_agent"])

    def visible(tool: str) -> bool | None:
        return is_tool_visible_for_with_profile(
            tool,
            unrestricted=False,
            role=WorkspaceRole.editor,
            capabilities=[],
            read_scopes=_ALL_SCOPES,
            memory_mode=MemoryMode.off,
            tool_profile=grant,
        )

    # Ohne `feedback_write` bleibt auch das Kern-Werkzeug `report_problem` weg.
    assert visible("report_problem") is False
    assert visible("create_agent") is False
    assert visible("whoami") is True


def test_full_rights_with_builder_profile_shows_exactly_the_profile() -> None:
    grant = _grant_for(BuiltinProfileKey.builder)
    builder = builtin_profile_tools(BuiltinProfileKey.builder)
    for tool in MCP_TOOL_REQUIREMENTS:
        expected = tool in builder
        assert is_tool_visible_with_profile(tool, _FULL_POLICY, grant) is expected, tool
        assert (
            is_tool_visible_for_with_profile(
                tool,
                unrestricted=False,
                role=WorkspaceRole.editor,
                capabilities=_ALL_CAPS,
                read_scopes=_ALL_SCOPES,
                memory_mode=MemoryMode.auto,
                tool_profile=grant,
            )
            is expected
        ), tool


def test_without_profile_wrappers_equal_rights_functions() -> None:
    # Ohne Profil keine Verhaltensaenderung gegenueber ADR-0042.
    for tool in [*MCP_TOOL_REQUIREMENTS, "does_not_exist"]:
        assert is_tool_visible_with_profile(tool, _FULL_POLICY, None) == is_tool_visible(
            tool, _FULL_POLICY
        )
        assert is_tool_visible_with_profile(tool, None, None) == is_tool_visible(tool, None)
        for unrestricted in (True, False):
            caps = [AgentCapability.feedback_write]
            scopes = {"playbook": ReadScope.none}
            with_profile = is_tool_visible_for_with_profile(
                tool,
                unrestricted=unrestricted,
                role=WorkspaceRole.viewer,
                capabilities=caps,
                read_scopes=scopes,
                memory_mode=MemoryMode.read_only,
            )
            rights_only = is_tool_visible_for(
                tool,
                unrestricted=unrestricted,
                role=WorkspaceRole.viewer,
                capabilities=caps,
                read_scopes=scopes,
                memory_mode=MemoryMode.read_only,
            )
            assert with_profile == rights_only, tool


def test_unknown_tool_stays_none_for_fail_open() -> None:
    grant = _grant_for(BuiltinProfileKey.read)
    assert is_tool_visible_with_profile("does_not_exist", _FULL_POLICY, grant) is None
    assert (
        is_tool_visible_for_with_profile(
            "does_not_exist",
            unrestricted=False,
            role=WorkspaceRole.editor,
            capabilities=_ALL_CAPS,
            read_scopes=_ALL_SCOPES,
            tool_profile=grant,
        )
        is None
    )


def test_unrestricted_principal_ignores_profile() -> None:
    # Menschen und ungebundene Tokens haben kein Profil (§3.1).
    grant = _grant_for(BuiltinProfileKey.read)
    assert (
        is_tool_visible_for_with_profile(
            "create_agent",
            unrestricted=True,
            role=WorkspaceRole.admin,
            capabilities=None,
            read_scopes=None,
            tool_profile=grant,
        )
        is True
    )


# --- Eingabe-Pruefungen fuer die API (§7.1) ---------------------------------


def test_validation_helpers() -> None:
    assert unknown_tools(["search", "nope", "nope"]) == ["nope"]
    assert unknown_groups(["read", "gibtsnicht"]) == ["gibtsnicht"]
    assert core_tools_in(["search", "whoami", "ping"]) == ["whoami", "ping"]


def test_profile_create_strips_name_and_dedupes() -> None:
    body = ToolProfileCreate(name="  Recherche ", groups=["read", "read"], tools=["a", "a"])
    assert body.name == "Recherche"
    assert body.groups == ["read"]
    assert body.tools == ["a"]
    with pytest.raises(ValidationError):
        ToolProfileCreate(name="   ")
    with pytest.raises(ValidationError):
        ToolProfileCreate(name="x" * 81)
    with pytest.raises(ValidationError):
        ToolProfileCreate.model_validate({"name": "x", "created_by": "y"})


def test_agent_tool_profile_update_defaults_to_alle() -> None:
    body = AgentToolProfileUpdate()
    assert body.tool_profile_id is None
    assert body.tools_added == [] and body.tools_removed == []


# --- whoami (§6.1) und Meldeweg (§8) -----------------------------------------


def test_whoami_tool_profile_is_optional_and_round_trips() -> None:
    base: dict[str, object] = {
        "user_id": str(uuid4()),
        "workspace_id": str(uuid4()),
        "role": "editor",
        "is_api_token": True,
        "agent_id": str(uuid4()),
        "unrestricted": False,
        "capabilities": [],
        "read_scopes": {},
        "features": [],
    }
    assert WhoAmIRead.model_validate(base).tool_profile is None
    grant = _grant_for(BuiltinProfileKey.builder, tools_removed=["create_agent"])
    payload = WhoAmIRead.model_validate({**base, "tool_profile": grant}).model_dump(mode="json")
    restored = WhoAmIRead.model_validate(payload)
    assert restored.tool_profile == grant
    # Bewusst keine ausgerechnete Werkzeugliste in der Antwort (§6.1).
    assert set(payload["tool_profile"]) == {
        "id",
        "name",
        "groups",
        "tools",
        "tools_added",
        "tools_removed",
    }


def test_report_problem_has_tool_request_category_w59_6() -> None:
    assert SystemFeedbackCategory("tool_request") is SystemFeedbackCategory.tool_request


# --- Rot-Probe ----------------------------------------------------------------


def test_red_probe_parity_detects_missing_and_duplicate_group() -> None:
    # Ein Werkzeug ohne Gruppe und eines in zwei Gruppen muessen auffallen —
    # sonst laeuft der Paritaetstest oben still gruen.
    broken = dict(TOOL_GROUPS)
    broken[ToolGroup.read] = tuple(t for t in broken[ToolGroup.read] if t != "search")
    broken[ToolGroup.curation] = (*broken[ToolGroup.curation], "ping", "erfunden")
    assert _group_parity_errors(broken) == [
        "erfunden: kein MCP-Werkzeug",
        "ping: in 2 Gruppen",
        "search: ohne Gruppe",
    ]
