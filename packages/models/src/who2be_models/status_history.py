"""Audit-Eintrag fuer Status-Wechsel (TASK Phase 2.1b).

Spiegel der `status_history`-Tabelle aus
`apps/api/src/who2be_api/migrations/0012_status_history.sql`. Append-only;
schreibender Code kommt in 2.1b-1 (Status-Endpoints).
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from who2be_models.status import VersionStatus

EntityType = Literal["persona", "playbook", "resource", "system_prompt_template"]


class StatusHistoryEntry(BaseModel):
    """Eine Zeile aus `status_history` (read-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: EntityType
    entity_id: UUID
    # `version` ist seit Migration 0029 gefuehrt; Alt-Eintraege tragen None.
    # Provenance filtert auf eine konkrete Version, sodass die Kette einer
    # Version isoliert beantwortet werden kann ("warum aktiv").
    version: int | None = None
    from_status: VersionStatus | None
    to_status: VersionStatus
    changed_by: UUID
    changed_at: datetime
    note: str | None = Field(default=None, max_length=2_000)
