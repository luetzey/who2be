"""Tests fuer das Content-Locale-Modell (ADR-0027)."""

import pytest
from pydantic import ValidationError

from who2be_models import DEFAULT_LOCALE, PersonaCreate, PlaybookCreate, ResourceCreate
from who2be_models.locale import normalize_locale


def test_default_locale_is_de() -> None:
    assert DEFAULT_LOCALE == "de"


def test_normalize_locale_trims_and_lowercases() -> None:
    assert normalize_locale("  EN ") == "en"
    assert normalize_locale("de-AT") == "de-at"


def test_normalize_locale_rejects_malformed() -> None:
    for bad in ("", "x", "deutsch!", "12", "en_US"):
        with pytest.raises(ValueError):
            normalize_locale(bad)


def test_persona_create_defaults_to_de() -> None:
    create = PersonaCreate(name="QA")
    assert create.locales == ["de"]


def test_persona_create_dedups_and_normalizes_locales() -> None:
    create = PersonaCreate.model_validate({"name": "QA", "locales": ["DE", " de ", "en"]})
    assert create.locales == ["de", "en"]


def test_persona_create_rejects_empty_locales() -> None:
    with pytest.raises(ValidationError):
        PersonaCreate.model_validate({"name": "QA", "locales": []})


def test_playbook_and_resource_create_share_locale_contract() -> None:
    pb = PlaybookCreate.model_validate({"name": "PB", "locales": ["en", "en", "de"]})
    rsc = ResourceCreate.model_validate({"name": "R", "locales": ["en"]})
    assert pb.locales == ["en", "de"]
    assert rsc.locales == ["en"]
