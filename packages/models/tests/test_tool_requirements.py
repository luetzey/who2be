from who2be_models import (
    MCP_TOOL_REQUIREMENTS,
    AgentCapability,
    AgentToolPolicy,
    MemoryMode,
    ReadScope,
    WorkspaceRole,
    is_tool_visible,
    is_tool_visible_for,
)

# Voll-Policy: alle Reads auf `all`, alle Write-Capabilities gewaehrt,
# Memory auf hoechster Stufe (ADR-0044).
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
    memory_mode=MemoryMode.auto,
)

# Default-Read-Scopes eines agent-gebundenen Tokens (whoami-normalisiert).
_DEFAULT_SCOPES = {
    "persona": ReadScope.all,
    "playbook": ReadScope.assigned,
    "resource": ReadScope.assigned,
    "agent": ReadScope.assigned,
    "external_tool": ReadScope.all,
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
    # Memory-Tools (ADR-0044) sind ohne Agent-Kontext ebenfalls unsichtbar.
    for name, requirement in MCP_TOOL_REQUIREMENTS.items():
        expected = not requirement.capabilities and requirement.memory is None
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
    # Ausnahme (ADR-0044): Memory-Tools brauchen eine Agent-Bindung — fuer
    # Unrestricted gibt es keinen Memory-Namespace, sie bleiben unsichtbar.
    for name, requirement in MCP_TOOL_REQUIREMENTS.items():
        expected = requirement.memory is None
        assert (
            is_tool_visible_for(
                name,
                unrestricted=True,
                role=WorkspaceRole.admin,
                capabilities=None,
                read_scopes=None,
            )
            is expected
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
        expected = not requirement.capabilities and requirement.memory is None
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


def test_external_tool_read_default_shows_read_tools_but_not_writes() -> None:
    # Default-Policy: external_tool_read=all (anders als playbook/resource
    # assigned) — die Read-Tools sind ohne Extra-Konfiguration sichtbar.
    policy = AgentToolPolicy()
    assert is_tool_visible("list_external_tools", policy) is True
    assert is_tool_visible("get_external_tool", policy) is True
    assert is_tool_visible("create_external_tool", policy) is False


def test_external_tool_read_none_hides_external_tool_reads() -> None:
    policy = AgentToolPolicy(external_tool_read=ReadScope.none)
    assert is_tool_visible("list_external_tools", policy) is False
    assert is_tool_visible("get_external_tool", policy) is False


def test_external_tool_write_capability_shows_writes() -> None:
    policy = AgentToolPolicy(external_tool_write=True)
    assert is_tool_visible("create_external_tool", policy) is True
    assert is_tool_visible("update_external_tool", policy) is True
    assert is_tool_visible("restore_external_tool", policy) is True


def test_transition_external_tool_visible_with_either_capability() -> None:
    for policy in (
        AgentToolPolicy(external_tool_write=True),
        AgentToolPolicy(promote_retire=True),
    ):
        assert is_tool_visible("transition_external_tool", policy) is True
    assert is_tool_visible("transition_external_tool", AgentToolPolicy()) is False


def test_every_capability_is_used_in_the_mapping() -> None:
    used = {
        cap for requirement in MCP_TOOL_REQUIREMENTS.values() for cap in requirement.capabilities
    }
    # WP8 (ADR-0047) hat `workarea_write` ins Mapping gebracht (Count 58 -> 66);
    # die KB-Capabilities folgen mit WP9 (`tools/kb.py`, Count 66 -> 71) — bis
    # dahin bewusst ohne Mapping-Eintrag.
    pending_wp9 = {
        AgentCapability.kb_write,
        AgentCapability.kb_edge_write,
    }
    assert used == set(AgentCapability) - pending_wp9


def test_mapping_covers_all_registered_server_tools() -> None:
    # 66 `@with_tool_log("<name>")`-Registrierungen in apps/mcp (58 in
    # server.py + 8 WorkArea-Tools aus `tools/workarea.py`, WP8/ADR-0047 —
    # Welle 3 zaehlt weiter 66 -> 71 -> 81).
    # Neues Tool => hier + im Mapping ergaenzen; der Paritaetstest in apps/mcp
    # prueft die Gegenrichtung gegen den Server.
    assert len(MCP_TOOL_REQUIREMENTS) == 66
    always = {name for name, req in MCP_TOOL_REQUIREMENTS.items() if req.always}
    assert always == {"ping", "whoami"}


def test_workarea_and_kb_domains_always_visible() -> None:
    # WP1 (ADR-0047): WorkArea/KB sind fuer agent-gebundene Identitaeten und
    # unrestricted Menschen sichtbar — Area-Grants sind dynamisch und werden
    # serverseitig durchgesetzt; der PolicyFilter ist ohnehin fail-open, die
    # API bleibt die Autoritaet. Seit WP8 traegt "workarea" konkrete Tools
    # (read_artifact/list_artifacts/search_workarea), "kb" folgt mit WP9 —
    # die Sichtbarkeitslogik wird weiterhin direkt gegen die Helper geprueft.
    from who2be_models.tool_requirements import ReadDomain, _read_visible, _scoped_read_visible

    locked_down = AgentToolPolicy(
        persona_read=False,
        playbook_read=ReadScope.none,
        resource_read=ReadScope.none,
        agent_read=ReadScope.none,
        external_tool_read=ReadScope.none,
    )
    domains: tuple[ReadDomain, ...] = ("workarea", "kb")
    for domain in domains:
        assert _read_visible(domain, locked_down) is True
        assert _read_visible(domain, AgentToolPolicy()) is True
        # whoami-Pfad: weder ein fehlender Key noch irgendein Scope sperrt.
        assert _scoped_read_visible(domain, {}) is True
        assert _scoped_read_visible(domain, _DEFAULT_SCOPES) is True


_WORKAREA_WRITE_TOOLS = (
    "create_artifact",
    "append_artifact",
    "patch_artifact",
    "delete_artifact",
    "ingest",
)
_WORKAREA_READ_TOOLS = ("read_artifact", "list_artifacts", "search_workarea")


def test_workarea_write_capability_gates_write_tools() -> None:
    # WP8 (ADR-0047): Default-Policy hat `workarea_write=False` — die fuenf
    # Write-Tools sind unsichtbar, bis die Capability gewaehrt wird.
    default = AgentToolPolicy()
    granted = AgentToolPolicy(workarea_write=True)
    for name in _WORKAREA_WRITE_TOOLS:
        assert is_tool_visible(name, default) is False, name
        assert is_tool_visible(name, granted) is True, name
        assert _visible_for_bound(name, []) is False, name
        assert _visible_for_bound(name, [AgentCapability.workarea_write]) is True, name


def test_workarea_read_tools_visible_even_when_locked_down() -> None:
    # Die WorkArea-Reads haengen an dynamischen Area-Grants (Domain
    # "workarea"), nicht an einem `ReadScope` — sie bleiben auch fuer eine
    # komplett zugesperrte Inhalts-Policy sichtbar (API = Autoritaet).
    locked_down = AgentToolPolicy(
        persona_read=False,
        playbook_read=ReadScope.none,
        resource_read=ReadScope.none,
        agent_read=ReadScope.none,
        external_tool_read=ReadScope.none,
    )
    for name in _WORKAREA_READ_TOOLS:
        assert is_tool_visible(name, locked_down) is True, name
        assert is_tool_visible(name, AgentToolPolicy()) is True, name
        assert _visible_for_bound(name, []) is True, name


def test_memory_tools_follow_memory_mode_ladder() -> None:
    # ADR-0044: Lesen ab read_only, Vorschlagen ab suggest; off blendet alles
    # aus; ohne Policy (kein Agent-Kontext) sind Memory-Tools NIE sichtbar —
    # bewusst anders als Read-Tools (policy=None => True).
    assert is_tool_visible("search_memory", None) is False
    assert is_tool_visible("save_memory", None) is False
    off = AgentToolPolicy()
    assert is_tool_visible("search_memory", off) is False
    assert is_tool_visible("list_memories", off) is False
    assert is_tool_visible("save_memory", off) is False
    read_only = AgentToolPolicy(memory_mode=MemoryMode.read_only)
    assert is_tool_visible("search_memory", read_only) is True
    assert is_tool_visible("list_memories", read_only) is True
    assert is_tool_visible("save_memory", read_only) is False
    for mode in (MemoryMode.suggest, MemoryMode.auto):
        policy = AgentToolPolicy(memory_mode=mode)
        assert is_tool_visible("search_memory", policy) is True
        assert is_tool_visible("save_memory", policy) is True


def test_memory_tools_hidden_for_unrestricted_whoami() -> None:
    # Unrestricted (Mensch/ungebundener Token): kein Memory-Namespace, also
    # keine Memory-Tools — obwohl alle anderen Reads sichtbar sind.
    for name in ("search_memory", "list_memories", "save_memory"):
        assert (
            is_tool_visible_for(
                name,
                unrestricted=True,
                role=WorkspaceRole.admin,
                capabilities=None,
                read_scopes=None,
            )
            is False
        )
    # Agent-gebunden: Stufenlogik ueber `memory_mode`.
    assert (
        is_tool_visible_for(
            "search_memory",
            unrestricted=False,
            role=WorkspaceRole.editor,
            capabilities=[],
            read_scopes={},
            memory_mode=MemoryMode.read_only,
        )
        is True
    )
    assert (
        is_tool_visible_for(
            "save_memory",
            unrestricted=False,
            role=WorkspaceRole.editor,
            capabilities=[],
            read_scopes={},
            memory_mode=MemoryMode.read_only,
        )
        is False
    )
    assert (
        is_tool_visible_for(
            "save_memory",
            unrestricted=False,
            role=WorkspaceRole.editor,
            capabilities=[],
            read_scopes={},
            memory_mode=MemoryMode.suggest,
        )
        is True
    )
