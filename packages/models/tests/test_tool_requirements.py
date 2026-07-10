from who2be_models import (
    MCP_TOOL_REQUIREMENTS,
    AgentCapability,
    AgentToolPolicy,
    ReadScope,
    WorkspaceRole,
    is_tool_visible,
    is_tool_visible_for,
)

# Voll-Policy: alle Reads auf `all`, alle Write-Capabilities gewaehrt.
_FULL_POLICY = AgentToolPolicy(
    playbook_read=ReadScope.all,
    resource_read=ReadScope.all,
    agent_read=ReadScope.all,
    persona_read=True,
    persona_write=True,
    playbook_write=True,
    resource_write=True,
    agent_write=True,
    system_prompt_write=True,
    feedback_write=True,
    promote_retire=True,
)

# Default-Read-Scopes eines agent-gebundenen Tokens (whoami-normalisiert).
_DEFAULT_SCOPES = {
    "persona": ReadScope.all,
    "playbook": ReadScope.assigned,
    "resource": ReadScope.assigned,
    "agent": ReadScope.assigned,
}


def test_default_policy_shows_reads_and_feedback_but_no_writes() -> None:
    policy = AgentToolPolicy()
    for name in ("ping", "whoami", "get_persona", "list_playbooks", "fetch_resource", "search"):
        assert is_tool_visible(name, policy) is True
    # feedback_write ist per Default an (ADR-0038).
    assert is_tool_visible("record_usage", policy) is True
    for name in ("create_playbook", "transition_persona", "list_system_prompts"):
        assert is_tool_visible(name, policy) is False


def test_full_policy_shows_every_tool() -> None:
    for name in MCP_TOOL_REQUIREMENTS:
        assert is_tool_visible(name, _FULL_POLICY) is True, name


def test_resource_read_none_hides_resource_tools_but_not_search() -> None:
    policy = AgentToolPolicy(resource_read=ReadScope.none)
    for name in ("fetch_resource", "list_resources", "list_resource_blocks"):
        assert is_tool_visible(name, policy) is False
    # `search` bleibt sichtbar, solange eine andere Inhalts-Domain lesbar ist.
    assert is_tool_visible("search", policy) is True


def test_search_hidden_when_no_content_domain_is_readable() -> None:
    policy = AgentToolPolicy(
        persona_read=False,
        playbook_read=ReadScope.none,
        resource_read=ReadScope.none,
    )
    assert is_tool_visible("search", policy) is False
    # Gleiche Regel fuer die Versions-/Discovery-Tools.
    assert is_tool_visible("find_usages", policy) is False


def test_policy_none_shows_reads_but_hides_writes() -> None:
    # Vor-Feature-Verhalten: ohne Policy (z. B. Persona-Body) nur Read-Tools.
    for name, requirement in MCP_TOOL_REQUIREMENTS.items():
        expected = not requirement.capabilities
        assert is_tool_visible(name, None) is expected, name


def test_unknown_tool_name_returns_none_in_both_functions() -> None:
    assert is_tool_visible("does_not_exist", AgentToolPolicy()) is None
    assert (
        is_tool_visible_for(
            "does_not_exist",
            unrestricted=True,
            role=WorkspaceRole.admin,
            capabilities=None,
            read_scopes=None,
        )
        is None
    )


def test_unrestricted_admin_sees_every_tool() -> None:
    for name in MCP_TOOL_REQUIREMENTS:
        assert (
            is_tool_visible_for(
                name,
                unrestricted=True,
                role=WorkspaceRole.admin,
                capabilities=None,
                read_scopes=None,
            )
            is True
        ), name


def test_unrestricted_viewer_sees_reads_but_no_writes() -> None:
    for name, requirement in MCP_TOOL_REQUIREMENTS.items():
        visible = is_tool_visible_for(
            name,
            unrestricted=True,
            role=WorkspaceRole.viewer,
            capabilities=None,
            read_scopes=None,
        )
        expected = not requirement.capabilities
        assert visible is expected, name


def _visible_for_bound(
    name: str,
    capabilities: list[AgentCapability],
    read_scopes: dict[str, ReadScope] | None = None,
) -> bool | None:
    return is_tool_visible_for(
        name,
        unrestricted=False,
        role=WorkspaceRole.editor,
        capabilities=capabilities,
        read_scopes=read_scopes if read_scopes is not None else _DEFAULT_SCOPES,
    )


def test_bound_token_with_feedback_capability_only() -> None:
    granted = [AgentCapability.feedback_write]
    assert _visible_for_bound("record_usage", granted) is True
    assert _visible_for_bound("create_playbook", granted) is False


def test_bound_token_resource_scope_none_hides_resource_reads() -> None:
    scopes = {**_DEFAULT_SCOPES, "resource": ReadScope.none}
    assert (
        is_tool_visible_for(
            "fetch_resource",
            unrestricted=False,
            role=WorkspaceRole.editor,
            capabilities=[],
            read_scopes=scopes,
        )
        is False
    )


def test_transition_tool_visible_with_either_capability() -> None:
    # Oder-Logik: draft->review genuegt die Schreib-Capability, active/inactive
    # braucht promote_retire — sichtbar, sobald EINE der beiden gewaehrt ist.
    for granted in ([AgentCapability.playbook_write], [AgentCapability.promote_retire]):
        assert (
            is_tool_visible_for(
                "transition_playbook",
                unrestricted=False,
                role=WorkspaceRole.editor,
                capabilities=granted,
                read_scopes=_DEFAULT_SCOPES,
            )
            is True
        ), granted
    policy_write_only = AgentToolPolicy(playbook_write=True)
    policy_promote_only = AgentToolPolicy(promote_retire=True)
    assert is_tool_visible("transition_playbook", policy_write_only) is True
    assert is_tool_visible("transition_playbook", policy_promote_only) is True


def test_bound_token_capabilities_none_hides_writes() -> None:
    # Defensiv: capabilities=None (statt []) darf keine Writes freischalten.
    assert (
        is_tool_visible_for(
            "create_persona",
            unrestricted=False,
            role=WorkspaceRole.editor,
            capabilities=None,
            read_scopes=_DEFAULT_SCOPES,
        )
        is False
    )


def test_every_capability_is_used_in_the_mapping() -> None:
    used = {
        cap for requirement in MCP_TOOL_REQUIREMENTS.values() for cap in requirement.capabilities
    }
    assert used == set(AgentCapability)


def test_mapping_covers_all_registered_server_tools() -> None:
    # 47 `@with_tool_log("<name>")`-Registrierungen in apps/mcp/.../server.py
    # (Stand ADR-0042). Neues Tool => hier + im Mapping ergaenzen; der
    # Paritaetstest in apps/mcp prueft die Gegenrichtung gegen den Server.
    assert len(MCP_TOOL_REQUIREMENTS) == 47
    always = {name for name, req in MCP_TOOL_REQUIREMENTS.items() if req.always}
    assert always == {"ping", "whoami"}
