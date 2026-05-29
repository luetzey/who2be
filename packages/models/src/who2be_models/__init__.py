"""Shared Pydantic models for Who2Be.

Einzige geteilte Abhaengigkeit zwischen `apps/api` und `apps/mcp`: reine
Pydantic-Modelle, kein I/O. Pro Aggregat ein Schema-Satz (`…Create` /
`…Update` / `…Read` / `…VersionRead`); `…Content` typisiert das `jsonb`-Feld.
"""

from who2be_models.dashboard import (
    DashboardKpis,
    DashboardResponse,
    DashboardStatusDistribution,
    EntityStatusDistribution,
)
from who2be_models.links import PersonaPlaybookLinkSet
from who2be_models.me import MeOrganization, MeRead, MeWorkspace
from who2be_models.organization import OrganizationCreate, OrganizationRead
from who2be_models.pagination import DEFAULT_LIMIT, MAX_LIMIT, decode_cursor, encode_cursor
from who2be_models.persona import (
    PersonaContent,
    PersonaCreate,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionRead,
)
from who2be_models.playbook import (
    PlaybookContent,
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookVersionRead,
)
from who2be_models.resource import (
    ResourceBlock,
    ResourceContent,
    ResourceCreate,
    ResourceLinkItem,
    ResourceLinkRead,
    ResourceLinkSet,
    ResourceRead,
    ResourceUpdate,
    ResourceVersionRead,
)
from who2be_models.status import (
    ALLOWED_TRANSITIONS,
    VersionStatus,
    VersionTransitionRequest,
    is_allowed_transition,
)
from who2be_models.status_history import EntityType, StatusHistoryEntry
from who2be_models.token import TokenCreate, TokenCreated, TokenRead
from who2be_models.workspace import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate

__version__ = "0.1.0"

__all__ = [
    "ALLOWED_TRANSITIONS",
    "DEFAULT_LIMIT",
    "DashboardKpis",
    "DashboardResponse",
    "DashboardStatusDistribution",
    "EntityStatusDistribution",
    "EntityType",
    "MAX_LIMIT",
    "MeOrganization",
    "MeRead",
    "MeWorkspace",
    "OrganizationCreate",
    "OrganizationRead",
    "PersonaContent",
    "PersonaCreate",
    "PersonaPlaybookLinkSet",
    "PersonaRead",
    "PersonaUpdate",
    "PersonaVersionRead",
    "PlaybookContent",
    "PlaybookCreate",
    "PlaybookRead",
    "PlaybookUpdate",
    "PlaybookVersionRead",
    "ResourceBlock",
    "ResourceContent",
    "ResourceCreate",
    "ResourceLinkItem",
    "ResourceLinkRead",
    "ResourceLinkSet",
    "ResourceRead",
    "ResourceUpdate",
    "ResourceVersionRead",
    "StatusHistoryEntry",
    "TokenCreate",
    "TokenCreated",
    "TokenRead",
    "VersionStatus",
    "VersionTransitionRequest",
    "WorkspaceCreate",
    "WorkspaceRead",
    "WorkspaceUpdate",
    "__version__",
    "decode_cursor",
    "encode_cursor",
    "is_allowed_transition",
]
