"""Shared Pydantic models for Who2Be.

Einzige geteilte Abhaengigkeit zwischen `apps/api` und `apps/mcp`: reine
Pydantic-Modelle, kein I/O. Pro Aggregat ein Schema-Satz (`…Create` /
`…Update` / `…Read` / `…VersionRead`); `…Content` typisiert das `jsonb`-Feld.
"""

from who2be_models.agent import (
    AgentCreate,
    AgentRead,
    AgentRenderResponse,
    AgentStatus,
    AgentUpdate,
    AgentWithRenderedPrompt,
    RenderFormat,
)
from who2be_models.dashboard import (
    DashboardActivity,
    DashboardActor,
    DashboardKpis,
    DashboardResponse,
    DashboardStatusDistribution,
    EntityStatusDistribution,
)
from who2be_models.invitation import (
    InvitationAccept,
    InvitationCreate,
    InvitationCreated,
    InvitationRead,
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
    PersonaVersionContent,
    PersonaVersionRead,
)
from who2be_models.playbook import (
    PlaybookContent,
    PlaybookCreate,
    PlaybookRead,
    PlaybookRef,
    PlaybookType,
    PlaybookUpdate,
    PlaybookUsage,
    PlaybookVersionRead,
    TriggerOverview,
)
from who2be_models.resource import (
    LinkedBlockSection,
    ResourceBlock,
    ResourceContent,
    ResourceCreate,
    ResourceLinkItem,
    ResourceLinkRead,
    ResourceLinkSet,
    ResourceRead,
    ResourceUpdate,
    ResourceUsage,
    ResourceVersionRead,
)
from who2be_models.status import (
    ALLOWED_TRANSITIONS,
    VersionStatus,
    VersionTransitionRequest,
    is_allowed_transition,
)
from who2be_models.status_history import EntityType, StatusHistoryEntry
from who2be_models.system_prompt_template import (
    SystemPromptTemplateContent,
    SystemPromptTemplateCreate,
    SystemPromptTemplateRead,
    SystemPromptTemplateUpdate,
    SystemPromptTemplateVersionRead,
)
from who2be_models.token import TokenCreate, TokenCreated, TokenRead
from who2be_models.workspace import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from who2be_models.workspace_member import (
    WorkspaceMemberRead,
    WorkspaceMemberUpdate,
    WorkspaceRole,
)

__version__ = "0.1.0"

__all__ = [
    "ALLOWED_TRANSITIONS",
    "AgentCreate",
    "AgentRead",
    "AgentRenderResponse",
    "AgentStatus",
    "AgentUpdate",
    "AgentWithRenderedPrompt",
    "DEFAULT_LIMIT",
    "DashboardActivity",
    "DashboardActor",
    "DashboardKpis",
    "DashboardResponse",
    "DashboardStatusDistribution",
    "EntityStatusDistribution",
    "EntityType",
    "InvitationAccept",
    "InvitationCreate",
    "InvitationCreated",
    "InvitationRead",
    "LinkedBlockSection",
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
    "PersonaVersionContent",
    "PersonaVersionRead",
    "PlaybookContent",
    "PlaybookCreate",
    "PlaybookRead",
    "PlaybookRef",
    "PlaybookType",
    "PlaybookUpdate",
    "PlaybookUsage",
    "PlaybookVersionRead",
    "ResourceBlock",
    "ResourceContent",
    "ResourceCreate",
    "ResourceLinkItem",
    "ResourceLinkRead",
    "ResourceLinkSet",
    "ResourceRead",
    "ResourceUpdate",
    "ResourceUsage",
    "ResourceVersionRead",
    "RenderFormat",
    "StatusHistoryEntry",
    "SystemPromptTemplateContent",
    "SystemPromptTemplateCreate",
    "SystemPromptTemplateRead",
    "SystemPromptTemplateUpdate",
    "SystemPromptTemplateVersionRead",
    "TokenCreate",
    "TokenCreated",
    "TokenRead",
    "TriggerOverview",
    "VersionStatus",
    "VersionTransitionRequest",
    "WorkspaceCreate",
    "WorkspaceMemberRead",
    "WorkspaceMemberUpdate",
    "WorkspaceRead",
    "WorkspaceRole",
    "WorkspaceUpdate",
    "__version__",
    "decode_cursor",
    "encode_cursor",
    "is_allowed_transition",
]
