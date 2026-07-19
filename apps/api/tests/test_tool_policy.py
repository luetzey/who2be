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
    MemoryDirective,
    MemoryMode,
    ReadScope,
    TransitionGrant,
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

    def test_higher_memory_mode_not_within(self) -> None:
        # memory_mode ist geordnet (off < read_only < suggest < auto): ein Agent
        # darf keinen Agenten mit hoeherem Gedaechtnis-Modus anlegen (ADR-0044).
        ordered = [MemoryMode.off, MemoryMode.read_only, MemoryMode.suggest, MemoryMode.auto]
        for lower, higher in zip(ordered, ordered[1:], strict=False):
            narrow = AgentToolPolicy(memory_mode=lower)
            broad = AgentToolPolicy(memory_mode=higher)
            assert broad.is_within(narrow) is False
            assert narrow.is_within(broad) is True

    def test_memory_directive_is_not_a_right(self) -> None:
        # `required` vs `recommended` ist reine Prompt-Formulierung — kein
        # Eskalations-Vektor, daher symmetrisch within.
        required = AgentToolPolicy(memory_directive=MemoryDirective.required)
        recommended = AgentToolPolicy(memory_directive=MemoryDirective.recommended)
        assert required.is_within(recommended) is True
        assert recommended.is_within(required) is True


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


class TestFeedbackResolveCapability:
    """Feedback-Triage (Signale schliessen) ist secure-by-default AUS."""

    def test_default_is_false(self) -> None:
        assert AgentToolPolicy().feedback_resolve is False

    def test_empty_json_defaults_to_false(self) -> None:
        # Bestands-Agenten (`{}` in der jsonb-Spalte) erben den sicheren Default.
        assert AgentToolPolicy.model_validate({}).feedback_resolve is False

    def test_granted_capabilities_lists_it_when_set(self) -> None:
        caps = AgentToolPolicy(feedback_resolve=True).granted_capabilities()
        assert AgentCapability.feedback_resolve in caps
        assert AgentCapability.feedback_resolve not in AgentToolPolicy().granted_capabilities()

    def test_round_trip_preserves_value(self) -> None:
        policy = AgentToolPolicy(feedback_resolve=True)
        assert AgentToolPolicy.model_validate(policy.model_dump()) == policy
        assert AgentToolPolicy.model_validate(policy.model_dump()).feedback_resolve is True

    def test_require_capability_blocks_default_policy(self) -> None:
        ctx = _ctx(AgentToolPolicy())
        with pytest.raises(ApiGateError) as exc:
            require_capability(ctx, AgentCapability.feedback_resolve)
        assert exc.value.status == 403
        assert exc.value.reason == "missing_capability"

    def test_require_capability_passes_when_granted(self) -> None:
        require_capability(
            _ctx(AgentToolPolicy(feedback_resolve=True)), AgentCapability.feedback_resolve
        )

    def test_no_policy_is_noop(self) -> None:
        # Mensch/JWT bzw. ungebundener Token: nur das Rollen-Gate greift.
        require_capability(_ctx(None), AgentCapability.feedback_resolve)

    def test_is_within_blocks_escalation(self) -> None:
        broad = AgentToolPolicy(feedback_resolve=True)
        narrow = AgentToolPolicy()
        assert broad.is_within(narrow) is False
        assert narrow.is_within(broad) is True


class TestTransitionGrants:
    """ADR-0039: per-Domain-Verfeinerung von promote_retire (Narrowing)."""

    def test_no_promote_retire_means_no_transition(self) -> None:
        p = AgentToolPolicy(promote_retire=False)
        assert p.can_transition("playbook", promote=True) is False

    def test_promote_retire_without_grants_is_full(self) -> None:
        p = AgentToolPolicy(promote_retire=True)
        assert p.can_transition("playbook", promote=True) is True
        assert p.can_transition("persona", promote=False) is True

    def test_grant_narrows_direction_per_domain(self) -> None:
        p = AgentToolPolicy(
            promote_retire=True,
            transition_grants={"playbook": TransitionGrant(promote=True, retire=False)},
        )
        assert p.can_transition("playbook", promote=True) is True
        assert p.can_transition("playbook", promote=False) is False
        # Nicht gelistete Domain bleibt voll (Grants schraenken nur Gelistetes ein).
        assert p.can_transition("persona", promote=False) is True

    def test_is_within_blocks_broader_transition(self) -> None:
        full = AgentToolPolicy(promote_retire=True)
        narrowed = AgentToolPolicy(
            promote_retire=True,
            transition_grants={"playbook": TransitionGrant(promote=True, retire=False)},
        )
        assert narrowed.is_within(full) is True
        assert full.is_within(narrowed) is False

    def test_gate_allows_promote_blocks_retire_when_grant_restricts(self) -> None:
        ctx = _ctx(
            AgentToolPolicy(
                promote_retire=True,
                transition_grants={"playbook": TransitionGrant(promote=True, retire=False)},
            )
        )
        # Promote (→active) erlaubt; Retire (→inactive) durch Grant gesperrt.
        _require_transition_capability(ctx, "playbook", VersionStatus.active)
        with pytest.raises(ApiGateError) as exc:
            _require_transition_capability(ctx, "playbook", VersionStatus.inactive)
        assert exc.value.actionable_by == "human"


