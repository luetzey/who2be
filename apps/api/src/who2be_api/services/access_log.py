"""Duenner Helper fuer das Auto-Zugriffslog (ADR-0047, WP14 — Spec F).

`log_access` ist der EINE Aufrufpunkt der Read-/Write-Services: er loggt einen
Agent-Zugriff auf ein WorkArea-/KB-Element in `agent_access_log` — automatisch
und serverseitig, KEIN `record_run`-Selbstauskunfts-Tool (User-Entscheidung 6:
Vollstaendigkeit darf nie an Agenten-Disziplin haengen).

Vertraege (bindend):

- **Nur agent-gebundene Tokens** (Spec F): ohne ``ctx.agent_id`` ist der
  Aufruf ein No-op — Menschen-/JWT-Zugriffe landen nie im Log (das Log
  beantwortet „welche Elemente gingen je an einen EXTERNEN Anbieter", und
  das Modell haengt am Agenten, nicht am Menschen).
- **Sensitivity kommt vom SERVER**: der Aufrufer uebergibt den Wert des
  gelesenen/geschriebenen Objekts (Artifact-/Node-Sensitivity bzw.
  ``general`` fuer Tabellen) — nie einen Client-Input.
- **Best-effort**: das Logging laeuft NACH der erfolgreichen Operation und
  darf den Hauptpfad NIE brechen — jede Exception wird gefangen und nur
  gewarnt. Bewusster Trade-off (ADR-0047): ein verlorener Log-Eintrag ist
  ein Beobachtungs-Loch, ein 500 wegen des Logs waere ein Funktionsausfall;
  der Dedupe pro Tag macht die Luecke klein (der naechste Zugriff desselben
  Tages schreibt denselben Eintrag erneut).
"""

from __future__ import annotations

import logging

import asyncpg

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.agent_access_log_repository import (
    AccessOperation,
    AccessRefKind,
    PgAgentAccessLogRepository,
)
from who2be_models import Sensitivity

logger = logging.getLogger(__name__)

_repo = PgAgentAccessLogRepository()


async def log_access(
    pool: asyncpg.Pool,
    ctx: WorkspaceContext,
    *,
    ref_kind: AccessRefKind,
    ref_id: str,
    operation: AccessOperation,
    sensitivity: Sensitivity,
) -> None:
    """Loggt einen Agent-Zugriff — No-op fuer Menschen, best-effort fuer Agenten.

    Args:
        pool: App-Pool (der Insert laeuft NACH der Fach-Transaktion).
        ctx: Workspace-Kontext; ``agent_id is None`` ⇒ No-op (Spec F).
        ref_kind: Elementart (``artifact``/``node``/``table``/``blob``).
        ref_id: Element-Kennung (uuid bzw. sha256) als String.
        operation: ``read`` oder ``write``.
        sensitivity: SERVER-Snapshot der Objekt-Sensitivity (nie Client-Input).
    """
    if ctx.agent_id is None:
        return
    try:
        await _repo.record(
            pool,
            ctx.workspace_id,
            ctx.agent_id,
            ref_kind=ref_kind,
            ref_id=ref_id,
            operation=operation,
            sensitivity=sensitivity.value,
        )
    except Exception:  # noqa: BLE001 — bewusst breit: Logging bricht NIE den Hauptpfad
        logger.warning(
            "agent_access_log-Eintrag fehlgeschlagen (agent=%s, %s %s:%s) — "
            "Hauptpfad laeuft weiter",
            ctx.agent_id,
            operation,
            ref_kind,
            ref_id,
            exc_info=True,
        )
