"""Unit-Tests fuer die Pro-Agent-Tool-Policy (Modell + Capability-Gate).

DB-frei: testet die reine Policy-Logik (`AgentToolPolicy`) und das
`require_capability`-Gate aus `core.security`. Die Endpoint-/Repo-Durchsetzung
und das Read-Scoping leben in den DB-gebundenen Integrationstests.
"""

from uuid import uuid4

import pytest

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import WorkspaceContext, require_capability
from who2be_models import AgentCapability, AgentToolPolicy, ReadScope, WorkspaceRole


def _ctx(tool_policy: AgentToolPolicy | None) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.editor,
        is_api_token=tool_policy is not None,
        agent_id=uuid4() if tool_policy is not None else None,
        tool_policy=tool_policy,
    )


class TestAgentToolPolicyDefaults:
    def test_default_is_read_assigned_no_writes(self) -> None:
        # Secure by default: ohne expliziten Eintrag sieht ein Agent nur die
        # ihm zugewiesenen Playbooks/Resources, nicht den ganzen Workspace.
        policy = AgentToolPolicy()
        assert policy.playbook_read == ReadScope.assigned
        assert policy.resource_read == ReadScope.assigned
        assert policy.agent_read == ReadScope.assigned
        assert policy.persona_read is True
        assert policy.persona_write is False
        assert policy.playbook_write is False
        assert policy.resource_write is False
        assert policy.agent_write is False
        assert policy.promote_retire is False

    def test_empty_json_deserialises_to_default(self) -> None:
        # Bestands-Agenten tragen `{}` in der jsonb-Spalte (Migration-Default).
        policy = AgentToolPolicy.model_validate({})
        assert policy == AgentToolPolicy()

    def test_allows_maps_capability_to_field(self) -> None:
        policy = AgentToolPolicy(playbook_write=True)
        assert policy.allows(AgentCapability.playbook_write) is True
        assert policy.allows(AgentCapability.resource_write) is False


class TestIsWithin:
    def test_equal_policies_are_within(self) -> None:
        policy = AgentToolPolicy(playbook_write=True, playbook_read=ReadScope.assigned)
        assert policy.is_within(policy) is True

    def test_more_writes_not_within(self) -> None:
        broad = AgentToolPolicy(playbook_write=True)
        narrow = AgentToolPolicy()
        assert broad.is_within(narrow) is False
        assert narrow.is_within(broad) is True

    def test_wider_read_scope_not_within(self) -> None:
        all_scope = AgentToolPolicy(resource_read=ReadScope.all)
        assigned = AgentToolPolicy(resource_read=ReadScope.assigned)
        assert all_scope.is_within(assigned) is False
        assert assigned.is_within(all_scope) is True
        # `none` ist die engste Stufe — innerhalb von allem.
        none = AgentToolPolicy(resource_read=ReadScope.none)
        assert none.is_within(assigned) is True

    def test_wider_agent_read_scope_not_within(self) -> None:
        # agent_read ist jetzt ebenfalls scope-gerankt: ein self-Agent darf via
        # agent_write keinen `all`-Agenten erzeugen.
        all_scope = AgentToolPolicy(agent_read=ReadScope.all)
        assigned = AgentToolPolicy(agent_read=ReadScope.assigned)
        assert all_scope.is_within(assigned) is False
        assert assigned.is_within(all_scope) is True


class TestRequireCapability:
    def test_no_policy_is_noop(self) -> None:
        # Mensch/ungebundener Token: kein Pro-Agent-Gate.
        require_capability(_ctx(None), AgentCapability.playbook_write)

    def test_granted_capability_passes(self) -> None:
        ctx = _ctx(AgentToolPolicy(playbook_write=True))
        require_capability(ctx, AgentCapability.playbook_write)

    def test_missing_capability_raises_403(self) -> None:
        ctx = _ctx(AgentToolPolicy())
        with pytest.raises(ApiGateError) as exc:
            require_capability(ctx, AgentCapability.playbook_write)
        assert exc.value.status == 403
        assert exc.value.reason == "missing_capability"
