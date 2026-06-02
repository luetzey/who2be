from who2be_models import (
    ALLOWED_TRANSITIONS,
    VersionStatus,
    VersionTransitionRequest,
    is_allowed_transition,
)


def test_version_status_values_match_db_check() -> None:
    # Spiegelt 0011_status_on_versions.sql CHECK-Werte.
    assert {s.value for s in VersionStatus} == {"draft", "review", "active", "inactive"}


def test_str_enum_serializes_as_string() -> None:
    assert VersionStatus.draft == "draft"
    assert f"{VersionStatus.active}" == "active"


def test_allowed_transitions_match_state_machine() -> None:
    # Task Phase 2.1b + Track A: draft→review, review→active|draft,
    # active→inactive|draft (Reset-auf-Draft), inactive→draft. Direkte Wege nach
    # `inactive` ausser von `active` sind nicht erlaubt (Drafts/Reviews verwirft
    # man via review→draft bzw. nach Promotion + Inactivierung).
    assert ALLOWED_TRANSITIONS[VersionStatus.draft] == frozenset({VersionStatus.review})
    assert ALLOWED_TRANSITIONS[VersionStatus.review] == frozenset(
        {VersionStatus.draft, VersionStatus.active}
    )
    assert ALLOWED_TRANSITIONS[VersionStatus.active] == frozenset(
        {VersionStatus.inactive, VersionStatus.draft}
    )
    assert ALLOWED_TRANSITIONS[VersionStatus.inactive] == frozenset({VersionStatus.draft})


def test_draft_can_go_to_review_but_not_active() -> None:
    assert is_allowed_transition(VersionStatus.draft, VersionStatus.review)
    assert not is_allowed_transition(VersionStatus.draft, VersionStatus.active)


def test_inactive_can_be_reanimated_as_draft() -> None:
    assert is_allowed_transition(VersionStatus.inactive, VersionStatus.draft)
    for target in (VersionStatus.review, VersionStatus.active, VersionStatus.inactive):
        assert not is_allowed_transition(VersionStatus.inactive, target)


def test_self_transition_is_never_allowed() -> None:
    for status in VersionStatus:
        assert not is_allowed_transition(status, status)


def test_review_can_bounce_back_to_draft() -> None:
    assert is_allowed_transition(VersionStatus.review, VersionStatus.draft)
    assert is_allowed_transition(VersionStatus.review, VersionStatus.active)


def test_transition_request_accepts_to_and_optional_note() -> None:
    body = VersionTransitionRequest.model_validate({"to": "review"})
    assert body.to == VersionStatus.review
    assert body.note is None
    with_note = VersionTransitionRequest.model_validate({"to": "active", "note": "OK"})
    assert with_note.note == "OK"
