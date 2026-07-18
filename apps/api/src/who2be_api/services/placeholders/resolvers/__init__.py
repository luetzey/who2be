"""Placeholder-Resolver, je Domaene ein Modul.

Neuen Placeholder hinzufuegen = Resolver hier (oder in einem passenden Modul)
ergaenzen und in `registry.REGISTRY` eintragen. Kein weiterer Umbau am Renderer.
"""

from who2be_api.services.placeholders.resolvers.catalog import (
    PlaybooksCatalogResolver,
    ResourcesCatalogResolver,
)
from who2be_api.services.placeholders.resolvers.content import (
    PlaybookResolver,
    ResourceResolver,
)
from who2be_api.services.placeholders.resolvers.date import DateResolver
from who2be_api.services.placeholders.resolvers.persona import (
    PersonaFieldResolver,
    PersonaRefResolver,
    render_skills_table,
)
from who2be_api.services.placeholders.resolvers.tool_ref import ToolRefResolver
from who2be_api.services.placeholders.resolvers.tools import ToolsOverviewResolver

__all__ = [
    "DateResolver",
    "PersonaFieldResolver",
    "PersonaRefResolver",
    "PlaybookResolver",
    "PlaybooksCatalogResolver",
    "ResourceResolver",
    "ResourcesCatalogResolver",
    "ToolRefResolver",
    "ToolsOverviewResolver",
    "render_skills_table",
]
