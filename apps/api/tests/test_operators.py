"""Betreiber-Pruefung im Kern (`who2be_api/core/operators.py`, ADR-0057 §7).

Drei Ebenen:

1. der eine Allowlist-Parser (leer, gueltig, Muell) — auf ihm stehen sowohl
   `WHO2BE_OPERATORS` als auch die Billing-Variable;
2. `is_operator`/`require_operator` in beiden Editionen (Owner-Entscheidung
   E2a: On-Prem nutzt dieselbe Allowlist) und mit API-Token;
3. die Compose-Verdrahtung: ohne Zeile in `services.api.environment` erreicht
   die Variable den Container nie, und das Gate antwortet fail-closed 403,
   obwohl sie in der `.env` steht. Weil die Regel in beiden Editionen gilt,
   muss die Zeile in jedem Basis-Stack stehen, nicht nur im Cloud-Overlay.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import yaml
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.core.operators import (
    OPERATORS_ENV,
    is_operator,
    operator_ids,
    parse_uuid_allowlist,
    require_operator,
)
from who2be_api.core.security import CurrentPrincipal, WorkspaceContext, get_current_principal
from who2be_models import WorkspaceRole

_OPERATOR = UUID("00000000-0000-4000-8000-0000000000aa")
_OTHER = UUID("00000000-0000-4000-8000-0000000000bb")
_SCRATCH_ENV = "WHO2BE_TEST_UUID_ALLOWLIST"


@pytest.fixture(params=["cloud", "onprem"])
def edition(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Jede Pruefung laeuft in beiden Editionen — die Regel ist dieselbe (E2a)."""
    monkeypatch.setenv("WHO2BE_EDITION", request.param)
    get_settings.cache_clear()
    yield request.param
    get_settings.cache_clear()


def _human(user_id: UUID) -> CurrentPrincipal:
    return CurrentPrincipal(user_id=user_id, token_workspace_id=None, aal="aal2")


def _token(user_id: UUID) -> CurrentPrincipal:
    return CurrentPrincipal(user_id=user_id, token_workspace_id=uuid4())


def _ctx(user_id: UUID, *, is_api_token: bool = False) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=user_id,
        role=WorkspaceRole.admin,
        is_api_token=is_api_token,
        aal="aal2",
    )


# --- 1. Parser ---------------------------------------------------------------


def test_parser_missing_or_blank_variable_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keine Variable und eine nur aus Trennern bestehende ergeben die leere Menge."""
    monkeypatch.delenv(_SCRATCH_ENV, raising=False)
    assert parse_uuid_allowlist(_SCRATCH_ENV) == frozenset()
    monkeypatch.setenv(_SCRATCH_ENV, " , ,, ")
    assert parse_uuid_allowlist(_SCRATCH_ENV) == frozenset()


def test_parser_reads_trimmed_uuids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_SCRATCH_ENV, f" {_OPERATOR} ,{_OTHER},{str(_OPERATOR).upper()}")
    assert parse_uuid_allowlist(_SCRATCH_ENV) == frozenset({_OPERATOR, _OTHER})


def test_parser_drops_and_logs_garbage_without_leaking_it(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Muell wird verworfen, die gueltigen Eintraege bleiben, der Wert landet nie im Log."""
    monkeypatch.setenv(_SCRATCH_ENV, f"not-a-uuid,{_OPERATOR},secret-ish-typo")
    with caplog.at_level(logging.WARNING, logger="who2be_api.core.operators"):
        assert parse_uuid_allowlist(_SCRATCH_ENV) == frozenset({_OPERATOR})
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2
    assert all(_SCRATCH_ENV in w for w in warnings)
    assert not any("secret-ish-typo" in w or "not-a-uuid" in w for w in warnings)


def test_parser_reads_on_every_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ungecacht: eine Rotation greift ohne Neustart."""
    monkeypatch.setenv(OPERATORS_ENV, str(_OPERATOR))
    assert operator_ids() == frozenset({_OPERATOR})
    monkeypatch.setenv(OPERATORS_ENV, str(_OTHER))
    assert operator_ids() == frozenset({_OTHER})


def test_billing_uses_the_core_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Genau ein Parser: Billing liest seine eigene Variable ueber den Kern."""
    billing_router = pytest.importorskip("who2be_billing.router")
    calls: list[str] = []

    def _spy(env_name: str) -> frozenset[UUID]:
        calls.append(env_name)
        return frozenset({_OPERATOR})

    monkeypatch.setattr(billing_router, "parse_uuid_allowlist", _spy)
    assert billing_router._override_operator_ids() == frozenset({_OPERATOR})
    assert calls == ["WHO2BE_BILLING_OVERRIDE_OPERATORS"]


# --- 2. is_operator / require_operator --------------------------------------


