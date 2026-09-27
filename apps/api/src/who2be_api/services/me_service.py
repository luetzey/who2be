"""Aggregations-Service fuer `GET /v1/me` (TASK-301)."""

from uuid import UUID

from who2be_api.repositories.me_repository import MeRepository
from who2be_models import MeRead


class MeService:
    """Liefert dem aktuellen User Organizations + Workspaces + Default-WS."""

    def __init__(self, me_repo: MeRepository) -> None:
        self._repo = me_repo

    async def fetch(self, user_id: UUID, token_workspace_id: UUID | None = None) -> MeRead:
        """Memberships des Users plus die Workspace-Bindung des Tokens.

        `token_workspace_id` stammt aus dem Principal (nur API-Token-Pfad) und
        wird durchgereicht statt im Repository ermittelt: es ist eine Eigenschaft
        der *Credential*, keine der Membership-Abfrage.

        Ist es gesetzt, wird die Antwort zugleich **auf diesen Workspace
        geschnitten** (`_scoped_to`). Diese Route ist die einzige kontoweite, die
        Maschinen-Tokens offen steht — der MCP-Server loest darueber Token und
        Workspace auf (Introspektion sowie Workspace-Resolution vor jedem
        Tool-Call), ein 403 legte den Betrieb still. Offen heisst aber nicht
        unbeschraenkt: der Workspace-Pin ist auf dem Token-Pfad die tragende
        Isolationslinie (`get_current_workspace`), und ohne den Schnitt nennte
        diese Antwort jede Organisation und jeden Workspace des Besitzers — auch
        die, an die der Token nicht gebunden ist.

        Der Schnitt liegt hier und nicht im Repository, aus demselben Grund, aus
        dem `token_workspace_id` ueberhaupt hier ankommt: er folgt aus der
        Credential, nicht aus der Membership-Abfrage. Menschliche Sitzungen
        (`None`) sehen unveraendert alles.
        """
        me = await self._repo.fetch(user_id)
        if token_workspace_id is None:
            return me
        return _scoped_to(me, token_workspace_id)


def _scoped_to(me: MeRead, workspace_id: UUID) -> MeRead:
    """Reduziert `me` auf den gepinnten Workspace und seine Organisation.

    `default_workspace_id` wird auf den gepinnten Workspace gezogen: es ist
    sonst die erste Membership des Menschen und benennte damit einen Workspace,
    der in der geschnittenen Liste nicht mehr vorkommt — eine Antwort, die sich
    selbst widerspricht. Der MCP-Server liest genau diese beiden Felder
    (`token_workspace_id`, mit `default_workspace_id` als Fallback) und bekommt
    so in jedem Fall den Workspace, an den der Token gebunden ist.

    Ist der gepinnte Workspace in den Memberships nicht (mehr) enthalten — der
    Ersteller wurde entfernt, waehrend der Token gueltig bleibt (ADR-0023:
    gepinnte Tokens ueberleben das bis zum Widerruf) — bleibt `organizations`
    leer. Bewusst kein Fehler: die Bindung steht weiter in `token_workspace_id`,
    und ueber den Zugriff entscheidet `get_current_workspace` bei jedem Aufruf,
    nicht diese Auskunft.
    """
    scoped = [
        org.model_copy(
            update={"workspaces": [ws for ws in org.workspaces if ws.id == workspace_id]}
        )
        for org in me.organizations
    ]
    return me.model_copy(
        update={
            "organizations": [org for org in scoped if org.workspaces],
            "default_workspace_id": workspace_id,
            "token_workspace_id": workspace_id,
        }
    )
