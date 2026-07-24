"""Workspace-Default fuer die Content-Sprache neuer Elemente (ADR-0045).

„Ein Element, eine Sprache": ein Create ohne explizites `locale` uebernimmt
die Content-Sprache des Workspaces (`workspace.content_locale`). Der Lookup
laeuft uebers Workspace-Repository (Leitplanke: kein SQL im Service); bis WP8
die Spalte in die Workspace-SELECTs aufnimmt, greift der Pydantic-Default
`'de'` des `WorkspaceRead`-Modells — als Interim genau richtig.
"""

from uuid import UUID

from who2be_api.repositories.workspace_repository import WorkspaceRepository
from who2be_models import DEFAULT_LOCALE


async def resolve_content_locale(
    workspace_repo: WorkspaceRepository | None,
    workspace_id: UUID,
    requested: str | None,
) -> str:
    """Explizit angefragte Sprache, sonst Workspace-Default, sonst `'de'`.

    `workspace_repo=None` deckt Test-Fakes ohne Workspace-Zugriff ab; ein
    (theoretisch) fehlender Workspace faellt defensiv auf `DEFAULT_LOCALE`.
    """
    if requested is not None:
        return requested
    if workspace_repo is None:
        return DEFAULT_LOCALE
    workspace = await workspace_repo.fetch(workspace_id)
    if workspace is None:
        return DEFAULT_LOCALE
    return workspace.content_locale