@pytest.mark.usefixtures("edition")
def test_listed_human_is_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OPERATORS_ENV, f"{_OTHER},{_OPERATOR}")
    assert is_operator(_human(_OPERATOR))
    assert is_operator(_ctx(_OPERATOR))
    assert not is_operator(_human(uuid4()))
    assert not is_operator(_ctx(uuid4()))


@pytest.mark.usefixtures("edition")
def test_empty_allowlist_means_nobody(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-closed in beiden Editionen — auch On-Prem gibt es keinen Default-Betreiber."""
    monkeypatch.delenv(OPERATORS_ENV, raising=False)
    assert not is_operator(_human(_OPERATOR))
    assert not is_operator(_ctx(_OPERATOR))


@pytest.mark.usefixtures("edition")
def test_api_token_is_never_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auch wenn der Token-Besitzer gelistet ist."""
    monkeypatch.setenv(OPERATORS_ENV, str(_OPERATOR))
    assert not is_operator(_token(_OPERATOR))
    assert not is_operator(_ctx(_OPERATOR, is_api_token=True))


def _probe_app(principal: CurrentPrincipal) -> FastAPI:
    app = FastAPI()

    @app.get("/probe")
    async def probe(caller: CurrentPrincipal = Depends(require_operator)) -> dict[str, str]:  # noqa: B008
        return {"user_id": str(caller.user_id)}

    app.dependency_overrides[get_current_principal] = lambda: principal
    return app


@pytest.mark.usefixtures("edition")
def test_require_operator_lets_operator_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(OPERATORS_ENV, str(_OPERATOR))
    with TestClient(_probe_app(_human(_OPERATOR))) as client:
        resp = client.get("/probe")
    assert resp.status_code == 200
    assert resp.json() == {"user_id": str(_OPERATOR)}


@pytest.mark.usefixtures("edition")
@pytest.mark.parametrize(
    ("allowlist", "principal"),
    [
        ("", _human(_OPERATOR)),
        (str(_OPERATOR), _human(_OTHER)),
        (str(_OPERATOR), _token(_OPERATOR)),
        ("garbage", _human(_OPERATOR)),
    ],
    ids=["empty", "not-listed", "api-token", "garbage"],
)
def test_require_operator_rejects_with_403(
    monkeypatch: pytest.MonkeyPatch, allowlist: str, principal: CurrentPrincipal
) -> None:
    """403 mit `detail` wie das Billing-Gate — das eine Signal, an dem das Web ausblendet."""
    monkeypatch.setenv(OPERATORS_ENV, allowlist)
    with TestClient(_probe_app(principal)) as client:
        resp = client.get("/probe")
    assert resp.status_code == 403
    assert OPERATORS_ENV in resp.json()["detail"]


# --- 3. Compose-Verdrahtung --------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
# Die drei Basis-Stacks, in denen `api` definiert ist. Die Cloud-Overlays
# erben die Zeile ueber den Compose-Merge der `environment`-Mappings.
_BASE_STACKS = (
    _REPO_ROOT / "docker-compose.yml",
    _REPO_ROOT / "deploy" / "dokploy" / "docker-compose.yml",
    _REPO_ROOT / "deploy" / "hetzner" / "who2be" / "docker-compose.yml",
)


class _ComposeLoader(yaml.SafeLoader):
    """Compose-Dateien tragen Merge-Tags (`!override`), die SafeLoader ablehnt."""


def _untagged(loader: yaml.Loader, suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    assert isinstance(node, yaml.ScalarNode)
    return loader.construct_scalar(node)


_ComposeLoader.add_multi_constructor("!", _untagged)


@pytest.mark.parametrize("compose_path", _BASE_STACKS, ids=lambda p: str(p.relative_to(_REPO_ROOT)))
def test_base_stack_passes_operators_to_api_with_empty_default(compose_path: Path) -> None:
    text = compose_path.read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.load(text, Loader=_ComposeLoader)
    environment = data["services"]["api"]["environment"]
    assert isinstance(environment, dict)
    assert environment.get(OPERATORS_ENV) == f"${{{OPERATORS_ENV}:-}}", (
        f"{compose_path.relative_to(_REPO_ROOT)}: `api.environment` muss "
        f"{OPERATORS_ENV} mit leerem Default durchreichen — sonst ist die "
        "Betreiber-Pruefung in dieser Edition fuer jeden 403."
    )


def test_hetzner_env_example_offers_operators() -> None:
    """Die Betreiber-Vorlage bietet die Variable an — sonst setzt sie niemand."""
    # effect-exempt: haelt die Betreiber-Vorlage gegen die Compose-Durchreichung, kein Subjekt
    example = (_REPO_ROOT / "deploy" / "hetzner" / ".env.example").read_text(encoding="utf-8")
    assert f"\n{OPERATORS_ENV}=\n" in example
