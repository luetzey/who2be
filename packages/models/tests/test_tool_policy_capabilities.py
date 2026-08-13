"""Unit-Tests fuer die neuen WorkArea-/KB-Capabilities (WP1, ADR-0047).

DB-frei, rein auf dem geteilten Modell: Defaults, JSONB-Abwaertskompatibilitaet,
`granted_capabilities` und vor allem der `is_within`-Anti-Escalation-Vergleich —
die drei neuen Bool-Felder MUESSEN dort verglichen werden, sonst koennte ein
Agent via `agent_write` einen maechtigeren Agenten anlegen. Das
`require_capability`-Gate selbst wird in `apps/api/tests/test_tool_policy.py`
getestet.
"""

from who2be_models import AgentCapability, AgentToolPolicy


class TestWorkAreaKbCapabilityDefaults:
    def test_defaults_are_false(self) -> None:
        policy = AgentToolPolicy()
        assert policy.workarea_write is False
        assert policy.kb_write is False
        assert policy.kb_edge_write is False

    def test_empty_json_deserialises_to_false(self) -> None:
        # Bestands-Agenten (`{}` bzw. alte JSONB-Policies) erben den sicheren
        # Default — keine Migration noetig (ADR-0009-Muster).
        policy = AgentToolPolicy.model_validate({})
        assert policy.workarea_write is False
        assert policy.kb_write is False
        assert policy.kb_edge_write is False
        assert policy == AgentToolPolicy()

    def test_old_policy_json_without_fields_still_validates(self) -> None:
        legacy = {"playbook_read": "all", "resource_write": True}
        policy = AgentToolPolicy.model_validate(legacy)
        assert policy.workarea_write is False
        assert policy.resource_write is True

    def test_allows_maps_capability_to_field(self) -> None:
        policy = AgentToolPolicy(workarea_write=True, kb_write=True)
        assert policy.allows(AgentCapability.workarea_write) is True
        assert policy.allows(AgentCapability.kb_write) is True
        assert policy.allows(AgentCapability.kb_edge_write) is False

    def test_granted_capabilities_lists_them_when_set(self) -> None:
        caps = AgentToolPolicy(
            workarea_write=True, kb_write=True, kb_edge_write=True
        ).granted_capabilities()
        assert AgentCapability.workarea_write in caps
        assert AgentCapability.kb_write in caps
        assert AgentCapability.kb_edge_write in caps
        default_caps = AgentToolPolicy().granted_capabilities()
        assert AgentCapability.workarea_write not in default_caps
        assert AgentCapability.kb_write not in default_caps
        assert AgentCapability.kb_edge_write not in default_caps

    def test_round_trip_preserves_values(self) -> None:
        policy = AgentToolPolicy(workarea_write=True, kb_edge_write=True)
        assert AgentToolPolicy.model_validate(policy.model_dump()) == policy


class TestWorkAreaKbAntiEscalation:
    """`is_within.bool_fields` MUSS die drei neuen Felder vergleichen."""

    def test_workarea_write_escalation_blocked(self) -> None:
        broad = AgentToolPolicy(workarea_write=True)
        narrow = AgentToolPolicy()
        assert broad.is_within(narrow) is False
        assert narrow.is_within(broad) is True

    def test_kb_write_escalation_blocked(self) -> None:
        broad = AgentToolPolicy(kb_write=True)
        narrow = AgentToolPolicy()
        assert broad.is_within(narrow) is False
        assert narrow.is_within(broad) is True

    def test_kb_edge_write_escalation_blocked(self) -> None:
        broad = AgentToolPolicy(kb_edge_write=True)
        narrow = AgentToolPolicy()
        assert broad.is_within(narrow) is False
        assert narrow.is_within(broad) is True

    def test_kb_edge_write_is_not_implied_by_kb_write(self) -> None:
        # Getrennte Capabilities: Kanten anlegen ist NICHT in `kb_write`
        # enthalten (Kanten sind im MVP nicht loeschbar).
        edge_only = AgentToolPolicy(kb_edge_write=True)
        node_only = AgentToolPolicy(kb_write=True)
        assert edge_only.is_within(node_only) is False
        assert node_only.is_within(edge_only) is False

    def test_equal_policies_are_within(self) -> None:
        policy = AgentToolPolicy(workarea_write=True, kb_write=True, kb_edge_write=True)
        assert policy.is_within(policy) is True
