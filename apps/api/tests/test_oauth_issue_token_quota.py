"""Der OAuth-Mint-Pfad und das Token-Quota-Gate (Issue #538, Review R1 Blocker 2).

`OAuthService._issue` (`services/oauth_service.py:425-447`) legt ueber
`new_token()` + `TokenRepository.insert` echte `api_token`-Zeilen an und umgeht
`TokenService.create` — und damit auch dessen Quota-Gate — laut ADR-0036
(Entscheidung 5) **bewusst**. Diese Datei haelt beide Haelften der Entscheidung
fest, damit sie beim naechsten Lesen nicht als Versehen durchgeht:

1. **Ungegatet:** `_issue` ist der Anmeldepfad eines OAuth-Connectors. Ein
   Login, das an einer Abrechnungsgrenze mit `402` bricht, ist der teurere
   Fehler als ein ueberzaehliger Connector-Token (PM-Entscheidung 2026-09-22).
2. **Zaehlt trotzdem mit:** die so ausgegebenen Tokens belegen Slots im
   Kontingent — sie werden mit `revoked_at IS NULL` und einer TTL in der Zukunft
   angelegt, erfuellen also die Zaehlbedingung von `TOKEN_COUNT_SQL`. Nur ihre
   Ausgabe wird nicht abgewiesen.

Wird `_issue` eines Tages doch gegatet, faellt Teil 1 — das ist dann eine
bewusste Aenderung der Entscheidung, keine stille.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from who2be_api.repositories.token_repository import TokenRepository
from who2be_api.services import token_quota_service
from who2be_api.services.oauth_service import OAuthService
from who2be_api.services.token_quota_service import TOKEN_COUNT_SQL, TokenQuotaService
from who2be_models import TokenRead, WorkspaceRole

_WORKSPACE_ID = uuid4()
_OWNER_ID = uuid4()
_AGENT_ID = uuid4()


class _RecordingTokenRepo:
    """Merkt sich die Insert-Argumente statt zu schreiben."""

    def __init__(self) -> None:
        self.inserts: list[dict[str, Any]] = []

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        token_hash: str,
        role: WorkspaceRole,
        agent_id: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> TokenRead:
        self.inserts.append(
            {
                "workspace_id": workspace_id,
                "owner_id": owner_id,
                "role": role,
                "agent_id": agent_id,
                "expires_at": expires_at,
            }
        )
        return TokenRead(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name,
            role=role,
            agent_id=agent_id,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
            last_used_at=None,
            revoked_at=None,
        )


class _StubOAuthRepo:
    """Nur die zwei Aufrufe, die `_issue` stellt."""

    async def get_client(self, _client_id: str) -> None:
        return None

    async def insert_refresh(self, **_kwargs: Any) -> None:
        return None


def _service(repo: _RecordingTokenRepo) -> OAuthService:
    return OAuthService(
        oauth_repo=_StubOAuthRepo(),  # type: ignore[arg-type]
        token_repo=cast(TokenRepository, repo),
        # `_issue` fasst den Pool nur fuers Audit an, und das ist hier None.
        pool=cast("Any", None),
        audit=None,
    )


def test_oauth_issue_is_not_gated_but_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Mint-Pfad ruft KEIN Quota-Gate — und legt dennoch zaehlbare Tokens an.

    Teil 1 (ungegatet) wird gemessen, indem `TokenQuotaService.enforce` mit
    einem Zaehler ueberschrieben wird: ein Aufruf hier waere die Regression.
    Teil 2 (zaehlt mit) wird an den Insert-Argumenten gemessen — Ablauf in der
    Zukunft, kein Widerruf, keine Sonderbehandlung, die `TOKEN_COUNT_SQL`
    ausschliessen wuerde.
    """
    enforce_calls = 0

    # pragma: no cover — ein Aufruf waere genau die Regression, die dieser Test sucht.
    async def _spy(_self: TokenQuotaService, _ctx: object) -> None:  # pragma: no cover
        nonlocal enforce_calls
        enforce_calls += 1

    monkeypatch.setattr(TokenQuotaService, "enforce", _spy)

    repo = _RecordingTokenRepo()
    service = _service(repo)
    asyncio.run(
        service._issue(
            workspace_id=_WORKSPACE_ID,
            owner_id=_OWNER_ID,
            role="viewer",
            agent_id=_AGENT_ID,
            client_id="oac_test",
            scope=None,
        )
    )

    assert enforce_calls == 0, "OAuth-Anmeldung darf nicht an einer Abrechnungsgrenze brechen"

    # … und der so angelegte Token belegt trotzdem einen Slot.
    assert len(repo.inserts) == 1
    inserted = repo.inserts[0]
    assert inserted["workspace_id"] == _WORKSPACE_ID
    assert inserted["expires_at"] is not None
    assert inserted["expires_at"] > datetime.now(UTC)  # erfuellt `expires_at > now()`
    # Die Zaehlquery kennt keine Herkunft: sie filtert nur auf Workspace,
    # Widerruf und Ablauf — ein OAuth-Token faellt darunter wie jeder andere.
    assert "client_id" not in TOKEN_COUNT_SQL
    assert "agent_id" not in TOKEN_COUNT_SQL
    assert "WHERE workspace_id = $1" in TOKEN_COUNT_SQL


