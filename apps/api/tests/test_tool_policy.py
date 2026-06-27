"""Unit-Tests fuer die Pro-Agent-Tool-Policy (Modell + Capability-Gate).

DB-frei: testet die reine Policy-Logik (`AgentToolPolicy`) und das
`require_capability`-Gate aus `core.security`. Die Endpoint-/Repo-Durchsetzung
und das Read-Scoping leben in den DB-gebundenen Integrationstests.
"""

from uuid import uuid4

import pytest

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import WorkspaceContext, require_capability
from who2be_api.services.version_status import _require_transition_capability
from who2be_models import (
    AgentCapability,
    AgentToolPolicy,
    ReadScope,
    VersionStatus,
    WorkspaceRole,
)


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


class TestSystemPromptWriteCapability:
    """ADR-0040: system_prompt_write + die Template-Transition-Sonderregel."""

    def test_default_is_false(self) -> None:
        assert AgentToolPolicy().system_prompt_write is False

    def test_granted_capabilities_lists_it_when_set(self) -> None:
        caps = AgentToolPolicy(system_prompt_write=True).granted_capabilities()
        assert AgentCapability.system_prompt_write in caps

    def test_is_within_blocks_escalation(self) -> None:
        broad = AgentToolPolicy(system_prompt_write=True)
        narrow = AgentToolPolicy()
        assert broad.is_within(narrow) is False
        assert narrow.is_within(broad) is True


class TestTemplateTransitionGate:
    """`_require_transition_capability` fuer entity_type='system_prompt_template'."""

    def test_review_allowed_with_capability(self) -> None:
        ctx = _ctx(AgentToolPolicy(system_prompt_write=True))
        # draft→review ist erlaubt — kein Raise.
        _require_transition_capability(ctx, "system_prompt_template", VersionStatus.review)

    def test_review_blocked_without_capability(self) -> None:
        ctx = _ctx(AgentToolPolicy())  # system_prompt_write=False
        with pytest.raises(ApiGateError) as exc:
            _require_transition_capability(ctx, "system_prompt_template", VersionStatus.review)
        assert exc.value.reason == "missing_capability"

    def test_activation_hard_blocked_even_with_capability(self) -> None:
        # Auch MIT der Capability bleibt →active fuer Agent-Token gesperrt.
        ctx = _ctx(AgentToolPolicy(system_prompt_write=True))
        with pytest.raises(ApiGateError) as exc:
            _require_transition_capability(ctx, "system_prompt_template", VersionStatus.active)
        assert exc.value.status == 403
        assert exc.value.actionable_by == "none"

    def test_retire_hard_blocked(self) -> None:
        ctx = _ctx(AgentToolPolicy(system_prompt_write=True))
        with pytest.raises(ApiGateError) as exc:
            _require_transition_capability(ctx, "system_prompt_template", VersionStatus.inactive)
        assert exc.value.actionable_by == "none"

    def test_unbound_token_is_noop(self) -> None:
        # Mensch/ungebundener Token: gar kein Pro-Agent-Gate, auch nicht fuer Templates.
        _require_transition_capability(_ctx(None), "system_prompt_template", VersionStatus.active)


class TestFeedbackWriteCapability:
    """ADR-0038: feedback_write ist default an (Telemetrie fuer alle, opt-out)."""

    def test_default_is_true(self) -> None:
        assert AgentToolPolicy().feedback_write is True

    def test_granted_by_default_policy(self) -> None:
        assert AgentCapability.feedback_write in AgentToolPolicy().granted_capabilities()

    def test_can_be_disabled(self) -> None:
        policy = AgentToolPolicy(feedback_write=False)
        assert policy.allows(AgentCapability.feedback_write) is False

    def test_require_capability_blocks_when_disabled(self) -> None:
        ctx = _ctx(AgentToolPolicy(feedback_write=False))
        with pytest.raises(ApiGateError):
            require_capability(ctx, AgentCapability.feedback_write)
