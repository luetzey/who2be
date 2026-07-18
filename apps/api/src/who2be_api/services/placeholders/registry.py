"""Registry-Fassade: bindet die Resolver-Module zum `REGISTRY`-Dict zusammen.

Neuen Placeholder hinzufuegen = Resolver in einem `resolvers/*`-Modul anlegen
(oder ein neues Modul) und hier einen Eintrag im `REGISTRY`-Dict ergaenzen.
Kein weiterer Umbau am Renderer noetig.

Resolver-Regeln (aus der Spec):
- playbook:       target_id ist UUID; sucht Active-Version im Workspace.
                  Nicht gefunden -> Miss (unresolved_key gesetzt).
- resource:       analog zu playbook.
- persona-field:  target_id in {"name", "description", "profile", ...}; bei
                  persona_id=None, unbekanntem Feld oder Persona nicht gefunden -> Miss.
- date:           target_id ist Format-Slug ("" -> ISO-8601, "human" ->
                  "31. Mai 2026"). Standardisiert auf ctx.locale = 'de-DE'. Nie Miss.
- tools-overview: kuratierte, pro-Agent gefilterte Markdown-Liste. Nie Miss.
- tool-ref:       target_id ist der Faehigkeits-Alias eines ExternalTool
                  (Migration 0065); sucht die Active-Version im Workspace.
                  Nicht gefunden (unbekannter Alias oder kein Active) -> Miss
                  (unresolved_key gesetzt). Keine Policy-Domain vor WP-3 ->
                  sichtbar fuer jeden Agenten (siehe `resolvers/tool_ref.py`).

Diese Datei bleibt die stabile Import-Oberflaeche: `RenderContext`,
`ResolveResult`, `render_skills_table`, die Resolver-Klassen und `REGISTRY`
werden hier re-exportiert (Bestands-Importe von `renderer`, Services und Tests).
Das Feature-Flag `SKILLS_ENABLED` lebt jetzt in `_core` (dort monkeypatchen).
"""

from __future__ import annotations

from who2be_api.services.placeholders._core import (
    PlaceholderResolver,
    RenderContext,
    ResolveResult,
)
from who2be_api.services.placeholders.resolvers import (
    DateResolver,
    PersonaFieldResolver,
    PersonaRefResolver,
    PlaybookResolver,
    PlaybooksCatalogResolver,
    ResourceResolver,
    ResourcesCatalogResolver,
    ToolRefResolver,
    ToolsOverviewResolver,
    render_skills_table,
)

__all__ = [
    "REGISTRY",
    "DateResolver",
    "PersonaFieldResolver",
    "PersonaRefResolver",
    "PlaceholderResolver",
    "PlaybookResolver",
    "PlaybooksCatalogResolver",
    "RenderContext",
    "ResolveResult",
    "ResourceResolver",
    "ResourcesCatalogResolver",
    "ToolRefResolver",
    "ToolsOverviewResolver",
    "render_skills_table",
]


# ---------------------------------------------------------------------------
# Registry-Dict — Neuen Placeholder: Resolver-Klasse + Eintrag hier.
# ---------------------------------------------------------------------------

REGISTRY: dict[str, PlaceholderResolver] = {
    "playbook": PlaybookResolver(),
    "resource": ResourceResolver(),
    "persona-field": PersonaFieldResolver(),
    "persona-ref": PersonaRefResolver(),
    "playbooks-catalog": PlaybooksCatalogResolver(),
    "resources-catalog": ResourcesCatalogResolver(),
    "date": DateResolver(),
    "tools-overview": ToolsOverviewResolver(),
    "tool-ref": ToolRefResolver(),
}