class TestExternalToolPolicy:
    """WP-3: `external_tool_read`/`external_tool_write` (Blueprint
    `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`)."""

    def test_default_read_is_all_not_assigned(self) -> None:
        # Anders als playbook/resource/agent: kein 'assigned'-Konzept fuer den
        # flachen ExternalTool-Katalog — Default ist 'all'.
        assert AgentToolPolicy().external_tool_read == ReadScope.all

    def test_default_write_is_false(self) -> None:
        assert AgentToolPolicy().external_tool_write is False

    def test_empty_json_deserialises_to_defaults(self) -> None:
        # JSONB-Abwaertskompatibilitaet (ADR-0009): eine alte Policy ohne die
        # neuen Felder verhaelt sich unveraendert (kein destruktiver Migrationsschritt).
        policy = AgentToolPolicy.model_validate({})
        assert policy.external_tool_read == ReadScope.all
        assert policy.external_tool_write is False
        assert policy == AgentToolPolicy()

    def test_old_policy_json_without_field_still_validates(self) -> None:
        # Simuliert eine VOR-WP-3 persistierte JSONB-Zeile (kennt die neuen
        # Felder nicht) — muss weiterhin klaglos validieren.
        legacy = {"playbook_read": "all", "persona_write": True}
        policy = AgentToolPolicy.model_validate(legacy)
        assert policy.external_tool_read == ReadScope.all
        assert policy.external_tool_write is False
        assert policy.persona_write is True

    def test_granted_capabilities_lists_it_when_set(self) -> None:
        caps = AgentToolPolicy(external_tool_write=True).granted_capabilities()
        assert AgentCapability.external_tool_write in caps
        assert AgentCapability.external_tool_write not in AgentToolPolicy().granted_capabilities()

    def test_read_scopes_includes_external_tool(self) -> None:
        assert AgentToolPolicy().read_scopes()["external_tool"] == ReadScope.all
        assert (
            AgentToolPolicy(external_tool_read=ReadScope.none).read_scopes()["external_tool"]
            == ReadScope.none
        )

    def test_require_capability_blocks_default_policy(self) -> None:
        ctx = _ctx(AgentToolPolicy())
        with pytest.raises(ApiGateError) as exc:
            require_capability(ctx, AgentCapability.external_tool_write)
        assert exc.value.status == 403
        assert exc.value.reason == "missing_capability"

    def test_require_capability_passes_when_granted(self) -> None:
        require_capability(
            _ctx(AgentToolPolicy(external_tool_write=True)), AgentCapability.external_tool_write
        )

    def test_is_within_blocks_read_scope_escalation(self) -> None:
        broad = AgentToolPolicy(external_tool_read=ReadScope.all)
        narrow = AgentToolPolicy(external_tool_read=ReadScope.none)
        assert narrow.is_within(broad) is True
        assert broad.is_within(narrow) is False

    def test_is_within_blocks_write_escalation(self) -> None:
        broad = AgentToolPolicy(external_tool_write=True)
        narrow = AgentToolPolicy()
        assert broad.is_within(narrow) is False
        assert narrow.is_within(broad) is True

    def test_transition_capability_gate_uses_external_tool_write_for_draft_review(self) -> None:
        # WP-1-Luecke geschlossen: `external_tool` ist jetzt in
        # `version_status._WRITE_CAPABILITY` — draft/review verlangt
        # `external_tool_write`, active/inactive zusaetzlich `promote_retire`.
        ctx = _ctx(AgentToolPolicy(external_tool_write=True))
        _require_transition_capability(ctx, "external_tool", VersionStatus.review)

    def test_transition_capability_gate_blocks_active_without_promote_retire(self) -> None:
        ctx = _ctx(AgentToolPolicy(external_tool_write=True))
        with pytest.raises(ApiGateError) as exc:
            _require_transition_capability(ctx, "external_tool", VersionStatus.active)
        assert exc.value.reason == "missing_capability"


