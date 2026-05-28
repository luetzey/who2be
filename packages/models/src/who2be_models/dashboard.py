"""Dashboard-Antwort fuer `GET /v1/workspaces/{ws_id}/dashboard`.

Schema folgt Plan §2.1.E (siehe
`.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md`): drei KPI-Werte,
eine `activity`-Liste aus `status_history` und eine Verteilung pro
Entity-Typ. Service- und Endpoint-Code kommt in 2.1b-2.
"""

from pydantic import BaseModel, ConfigDict, Field

from who2be_models.status_history import StatusHistoryEntry


class DashboardKpis(BaseModel):
    """Top-Line-KPIs des Workspaces."""

    model_config = ConfigDict(from_attributes=True)

    active_personas: int = Field(ge=0)
    active_playbooks: int = Field(ge=0)
    pending_reviews: int = Field(ge=0)


class EntityStatusDistribution(BaseModel):
    """Anzahl Versionen je Status fuer einen Entity-Typ."""

    model_config = ConfigDict(from_attributes=True)

    draft: int = Field(ge=0)
    review: int = Field(ge=0)
    active: int = Field(ge=0)
    inactive: int = Field(ge=0)


class DashboardStatusDistribution(BaseModel):
    """Status-Verteilung pro Entity-Typ."""

    model_config = ConfigDict(from_attributes=True)

    persona: EntityStatusDistribution
    playbook: EntityStatusDistribution


class DashboardResponse(BaseModel):
    """Antwort von `GET /v1/workspaces/{ws_id}/dashboard`."""

    model_config = ConfigDict(from_attributes=True)

    kpis: DashboardKpis
    activity: list[StatusHistoryEntry] = Field(default_factory=list)
    status_distribution: DashboardStatusDistribution