def test_the_decision_is_recorded_at_the_gate() -> None:
    """Die Begruendung steht im Modul-Docstring des Gates, nicht nur hier.

    Ein ungegateter Pfad ohne Begruendung am Gate selbst ist beim naechsten
    Lesen ununterscheidbar von einem vergessenen.
    """
    doc = token_quota_service.__doc__
    assert doc is not None
    assert "_issue" in doc
    assert "ADR-0036" in doc


# --- Rollen-Deckel auf dem OAuth-Mint-Pfad ----------------------------------
#
# Derselbe Grund, aus dem diese Datei ueberhaupt existiert: `_issue` legt
# `api_token`-Zeilen an, ohne `TokenService.create` zu durchlaufen. Der Deckel
# fuer agent-gebundene Tokens muss deshalb hier eigens sitzen — sonst waere die
# Grenze loecherig, und zwar genau auf dem Pfad, den ein Remote-Connector nimmt.


@pytest.mark.parametrize("requested", ["admin", "editor", "viewer"])
def test_oauth_issue_never_mints_above_editor(requested: str) -> None:
    """Keine Rolle ueber `editor` verlaesst den OAuth-Mint-Pfad.

    Gemessen wird am Insert-Argument, nicht am Rueckgabewert: die gepinnte Rolle
    in der `api_token`-Zeile ist es, die spaeter jeden Tool-Call autorisiert.
    """
    repo = _RecordingTokenRepo()
    asyncio.run(
        _service(repo)._issue(
            workspace_id=_WORKSPACE_ID,
            owner_id=_OWNER_ID,
            role=requested,
            agent_id=_AGENT_ID,
            client_id="oac_test",
            scope=None,
        )
    )
    assert len(repo.inserts) == 1
    minted = repo.inserts[0]["role"]
    assert minted != WorkspaceRole.admin
    # Der Deckel senkt nur, er hebt nicht: `viewer` bleibt `viewer`.
    expected = WorkspaceRole.editor if requested == "admin" else WorkspaceRole(requested)
    assert minted == expected


def test_oauth_issue_caps_silently_instead_of_failing_the_consent_flow() -> None:
    """Der Deckel lehnt den Connector nicht ab, er reicht ihn gedeckelt durch.

    Anders als bei einer ausdruecklich angeforderten Rolle in
    `TokenService.create` waehlt hier niemand die Rolle — sie kommt aus der
    Membership. Ein 403 im Consent-Flow verweigerte jedem Admin den Connector,
    statt ihm einen ausreichenden zu geben.
    """
    repo = _RecordingTokenRepo()
    issued = asyncio.run(
        _service(repo)._issue(
            workspace_id=_WORKSPACE_ID,
            owner_id=_OWNER_ID,
            role="admin",
            agent_id=_AGENT_ID,
            client_id="oac_test",
            scope=None,
        )
    )
    assert issued.access_token.startswith("w2b_")
    assert repo.inserts[0]["role"] == WorkspaceRole.editor
