"""Dünner Wrapper fuer Admin-/Security-Audit-Eintraege (WP-B).

Normalisiert pro Domaenen-Event die Felder fuer `audit_log` (Migration 0044)
und delegiert an `AuditLogRepository.insert`. Bewusst dünn — die
Geschaeftslogik bleibt in den jeweiligen Domain-Services; hier wird nur die
Feldzuordnung konsolidiert, damit nicht jeder Aufrufer das Action-String-
und JSON-Detail-Format frei interpretiert.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from who2be_api.repositories.audit_log_repository import AuditLogRepository, Executor


class AuditService:
    """Erzeugt Audit-Eintraege fuer Mutationen mit Sicherheitsbezug."""

    def __init__(self, audit_repo: AuditLogRepository) -> None:
        self._repo = audit_repo

    async def record(
        self,
        executor: Executor,
        *,
        action: str,
        actor_id: UUID | None,
        org_id: UUID | None = None,
        workspace_id: UUID | None = None,
        target: UUID | str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Schreibt einen Audit-Eintrag. `target` wird zu Text serialisiert
        (UUID → str), damit der Aufrufer nicht selbst casten muss."""
        await self._repo.insert(
            executor,
            action=action,
            org_id=org_id,
            workspace_id=workspace_id,
            actor_id=actor_id,
            target=str(target) if target is not None else None,
            detail=detail,
        )
