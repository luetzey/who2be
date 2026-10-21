"""Tutorial-Fortschritt: Katalog pruefen, Schritte ableiten, Neustart (ADR-0060).

Der Katalog (`who2be_models.tutorial.tutorial_catalog`) ist die einzige Quelle
fuer gueltige Tutorial- und Schritt-IDs. Unbekannte IDs enden als regulaeres
422 (`RequestValidationError`, `loc` zeigt auf das Feld): der Katalog ist
oeffentlich, eine Unterscheidung „unbekannt“ vs. „fremd“ gibt es nicht —
jeder Nutzer sieht dieselben Tutorials, und geschrieben wird nur das eigene
Konto.

Automatische Schritte leitet der Service aus Workspace-Daten ab und speichert
sie nicht. Dafuer braucht er einen Workspace (`?workspace_id=`), in dem der
Nutzer Mitglied ist; ohne Angabe bleiben sie offen (nur `head_start` gilt
immer). Ein fremder oder unbekannter Workspace ist `workspace_not_found` —
fuer beide Faelle derselbe Fehler, kein Existenz-Orakel.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from fastapi import status
from fastapi.exceptions import RequestValidationError

from who2be_api.core.errors import ApiError
from who2be_api.core.tenancy import tenant_scope
from who2be_api.repositories.tutorial_repository import (
    DerivedSignals,
    Membership,
    StepProgressRow,
    TutorialRepository,
    TutorialStateRow,
)
from who2be_models.tutorial import (
    AUTOMATIC_STEP_TYPES,
    TutorialDefinition,
    TutorialPatch,
    TutorialRead,
    TutorialStepDefinition,
    TutorialStepRead,
    TutorialStepState,
    tutorial_catalog,
)

_NO_SIGNALS = DerivedSignals(first_mcp_call=None, agent_created=None, own_agent_mcp_call=None)


def _unknown(loc: tuple[str, ...], value: str, what: str) -> RequestValidationError:
    return RequestValidationError(
        [
            {
                "type": "value_error",
                "loc": loc,
                "msg": f"Value error, {what} {value!r} ist im Tutorial-Katalog unbekannt.",
                "input": value,
            }
        ]
    )


def _not_automatic(step: TutorialStepDefinition) -> RequestValidationError:
    return RequestValidationError(
        [
            {
                "type": "value_error",
                "loc": ("body", "state"),
                "msg": (
                    f"Value error, Schritt {step.id!r} wird automatisch erkannt und laesst "
                    "sich nur ueberspringen oder wieder oeffnen, nicht abhaken."
                ),
                "input": "done",
            }
        ]
    )


def _workspace_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Workspace nicht gefunden.",
        reason="workspace_not_found",
    )


def _signal(step: TutorialStepDefinition, signals: DerivedSignals) -> datetime | None:
    if step.type == "first_mcp_call":
        return signals.first_mcp_call
    if step.type == "agent_created":
        return signals.agent_created
    if step.type == "own_agent_mcp_call":
        return signals.own_agent_mcp_call
    return None


def build_tutorial_read(
    definition: TutorialDefinition,
    state: TutorialStateRow | None,
    progress: Mapping[tuple[str, str], StepProgressRow],
    signals: DerivedSignals,
) -> TutorialRead:
    """Reiner Zusammenbau ohne I/O — die Regeln aus ADR-0060 §3 an einer Stelle."""
    steps: list[TutorialStepRead] = []
    for step in definition.steps:
        automatic = step.type in AUTOMATIC_STEP_TYPES
        row = progress.get((definition.id, step.id))
        step_state: TutorialStepState = "open"
        completed_at: datetime | None = None
        derived_at = _signal(step, signals)
        if step.type == "head_start":
            step_state = "done"
        elif derived_at is not None:
            # Ein erkanntes Ereignis schlaegt ein frueheres Ueberspringen.
            step_state, completed_at = "done", derived_at
        elif row is not None and (row.state == "skipped" or not automatic):
            step_state = "done" if row.state == "done" else "skipped"
            completed_at = row.changed_at
        steps.append(
            TutorialStepRead(
                id=step.id,
                type=step.type,
                page=step.page,
                automatic=automatic,
                state=step_state,
                completed_at=completed_at,
            )
        )
    return TutorialRead(
        id=definition.id,
        audience=definition.audience,
        welcome=definition.welcome,
        welcome_seen_at=state.welcome_seen_at if state else None,
        restarted_at=state.restarted_at if state else None,
        completed=all(s.state != "open" for s in steps),
        steps=steps,
    )


class TutorialService:
    def __init__(
        self,
        repo: TutorialRepository,
        catalog: Mapping[str, TutorialDefinition] | None = None,
    ) -> None:
        self._repo = repo
        self._catalog = catalog if catalog is not None else tutorial_catalog()

    def _definition(self, tutorial_id: str) -> TutorialDefinition:
        definition = self._catalog.get(tutorial_id)
        if definition is None:
            raise _unknown(("path", "tutorial_id"), tutorial_id, "Tutorial")
        return definition

    async def _check_workspace(self, user_id: UUID, workspace_id: UUID | None) -> Membership | None:
        if workspace_id is None:
            return None
        membership = await self._repo.membership(user_id, workspace_id)
        if membership is None:
            raise _workspace_not_found()
        return membership

    async def _signals(
        self,
        user_id: UUID,
        workspace_id: UUID | None,
        membership: Membership | None,
        since: datetime | None,
    ) -> DerivedSignals:
        if workspace_id is None or membership is None:
            return _NO_SIGNALS
        # `usage_event` und `agent` stehen strikt unter RLS: ohne Mandant
        # saehe die App-Rolle keine Zeile.
        async with tenant_scope(workspace_id, membership.org_id):
            return await self._repo.derived(user_id, workspace_id, since)

    async def _read(
        self,
        user_id: UUID,
        definitions: list[TutorialDefinition],
        workspace_id: UUID | None,
        membership: Membership | None,
    ) -> list[TutorialRead]:
        states = await self._repo.states(user_id)
        progress = await self._repo.progress(user_id)
        result: list[TutorialRead] = []
        for definition in definitions:
            state = states.get(definition.id)
            signals = await self._signals(
                user_id, workspace_id, membership, state.restarted_at if state else None
            )
            result.append(build_tutorial_read(definition, state, progress, signals))
        return result

    async def list_tutorials(self, user_id: UUID, workspace_id: UUID | None) -> list[TutorialRead]:
        membership = await self._check_workspace(user_id, workspace_id)
        return await self._read(user_id, list(self._catalog.values()), workspace_id, membership)

    async def get(self, user_id: UUID, tutorial_id: str, workspace_id: UUID | None) -> TutorialRead:
        definition = self._definition(tutorial_id)
        membership = await self._check_workspace(user_id, workspace_id)
        return (await self._read(user_id, [definition], workspace_id, membership))[0]

    async def patch(
        self, user_id: UUID, tutorial_id: str, body: TutorialPatch, workspace_id: UUID | None
    ) -> TutorialRead:
        definition = self._definition(tutorial_id)
        # Erst alles pruefen, dann schreiben: ein abgewiesener Aufruf aendert nichts.
        membership = await self._check_workspace(user_id, workspace_id)
        if body.step_id is not None:
            step = definition.step(body.step_id)
            if step is None:
                raise _unknown(("body", "step_id"), body.step_id, "Schritt")
            if body.state == "done" and step.type in AUTOMATIC_STEP_TYPES:
                raise _not_automatic(step)
            if body.state == "open":
                await self._repo.clear_step(user_id, tutorial_id, step.id)
            else:
                assert body.state is not None
                await self._repo.set_step(user_id, tutorial_id, step.id, body.state)
        if body.welcome_seen:
            await self._repo.mark_welcome_seen(user_id, tutorial_id)
        return (await self._read(user_id, [definition], workspace_id, membership))[0]

    async def restart(
        self, user_id: UUID, tutorial_id: str, workspace_id: UUID | None
    ) -> TutorialRead:
        """Setzt nur dieses Tutorial zurueck; `welcome_seen_at` bleibt stehen.

        Die Begruessung erneut abzuspielen ist eine Sache des Web (O2 a:
        automatisch nur einmal pro Konto).
        """
        definition = self._definition(tutorial_id)
        membership = await self._check_workspace(user_id, workspace_id)
        await self._repo.restart(user_id, tutorial_id)
        return (await self._read(user_id, [definition], workspace_id, membership))[0]
