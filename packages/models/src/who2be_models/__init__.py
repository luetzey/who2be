"""Shared Pydantic models for Who2Be.

Einzige geteilte Abhaengigkeit zwischen `apps/api` und `apps/mcp`: reine
Pydantic-Modelle, kein I/O. Pro Aggregat ein Schema-Satz (`…Create` /
`…Update` / `…Read` / `…VersionRead`); `…Content` typisiert das `jsonb`-Feld.
"""

from who2be_models.links import PersonaPlaybookLinkSet
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
from who2be_models.token import TokenCreate, TokenCreated, TokenRead

__version__ = "0.1.0"

__all__ = [
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
    "TokenCreate",
    "TokenCreated",
    "TokenRead",
    "__version__",
]
