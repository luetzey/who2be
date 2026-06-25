"""Tests fuer das Admin-MFA-Gate (AAL2) in `core/security.py` (WP-F, Befund S1).

Reine Unit-Tests ueber `require_role`/`require_aal2` mit konstruierten
`WorkspaceContext`-Objekten — kein I/O, keine DB. Deckt ab:
- Admin-Aktion mit `aal1` → 403 (MFA-Pflicht greift),
- Admin-Aktion mit `aal2` → ok,
- fehlender aal-Claim (`None`) On-Prem → ok (fail-open, Bestands-/Test-JWTs),
- fehlender aal-Claim (`None`) Cloud → 403 (fail-closed, Zero-Trust),
- API-Token (Maschinen-Pfad) → ok (vom Gate ausgenommen),
- nicht-administrative Aktionen (editor/viewer) → kein AAL2-Gate.
"""

from uuid import uuid4

import pytest

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    require_aal2,
    require_role,
)
from who2be_models import WorkspaceRole


def _ctx(
    role: WorkspaceRole,
    *,
    aal: str | None = None,
    is_api_token: bool = False,
) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=role,
        is_api_token=is_api_token,
        aal=aal,
    )


def test_admin_action_with_aal1_is_blocked() -> None:
    with pytest.raises(ApiGateError) as exc:
        require_role(_ctx(WorkspaceRole.admin, aal="aal1"), WorkspaceRole.admin)
    assert exc.value.status == 403
    assert exc.value.reason == "mfa_required"
    assert "MFA" in exc.value.detail


def test_admin_action_with_aal2_is_allowed() -> None:
    # Kein Raise → ok.
    require_role(_ctx(WorkspaceRole.admin, aal="aal2"), WorkspaceRole.admin)


def test_admin_action_without_aal_claim_is_allowed_fail_open_onprem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # On-Prem/Dev: fehlender Claim (Legacy-/Magic-Link-/Test-JWT) → erlaubt.
    monkeypatch.setattr("who2be_api.core.security.is_onprem", lambda: True)
    require_role(_ctx(WorkspaceRole.admin, aal=None), WorkspaceRole.admin)


def test_admin_action_without_aal_claim_blocked_in_cloud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Cloud: GoTrue setzt aal immer; ein fehlender Claim ist verdaechtig und
    # wird fail-closed behandelt (Zero-Trust, QW-2).
    monkeypatch.setattr("who2be_api.core.security.is_onprem", lambda: False)
    with pytest.raises(ApiGateError) as exc:
        require_role(_ctx(WorkspaceRole.admin, aal=None), WorkspaceRole.admin)
    assert exc.value.status == 403
    assert exc.value.reason == "mfa_required"
    assert "MFA" in exc.value.detail


def test_admin_action_via_api_token_is_exempt() -> None:
    # API-Token tragen kein aal; der Maschinen-Pfad ist vom MFA-Gate ausgenommen.
    require_role(
        _ctx(WorkspaceRole.admin, aal=None, is_api_token=True),
        WorkspaceRole.admin,
    )


def test_admin_via_api_token_with_stray_aal_still_exempt() -> None:
    # Defensiv: selbst falls ein Token-Kontext je ein aal traegt, bleibt er exempt.
    require_aal2(_ctx(WorkspaceRole.admin, aal="aal1", is_api_token=True))


def test_non_admin_actions_are_not_gated_by_aal2() -> None:
    # Editor-/Viewer-Mindestrollen verlangen kein AAL2, auch mit aal1.
    require_role(_ctx(WorkspaceRole.editor, aal="aal1"), WorkspaceRole.editor)
    require_role(_ctx(WorkspaceRole.admin, aal="aal1"), WorkspaceRole.viewer)


def test_insufficient_role_still_takes_precedence() -> None:
    # Rollen-Check schlaegt vor dem AAL2-Check zu (Rollen-Meldung, nicht MFA).
    with pytest.raises(ApiGateError) as exc:
        require_role(_ctx(WorkspaceRole.editor, aal="aal2"), WorkspaceRole.admin)
    assert exc.value.status == 403
    assert exc.value.reason == "insufficient_role"
    assert "Rolle" in exc.value.detail


def test_require_aal2_blocks_unknown_present_value() -> None:
    with pytest.raises(ApiGateError) as exc:
        require_aal2(_ctx(WorkspaceRole.admin, aal="aal1"))
    assert exc.value.status == 403
    assert exc.value.reason == "mfa_required"
