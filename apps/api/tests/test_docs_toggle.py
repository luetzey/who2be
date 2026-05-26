"""Tests fuer den `WHO2BE_DOCS_PUBLIC`-Toggle (H5 / F-13).

Direkter Attribute-Check auf der gebauten FastAPI-App — kein TestClient,
damit der Test ohne DB und ohne Lifespan laeuft.
"""

import pytest

from who2be_api.core.config import Settings
from who2be_api.main import create_app


@pytest.mark.parametrize(
    ("docs_public", "expected_docs", "expected_redoc", "expected_openapi"),
    [
        (False, None, None, None),
        (True, "/docs", "/redoc", "/openapi.json"),
    ],
)
def test_docs_toggle(
    docs_public: bool,
    expected_docs: str | None,
    expected_redoc: str | None,
    expected_openapi: str | None,
) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        docs_public=docs_public,
    )
    app = create_app(settings=settings)
    assert app.docs_url == expected_docs
    assert app.redoc_url == expected_redoc
    assert app.openapi_url == expected_openapi


def test_docs_public_env_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    """`WHO2BE_DOCS_PUBLIC=true` aus dem Env wird via AliasChoices angenommen."""
    monkeypatch.setenv("WHO2BE_DOCS_PUBLIC", "true")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.docs_public is True
