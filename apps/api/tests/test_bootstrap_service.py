"""Unit-Tests fuer den On-Prem-Bootstrap (`services/bootstrap_service.py`).

Der DB-Seed selbst ist integration-gated (siehe `test_phase21_migrations.py`-Muster);
hier wird die deterministische, idempotente User-ID-Ableitung geprueft sowie der
No-Op ohne konfigurierte Bootstrap-Email.
"""

from __future__ import annotations

import asyncio

from who2be_api.core.config import Settings
from who2be_api.services.bootstrap_service import (
    _deterministic_user_id,
    bootstrap_admin_if_needed,
)


def test_deterministic_user_id_is_stable_and_case_insensitive() -> None:
    a = _deterministic_user_id("Admin@Example.com")
    b = _deterministic_user_id("admin@example.com")
    assert a == b


def test_deterministic_user_id_differs_per_email() -> None:
    assert _deterministic_user_id("a@example.com") != _deterministic_user_id("b@example.com")


def test_noop_without_bootstrap_email() -> None:
    # Ohne Email darf der Pool nie beruehrt werden — ein None-Pool wuerde sonst crashen.
    result = asyncio.run(
        bootstrap_admin_if_needed(pool=None, settings=Settings(bootstrap_admin_email=""))
    )
    assert result is False