class TestTokenExpiry:
    """ADR-0039: optionaler Ablaufzeitpunkt im TokenCreate-Modell."""

    def test_default_is_none(self) -> None:
        from who2be_models import TokenCreate

        tok = TokenCreate(name="t", agent_id=uuid4())
        assert tok.expires_at is None

    def test_accepts_datetime(self) -> None:
        from datetime import UTC, datetime, timedelta

        from who2be_models import TokenCreate

        when = datetime.now(UTC) + timedelta(days=14)
        tok = TokenCreate(name="t", agent_id=uuid4(), expires_at=when)
        assert tok.expires_at == when


class TestWriteTagsScope:
    """ADR-0039: Tag-Praedikat-Write-Scoping (write_tags) + Anti-Escalation."""

    def test_unrestricted_permits_any_tags(self) -> None:
        p = AgentToolPolicy()
        assert p.write_tags_for("playbook") is None
        assert p.tags_permitted("playbook", ["legal"]) is True

    def test_empty_list_is_unrestricted(self) -> None:
        # Leerer Eintrag == keine Einschraenkung (Backward-Compat).
        p = AgentToolPolicy(write_tags={"playbook": []})
        assert p.write_tags_for("playbook") is None
        assert p.tags_permitted("playbook", ["legal"]) is True

    def test_restricted_requires_intersection(self) -> None:
        p = AgentToolPolicy(write_tags={"playbook": ["support"]})
        assert p.tags_permitted("playbook", ["support", "billing"]) is True
        assert p.tags_permitted("playbook", ["legal"]) is False
        assert p.tags_permitted("playbook", []) is False
        # Andere Domain bleibt unbeschraenkt.
        assert p.tags_permitted("persona", ["legal"]) is True

    def test_is_within_blocks_broader_or_unrestricted(self) -> None:
        manager = AgentToolPolicy(playbook_write=True, write_tags={"playbook": ["support"]})
        narrow = AgentToolPolicy(playbook_write=True, write_tags={"playbook": ["support"]})
        broader = AgentToolPolicy(
            playbook_write=True, write_tags={"playbook": ["support", "legal"]}
        )
        unrestricted = AgentToolPolicy(playbook_write=True)
        assert narrow.is_within(manager) is True
        # Breiterer Tag-Satz als der Verwalter → nicht innerhalb.
        assert broader.is_within(manager) is False
        # Unrestringiert (alle Tags) ist breiter als ein eingeschraenkter Verwalter.
        assert unrestricted.is_within(manager) is False
        # Ein eingeschraenkter Agent ist innerhalb eines unrestringierten Verwalters.
        assert manager.is_within(unrestricted) is True


class TestRequireWriteTagsGate:
    """`require_write_tags`-Gate (core.security)."""

    def test_no_policy_is_noop(self) -> None:
        from who2be_api.core.security import require_write_tags

        require_write_tags(_ctx(None), "playbook", ["legal"])

    def test_permitted_passes(self) -> None:
        from who2be_api.core.security import require_write_tags

        ctx = _ctx(AgentToolPolicy(playbook_write=True, write_tags={"playbook": ["support"]}))
        require_write_tags(ctx, "playbook", ["support"])

    def test_forbidden_raises_403_human(self) -> None:
        from who2be_api.core.security import require_write_tags

        ctx = _ctx(AgentToolPolicy(playbook_write=True, write_tags={"playbook": ["support"]}))
        with pytest.raises(ApiGateError) as exc:
            require_write_tags(ctx, "playbook", ["legal"])
        assert exc.value.status == 403
        assert exc.value.actionable_by == "human"


class TestWriteRateLimit:
    """ADR-0039: per-Agent Write-Rate-Limit (write_rate_limit) + Gate."""

    def test_is_within_unlimited_not_within_limited(self) -> None:
        limited = AgentToolPolicy(write_rate_limit=10)
        unlimited = AgentToolPolicy()
        assert AgentToolPolicy(write_rate_limit=5).is_within(limited) is True
        assert AgentToolPolicy(write_rate_limit=20).is_within(limited) is False
        # Unbegrenzt ist breiter als ein limitierter Verwalter → nicht innerhalb.
        assert unlimited.is_within(limited) is False
        assert limited.is_within(unlimited) is True

    def test_no_limit_is_noop(self) -> None:
        from who2be_api.core.security import require_write_rate

        require_write_rate(_ctx(None))
        require_write_rate(_ctx(AgentToolPolicy()))  # write_rate_limit None

    def test_gate_blocks_after_threshold(self) -> None:
        from fastapi import HTTPException

        from who2be_api.core.rate_limit import token_rate_limiter
        from who2be_api.core.security import require_write_rate

        token_rate_limiter.reset()
        ctx = _ctx(AgentToolPolicy(write_rate_limit=2))
        require_write_rate(ctx)
        require_write_rate(ctx)
        with pytest.raises(HTTPException) as exc:
            require_write_rate(ctx)
        assert exc.value.status_code == 429
