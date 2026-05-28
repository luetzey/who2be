from who2be_models import ALLOWED_TRANSITIONS, VersionStatus, is_allowed_transition


def test_version_status_values_match_db_check() -> None:
    # Spiegelt 0011_status_on_versions.sql CHECK-Werte.
    assert {s.value for s in VersionStatus} == {"draft", "review", "active", "inactive"}


def test_str_enum_serializes_as_string() -> None:
    assert VersionStatus.draft == "draft"
    assert f"{VersionStatus.active}" == "active"


def test_allowed_transitions_match_state_machine() -> None:
    assert ALLOWED_TRANSITIONS[VersionStatus.draft] == frozenset(
        {VersionStatus.review, VersionStatus.inactive}
    )
    assert ALLOWED_TRANSITIONS[VersionStatus.review] == frozenset(
        {VersionStatus.draft, VersionStatus.active, VersionStatus.inactive}
    )
    assert ALLOWED_TRANSITIONS[VersionStatus.active] == frozenset({VersionStatus.inactive})
    assert ALLOWED_TRANSITIONS[VersionStatus.inactive] == frozenset()


def test_draft_can_go_to_review_but_not_active() -> None:
    assert is_allowed_transition(VersionStatus.draft, VersionStatus.review)
    assert not is_allowed_transition(VersionStatus.draft, VersionStatus.active)


def test_inactive_is_terminal() -> None:
    for target in VersionStatus:
        assert not is_allowed_transition(VersionStatus.inactive, target)


def test_self_transition_is_never_allowed() -> None:
    for status in VersionStatus:
        assert not is_allowed_transition(status, status)


def test_review_can_bounce_back_to_draft() -> None:
    assert is_allowed_transition(VersionStatus.review, VersionStatus.draft)
    assert is_allowed_transition(VersionStatus.review, VersionStatus.active)
